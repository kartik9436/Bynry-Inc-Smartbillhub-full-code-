# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-004 (Rate schedules card grid, S9) · US-RAT-005 (New Rate
#           wizard: basics, flat & pure tiers, S11) · US-RAT-006 (TOU Option B) ·
#           US-RAT-007 (demand, seasonal, capacity & %-of-water structures)
# Rules:    BR-RAT-019 (tariff models) · BR-RAT-024 (tenant-enabled services) ·
#           BR-RAT-026 (pure tiers) · BR-RAT-031 (one service/one model;
#           SAVE-DRAFT RESUMABLE — dateless tariff_versions row, one per
#           tariff; activation needs a complete structure + effective_from;
#           approval REMOVED) · BR-RAT-007 (in-force by service date — drafts
#           never resolve) · BR-RAT-032 (tier contiguity) · BR-RAT-033 (TOU coverage) ·
#           BR-RAT-034 (seasonal coverage) · BR-RAT-038 (UoM gate) ·
#           BR-RAT-014 (demand capture) · BR-RAT-015 (%-of-water) ·
#           BR-RAT-018/022 (capacity, tenant-defined unit label)
# Note:     the holiday-calendar TCs (US-RAT-006 TC-2/TC-7) belong to the
#           tenancy S63 endpoints (holiday_calendars is a W0 tenancy table) —
#           skipped here with that reason rather than duplicated, and NOT marked
#           `isolation` so they never inflate the G5 skip count (DEF-101).
#           The RLS halves now RUN on Postgres under @requires_postgres; they
#           were bare pytest.mark.skip until 2026-08-15 and proved nothing.
# ───────────────────────────────────────────────────────
"""US-RAT-004..007 — the rate-schedule card grid and every v1 structure."""

from datetime import date

import pytest
from django.db import IntegrityError, transaction

from apps.rating import models, selectors, services
from core import errors
from core.pagination import ListParams

from tests.isolation_helpers import (  # noqa: F401 — fixtures resolved by name
    assert_denied_without_context,
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import (
    RES_ELECTRIC_TIERS,
    RES_WATER_TIERS,
    SUMMER,
    WINTER,
    audit_actions,
    tenant_ctx,
    tou_structure,
)

pytestmark = pytest.mark.django_db


def _params(**kwargs):
    return ListParams(**{"sort": "name", "dir": "asc", **kwargs})


def _capacity_payload(name, service, unit_label, rate):
    return {
        "name": name,
        "service": service,
        "model": "capacity",
        "effective_from": "2026-08-01",
        "structure": {"capacity": {"unit_label": unit_label, "rate_per_unit": rate}},
    }


# ── US-RAT-004 — Rate schedules list tab ────────────────────────────────────
def test_us_rat_004_tc1__cards_preview_the_structure_and_usage_counts(env):
    electric = env.tiered_schedule("Res Electric · Tiered", "electric", RES_ELECTRIC_TIERS)
    plan_a = env.plan(
        "Residential Standard",
        "RES-STD",
        [{"service": "electric", "base_charge": "18.50", "tariff": electric["id"]}],
        publish=True,
    )
    plan_b = env.plan(
        "Residential Electric-only",
        "RES-E",
        [{"service": "electric", "base_charge": "18.50", "tariff": electric["id"]}],
        publish=True,
    )
    env.assign(plan_a["id"], env.unit("Unit A"))
    env.assign(plan_b["id"], env.unit("Unit B"))
    with tenant_ctx(env.tenant):
        cards = selectors.schedule_list(_params())
    card = next(row for row in cards if row["name"] == "Res Electric · Tiered")
    tiers = card["current_version"]["structure"]["tiers"]
    assert [(tier["from_qty"], tier["unit_price"]) for tier in tiers][0] == (
        "0.000000",
        "0.110000",
    )
    assert len(tiers) == 3 and card["structure"] == "tiered"
    assert (card["used_by_plans"], card["applied_to_accounts"]) == (2, 2)


# ── DEF-441 — r10 line 764's nine columns ───────────────────────────────────
# The screen drew a card grid where r10 draws a nine-column table, and FIVE of
# those columns had no field behind them at all. These prove the five are served
# and that all nine sort for real.
#
# PROVED RED FIRST (hard-won law 7): every assertion below fails on the branch
# tip — `KeyError: 'size_count'` on the first four, and the sort test returns the
# name order for every derived key, because `schedule_list` mapped an unknown
# sort back to `name` and reported success.
def test_def_441__the_card_serves_r10s_five_missing_columns(env):
    """Sizes · Seasons · Structure detail · Effective — all counted from rows
    this selector already read, none of them invented."""
    tou = env.tiered_schedule(
        "Commercial Electric · Time-of-use",
        "electric",
        RES_ELECTRIC_TIERS,
        model="time_of_use",
        structure=tou_structure(),
        uom="kWh",
    )
    with tenant_ctx(env.tenant):
        card = selectors.schedule_card(models.Tariff.objects.get(pk=tou["id"]))
    # r10's `TOU · 2 periods` — the count is the DISTINCT window LABEL, not the
    # row count. This fixture's three windows carry three names (On-peak,
    # Off-peak, All day) so it reads three; the On-peak/Off-peak pair repeated
    # across two seasons would still read two, which is the whole reason the
    # count is over a set.
    assert card["window_count"] == 3
    assert len(card["current_version"]["structure"]["windows"]) == 3
    # r10's `Summer / Winter`. The LABELS travel, not a count: a CSV reader
    # cannot recover them from the number 2.
    assert card["season_labels"] == ["Summer", "Winter"]
    # DEF-360 — no size axis on this version means "one row prices every
    # connection size", which the screen renders as words, never as an em-dash.
    assert card["size_count"] == 0
    # r10's Effective column: the in-force version's own date.
    assert card["effective_from"] == "2026-08-01"


def test_def_441__blocks_are_counted_by_seq_not_by_row(env):
    """A three-block tiered schedule reads `3 blocks`, and would read `6` if the
    count were `len(tiers)` on a seasonal rate."""
    tiered = env.tiered_schedule("Res Electric · Tiered", "electric", RES_ELECTRIC_TIERS)
    with tenant_ctx(env.tenant):
        card = selectors.schedule_card(models.Tariff.objects.get(pk=tiered["id"]))
    assert card["block_count"] == 3
    assert card["window_count"] == 0  # not a TOU rate — the model decides which shows


def test_def_441__a_draft_has_no_effective_date(env):
    """BR-RAT-031: a draft is a version with NO date, so r10's Effective cell is
    an em-dash — never today's date and never the draft's created_at."""
    with tenant_ctx(env.tenant):
        draft = services.create_rate_schedule(
            env.admin,
            {
                "name": "Residential Water 2027 filing",
                "service": "water",
                "model": "tiered",
                "uom": "kgal",
                "structure": {"tiers": RES_WATER_TIERS},
            },
        )
        card = selectors.schedule_card(models.Tariff.objects.get(pk=draft["id"]))
    assert card["status"] == "draft"
    assert card["effective_from"] is None
    assert card["current_version"] is None and card["draft_version"] is not None


def test_def_441__all_nine_of_r10s_headers_actually_sort(env):
    """The PO asked for sortable headers on all nine. Before this fix six of the
    nine fell back to `name` server-side and the header drew an arrow over a
    sort that never happened."""
    # Two schedules that differ on every derived key, so a fallback-to-name sort
    # is DISTINGUISHABLE from a real one. "Alpha" sorts first by name and has
    # the LARGER counts, so any derived sort ascending must put "Zulu" first.
    alpha = env.tiered_schedule("Alpha Water", "water", RES_WATER_TIERS)
    env.flat_schedule("Zulu Water", "water", "2.90")
    plan = env.plan(
        "Alpha plan",
        "ALPHA",
        [{"service": "water", "base_charge": "12.00", "tariff": alpha["id"]}],
        publish=True,
    )
    env.assign(plan["id"], env.unit("Unit A"))

    def names(sort, direction="asc"):
        with tenant_ctx(env.tenant):
            rows = selectors.schedule_list(_params(sort=sort, dir=direction))
        return [row["name"] for row in rows]

    assert selectors.SCHEDULE_SORTS == (
        "name",
        "service",
        "structure",
        "sizes",
        "seasons",
        "plans",
        "accounts",
        "effective",
        "status",
    )
    # `plans` and `accounts`: Alpha has 1 of each, Zulu has 0 — so ascending is
    # Zulu first, which is the OPPOSITE of the name order the old code returned.
    assert names("plans") == ["Zulu Water", "Alpha Water"]
    assert names("accounts") == ["Zulu Water", "Alpha Water"]
    assert names("plans", "desc") == ["Alpha Water", "Zulu Water"]
    # `structure`: "flat" < "tiered", so Zulu (flat) leads ascending.
    assert names("structure") == ["Zulu Water", "Alpha Water"]
    # `name` still behaves, and every derived key falls back to a NAME-ascending
    # tie-break rather than reversing it with the user's direction.
    assert names("name") == ["Alpha Water", "Zulu Water"]
    # Both have no seasons, so the NAME tie-break decides — and it stays ascending.
    assert names("seasons") == ["Alpha Water", "Zulu Water"]


def test_us_rat_004_tc2__filter_structure_capacity(env):
    env.enable("solar", "battery")
    env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant):
        services.create_rate_schedule(
            env.admin, _capacity_payload("Solar Capacity", "solar", "panel", "10.00")
        )
        services.create_rate_schedule(
            env.admin, _capacity_payload("Battery Capacity", "battery", "kW block", "12.00")
        )
        cards = selectors.schedule_list(_params(filters={"structure": "capacity"}))
    assert sorted(row["name"] for row in cards) == ["Battery Capacity", "Solar Capacity"]


