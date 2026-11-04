# ── Trace ──────────────────────────────────────────────
# Story:    CR-028 AST-W2 (B16 §5.1/§5.1b — the details view for every kind):
#           T3 the three Overview panels' payload · T4 the Reads tab SERVED
#           (DEF-475 closed) · T6 names not UUIDs · T7 maintenance cost
#           captured + totalled, never posted (D3) · T8 the device model's
#           linked net meter
# Rules:    BR-AST-029 (net-meter reads are TWO typed records, folded per date
#           on this tab) · BR-AST-025/016 (no money on any read surface;
#           quantities carry their unit — CLAUDE.md rule 3) · BR-AST-039 (the
#           LIVE billing chain, account leg included now customers owns
#           tables) · BR-AST-047 (valuation captured on the record; NO finance
#           link — §10-D3/D4) · BR-AST-018 (maintenance append-only; cost is a
#           captured figure) · BR-AST-026 (uuids are addressing, never
#           display — the "By"/Technician columns resolve to NAMES)
# Tests:    this file
# Impacts:  apps/assets/selectors.py · apps/assets/api.py · apps/assets/
#           seams.py · apps/metering/selectors.py (READ_FILTERS gains `asset`
#           — the DEF-475 fix — and typed_reads_for_asset carries `source`)
# ───────────────────────────────────────────────────────
"""CR-028 AST-W2 — the detail payload, the served Reads tab, names, cost.

RED-FIRST: every test here was run against the pre-change tree and its
failure quoted in the lane report before the code landed.
"""

from datetime import date
from decimal import Decimal

import pytest

from tests import identity_fixtures
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    accept_warnings,
    commit_read,
    seed_config,
    stage,
    tenant_ctx,
)
from tests.test_us_met_helpers import make_asset, make_plan, make_premises, make_unit

# ⚠ AFTER the star imports on purpose: the shared reads helpers export a
# `services` (metering's) that would otherwise shadow this module's own.
from apps.assets import selectors, services  # noqa: E402
from apps.metering import selectors as metering_selectors  # noqa: E402
from core import errors  # noqa: E402

pytestmark = pytest.mark.django_db

NET_HEADER = "meter_id,read_date,reading,read_type,service,flags\n"


def net_csv(*rows: str) -> str:
    return NET_HEADER + "".join(row if row.endswith("\n") else row + "\n" for row in rows)


def post(actor, content):
    from apps.metering import services as metering_services

    batch = stage(actor, content)
    metering_services.validate_read_batch(actor, batch["id"])
    accept_warnings(actor, batch["id"])
    return metering_services.commit_read_batch(actor, batch["id"], {"certified": True})


def net_meter(actor, asset_no="M-4021", **kw):
    asset = a_meter(actor, asset_no=asset_no, **kw)
    services.update_asset(actor, asset["id"], {"net_metering": True})
    return asset


