# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-002 (S15 units — this is a unit sub-resource on the same
#           tenant-scoped row) · CR-030 W5 tasks 5.2 + 5.3 (B18 §5.5.5, both
#           endpoints marked NEW there)
#           ⚠ NO STORY OWNS MOVE-IN STEP 3/4 — hard-won law 8. B18 proposes the
#           two endpoints and 05-user-stories.md carries none for them; the W4
#           lane reported the same gap for S83/S84/S85. REPORTED, not invented.
# Rules:    BR-AST-004 (exactly one tab per asset — the grouping key) ·
#           BR-MET-036/037 (unit reads) · BR-MET-100 (an unplanned unit is
#           COUNTED AND FINDABLE, not an error) · BR-RAT-027 (base_charges is
#           rating's DERIVED Σ, forwarded here, never recomputed) ·
#           BR-RAT-081 / DEF-495 (the metered declaration has no reader, so
#           `reading_expected` is a STATED ABSENCE) · hard rule 1 (tenant
#           scoping) · hard rule 3 (consumption carries its unit)
# Golden:   NONE, and that is the finding — no worked month is computed, so no
#           GT figure is reproduced here. See TC-9's docstring.
# Tests:    this file (TC-1..TC-9)
# Impacts:  apps/metering/api.py (the two routes) · apps/metering/selectors.py
#           (unit_assets · unit_pricing)
# ───────────────────────────────────────────────────────
"""CR-030 W5 tasks 5.2/5.3 — `GET /units/{id}/assets` and `/units/{id}/pricing`.

Every case runs through the REAL view function (`api_call`), so the tenant
context, the permission class and the selector are all exercised together — a
selector-only test would not prove the route is reachable.
"""

import uuid
from decimal import Decimal

import pytest