def _first_of_next_month() -> str:
    """A date that is in the FUTURE whenever the suite runs. This case read a
    literal `2026-09-01`, which stopped being a future date on 1 September 2026
    and turned the case red with nothing in the product changing (dated
    2026-10-01, CR-157-BRC10 wave B)."""
    today = date.today()
    year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    return date(year, month, 1).isoformat()


def test_us_rat_004_tc3__future_version_shows_change_scheduled_and_no_approval_state(env):
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    future = _first_of_next_month()
    with tenant_ctx(env.tenant):
        services.create_rate_schedule_version(
            env.admin,
            water["id"],
            {
                "model": "tiered",
                "uom": "kgal",
                "effective_from": future,
                "reason": "TWDB pass-through 2026",
                "structure": {"tiers": RES_WATER_TIERS},
            },
        )
        card = selectors.schedule_card(models.Tariff.objects.get(pk=water["id"]))
    assert card["scheduled_change"] == future
    assert card["status"] == "active"  # BR-RAT-031 as-modified: no approval-pending state
    assert card["current_version"]["approved_by"] is None


def test_us_rat_004_tc4__archive_blocked_while_plans_reference_the_schedule(env):
    electric = env.tiered_schedule("Res Electric · Tiered", "electric", RES_ELECTRIC_TIERS)
    for name, code in (("Residential Standard", "RES-STD"), ("Small Commercial", "COM-SM")):
        env.plan(
            name,
            code,
            [{"service": "electric", "base_charge": "18.50", "tariff": electric["id"]}],
            publish=True,
        )
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.BizError) as excinfo:
            services.archive_rate_schedule(env.admin, electric["id"])
        assert models.Tariff.objects.get(pk=electric["id"]).deleted_at is None
    assert excinfo.value.code == errors.BIZ_LOCKED
    # AMENDED 2026-08-21 (DEF-278). The rule did not change — the refusal did.
    # It used to assert `{"plans": 2}` and nothing else, which is the defect in
    # one line: a user told "referenced by 2 plans" has to open every plan in
    # the tenant to find which two. The count is kept (the sentence still
    # counts) and the NAMES travel beside it, alphabetically so the refusal
    # reads the same twice.
    assert excinfo.value.params == {"plans": 2, "names": "Residential Standard, Small Commercial"}
    assert excinfo.value.message_key == "rating.schedules.locked_referenced"


def test_def278__the_refusal_names_the_blocking_plans_and_caps_the_list(env):
    """DEF-278 — with more blocking plans than the sentence can carry, the
    refusal switches to the counted form and still names some of them.

    Six plans, five names: the count stays TRUE (`6`) while the list stays
    readable. The cap is `selectors.BLOCKING_PLAN_NAMES_SHOWN`, read here rather
    than hard-coded so raising it does not leave a test asserting the old shape.
    """
    electric = env.tiered_schedule("Res Electric · Tiered", "electric", RES_ELECTRIC_TIERS)
    for index in range(6):
        env.plan(
            f"Plan {index}",
            f"PLN-{index}",
            [{"service": "electric", "base_charge": "18.50", "tariff": electric["id"]}],
            publish=True,
        )
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.BizError) as excinfo:
            services.archive_rate_schedule(env.admin, electric["id"])
    assert excinfo.value.message_key == "rating.schedules.locked_referenced_many"
    assert excinfo.value.params["plans"] == 6
    named = excinfo.value.params["names"].split(", ")
    assert len(named) == selectors.BLOCKING_PLAN_NAMES_SHOWN
    assert named == ["Plan 0", "Plan 1", "Plan 2", "Plan 3", "Plan 4"]