def _months_between(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


# ══════════════════════════════════════════════════════════════════════════
# T4 — the Reads tab SERVED (DEF-475 closed)
# ══════════════════════════════════════════════════════════════════════════
def test_w2_t4__asset_reads_folds_the_net_pair_per_date_newest_first(brazos, marcus):
    """BR-AST-029: a net cycle's TWO typed records land as ONE row — the
    Import/Export columns of r10's AST-02 Reads tab — and the list is newest
    first. §4's fixture: Aug 684 consumed; Sep 702 consumed / 141 exported."""
    with tenant_ctx(brazos):
        seed_config()
        asset = net_meter(marcus)
        commit_read(marcus, asset["id"], day="2026-08-03", value="42864", consumption="684")
        post(
            marcus,
            net_csv(
                "M-4021,2026-09-03,43566,consumption,electric,",
                "M-4021,2026-09-03,141,export,electric,",
            ),
        )
        rows = selectors.asset_reads(asset["id"])
    # ⚠ **NO `[:10]` HERE ANY MORE, AND THAT SLICE WAS HALF OF `DEF-MET-4101`.**
    # It compared the first ten characters, so it passed identically whether the
    # server served `"2026-09-03"` or `"2026-09-03T00:00:00+00:00"` — it could
    # not see the shape it was standing on. The whole product drew these reads a
    # day early for three weeks underneath a green assertion. Compare the WHOLE
    # served value: the shape IS the contract.
    assert [row["date"] for row in rows] == ["2026-09-03", "2026-08-03"]
    september = rows[0]
    # The pair is FOLDED: one row, both quantities, each with its explicit unit.
    assert september["consumption"] == "702.000000" and september["unit"] == "kWh"
    assert september["export"] == "141.000000" and september["export_unit"] == "kWh"
    assert september["reading"] == "43566.000000"
    assert september["source"] and september["status"]
    # ...and no money key of any kind (BR-AST-025/016).
    for row in rows:
        for key in row:
            assert key not in ("amount", "currency", "credit", "credit_amount", "rate")


# ══════════════════════════════════════════════════════════════════════════
# DEF-MET-4101 — a read's date is served as a CALENDAR DATE
# ══════════════════════════════════════════════════════════════════════════
def test_def_met_4101__read_dates_are_served_as_calendar_dates_never_instants(brazos, marcus):
    """**The contract half of `DEF-MET-4101`.** A read's date IS a calendar date:
    `read_import._parse_date` stamps every one at `00:00:00Z` of the read day,
    because that midnight is what makes `UNIQUE (asset, read_at, channel)` the
    per-date key `BR-MET-052` describes. Served as a raw instant it reached
    `DateCell`, which converts an instant INTO the tenant's timezone — so every
    read drew a day early for every tenant west of UTC. Brazos Bend is
    `America/Chicago`: a read stored `2026-09-03T00:00:00Z` was DRAWN `09/02/2026`
    on the Reads tab, the Export tab, the read detail page, the account read log,
    the S25 list (there as `09/02/2026 19:00`, with a clock time nobody recorded)
    and the customer's own bill in the portal.

    ⚠ **THIS IS A TEST ABOUT WHAT WE SERVE, AND NOTHING ABOUT WHAT WE STORE.**
    The tempting repair at the other end — storing the completion moment instead
    of the date — makes the screen right and SILENTLY disables the
    one-read-per-meter-per-date guarantee, because that guarantee IS the midnight
    normalisation. So this asserts the stored row is untouched too: if a change
    ever makes the served date right by moving `read_at`, this fails.

    ⚠ **AND IT PINS THE SHAPE, NOT A PREFIX.** Every check in the repo compared
    UTC dates while the screen rendered local ones, so the two never met; the
    sibling case above did `row["date"][:10]`, which cannot tell the two shapes
    apart. `AssetDetail.test.tsx` holds the other half — the same read RENDERED,
    east and west of UTC. Neither half can catch this alone.
    """
    from apps.metering import models as metering_models
    from apps.metering import selectors as metering_selectors

    with tenant_ctx(brazos):
        seed_config()
        asset = net_meter(marcus)
        commit_read(marcus, asset["id"], day="2026-09-03", value="43566", consumption="702")

        # 1 · what the S50 Reads tab / Export tab / S29 history / account read
        #     log are served (`assets.selectors._fold_row`).
        rows = selectors.asset_reads(asset["id"])
        served = rows[0]["date"]

        # 2 · what the S25 list, the S29 header and the portal are served
        #     (`metering.selectors.read_dict`).
        read = metering_models.MeterRead.objects.filter(asset_id=asset["id"]).order_by("-read_at")[
            0
        ]
        detail = metering_selectors.read_dict(read)

        stored = read.read_at

    # THE ASSERTION THAT WOULD HAVE CAUGHT IT — an exact value, not a prefix.
    assert served == "2026-09-03", f"served an instant, not a calendar date: {served!r}"
    assert "T" not in served
    assert detail["read_at"] == "2026-09-03", f"read_dict served {detail['read_at']!r}"
    assert "T" not in detail["read_at"]

    # ...and it matches its own siblings on the same payload, which are DateFields
    # and were always right. On S29 these two disagreed by exactly one day, next
    # to a usage line that said "14 days".
    if detail.get("period_end"):
        assert "T" not in detail["period_end"]

    # NOTHING STORED MOVED. Midnight UTC is the per-date key and it stays.
    assert stored.hour == 0 and stored.minute == 0 and stored.second == 0
    assert stored.date().isoformat() == "2026-09-03"


def test_w2_t4__a_non_net_meter_serves_rows_with_no_export_value(brazos, marcus):
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus, asset_no="M-4022", service="water", uom="kgal", unit_label="Unit W")
        commit_read(
            marcus, asset["id"], day="2026-08-03", value="312", consumption="9", unit="kgal"
        )
        rows = selectors.asset_reads(asset["id"])
    assert len(rows) == 1
    assert rows[0]["consumption"] == "9.000000" and rows[0]["unit"] == "kgal"
    assert rows[0]["export"] is None and rows[0]["export_unit"] is None