from apps.metering import api, selectors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import (
    a_meter,
    commit_read,
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


#: The two base charges the plan fixture states, at the column's six stored
#: places. Σ = 20.500000, which is the figure `plan_detail` DERIVES (BR-RAT-027)
#: and which TC-9 pins against rating's own answer rather than against a
#: constant computed here.
ELECTRIC_BASE = Decimal("8.000000")
WATER_BASE = Decimal("12.500000")


def _plan_with_base_charges(tenant, services=("electric", "water")):
    """A published plan WITH its per-service base-charge rows.

    `make_plan` builds the plan and one rate schedule per service and stops
    there — `PlanService` is a separate table and nothing in the shared helper
    writes it, so `plan_detail(...)["services"]` comes back empty. These are
    FIXTURE ROWS, written the same way `make_plan` writes its own (the helper's
    standing note: fixture data, not a cross-module write from metering).
    """
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    plan = make_plan(tenant, services=services)
    for code, amount in (("electric", ELECTRIC_BASE), ("water", WATER_BASE)):
        if code not in services:
            continue
        rating_models.PlanService.objects.get_or_create(
            tenant=tenant,
            rate_plan=plan,
            service=tenancy_models.Service.objects.get(code=code),
            defaults={"base_charge": amount, "currency": "USD"},
        )
    return plan


def _unit_with_plan(actor, tenant, *, label="Unit A", with_plan=True):
    """One unit on a real premise, optionally holding a PUBLISHED plan."""
    from apps.metering import services

    premise = make_premises(actor, services_available=["electric", "water"])
    unit = make_unit(actor, premise["id"], label=label, services=["electric", "water"])
    if with_plan:
        plan = _plan_with_base_charges(tenant)
        services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    return unit


# ── 5.2 · GET /units/{id}/assets ───────────────────────────────────────────
def test_w5_tc1__the_four_assets_group_by_CATEGORY_not_by_qualifier(brazos, dana):
    """B18 TC-MVI-4: *"a unit with 2 meters + 1 sub-meter + 1 PV inverter →
    all four listed, grouped"*.

    THE CASE THAT MAKES THE GROUPING KEY LOAD-BEARING: the PV inverter hangs
    off its meter by `parent_asset`, so `assets_on_unit`'s `(sub)/(master)`
    qualifier calls it a SUB-METER. Only `asset_types.category` (BR-AST-004)
    puts it under behind-the-meter, which is what post-CR-028 means here.
    """
    with tenant_ctx(brazos):
        unit = _unit_with_plan(dana, brazos, with_plan=False)
        master = a_meter(dana, "M-7001", unit_id=unit["id"])
        a_meter(dana, "M-7002", unit_id=unit["id"], service="water", uom="kgal")
        from apps.assets import services as asset_services

        asset_services.create_asset(
            dana,
            {
                "type": "sub_meter",
                "asset_no": "SM-8801",
                "service": "electric",
                "unit": "kWh",
                "read_method": "walk_by",
                "multiplier": "1",
                "parent_asset_no": master["asset_no"],
                "unit_id": unit["id"],
                "install_date": "2026-01-05",
            },
        )
        asset_services.create_asset(
            dana,
            {
                "type": "pv",
                "asset_no": "PV-3300",
                "service": "electric",
                "unit": "kWh",
                "parent_asset_no": master["asset_no"],
                "unit_id": unit["id"],
                "install_date": "2026-01-05",
            },
        )
        response = api_call(  # noqa: F405 — shared fixture import
            api.unit_assets,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            unit_id=unit["id"],
        )
    assert response.status_code == 200
    body = response.data
    assert body["counts"] == {
        "meters": 2,
        "sub_meters": 1,
        "behind_the_meter": 1,
        "unclassified": 0,
        "total": 4,
    }
    assert [g["category"] for g in body["groups"]] == [
        "meters",
        "sub_meters",
        "behind_the_meter",
        "unclassified",
    ]
    by_group = {g["category"]: [a["asset_no"] for a in g["assets"]] for g in body["groups"]}
    assert by_group["meters"] == ["M-7001", "M-7002"]
    assert by_group["sub_meters"] == ["SM-8801"]
    # The whole point: qualifier says "sub", category says behind-the-meter.
    assert by_group["behind_the_meter"] == ["PV-3300"]
    inverter = next(a for g in body["groups"] for a in g["assets"] if a["asset_no"] == "PV-3300")
    assert inverter["qualifier"] == "sub" and inverter["category"] == "behind_the_meter"
    # The service travels from METERING'S OWN service points, not from assets.
    assert {a["asset_no"]: a["service"] for a in body["groups"][0]["assets"]} == {
        "M-7001": "electric",
        "M-7002": "water",
    }


def test_w5_tc2__the_last_read_carries_its_explicit_unit(brazos, dana):
    """Hard rule 3: *consumption always with an explicit unit; never assume.*

    Step 3 asks for a start reading, so the register POSITION travels beside
    the consumption — and both are null-safe: a meter never read serves
    `last_read: null`, which nothing downstream may read as a zero.
    """
    with tenant_ctx(brazos):
        unit = _unit_with_plan(dana, brazos, with_plan=False)
        meter = a_meter(dana, "M-7001", unit_id=unit["id"])
        a_meter(dana, "M-7002", unit_id=unit["id"], service="water", uom="kgal")
        commit_read(
            dana,
            meter["id"],
            day="2026-07-31",
            value="42864",
            prior_value="42180",
            consumption="684.000000",
            unit="kWh",
        )
        response = api_call(  # noqa: F405
            api.unit_assets,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            unit_id=unit["id"],
        )
    rows = {a["asset_no"]: a for g in response.data["groups"] for a in g["assets"]}
    read = rows["M-7001"]["last_read"]
    assert read["current_value"] == "42864.000000"
    assert read["consumption"] == "684.000000"
    assert read["unit"] == "kWh"  # the unit NEVER travels separately from the figure
    assert read["read_at"] == "2026-07-31"
    assert rows["M-7002"]["last_read"] is None  # never read → null, never 0


def test_def_met_10091__a_demand_meter_answers_its_total_register(brazos, dana):
    """`DEF-MET-10094` — E-5046 on the demo: read the same day on `total`
    (21,502 kWh) and `demand` (11 kW). The move-out row prefilled from the
    DEMAND read and the door posted it against TOTAL, refusing it as negative
    usage. The answer follows the register the door writes, whichever row was
    inserted last."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(dana, brazos, with_plan=False)
        meter = a_meter(dana, "M-7101", unit_id=unit["id"])
        commit_read(dana, meter["id"], day="2026-10-06", value="21502", unit="kWh")
        # Inserted AFTER the total read on the same day — the id tie-break
        # used to pick this one.
        commit_read(dana, meter["id"], day="2026-10-06", value="11", channel="demand", unit="kW")
        response = api_call(  # noqa: F405
            api.unit_assets,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            unit_id=unit["id"],
        )
    rows = {a["asset_no"]: a for g in response.data["groups"] for a in g["assets"]}
    read = rows["M-7101"]["last_read"]
    assert read["channel"] == "total"
    assert read["current_value"] == "21502.000000"
    assert read["unit"] == "kWh"


def test_def_met_10091__a_demand_only_meter_still_answers(brazos, dana):
    """The fallback: a meter only ever read on another channel is not `None`."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(dana, brazos, with_plan=False)
        meter = a_meter(dana, "M-7102", unit_id=unit["id"])
        commit_read(dana, meter["id"], day="2026-10-06", value="11", channel="demand", unit="kW")
        response = api_call(  # noqa: F405
            api.unit_assets,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            unit_id=unit["id"],
        )
    rows = {a["asset_no"]: a for g in response.data["groups"] for a in g["assets"]}
    assert rows["M-7102"]["last_read"]["channel"] == "demand"


def test_w5_tc3__a_unit_with_no_assets_is_an_empty_panel_not_an_error(brazos, dana):
    """A vacant unit with nothing installed is the NORMAL state at move-in.

    Four empty groups and a zero total — an error here would refuse the
    commonest case B18 §5.5.3 step 1 selects for (*"vacant and reserved only"*).
    """
    with tenant_ctx(brazos):
        unit = _unit_with_plan(dana, brazos, with_plan=False)
        response = api_call(  # noqa: F405
            api.unit_assets,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            unit_id=unit["id"],
        )
    assert response.status_code == 200
    assert response.data["counts"]["total"] == 0
    assert all(g["assets"] == [] for g in response.data["groups"])
    assert response.data["unit"]["id"] == unit["id"]


def test_w5_tc4__reading_expected_is_a_STATED_ABSENCE_carrying_DEF_495(brazos, dana):
    """B18 TC-MVI-4 asks a reading *"for the billable meters only"* and this
    payload cannot say which those are.

    BR-RAT-081's metered/unmetered declaration lives on `tenant_services.metered`
    and DEF-495 (OPEN) records that NOTHING IN THE PRODUCT READS THAT COLUMN.
    Deriving the flag from the asset category would be a guess. So the absence
    is served with the id that will expire it — G38's law applied to a payload.
    """
    with tenant_ctx(brazos):
        unit = _unit_with_plan(dana, brazos, with_plan=False)
        a_meter(dana, "M-7001", unit_id=unit["id"])
        response = api_call(  # noqa: F405
            api.unit_assets,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            unit_id=unit["id"],
        )
    stated = response.data["reading_expected"]
    assert stated["served"] is False
    assert stated["reason"] == "metered_declaration_has_no_reader"
    assert stated["tracks"] == "DEF-495"
    # ...and no asset row carries a fabricated flag instead.
    for group in response.data["groups"]:
        for asset in group["assets"]:
            assert "reading_expected" not in asset and "billable" not in asset


# ── 5.3 · GET /units/{id}/pricing ──────────────────────────────────────────
def test_w5_tc5__the_plan_its_schedules_charges_and_taxes_are_served(brazos, dana):
    """B18 §5.5.5: *"plan, rate schedules with blocks, charge codes, taxes"*.

    Every figure is RATING'S OWN STRING, forwarded verbatim — this module does
    no money math (B4/B5 ❄️ FROZEN). The assertion is therefore about the SHAPE
    reaching the screen and about the plan being the one the unit holds.
    """
    with tenant_ctx(brazos):
        unit = _unit_with_plan(dana, brazos)
        response = api_call(  # noqa: F405
            api.unit_pricing,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            unit_id=unit["id"],
        )
    assert response.status_code == 200
    body = response.data
    assert body["plan_absent"] is None
    assert body["plan"]["id"] == body["unit"]["rate_plan_id"]
    assert body["plan"]["name"] == "Small Commercial"
    assert body["plan"]["status"] == "published"  # BR-RAT-030 — only these assign
    # The plan's services and their STORED base charges, forwarded verbatim at
    # the column's six places (rule 2: money stored to 4 dp, this column is a
    # lawful 18,6 container — see CLAUDE.md rule 2's amendment). Nothing here
    # rounds, re-quantizes or sums them.
    assert [(row["service"], row["base_charge"]) for row in body["services"]] == [
        ("electric", "8.000000"),
        ("water", "12.500000"),
    ]
    assert [row["service"] for row in body["rate_schedules"]] == ["electric", "water"]
    for row in body["rate_schedules"]:
        assert row["absent"] is None, "the plan's schedule must be readable"
        assert row["schedule"]["service"] == row["service"]
        # "with blocks" — the in-force version's own structure, not a summary.
        assert "current_version" in row["schedule"]
        assert "uom_gate" in row["schedule"]  # BR-RAT-038 must be sayable
    assert isinstance(body["charge_codes"], list)
    # ⚠ AMENDED 2026-08-25 (CR-034 (b)) — `narrowing` JOINED THIS SET, and the
    # exact-set assertion is KEPT rather than loosened: the two lists are still
    # two lists, and pinning the set is what made this contract change
    # deliberate instead of accidental. `narrowing` says these are the PLAN's
    # bindings and attachments and NOT R7's final answer — the tax set narrows
    # again by the account's customer class at bill time (DEF-273: three of
    # r10's five Texas rates scope by class), which a UNIT cannot answer
    # because it has no account.
    assert set(body["taxes"]) == {"jurisdiction_rules", "attachments", "narrowing"}
    assert body["taxes"]["narrowing"]["final"] is False
    assert body["taxes"]["narrowing"]["reason"] == "narrows_by_customer_class_at_bill_time"
    # The filing HISTORY is deliberately not shipped to a wizard step.
    assert all("versions" not in row["schedule"] for row in body["rate_schedules"])


def test_w5_tc6__a_unit_with_no_plan_states_it_and_is_not_an_error(brazos, dana):
    """BR-MET-100: an unplanned unit is COUNTED AND FINDABLE.

    Step 4 has to draw the reason and offer the picker, so this is a 200 with
    `plan_absent.reason == "unit_has_no_plan"` — never a 404 on a unit that
    exists, and never an empty plan object that would read as a plan.
    """
    with tenant_ctx(brazos):
        unit = _unit_with_plan(dana, brazos, with_plan=False)
        response = api_call(  # noqa: F405
            api.unit_pricing,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            unit_id=unit["id"],
        )
    assert response.status_code == 200
    assert response.data["plan"] is None
    assert response.data["plan_absent"]["reason"] == "unit_has_no_plan"
    assert response.data["rate_schedules"] == []
    assert response.data["unit"]["rate_plan_id"] is None


def test_w5_tc7__the_worked_month_is_NOT_computed_and_the_payload_says_so(brazos, dana):
    """⚠ THE ONE B18 ASKS FOR AND THIS LANE REFUSED TO INVENT.

    Two things are missing and neither is a bug in this file:

      1. Nothing prices a plan outside a bill run. `engine.price_bill` /
         `price_period` are PURE functions; the assembly that feeds them
         (`apps/billing/gather.py`, `runs.calculate_account`) is keyed on an
         ACCOUNT, and a move-in at step 4 has none yet.
      2. No signed rule states the consumption a worked month is priced at. A
         unit being moved into has no history; typical-household, last-tenant
         and base-only give three different numbers on the same screen.

    Choosing either resolves an open question by picking a value, which the
    prime directive forbids.

    ⚠ **AMENDED 2026-08-25 — `tracks` WAS `None` AND IS NOW `OQ-363`.** The lane
    that wrote this refused to invent an id and left it null, which was right: an
    absence citing a row that does not exist is worse than one citing none
    (DEF-445). The row was then minted on merge, the selector was updated to cite
    it, and **this assertion was not re-run — it went red and stayed red until
    another lane reported it.** The lesson is not about the value: a merge that
    changes what a module SERVES owes a run of the tests that assert it, and the
    two edits were minutes apart in the same session.

    **This test goes RED the day a worked month is served without a rule behind
    it**, which is the point of pinning it — and it now also goes red if the
    absence stops naming the question that will close it.
    """
    with tenant_ctx(brazos):
        unit = _unit_with_plan(dana, brazos)
        response = api_call(  # noqa: F405
            api.unit_pricing,
            "get",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            unit_id=unit["id"],
        )
    worked = response.data["worked_month"]
    assert worked["served"] is False
    assert worked["reason"] == "no_service_prices_a_plan_outside_a_bill_run"
    assert worked["tracks"] == "OQ-363"
    # No total, no tax, no month figure anywhere in the payload.
    assert "total" not in worked and "amount" not in worked


def test_w5_tc8__both_reads_are_tenant_scoped__a_foreign_unit_is_ABSENT(
    brazos, dana, lonestar, erin
):
    """Hard rule 1. A cross-tenant id is 404, never 403 (HR-1: existence must
    not leak), and it is answered BEFORE any asset or plan is read — an empty
    panel would tell Lone Star that Brazos Bend's unit exists and is empty."""
    from core import errors

    with tenant_ctx(brazos):
        unit = _unit_with_plan(dana, brazos)
        a_meter(dana, "M-7001", unit_id=unit["id"])

    with tenant_ctx(lonestar):
        for reader in (selectors.unit_assets, selectors.unit_pricing):
            with pytest.raises(errors.NotFoundError):
                reader(unit["id"])
        # ...and the same through the wired view, which is what a browser hits:
        # the BE-02 handler renders it as a plain 404, byte-identical to a unit
        # that never existed, so nothing leaks that Brazos Bend holds this id.
        for view in (api.unit_assets, api.unit_pricing):
            denied = api_call(  # noqa: F405
                view,
                "get",
                user=erin.user,
                role="system_admin",
                tenant=lonestar,
                unit_id=unit["id"],
            )
            unknown = api_call(  # noqa: F405
                view,
                "get",
                user=erin.user,
                role="system_admin",
                tenant=lonestar,
                unit_id=str(uuid.uuid4()),
            )
            assert denied.status_code == unknown.status_code == 404

            # `trace_id` is per-request; everything that could LEAK is compared.
            def strip(payload):
                return {k: v for k, v in payload.items() if k != "trace_id"}

            assert strip(denied.data) == strip(unknown.data)
            assert denied.data["code"] is None and denied.data["br_ref"] is None


def test_w5_tc9__neither_read_writes_and_neither_serves_money_it_computed(brazos, dana, audit_rows):
    """LAW 0 + hard rule 4: these are READS. A GET that writes is a GET that
    surprises somebody (the `account_usage` precedent).

    Also pins the 🔒 boundary: `unit_assets` carries NO money at all
    (BR-AST-025's posture on the assets side), and `unit_pricing` carries only
    figures rating computed — asserted by the plan's Σ being rating's own
    `plan_detail` value rather than one summed here.
    """
    with tenant_ctx(brazos):
        unit = _unit_with_plan(dana, brazos)
        a_meter(dana, "M-7001", unit_id=unit["id"])
        before = len(audit_rows)
        assets_body = selectors.unit_assets(unit["id"])
        pricing_body = selectors.unit_pricing(unit["id"])
        assert len(audit_rows) == before, "a read writes no audit row"

        from apps.rating import selectors as rating_selectors

        rating_says = rating_selectors.plan_detail(pricing_body["unit"]["rate_plan_id"])
    # BR-RAT-027: the plan total base is rating's DERIVED Σ. Both sides read
    # rating; the figure is pinned so a sum sneaking into THIS module goes RED.
    assert pricing_body["plan"]["base_charges"] == rating_says["base_charges"]
    assert pricing_body["plan"]["base_charges"] == str(ELECTRIC_BASE + WATER_BASE) == "20.500000"
    assert "money" not in str(assets_body).lower()
    for group in assets_body["groups"]:
        for asset in group["assets"]:
            assert set(asset) == {
                "id",
                "asset_no",
                "type",
                "type_name",
                "category",
                "qualifier",
                "service",
                "last_read",
            }