def test_us_rat_004_tc5__retry_reissues_the_identical_read(env):
    env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant):
        first = selectors.schedule_list(_params())
        second = selectors.schedule_list(_params())
    # A18 failed-with-retry: the card read is pure, so Retry re-issues the same
    # query and gets the same payload (the failure state itself is FE-side).
    assert first == second


def test_us_rat_004_tc6__cards_and_counts_are_tenant_scoped(env, other_env):
    env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    other_env.flat_schedule("Co-op Water Flat", "water", "3.10")
    with tenant_ctx(other_env.tenant):
        cards = selectors.schedule_list(_params())
    assert [(row["name"], row["used_by_plans"]) for row in cards] == [("Co-op Water Flat", 0)]


SCHEDULE_TABLES = ("tariffs", "tariff_versions", "rate_tiers")


@pytest.mark.isolation
@requires_postgres
def test_us_rat_004_tc6_rls__schedule_cards_are_rls_scoped(env, other_env, rls):  # noqa: F811
    """US-RAT-004 TC-6 at the DATABASE, app-layer filter deliberately out of the path.

    The card grid's `used_by_plans` count is a JOIN over plan_rate_schedules —
    an aggregate leaks just as surely as a row does, so the join table is
    asserted alongside the tariff itself.
    """
    mine = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    other = other_env.flat_schedule("Co-op Water Flat", "water", "3.10")

    for table in SCHEDULE_TABLES:
        assert_rls_scoped(rls, table, owner=env.tenant, intruder=other_env.tenant)
    assert_rls_scoped(
        rls, "tariffs", owner=env.tenant, intruder=other_env.tenant, owner_ids={str(mine["id"])}
    )
    with live_tenant_context(other_env.tenant.id):
        assert rls.count("tariffs", "id = %s", [str(mine["id"])]) == 0
        assert rls.ids("tariffs") == {str(other["id"])}
    assert_no_foreign_rows_anywhere(rls, other_env.tenant, SCHEDULE_TABLES)
    assert_denied_without_context(rls, *SCHEDULE_TABLES)


# ── US-RAT-005 — basics, flat & pure tiers ──────────────────────────────────
def test_us_rat_005_tc1__tiered_schedule_activates_with_contiguous_tiers(env, audit_rows):
    audit_rows.clear()
    schedule = env.tiered_schedule(
        "Res Water · Inclining", "water", RES_WATER_TIERS, effective_from="2026-09-01"
    )
    version = schedule["current_version"]
    assert version["model"] == "tiered" and version["effective_from"] == "2026-09-01"
    tiers = version["structure"]["tiers"]
    assert [tier["seq"] for tier in tiers] == [1, 2, 3]
    assert [tier["to_qty"] for tier in tiers] == ["4.000000", "10.000000", None]
    assert "tariff.activated" in audit_actions(audit_rows)


def test_us_rat_005_tc2__flat_is_stored_as_one_open_ended_tier(env):
    schedule = env.flat_schedule("Comm Water · Flat", "water", "2.90")
    tiers = schedule["current_version"]["structure"]["tiers"]
    assert schedule["current_version"]["model"] == "flat"
    assert len(tiers) == 1  # BR-RAT-032: flat = a single 0 → ∞ row
    assert (tiers[0]["from_qty"], tiers[0]["to_qty"], tiers[0]["unit_price"]) == (
        "0.000000",
        None,
        "2.900000",
    )


def test_us_rat_005_tc3__activation_needs_effective_from_and_leaves_approved_by_null(env):
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("water")
    with tenant_ctx(env.tenant):
        draft = services.create_rate_schedule(
            env.admin, {"name": "Res Water · Inclining", "service": "water"}
        )
        assert draft["status"] == "draft"  # identity persists; resumable
        with pytest.raises(errors.ValidationError) as excinfo:
            services.activate_rate_schedule(
                env.admin,
                draft["id"],
                {
                    "model": "tiered",
                    "uom": "kgal",
                    "regulator_ref": "TX PUC docket 51234",
                    "structure": {"tiers": RES_WATER_TIERS},
                },
            )
        assert excinfo.value.code == errors.VAL_REQUIRED
        activated = services.activate_rate_schedule(
            env.admin,
            draft["id"],
            {
                "model": "tiered",
                "uom": "kgal",
                "effective_from": "2026-09-01",
                "regulator_ref": "TX PUC docket 51234",
                "structure": {"tiers": RES_WATER_TIERS},
            },
        )
    assert activated["current_version"]["approved_by"] is None  # optional metadata, never a gate
    assert activated["current_version"]["regulator_ref"] == "TX PUC docket 51234"


def test_us_rat_005_tc3_draft_structure__resumes_with_tiers_intact(env):
    """BR-RAT-031 save-draft resumable — the half the NOT NULL effective_from
    made unstorable: the STRUCTURE is saved with no date and reloads verbatim."""
    with tenant_ctx(env.tenant):
        saved = services.create_rate_schedule(
            env.admin,
            {
                "name": "Res Water · Inclining",
                "service": "water",
                "model": "tiered",
                "uom": "kgal",
                "regulator_ref": "TX PUC docket 51234",
                "structure": {"tiers": RES_WATER_TIERS},
            },
        )
        reopened = selectors.schedule_detail(saved["id"])
    draft = reopened["draft_version"]
    assert reopened["status"] == "draft" and reopened["current_version"] is None
    assert draft["effective_from"] is None  # the dateless row IS the draft
    assert draft["regulator_ref"] == "TX PUC docket 51234"
    assert [(tier["from_qty"], tier["unit_price"]) for tier in draft["structure"]["tiers"]] == [
        ("0.000000", "3.200000"),
        ("4.000000", "4.800000"),
        ("10.000000", "7.200000"),
    ]
    assert reopened["versions"] == []  # a draft is not history — it never priced