def test_w2_t4__no_reads_is_an_empty_list_and_the_route_is_served(brazos, dana):
    """The honest empty state DEF-475 blocked on: with the per-asset read now
    possible, an empty history is a TRUE claim and the endpoint may make it."""
    from apps.assets import api

    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-5099", service="electric", unit="kWh")
        assert selectors.asset_reads(asset["id"]) == []
    routes = {p.pattern._route for p in api.urlpatterns}
    assert "assets/<uuid:asset_id>/reads" in routes


def test_def_475__the_reads_list_narrows_to_one_asset(brazos, marcus):
    """DEF-475's actual gap, closed on the metering side: READ_FILTERS lacked
    an `asset` filter, so no caller could ask for one meter's rows."""
    with tenant_ctx(brazos):
        seed_config()
        mine = a_meter(marcus, asset_no="M-7001")
        other = a_meter(marcus, asset_no="M-7002", unit_label="Unit B", address="9 Oak St")
        commit_read(marcus, mine["id"], day="2026-08-03", value="100", consumption="10")
        commit_read(marcus, other["id"], day="2026-08-04", value="200", consumption="20")
        assert "asset" in metering_selectors.READ_FILTERS
        rows = list(metering_selectors.read_list(filters={"asset": mine["id"]}))
    assert [str(row.asset_id) for row in rows] == [str(mine["id"])]