def test_us_rat_005_tc3_draft__resave_replaces_the_stored_structure(env):
    """Reopen → edit → Save draft again: one draft, the new rows."""
    with tenant_ctx(env.tenant):
        saved = services.create_rate_schedule(
            env.admin,
            {
                "name": "Res Water · Inclining",
                "service": "water",
                "model": "tiered",
                "structure": {"tiers": RES_WATER_TIERS},
            },
        )
        services.update_rate_schedule(
            env.admin,
            saved["id"],
            {"model": "flat", "uom": "kgal", "structure": {"unit_price": "2.90"}},
        )
        reopened = selectors.schedule_detail(saved["id"])
        drafts = models.TariffVersion.objects.filter(
            tariff_id=saved["id"], effective_from__isnull=True
        ).count()
        tiers = models.RateTier.objects.filter(tariff_version__tariff_id=saved["id"]).count()
    assert drafts == 1 and tiers == 1  # the superseded draft's rows are gone
    assert reopened["draft_version"]["structure"]["tiers"][0]["unit_price"] == "2.900000"


def test_us_rat_005_tc3_draft__dates_are_refused_outside_activation(env):
    with tenant_ctx(env.tenant):
        saved = services.create_rate_schedule(
            env.admin,
            {
                "name": "Res Water · Inclining",
                "service": "water",
                "model": "tiered",
                "structure": {"tiers": RES_WATER_TIERS},
            },
        )
        with pytest.raises(errors.ValidationError) as excinfo:
            services.update_rate_schedule(env.admin, saved["id"], {"effective_from": "2026-09-01"})
    assert excinfo.value.message_key == "rating.schedules.dates_land_at_activation"


def test_us_rat_005_tc3_draft__two_drafts_on_one_tariff_are_refused(env):
    """uq_tariff_versions_one_draft (PARTIAL, WHERE effective_from IS NULL)."""
    with tenant_ctx(env.tenant):
        saved = services.create_rate_schedule(
            env.admin,
            {
                "name": "Res Water · Inclining",
                "service": "water",
                "model": "tiered",
                "structure": {"tiers": RES_WATER_TIERS},
            },
        )
        tariff = models.Tariff.objects.get(pk=saved["id"])
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                models.TariffVersion.objects.create(
                    tenant=env.tenant, tariff=tariff, model="tiered", effective_from=None
                )
        # …while two DATED versions on the same tariff stay perfectly legal.
        # ⚠ `DEF-RAT-9027` — as long as their windows do not overlap: B2 s2's
        # `ex_tariff_versions_no_overlap` (rating/0047, 2026-09-29) refuses two
        # open-ended versions on PostgreSQL, so the first ends the day before
        # the second starts.
        models.TariffVersion.objects.create(
            tenant=env.tenant,
            tariff=tariff,
            model="tiered",
            effective_from=date(2026, 8, 1),
            effective_to=date(2026, 8, 31),
        )
        models.TariffVersion.objects.create(
            tenant=env.tenant, tariff=tariff, model="tiered", effective_from=date(2026, 9, 1)
        )


def test_us_rat_004_tc3_draft__is_invisible_to_in_force_resolution(env):
    """BR-RAT-007/BR-RAT-031: a dateless row has no window and must never be
    resolved as the version that prices a service date."""
    with tenant_ctx(env.tenant):
        saved = services.create_rate_schedule(
            env.admin,
            {
                "name": "Res Water · Inclining",
                "service": "water",
                "model": "tiered",
                "structure": {"tiers": RES_WATER_TIERS},
            },
        )
        tariff = models.Tariff.objects.get(pk=saved["id"])
        assert selectors.in_force_version(tariff, date(2026, 8, 9)) is None
        assert selectors.in_force_version(tariff, date(2030, 1, 1)) is None
        assert selectors.latest_version(tariff) is None
        assert selectors.tariff_versions(tariff) == []
        assert selectors.draft_version(tariff) is not None
        assert selectors.rating_rollup()["effective_from"] is None


def test_us_rat_005_tc3_draft__activation_without_effective_from_is_refused(env):
    with tenant_ctx(env.tenant):
        saved = services.create_rate_schedule(
            env.admin,
            {
                "name": "Res Water · Inclining",
                "service": "water",
                "model": "tiered",
                "structure": {"tiers": RES_WATER_TIERS},
            },
        )
        with pytest.raises(errors.ValidationError) as excinfo:
            services.activate_rate_schedule(env.admin, saved["id"], {})
        still_draft = selectors.schedule_detail(saved["id"])
    assert excinfo.value.code == errors.VAL_REQUIRED
    assert excinfo.value.field_errors[0]["field"] == "effective_from"
    assert still_draft["status"] == "draft"


def test_us_rat_005_tc3_draft__activation_without_a_complete_structure_is_refused(env):
    """A model was picked, no rows entered yet — legal as a draft, never
    activatable (BR-RAT-031 "activation requires a complete structure")."""
    with tenant_ctx(env.tenant):
        saved = services.create_rate_schedule(
            env.admin, {"name": "Empty tiers", "service": "water", "model": "tiered"}
        )
        with pytest.raises(errors.BizError) as excinfo:
            services.activate_rate_schedule(
                env.admin, saved["id"], {"effective_from": "2026-09-01"}
            )
        after = selectors.schedule_detail(saved["id"])
    assert excinfo.value.code == errors.BIZ_COMPLETENESS
    assert excinfo.value.params["missing"] == "tiers"
    assert after["status"] == "draft" and after["draft_version"]["effective_from"] is None


def test_us_rat_004_tc3_draft__activation_flips_the_derived_status(env, audit_rows):
    """US-RAT-004 §5: no version in force → Draft; activated → Active; a
    future-effective version → Draft + "Change scheduled"."""
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("water")
    with tenant_ctx(env.tenant):
        saved = services.create_rate_schedule(
            env.admin,
            {
                "name": "Res Water · Inclining",
                "service": "water",
                "model": "tiered",
                "uom": "kgal",
                "structure": {"tiers": RES_WATER_TIERS},
            },
        )
        assert saved["status"] == "draft"
        draft_id = selectors.schedule_detail(saved["id"])["draft_version"]["id"]
        audit_rows.clear()
        future = services.activate_rate_schedule(
            env.admin, saved["id"], {"effective_from": "2026-12-01"}
        )
        assert future["status"] == "draft"  # not in force yet
        assert future["scheduled_change"] == "2026-12-01"
        version = models.TariffVersion.objects.get(pk=draft_id)
        version.effective_from = date(2026, 8, 1)
        version.save(update_fields=["effective_from"])
        live = selectors.schedule_detail(saved["id"])
    # the SAME row left draft — the structure was never rewritten to activate
    assert live["current_version"]["id"] == draft_id
    assert live["status"] == "active" and live["draft_version"] is None
    assert len(live["versions"]) == 1
    assert "tariff.activated" in audit_actions(audit_rows)


def test_us_rat_005_tc3_draft__posting_the_full_structure_supersedes_the_draft(env):
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("water")
    with tenant_ctx(env.tenant):
        saved = services.create_rate_schedule(
            env.admin,
            {
                "name": "Res Water · Inclining",
                "service": "water",
                "model": "tiered",
                "structure": {"tiers": RES_WATER_TIERS},
            },
        )
        activated = services.activate_rate_schedule(
            env.admin,
            saved["id"],
            {
                "model": "flat",
                "uom": "kgal",
                "effective_from": "2026-09-01",
                "structure": {"unit_price": "2.90"},
            },
        )
        versions = models.TariffVersion.objects.filter(tariff_id=saved["id"]).count()
    assert versions == 1 and activated["draft_version"] is None
    assert activated["current_version"]["structure"]["tiers"][0]["unit_price"] == "2.900000"


def test_us_rat_005_tc4__tier_gap_is_refused(env):
    gapped = [
        {"from_qty": "0", "to_qty": "4", "unit_price": "3.20"},
        {"from_qty": "5", "to_qty": None, "unit_price": "4.80"},
    ]
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_rate_schedule(
                env.admin,
                {
                    "name": "Gapped",
                    "service": "water",
                    "model": "tiered",
                    "effective_from": "2026-09-01",
                    "structure": {"tiers": gapped},
                },
            )
        assert models.Tariff.objects.filter(name="Gapped").exists() is False
    assert excinfo.value.field_errors[0]["message_key"] == "rating.tiers.not_contiguous"
    # ⚠ DEF-RAT-5717 — **AND THE PARAMS, WHICH ARE THE MESSAGE.** The PO's own
    # report was *"tier 2 should start from 100"*, and the number was already
    # being computed here and thrown away by a sentence with no placeholder for
    # it. All four are asserted because the sentence names all four, and a
    # param the raiser stops sending is dropped by i18next in SILENCE.
    params = excinfo.value.field_errors[0]["params"]
    assert params["tier"] == 2, "the tier a clerk reads is its place in its own group"
    assert params["previous"] == 1
    assert params["expected"] == "4", "the number to type"
    assert params["starts"] == "5", "the number that was typed"


def test_us_rat_005_tc5__only_the_last_tier_may_be_open_ended(env):
    open_middle = [
        {"from_qty": "0", "to_qty": None, "unit_price": "3.20"},
        {"from_qty": "4", "to_qty": None, "unit_price": "4.80"},
    ]
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_rate_schedule(
                env.admin,
                {
                    "name": "Open middle",
                    "service": "water",
                    "model": "tiered",
                    "effective_from": "2026-09-01",
                    "structure": {"tiers": open_middle},
                },
            )
    assert excinfo.value.field_errors[0]["message_key"] == "rating.tiers.open_middle_tier"


def test_us_rat_005_tc6__negative_rate_is_refused(env):
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_rate_schedule(
                env.admin,
                {
                    "name": "Negative",
                    "service": "water",
                    "model": "flat",
                    "effective_from": "2026-09-01",
                    "structure": {"unit_price": "-0.50"},
                },
            )
    assert excinfo.value.code == errors.VAL_RANGE


def test_us_rat_005_tc7__uom_mismatch_without_a_factor_warns_and_closes_the_gate(env):
    env.set_billed_uom("water", "kgal")  # billed in kgal, no ccf factor defined
    schedule = env.flat_schedule("Comm Water · ccf", "water", "2.90", uom="ccf")
    codes = [notice["code"] for notice in schedule["notices"]]
    assert "rating.uom.mismatch_no_factor" in codes  # BR-RAT-038: never a silent conversion
    assert schedule["uom_gate"]["satisfied"] is False
    env.set_billed_uom("water", "kgal", factor="0.748")
    with tenant_ctx(env.tenant):
        reread = selectors.schedule_detail(schedule["id"])
    assert reread["uom_gate"]["satisfied"] is True  # a factor re-opens the gate


def test_us_rat_005_tc8__schedule_names_may_repeat_across_tenants(env, other_env):
    env.flat_schedule("Co-op Water Flat", "water", "2.90")
    other = other_env.flat_schedule("Co-op Water Flat", "water", "3.10")
    with tenant_ctx(other_env.tenant):
        cards = selectors.schedule_list(_params())
    assert [row["id"] for row in cards] == [other["id"]]
    assert models.Tariff.objects.filter(tenant=other_env.tenant).count() == 1


@pytest.mark.isolation
@requires_postgres
def test_us_rat_005_tc8_rls__schedules_are_rls_scoped(env, other_env, rls):  # noqa: F811
    """US-RAT-005 TC-8 at the DATABASE: same NAME, two tenants, no bleed.

    The app half proves the list returns only the caller's row. The sharper
    database question is the WRITE one: a same-named schedule must not let one
    tenant re-stamp its row into the other's catalogue — that is WITH CHECK, and
    it is the half a USING-only policy would pass.
    """
    mine = env.flat_schedule("Co-op Water Flat", "water", "2.90")
    other = other_env.flat_schedule("Co-op Water Flat", "water", "3.10")

    assert_rls_scoped(
        rls, "tariffs", owner=env.tenant, intruder=other_env.tenant, owner_ids={str(mine["id"])}
    )
    with live_tenant_context(other_env.tenant.id):
        assert rls.ids("tariffs") == {str(other["id"])}
    assert_write_into_other_tenant_refused(
        rls, "tariffs", owner=env.tenant, intruder=other_env.tenant
    )


# ── US-RAT-006 — TOU Option B ───────────────────────────────────────────────
def _tou_payload(structure, name="Comm Electric · TOU"):
    return {
        "name": name,
        "service": "electric",
        "model": "time_of_use",
        "uom": "kWh",
        "effective_from": "2026-08-01",
        "structure": structure,
    }