# ══════════════════════════════════════════════════════════════════════════
# T3 — the three Overview panels' payload
# ══════════════════════════════════════════════════════════════════════════
def test_w2_t3__detail_serves_valuation_and_lifecycle_blocks(brazos, dana):
    """BR-AST-047: captured on the record, displayed, never posted — the
    payload carries the figures and NO GL account, ever (D3)."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="1408 Elm Street")
        unit = make_unit(dana, premise["id"], label="Unit A")
        asset = make_asset(
            dana,
            asset_no="M-4021",
            service="electric",
            unit_id=unit["id"],
            install_date="2024-03-12",
            supplier="Itron Direct",
            purchase_cost="164",
            expected_life_years=8,
            warranty_end="2029-03-12",
        )
        detail = selectors.asset_detail(asset["id"])
        from apps.assets import seams

        today = seams.tenant_today()
    valuation = detail["valuation"]
    assert valuation["supplier"] == "Itron Direct"
    assert valuation["purchase_cost"] == "164.0000"  # stored 4dp (rule 2, D10)
    assert valuation["warranty_end"] == "2029-03-12"
    assert valuation["warranty_covered"] is True  # cover ends 2029 — Covered
    assert valuation["currency"] == "USD"  # CHAR(3) rides WITH the amount (rule 2)
    lifecycle = detail["lifecycle"]
    assert lifecycle["age_months"] == _months_between(date(2024, 3, 12), today)
    assert lifecycle["expected_life_years"] == 8
    assert lifecycle["replacement_year"] == 2032  # install 2024 + 8-year life
    # No GL sentence, no account code, anywhere in this payload (D3).
    assert "5300" not in str(detail) and "5400" not in str(detail)


def test_w2_t3__warranty_expired_and_absent_states_are_distinct(brazos, dana):
    with tenant_ctx(brazos):
        expired = make_asset(
            dana, asset_no="M-OLD", service="electric", unit="kWh", warranty_end="2020-01-01"
        )
        none = make_asset(dana, asset_no="M-NONE", service="electric", unit="kWh")
        expired_detail = selectors.asset_detail(expired["id"])
        none_detail = selectors.asset_detail(none["id"])
    assert expired_detail["valuation"]["warranty_covered"] is False
    assert none_detail["valuation"]["warranty_covered"] is None
    assert none_detail["lifecycle"]["replacement_year"] is None


def test_w2_t3__the_account_leg_of_the_chain_is_live(brazos, dana):
    """BR-AST-039: Premises → Unit → ACTIVE ACCOUNT — the leg that was null
    while customers owned no tables now serves `A-… · name` (B16 §5.1)."""
    from apps.customers import services as customers_services
    from apps.metering import services as metering_services

    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="1408 Elm Street")
        unit = make_unit(dana, premise["id"], label="Unit A")
        metering_services.assign_unit_plan(
            dana, unit["id"], {"tariff_id": str(make_plan(brazos, name="Res Std").id)}
        )
        metering_services.ensure_service_point(unit["id"], "electric")
        account = customers_services.create_account(
            dana,
            {
                "unit_id": str(unit["id"]),
                "account_type": "residential",
                "opened_at": "2026-08-01",
                "contact": {"full_name": "Sarah Miller", "email": "sarah@example.com"},
                # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
                # customer identifies nobody, and this fixture's own name went in above.
                # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
                "customer": identity_fixtures.customer_block(
                    "Sarah Miller", account_type="residential"
                ),
            },
        )
        customers_services.activate_account(dana, account["id"])
        asset = make_asset(
            dana,
            asset_no="M-4021",
            service="electric",
            unit_id=unit["id"],
            install_date="2024-03-12",
        )
        chain = selectors.asset_detail(asset["id"])["billing_chain"]
    assert chain["account"] is not None
    assert chain["account"]["account_no"] == account["account_no"]
    assert chain["account"]["customer_name"] == "Sarah Miller"


# ══════════════════════════════════════════════════════════════════════════
# T6 — names, not UUIDs
# ══════════════════════════════════════════════════════════════════════════
def test_w2_t6__assignment_by_and_maintenance_technician_resolve_to_names(brazos, dana):
    """BR-AST-026's spirit on the history tabs: the uuid is addressing, the
    NAME is display — resolved server-side so a Clerk (who cannot list users)
    still reads a person, not a key (the deployed W-5000 defect)."""
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        unit = make_unit(dana, premise["id"])
        asset = make_asset(
            dana,
            asset_no="M-4021",
            service="electric",
            unit_id=unit["id"],
            install_date="2026-01-01",
        )
        services.log_maintenance(
            dana,
            asset["id"],
            {
                "kind": "inspection",
                "detail": "checked",
                "tech_user_id": str(dana.id),
            },
        )
        assignments = selectors.assignments(asset["id"])
        maintenance = selectors.maintenance(asset["id"])
    dana_name = "System_Admin".title()  # staff_actor names the row role.title()
    assert assignments[0]["by"] == dana_name
    assert str(dana.id) not in [row["by"] for row in assignments]
    assert maintenance[0]["technician"] == dana_name
    assert maintenance[0]["tech_user_id"] == str(dana.id)  # addressing stays


def test_w2_t6__a_null_actor_still_reads_system(brazos, dana):
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-5099", service="electric", unit="kWh")
        from apps.assets import models

        row = models.Asset.objects.get(pk=asset["id"])
        models.AssetAssignment.objects.create(
            tenant_id=row.tenant_id,
            asset=row,
            unit_id=make_unit(dana, make_premises(dana)["id"])["id"],
            from_date="2026-01-01",
            actor_user=None,
        )
        assignments = selectors.assignments(asset["id"])
    assert assignments[0]["by"] == "System"


# ══════════════════════════════════════════════════════════════════════════
# T7 — maintenance cost: captured and totalled, never posted (D3)
# ══════════════════════════════════════════════════════════════════════════
def test_w2_t7__maintenance_cost_is_captured_4dp_and_totalled(brazos, dana):
    """B16 §7's worked figures: $31.00 + $88.40 = 'Lifetime maintenance
    $119.40'. Stored 4dp; the total is the server's sum, not a screen's."""
    from apps.assets import models

    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-4021", service="electric", unit="kWh")
        services.log_maintenance(
            dana,
            asset["id"],
            {"kind": "repair", "date": "2026-06-02", "detail": "seal", "cost": "31"},
        )
        services.log_maintenance(
            dana,
            asset["id"],
            {"kind": "repair", "date": "2026-07-02", "detail": "comms", "cost": "88.40"},
        )
        services.log_maintenance(
            dana, asset["id"], {"kind": "inspection", "date": "2026-08-01", "detail": "no cost"}
        )
        rows = selectors.maintenance(asset["id"])
        total = selectors.maintenance_lifetime_cost(asset["id"])
        stored = models.AssetMaintenance.objects.filter(asset_id=asset["id"], cost__isnull=False)
    assert [row["cost"] for row in rows] == [None, "88.4000", "31.0000"]  # newest first
    assert total == "119.4000"
    assert {entry.cost for entry in stored} == {Decimal("31"), Decimal("88.40")}
    # D3: the payload names no GL account and no posting sentence.
    assert "5300" not in str(rows) and "post" not in str(rows).lower()