def test_us_rat_006_tc1__option_b_config_stores_seasons_windows_and_day_types(env):
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("electric")
    with tenant_ctx(env.tenant):
        schedule = services.create_rate_schedule(env.admin, _tou_payload(tou_structure()))
    structure = schedule["current_version"]["structure"]
    assert [season["label"] for season in structure["seasons"]] == ["Summer", "Winter"]
    summer = [row for row in structure["windows"] if row["season"] == "Summer"]
    assert {
        (row["label"], row["start_time"], row["end_time"], row["unit_price"]) for row in summer
    } == {
        ("On-peak", "14:00", "20:00", "0.220000"),
        ("Off-peak", "20:00", "14:00", "0.090000"),
    }
    assert {row["day_type"] for row in structure["windows"]} == {"weekday"}


@pytest.mark.skip(
    reason="US-RAT-006 TC-2: the holiday calendar is a tenancy W0 table with its own "
    "S63 endpoints (/settings/holidays) — covered by the tenancy lane, not duplicated "
    "here; rating only reads it at engine time (W3)"
)
def test_us_rat_006_tc2__holiday_calendar_rows_are_added():
    raise NotImplementedError


def test_us_rat_006_tc3__a_third_mid_peak_window_is_accepted(env):
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("electric")
    windows = tou_structure()["windows"]
    reshaped = [
        window
        for window in windows
        if not (window["season"] == "Summer" and window["label"] == "Off-peak")
    ] + [
        {
            "label": "Mid-peak",
            "season": "Summer",
            "day_type": "weekday",
            "start_time": "11:00",
            "end_time": "14:00",
            "unit_price": "0.15",
            "channel": "tou_mid",
        },
        {
            "label": "Off-peak",
            "season": "Summer",
            "day_type": "weekday",
            "start_time": "20:00",
            "end_time": "11:00",
            "unit_price": "0.09",
            "channel": "tou_off",
        },
    ]
    with tenant_ctx(env.tenant):
        schedule = services.create_rate_schedule(
            env.admin, _tou_payload(tou_structure(windows=reshaped))
        )
    summer = [
        row
        for row in schedule["current_version"]["structure"]["windows"]
        if row["season"] == "Summer"
    ]
    assert len(summer) == 3  # ≤3 windows, coverage still complete


def test_us_rat_006_tc4__a_fourth_window_is_refused(env):
    windows = tou_structure()["windows"] + [
        {
            "label": "Super-peak",
            "season": "Summer",
            "day_type": "weekday",
            "start_time": "16:00",
            "end_time": "18:00",
            "unit_price": "0.30",
            # A meter has three TOU registers (B2 r8), so a fourth window can
            # only re-use one. BR-RAT-021's cap is the error that fires first.
            "channel": "tou_on",
        },
        {
            "label": "Shoulder",
            "season": "Summer",
            "day_type": "weekday",
            "start_time": "10:00",
            "end_time": "11:00",
            "unit_price": "0.12",
            "channel": "tou_mid",
        },
    ]
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_rate_schedule(env.admin, _tou_payload(tou_structure(windows=windows)))
    assert excinfo.value.field_errors[0]["message_key"] == "rating.tou.too_many_windows"


def test_us_rat_006_tc5__an_uncovered_hour_blocks_activation(env):
    windows = [
        {
            "label": "On-peak",
            "season": "Summer",
            "day_type": "weekday",
            "start_time": "14:00",
            "end_time": "20:00",
            "unit_price": "0.22",
            "channel": "tou_on",
        },
        {
            "label": "Off-peak",
            "season": "Summer",
            "day_type": "weekday",
            "start_time": "20:00",
            "end_time": "13:00",  # 13:00–14:00 unpriced
            "unit_price": "0.09",
            "channel": "tou_off",
        },
        {
            "label": "All day",
            "season": "Winter",
            "day_type": "weekday",
            "start_time": "00:00",
            "end_time": "00:00",
            "unit_price": "0.13",
            "channel": "tou_off",
        },
    ]
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_rate_schedule(env.admin, _tou_payload(tou_structure(windows=windows)))
    assert excinfo.value.field_errors[0]["message_key"] == "rating.tou.coverage"


def test_us_rat_006_tc6__overlapping_seasons_are_refused(env):
    overlapping = [
        dict(SUMMER),
        {"label": "Winter", "start_month": 9, "start_day": 15, "end_month": 5, "end_day": 31},
    ]
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_rate_schedule(
                env.admin, _tou_payload(tou_structure(seasons=overlapping))
            )
    assert excinfo.value.field_errors[0]["message_key"] == "rating.seasons.coverage"


@pytest.mark.skip(
    reason="US-RAT-006 TC-7: duplicate holiday dates are refused by the tenancy S63 "
    "holiday endpoints ((tenant, holiday_date) UNIQUE) — tenancy lane's TC"
)
def test_us_rat_006_tc7__duplicate_holiday_date_is_rejected():
    raise NotImplementedError


@pytest.mark.isolation
@requires_postgres
def test_us_rat_006_tc8_rls__holiday_calendars_are_rls_scoped(env, other_env, rls):  # noqa: F811
    """US-RAT-006 TC-8 at the DATABASE.

    WHY THIS ONE LIVES HERE even though `holiday_calendars` is a tenancy W0
    table (DEF-101, 2026-08-15): the old skip reason delegated the proof to
    "the G5 suite on Postgres" and no such test was ever written anywhere —
    a grep for `holiday_calendars` across tests/ finds only this line and a
    provisioning table list. Delegating to a suite is not the same as being
    covered by it, which is hard-won law 1. Rating is the module that READS the
    calendar (TOU Option B bills a holiday off-peak), so a leak here mis-prices
    a neighbour's bill; the proof therefore sits with the reader until the
    tenancy lane claims it.
    """
    from apps.tenancy import services as tenancy_services

    # Provisioning already seeds the US federal dates for both tenants, so each
    # side gets a LOCAL date the other has never heard of — the interesting leak.
    with tenant_ctx(env.tenant):
        mine = tenancy_services.create_holiday(
            env.admin, {"date": "2026-03-02", "label": "Texas Independence Day"}
        )
    with tenant_ctx(other_env.tenant):
        theirs = tenancy_services.create_holiday(
            other_env.admin, {"date": "2026-04-21", "label": "Co-op founders' day"}
        )

    assert_rls_scoped(
        rls,
        "holiday_calendars",
        owner=env.tenant,
        intruder=other_env.tenant,
        owner_ids={str(mine["id"])},
    )
    with live_tenant_context(other_env.tenant.id):
        assert rls.count("holiday_calendars", "id = %s", [str(mine["id"])]) == 0
        assert str(theirs["id"]) in rls.ids("holiday_calendars")
        labels = {row[0] for row in rls.rows("SELECT label FROM holiday_calendars")}
    assert "Texas Independence Day" not in labels, f"LEAK — the intruder read {labels}"
    assert_denied_without_context(rls, "holiday_calendars")


# ── US-RAT-007 — demand, seasonal, capacity & %-of-water ────────────────────
def test_us_rat_007_tc1__demand_components_are_captured_without_a_pf_row(env):
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("electric")
    with tenant_ctx(env.tenant):
        schedule = services.create_rate_schedule(
            env.admin,
            {
                "name": "Industrial Electric · Demand",
                "service": "electric",
                "model": "demand",
                "uom": "kWh",
                "effective_from": "2026-08-01",
                "structure": {
                    "demand": {
                        "energy_rate_per_kwh": "0.08",
                        "demand_rate_per_kw": "14.50",
                        "peak_window_label": "15-min monthly",
                        "pf_penalty_enabled": False,
                    }
                },
            },
        )
    demand = schedule["current_version"]["structure"]["demand"]
    assert (demand["energy_rate_per_kwh"], demand["demand_rate_per_kw"]) == (
        "0.080000",
        "14.500000",
    )
    assert demand["pf_penalty_enabled"] is False and demand["ratchet_enabled"] is False
    assert schedule["notices"] == []


def test_us_rat_007_tc2__capacity_unit_labels_are_tenant_defined(env):
    env.enable("solar", "battery")
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("solar")
    env._base_codes_for_activation("battery")
    with tenant_ctx(env.tenant):
        solar = services.create_rate_schedule(
            env.admin, _capacity_payload("Solar Capacity", "solar", "panel", "10.00")
        )
        battery = services.create_rate_schedule(
            env.admin, _capacity_payload("Battery Capacity", "battery", "kW block", "12.00")
        )
    assert solar["current_version"]["structure"]["capacity"] == {
        "unit_label": "panel",
        "rate_per_unit": "10.000000",
        "currency": "USD",
    }
    assert battery["current_version"]["structure"]["capacity"]["unit_label"] == "kW block"


def test_us_rat_007_tc3__sewer_percent_of_water_stores_percent_and_basis(env):
    env.enable("sewer")
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("sewer")
    with tenant_ctx(env.tenant):
        schedule = services.create_rate_schedule(
            env.admin,
            {
                "name": "Sewer · % of water",
                "service": "sewer",
                "model": "percent_of_service",
                "effective_from": "2026-08-01",
                # ⚠ **THIS PAYLOAD WAS `{"percent": …, "basis_service": …}` AND
                # THE CASE HAD BEEN RED SINCE `CR-081` (2026-09-08), WHICH IS
                # `DEF-RAT-6146` IN THE REGISTER.** That CR made a rate
                # REQUIRED on a percent schedule and nothing updated the one
                # case that goes through `create_rate_schedule` — which is also
                # the exact payload `RateScheduleWizard.tsx:786` sends, so the
                # screen could not save a percent schedule either. Measured at
                # the pinned tip `b69d1f398`: this case fails there with
                # `structure.unit_price` / `rating.required`.
                #
                # `percent_basis` is `CR-130-BRC07`'s addition (2026-09-22) and
                # is required for the same reason the rate is: on this bill 40%
                # of the water VOLUME and 40% of the water MONEY are different
                # numbers, and the product does not guess between them.
                "structure": {
                    "percent": "40",
                    "basis_service": "water",
                    "percent_basis": "usage",
                    "unit_price": "5.0000",
                },
            },
        )
    structure = schedule["current_version"]["structure"]
    assert (structure["percent"], structure["basis_service"]) == ("40.000000", "water")
    assert structure["percent_basis"] == "usage"


def test_us_rat_007_tc4__seasonal_price_sets_cover_the_year(env):
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("water")
    seasons = [
        {
            **SUMMER,
            "start_month": 5,
            "start_day": 1,
            "end_month": 10,
            "end_day": 31,
            "unit_price": "4.10",
        },
        {
            **WINTER,
            "start_month": 11,
            "start_day": 1,
            "end_month": 4,
            "end_day": 30,
            "unit_price": "3.40",
        },
    ]
    with tenant_ctx(env.tenant):
        schedule = services.create_rate_schedule(
            env.admin,
            {
                "name": "Res Water · Seasonal",
                "service": "water",
                "model": "seasonal",
                "uom": "kgal",
                "effective_from": "2026-08-01",
                "structure": {"seasons": seasons},
            },
        )
    structure = schedule["current_version"]["structure"]
    assert [season["label"] for season in structure["seasons"]] == ["Summer", "Winter"]
    assert {(tier["season"], tier["unit_price"]) for tier in structure["tiers"]} == {
        ("Summer", "4.100000"),
        ("Winter", "3.400000"),
    }


def test_us_rat_007_tc5__negative_capacity_rate_is_refused(env):
    env.enable("solar")
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_rate_schedule(
                env.admin, _capacity_payload("Solar Capacity", "solar", "panel", "-10")
            )
        assert models.CapacityRate.objects.count() == 0
    assert excinfo.value.code == errors.VAL_RANGE


def test_us_rat_007_tc6__percent_requires_confirmation_above_100_and_refuses_zero(env):
    env.enable("sewer")
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("sewer")
    payload = {
        "name": "Sewer · % of water",
        "service": "sewer",
        "model": "percent_of_service",
        "effective_from": "2026-08-01",
        # See tc3 above for why this payload gained two fields: the rate has
        # been required since CR-081 and the basis since CR-130-BRC07. The case
        # asserts a message key by POSITION, so the payload has to be complete
        # in every other respect or the first error in the list is a different
        # one and the assertion tests the order rather than the rule.
        "structure": {
            "percent": "140",
            "basis_service": "water",
            "percent_basis": "usage",
            "unit_price": "5.0000",
        },
    }
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_rate_schedule(env.admin, payload)
        assert excinfo.value.field_errors[0]["message_key"] == "rating.percent.confirm_over_100"
        with pytest.raises(errors.ValidationError) as zero_exc:
            services.create_rate_schedule(
                env.admin,
                {**payload, "structure": {**payload["structure"], "percent": "0"}},
            )
        assert zero_exc.value.field_errors[0]["message_key"] == "rating.percent.not_positive"
        confirmed = services.create_rate_schedule(
            env.admin, {**payload, "confirm_percent_over_100": True}
        )
    assert confirmed["current_version"]["structure"]["percent"] == "140.000000"