def test_w2_t7__a_negative_cost_is_refused_and_no_cost_totals_none(brazos, dana):
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-5099", service="electric", unit="kWh")
        with pytest.raises(errors.ValidationError):
            services.log_maintenance(
                dana,
                asset["id"],
                {"kind": "repair", "detail": "bad", "cost": "-5"},
            )
        assert selectors.maintenance_lifetime_cost(asset["id"]) is None


def test_w2_t7__the_maintenance_api_serves_rows_and_the_lifetime_total(brazos, dana):
    from apps.assets import api as assets_api

    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-4021", service="electric", unit="kWh")
        services.log_maintenance(
            dana,
            asset["id"],
            {"kind": "repair", "date": "2026-06-02", "detail": "seal", "cost": "31"},
        )
        response = api_call(  # noqa: F405 — star import from the shared helpers
            assets_api.asset_maintenance,
            "get",
            user=FakeUser(),  # noqa: F405
            role="system_admin",
            tenant=brazos,
            asset_id=asset["id"],
        )
    assert response.status_code == 200
    # ⚠ `results`, NOT `rows` — `DEF-AST-5776`. `784361367` (2026-09-12,
    # CR-092 wave C lane 1, `NFR-3`) moved this tab onto the ONE paginated
    # envelope `{count, next, previous, results}`, with `lifetime_cost` and
    # `currency` as siblings of it; this case was red from that commit (green
    # at `2b708074a`). The money figures asserted are unchanged.
    assert response.data["count"] == 1
    assert response.data["results"][0]["cost"] == "31.0000"
    assert response.data["lifetime_cost"] == "31.0000"
    assert response.data["currency"] == "USD"  # CHAR(3) rides WITH the amount