def test_us_rat_007_tc7__seasonal_config_missing_half_the_year_is_blocked(env):
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_rate_schedule(
                env.admin,
                {
                    "name": "Summer only",
                    "service": "water",
                    "model": "seasonal",
                    "effective_from": "2026-08-01",
                    "structure": {
                        "seasons": [
                            {
                                "label": "Summer",
                                "start_month": 5,
                                "start_day": 1,
                                "end_month": 10,
                                "end_day": 31,
                                "unit_price": "4.10",
                            }
                        ]
                    },
                },
            )
    assert excinfo.value.field_errors[0]["message_key"] == "rating.seasons.coverage"


def test_us_rat_007_tc8__pf_penalty_capture_is_flagged_pending_ratification(env):
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("electric")
    with tenant_ctx(env.tenant):
        schedule = services.create_rate_schedule(
            env.admin,
            {
                "name": "Industrial Electric · Demand PF",
                "service": "electric",
                "model": "demand",
                "effective_from": "2026-08-01",
                "structure": {
                    "demand": {
                        "energy_rate_per_kwh": "0.08",
                        "demand_rate_per_kw": "14.50",
                        "pf_penalty_enabled": True,
                        "pf_penalty_rate_per_kw": "1.25",
                    }
                },
            },
        )
    codes = [notice["code"] for notice in schedule["notices"]]
    assert "rating.demand.pf_penalty_pending_ratification" in codes  # BR-RAT-014, no silent math
    assert schedule["current_version"]["structure"]["demand"]["pf_penalty_enabled"] is True


def test_us_rat_007_tc9__capacity_labels_never_leak_across_tenants(env, other_env):
    env.enable("solar")
    other_env.enable("solar")
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("solar")
    other_env._base_codes_for_activation("solar")
    with tenant_ctx(env.tenant):
        services.create_rate_schedule(
            env.admin, _capacity_payload("Solar Capacity", "solar", "panel", "10.00")
        )
    with tenant_ctx(other_env.tenant):
        services.create_rate_schedule(
            other_env.admin,
            _capacity_payload("Co-op Capacity", "solar", "meter equivalent", "6.00"),
        )
        labels = [
            row["unit_label"]
            for row in models.CapacityRate.objects.filter(tenant=other_env.tenant).values(
                "unit_label"
            )
        ]
    assert labels == ["meter equivalent"]


@pytest.mark.isolation
@requires_postgres
def test_us_rat_007_tc9_rls__capacity_rates_are_rls_scoped(env, other_env, rls):  # noqa: F811
    """US-RAT-007 TC-9 at the DATABASE.

    `capacity_rates.unit_label` is tenant-authored free text (BR-RAT-018/022) —
    "panel" vs "meter equivalent". A leak here exposes not just a price but how
    a neighbouring utility words its own tariff.
    """
    env.enable("solar")
    other_env.enable("solar")
    # ⚠ BR-RAT-088 / DEF-2965: activating a rate schedule for a service with no
    # declared `is_base` charge code is REFUSED by name, and that refusal is the
    # product working — without it the tenant bills every usage line correctly
    # and the total short by the whole base, which §A3 priced at $23,069.50 a
    # month across 1,247 connections. Both these tenants already carry base
    # codes for the services they price, so the gate is armed for them
    # (`_guard_base_charge_code` self-activates on a tenant's first `is_base`
    # row) and solar needs its own. `declare_base_charge_code` is the fixture
    # helper written for exactly this, and it declares the code the way the
    # utility would — on the Charge codes screen, through `create_charge`.
    env.declare_base_charge_code("solar")
    other_env.declare_base_charge_code("solar")
    with tenant_ctx(env.tenant):
        services.create_rate_schedule(
            env.admin, _capacity_payload("Solar Capacity", "solar", "panel", "10.00")
        )
    with tenant_ctx(other_env.tenant):
        services.create_rate_schedule(
            other_env.admin,
            _capacity_payload("Co-op Capacity", "solar", "meter equivalent", "6.00"),
        )

    assert_rls_scoped(rls, "capacity_rates", owner=env.tenant, intruder=other_env.tenant)
    with live_tenant_context(other_env.tenant.id):
        labels = {row[0] for row in rls.rows("SELECT unit_label FROM capacity_rates")}
    assert labels == {"meter equivalent"}, f"LEAK — the intruder read labels {labels}"
    assert_denied_without_context(rls, "capacity_rates")


# ── DEF-487 · the seeded payloads must SURVIVE THE VALIDATOR, not just parse ──


def test_def_471__every_seeded_schedule_payload_is_accepted_by_create(env):
    """⚠ THE TEST I SHOULD HAVE WRITTEN FOR DEF-463 AND DID NOT.

    That lane asserted on `_schedule_payloads()` — the payload SHAPE — and never
    ran one through `create_rate_schedule`. A dict with the wrong key is a
    perfectly good dict; it is the VALIDATOR that refuses it. So a draft
    schedule keyed `rate` where `_validate_tiers` accepts `unit_price` passed
    every assertion, and the whole rating sample-data block failed at runtime —
    taking identity, metering, customers and billing down behind it with
    `BlockCannotRun`. "Load sample data" loaded nothing.

    It is the same lesson as DEF-465, written two hours earlier: **a test on the
    far side of a broken hop passes forever.** This one sits on the near side —
    it builds every seeded payload and puts it through the real service.
    """
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("water")
    from apps.rating import sample_data

    # ⚠ ENABLEMENT IS **NOT** FORCED HERE, and the first draft of this test got
    # that wrong. Forcing it makes the seeder build a sewer schedule for a
    # tenant that does not sell sewer, and `create_rate_schedule` then refuses
    # with `rating.service_not_enabled` — which is CORRECT behaviour and has
    # nothing to do with the defect. The seeder skipping a disabled service is
    # the whole point of its own docstring.
    with tenant_ctx(env.tenant):
        payloads = sample_data._schedule_payloads()
        assert payloads, "the seeder builds no schedules for this tenant at all"
        for payload in payloads:
            # No try/except: a refusal here IS the failure, and its own message
            # names the offending field better than any assertion could.
            services.create_rate_schedule(env.admin, dict(payload))