# ══════════════════════════════════════════════════════════════════════════
# T8 — the device model: linked net meter, cadence, sub-meter facts
# ══════════════════════════════════════════════════════════════════════════
def test_w2_t8__an_inverter_detail_names_its_linked_net_meter(brazos, dana):
    """B16 §5.1b (B): the Export tab reads the LINKED NET METER's records —
    the link is served, never guessed ('Measured by M-4310 · net →')."""
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        unit = make_unit(dana, premise["id"])
        meter = make_asset(
            dana,
            asset_no="M-4310",
            type="net_meter",
            service="electric",
            unit_id=unit["id"],
            install_date="2024-01-01",
            net_metering=True,
        )
        inverter = make_asset(
            dana,
            asset_no="PV-1204",
            type="pv",
            unit=None,
            service=None,
            parent_asset_no="M-4310",
            export_capacity_kw="11.4",
        )
        detail = selectors.asset_detail(inverter["id"])
        plain = selectors.asset_detail(
            make_asset(dana, asset_no="BF-3301", type="backflow", unit=None, service=None)["id"]
        )
    assert detail["linked_meter"] == {
        "id": meter["id"],
        "asset_no": "M-4310",
        "net_metering": True,
    }
    assert plain["linked_meter"] is None


def test_w2_t8__a_device_with_a_cadence_says_so(brazos, dana):
    with tenant_ctx(brazos):
        tested = make_asset(
            dana,
            asset_no="BF-3301",
            type="backflow",
            unit=None,
            service=None,
            last_test_date="2026-02-10",
            test_interval_months=12,
        )
        untested = make_asset(dana, asset_no="BAT-0904", type="battery", unit=None, service=None)
        tested_detail = selectors.asset_detail(tested["id"])
        untested_detail = selectors.asset_detail(untested["id"])
    assert tested_detail["has_test_cadence"] is True
    assert tested_detail["lifecycle"]["certification_due"] == "2027-02-10"
    assert untested_detail["has_test_cadence"] is False


def test_w2_t8__a_sub_meter_detail_serves_its_master_link_and_share(brazos, dana):
    """B16 §5.1b: Specifications add Parent/master (a LINK — the id, not just
    the number) and the allocation share, blank = metered."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="Vega Apts")
        unit = make_unit(dana, premise["id"], label="Unit 12")
        master = make_asset(
            dana,
            asset_no="M-MASTER-12",
            service="electric",
            unit_id=unit["id"],
            install_date="2024-01-01",
        )
        sub = make_asset(
            dana,
            asset_no="SM-8801",
            type="sub_meter",
            service="electric",
            unit_id=unit["id"],
            install_date="2024-02-01",
            parent_asset_no="M-MASTER-12",
            allocation_share_pct="25",
        )
        detail = selectors.asset_detail(sub["id"])
    assert detail["parent_asset_id"] == master["id"]
    assert detail["parent_asset_no"] == "M-MASTER-12"
    assert detail["specs"]["allocation_share_pct"] == "25.000000"
    # blank = metered, not allocated — served as null, never a zero.
    with tenant_ctx(brazos):
        metered = selectors.asset_detail(master["id"])
    assert metered["specs"]["allocation_share_pct"] is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-028 AST-W2 (B16 §5.1/§5.1b · §10 D3/D7 rulings · §4.8 Details row)
# generated: 2026-08-22 by the CR-028 AST-W2 lane (tests FIRST — every case run
#   RED against the pre-change tree; failures quoted in the lane report)
# checklist: A✔ B✔ C✔ D✔ E=deferred(frontend half in AssetDetail.test.tsx) F✔ G✔
#   H=deferred(PO 2026-08-09)
# gates: see the lane report (this file rides the W2 commit)
# exceptions: the account-chain test builds its plan through make_plan (fixture
#   data, the documented test-only path) — the rating lane owns the service
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
