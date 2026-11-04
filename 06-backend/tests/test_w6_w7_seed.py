# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data). ⚠ **NO STORY OWNS
#           S86, S89 OR S90** — hard-won law 8; the three selector lanes each
#           filed it and all three are still OWED.
#           Screens: S86 (New connects) · S89 (Transfers) · S90 (Disconnects)
# Change:   CR-030 W6 tasks 6.3 + 6.15 and W7 task 7.12 — the SEED half.
# Rules:    BR-MET-109 (work-order templates are the utility's own and batching
#           is their choice — PO 2026-08-25) · BR-MET-110 (the field confirms, a
#           human accepts, and only then does service go live) · BR-CUS-039 (the
#           ladder) · BR-CUS-043 (a payment-plan protection holds while the plan
#           is active AND current) · BR-CUS-100 (the send and the proof are two
#           records; a tier-3 cut needs a recorded proof of service) ·
#           BR-CUS-101 (three protections, PO: *"3 is okay to start with"*) ·
#           BR-CUS-017 (one occupying account per unit) · BR-CUS-023 (the
#           deposit is a refused field) · BR-CUS-048/049 (buckets age from the
#           cutover; opening entries are posted by the ledger) · BR-TEN-035
#           (a number series moves FORWARD only) · BR-TEN-043 (the event date is
#           an argument, never a wall clock) · BR-TEN-057 (`is_sample` on the
#           owning row) · BR-TEN-061/066 (removal order; report the rest BY
#           NAME) · BR-TEN-063 (idempotent) · CLAUDE.md hard rules 1, 2, 5
# Questions: OQ-371 / OQ-374 (the segment strips — OPEN; both lists serve
#           `segment=all` only, and nothing here depends on a segment filter) ·
#           OQ-366 (who a restarted ladder chases — OPEN; no row names a party)
# Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.4.1 · §5.4.8 ·
#           §5.4.9 · §5.7.1 · §5.7.6 · §5.8.1 · §5.8.6 · §8.1 · §8.2 · §11
#           (W6 tasks 6.3/6.15, W7 task 7.12)
# Tests:    this file
# Impacts:  apps/metering/sample_data.py · apps/customers/sample_data.py
# ───────────────────────────────────────────────────────
"""CR-030 W6 T6.3/T6.15 + W7 T7.12 — the three seeds, proved through the
SELECTORS the screens call.

**WHY EVERY ASSERTION GOES THROUGH A SELECTOR AND NOT THROUGH A COUNT.**
B18 draws FIGURES — `OPEN 7`, `UNITS AWAITING ENERGISATION 42`, `AT NOTICE 4` —
and those figures are what a Product Owner looks at. A test that counted
`Connection.objects.count()` would pass on a seed that puts the right number of
rows in the wrong shape, and hard-won law 6 (*"diff the running app against the
prototype"*) exists because exactly that kind of test kept passing. So the
tiles are read from `connection_reads.list_connections`,
`transfer_reads.list_transfers` and `disconnect_reads.list_disconnects` — the
same three calls the three screens make.

**WHAT THIS FILE PROVES, AND WHAT IT REFUSES TO PROVE.**
Five of the fifteen drawn KPI figures cannot come out of this tree, and each is
asserted **as the number the product actually serves, beside the drawn one**,
with the measurement in `W7_ABSENCES` naming what is missing. A test tuned to
make a tile read 1 would be a fixture proving a fixture:

  · `CUT, AWAITING PAYMENT 1` and `RECONNECTIONS DUE 1` — **nothing in this
    product writes `cut` or `reconnecting`.** Tasks 7.8 and 7.9 are unbuilt;
    `schedule_cut` says so in its own docstring.
  · `DEPOSITS CARRYING 1` — `A-11455` holds no deposit and `deposit_on_file` is
    a REFUSED field on both account doors (BR-CUS-023).
  · `ON HOLD — PROTECTED 3` — the fixture's one live payment plan is no longer
    CURRENT (its instalment dues are literal dates and Aug 17 has passed), so
    BR-CUS-043's protection is stored and not in force.
  · `A-11720` — a drawn number another drawn fact already holds; the row
    carries both numbers.
  · **ALL FIVE TRANSFER TILES READ 0 (`DEF-CUS-9072`).** §5.7.6's five rows are
    each a customer MOVING, which `BR-CUS-1030` (2026-09-01) took out of
    transfers; none is planted and each row names that blocker.

**RED PROVED FIRST for every guard here** (hard-won law 7). Each was broken
under a mutation, run, the failure quoted in the lane report, and the mutation
reverted — no `# BREAK:` marker survives in this file (DEF-666).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.customers import disconnect_reads, disconnects, transfer_reads, transfers
from apps.customers import models as customers_models
from apps.customers import sample_data as customers_sample
from apps.metering import connection_reads
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.metering import sample_data as metering_sample
from apps.tenancy import sample_data as tenancy_sample
from apps.tenancy import services as tenancy_services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import tenant_ctx
from tests.test_us_met_helpers import brazos, dana  # noqa: F401

pytestmark = pytest.mark.django_db

#: B18 §5.4.8's eight rows exactly — the drawn UNITS, the drawn ORDERS fraction,
#: the drawn WAITING ON and the drawn STATE, in CR-032's vocabulary
#: (`activated` / `partly_activated`, never `energised`).
DRAWN_CONNECTIONS = {
    "CON-26-0110": (1, (5, 5), None, work_tables.ACTIVATED),
    "CON-26-0119": (1, (5, 9), "permit", work_tables.ON_HOLD),
    "CON-26-0121": (1, (2, 5), "materials", work_tables.IN_PROGRESS),
    "CON-26-0126": (1, (3, 9), "inspection", work_tables.PARTLY_ACTIVATED),
    "CON-26-0117": (25, (5, 7), "inspection", work_tables.PARTLY_ACTIVATED),
    "CON-26-0128": (1, (2, 5), None, work_tables.PARTLY_ACTIVATED),
    "CON-26-0124": (1, (0, 7), None, work_tables.REQUESTED),
    "CON-26-0122": (12, (1, 6), "site access", work_tables.IN_PROGRESS),
}

#: §5.4.1's five tiles, verbatim.
DRAWN_NCT_KPIS = {
    "open": 7,
    "waiting_on_inspection": 2,
    "partly_activated": 3,
    "units_awaiting_activation": 42,
    "oldest_days": 19,
    "oldest_connection_no": "CON-26-0119",
    "oldest_waiting_on": "permit",
}

#: The six services the tenant must sell before B18's builds can be seeded whole
#: — electric and water are the fixture's own; these four are the rest.
#: `w6_unseeded_services()` names them on a tenant that does not.
EXTRA_SERVICES = ("gas", "sewer", "trash", "broadband")


@pytest.fixture()
def seeded(brazos, dana):
    """THE WHOLE PLANT, through the orchestrator's own seam.

    `tenancy.sample_data.seed_sample_data` runs every module's block in the
    ruled order, so this fixture cannot drift from what a tenant actually
    receives — the posture `tests/test_cr030_w1_import_seed.py` sets, widened
    because W7 needs blocks from six modules: rating (the plans a unit must
    carry), metering (the seats), customers (the accounts), billing and payments
    (the debt a payment plan spreads) and then the plan itself.

    The four extra services are enabled FIRST, through tenancy's own service.
    B18's builds take five services between them and the fixture tenant sells
    two, and BR-MET-003 refuses the rest — correctly. Enabling them is what a
    utility selling gas would have done, and `w6_unseeded_services()` is what a
    tenant that has not sees instead.
    """
    with tenant_ctx(brazos):
        for code in EXTRA_SERVICES:
            tenancy_services.update_tenant_service(dana, code, {"enabled": True})
        summary = tenancy_sample.seed_sample_data(dana)
    return brazos, dana, summary


# ══════════════════════════════════════════════════════════════════════════
# W6 TASK 6.3 — THE TEMPLATE STARTERS (BR-MET-109)
# ══════════════════════════════════════════════════════════════════════════


def test_the_starters_are_a_removable_catalogue_and_not_a_policy(seeded):
    """BR-MET-109, PO 2026-08-25: *"we will give them ready to use tempaltes -
    they will develope these templats in work order section"*.

    A starter is sample data the utility owns and edits, so every row carries
    BR-TEN-057's tag and `--remove` can take it away. A row without the tag
    would be a policy this product imposes, which is the thing the ruling
    reversed.
    """
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        rows = work_tables.WorkOrderTemplate.objects.filter(tenant_id=tenant.id)
        assert rows.exists(), "task 6.3 seeds the starters"
        assert rows.filter(is_sample=False).count() == 0


def test_gas_gates_on_the_light_up_and_never_on_the_meter_set(seeded):
    """B18 §8.1: *"Gas is the one that catches people out … a lane that gates
    gas on the meter set will bill a customer with no gas."*

    The single most consequential row in task 6.3, asserted from BOTH sides: the
    light-up IS the gate and the meter set is NOT.
    """
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        gas = list(
            work_tables.WorkOrderTemplate.objects.filter(
                tenant_id=tenant.id, service__code="gas"
            ).order_by("sequence")
        )
        assert [row.name for row in gas] == [
            "Inspection",
            "Service line and tap",
            "Meter set",
            "Pressure test and light-up",
        ]
        gates = [row.name for row in gas if row.is_gate]
        assert gates == ["Pressure test and light-up"]


def test_every_other_metered_service_gates_on_its_meter_set(seeded):
    """§8.1's own sentence — *"Every other metered service is billable once the
    meter is set"*.

    Asserted on the SEEDED rows for electric and water, and on the DECLARATION
    for thermal: a starter is only planted for a service the tenant sells
    (BR-MET-003), and this fixture's utility does not sell thermal. Reading the
    declaration is what keeps the third service's gate covered without pretending
    the tenant has it.
    """
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        for code in ("electric", "water"):
            gates = list(
                work_tables.WorkOrderTemplate.objects.filter(
                    tenant_id=tenant.id, service__code=code, is_gate=True
                ).values_list("name", flat=True)
            )
            assert gates == ["Meter set"], code
    declared = dict(metering_sample.W6_TEMPLATE_STARTERS)
    # DEF-WRK-9266: thermal fits no meter (CR-080); its gate is the service connection.
    assert [name for name, _scope, is_gate in declared["thermal_heat"] if is_gate] == [
        "Service connection"
    ]


def test_three_services_carry_no_gate_row_and_each_says_why(seeded):
    """⚠ A NEGATIVE ASSERTION, AND IT MUST STAY NEGATIVE.

    Sewer gates on the WATER service it derives from, solar on a *permission to
    operate* that names none of its four drawn steps, and storm water has **0**
    orders at all. A later lane that makes one of these green by flagging a row
    must do it because somebody RULED which step authorises the service — not
    because an unflagged set looked incomplete.
    """
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        for code in ("sewer", "solar", "storm_water"):
            assert code in metering_sample.W6_UNGATED_STARTERS, code
            assert (
                work_tables.WorkOrderTemplate.objects.filter(
                    tenant_id=tenant.id, service__code=code, is_gate=True
                ).count()
                == 0
            ), code
        assert (
            work_tables.WorkOrderTemplate.objects.filter(
                tenant_id=tenant.id, service__code="storm_water"
            ).count()
            == 0
        ), "§8.1 gives storm water zero orders — *assessed from records, no visit*"


def test_no_batching_rule_is_shipped_by_the_seed(seeded):
    """BR-MET-109: *"`CON-26-0117`'s 5 of 7 orders across 25 units is an OUTCOME
    of that tenant's templates, not a figure the engine derives."*

    The seven orders are DECLARED, one per line of §8.2's breakdown, and the
    seeder holds no arithmetic that turns 25 units into 7. This asserts the
    absence the way `connection_reads` asserts OQ-371's: by reading the
    declaration, so that adding a batcher here goes RED.
    """
    row = next(
        entry for entry in metering_sample.W6_CONNECTIONS if entry["connection_no"] == "CON-26-0117"
    )
    assert len(row["orders"]) == 7
    assert row["units"] == 25
    assert not hasattr(metering_sample, "batch_orders")


# ══════════════════════════════════════════════════════════════════════════
# W6 TASK 6.15 — THE EIGHT BUILDS, THROUGH `NCT-01`'s OWN SELECTOR
# ══════════════════════════════════════════════════════════════════════════


def test_the_five_kpi_tiles_reproduce_b18_5_4_1(seeded):
    """B18 §5.4.1, verbatim: `OPEN 7` · `WAITING ON INSPECTION 2` ·
    `PARTLY ENERGISED 3` · `UNITS AWAITING ENERGISATION 42` ·
    `OLDEST 19 days · CON-26-0119 · waiting on permit`.

    ⚠ **`UNITS AWAITING ACTIVATION 42` IS THE ONE THAT DECIDES WHETHER THE SEED
    IS RIGHT.** It is `1+1+1+25+1+1+12` — the UNITS column summed over the seven
    OPEN builds — so it is false unless `CON-26-0117` really carries 25 units
    with per-unit service rows on them. A seed that made the other four tiles
    foot with per-premise services only would fail here and nowhere else.
    """
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        kpis = connection_reads.list_connections(per=50)["kpis"]
    assert kpis["open"] == DRAWN_NCT_KPIS["open"]
    assert kpis["waiting_on_inspection"] == DRAWN_NCT_KPIS["waiting_on_inspection"]
    assert kpis["partly_activated"] == DRAWN_NCT_KPIS["partly_activated"]
    assert kpis["units_awaiting_activation"] == DRAWN_NCT_KPIS["units_awaiting_activation"]
    assert kpis["oldest"]["days"] == DRAWN_NCT_KPIS["oldest_days"]
    assert kpis["oldest"]["connection_no"] == DRAWN_NCT_KPIS["oldest_connection_no"]
    assert kpis["oldest"]["waiting_on"] == DRAWN_NCT_KPIS["oldest_waiting_on"]


def test_every_drawn_row_renders_as_b18_5_4_8_draws_it(seeded):
    """§5.4.8's eight rows, cell by cell, off the list the screen calls.

    ⚠ **THE STATE WORDS ARE `activated` / `partly_activated` (CR-032).** B18
    still prints `Energised`; the ruled vocabulary is what the seed writes and
    what this asserts.
    """
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        rows = {
            row["connection_no"]: row for row in connection_reads.list_connections(per=50)["rows"]
        }
    assert set(rows) == set(DRAWN_CONNECTIONS)
    for number, (units, orders, waiting_on, state) in DRAWN_CONNECTIONS.items():
        row = rows[number]
        assert row["units"] == units, number
        assert (row["orders"]["done"], row["orders"]["total"]) == orders, number
        assert row["waiting_on"] == waiting_on, number
        assert row["state"] == state, number


def test_con_26_0117_is_twenty_five_units_and_seven_orders(seeded):
    """§5.4.8: *"`CON-26-0117` is the batching proof and must stay in the seed
    exactly as it is: 25 units, 5 services, and SEVEN orders. A lane that
    produces 76 has broken §8."*"""
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        row = next(
            entry
            for entry in connection_reads.list_connections(per=50)["rows"]
            if entry["connection_no"] == "CON-26-0117"
        )
        orders = work_tables.WorkOrder.objects.filter(
            tenant_id=tenant.id, connection__connection_no="CON-26-0117"
        )
    assert row["units"] == 25
    assert orders.count() == 7, "SEVEN, not seventy-six (§8.2)"
    assert sorted(row["services"]) == ["electric", "gas", "sewer", "trash", "water"]


def test_a_build_ends_with_its_units_vacant_and_holding_no_account(seeded):
    """§5.4.9: *"A NEW CONNECT ENDS WITH UNITS VACANT, SERVICE OFF AND NO
    ACCOUNT. That is the terminal state, not an incomplete one."*

    Asserted on the ACTIVATED build, which is the only one that has finished:
    if a seeded build ever hands its unit an account, the demo teaches that a
    new connect produces a customer, and it does not — a move-in does.
    """
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        unit_ids = list(
            work_tables.ConnectionService.objects.filter(
                tenant_id=tenant.id,
                connection__connection_no="CON-26-0110",
                unit__isnull=False,
            ).values_list("unit_id", flat=True)
        )
        assert unit_ids
        assert (
            customers_models.Account.objects.filter(
                tenant_id=tenant.id, unit_id__in=unit_ids
            ).count()
            == 0
        )


def test_the_estate_units_at_500_main_street_never_join_the_build(seeded):
    """`core/sample_fixture.py`'s `500 Main St` carries five ESTATE units —
    `Ridge Coffee Co.`'s four suites and the `+3` chip overflow seat — and the
    build's 25 apartments are a separate block. If the build ever took the whole
    premises, `UNITS` would read 30 and the `42` tile would read 47."""
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        joined = set(
            work_tables.ConnectionService.objects.filter(
                tenant_id=tenant.id,
                connection__connection_no="CON-26-0117",
                unit__isnull=False,
            ).values_list("unit__unit_no", flat=True)
        )
    assert len(joined) == 25
    assert not joined & {"SCW-U-208", "SCW-U-209", "SCW-U-210", "SCW-U-211", "SCW-U-212"}


def test_the_drawn_connection_numbers_come_from_the_product_s_own_series(seeded):
    """The eight numbers are `CON-{YY}-{0000}` allocations, not strings written
    into a column: the seeder moves the counter forward (BR-TEN-035,
    forward-only, through tenancy's own service) and `create_connection`
    allocates in the ordinary way.

    ⚠ **AND THEY ARE SEEDED IN ASCENDING SEQUENCE, WHICH IS NOT THE ORDER B18
    LISTS THEM IN.** §5.4.8 is sorted by TARGET DATE, so its numbers run
    110 · 119 · 121 · 126 · **117** · 128 · **124** · **122**. Seeding in that
    order asks a forward-only counter to go backwards, the move is refused, and
    the build silently takes the next free number — measured, on the first run
    of this seeder, as `CON-26-0127` / `CON-26-0129` / `CON-26-0130`.
    """
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        numbers = set(
            work_tables.Connection.objects.filter(tenant_id=tenant.id).values_list(
                "connection_no", flat=True
            )
        )
    assert numbers == set(DRAWN_CONNECTIONS)


def test_a_seeded_order_that_is_done_went_through_br_met_110_s_three_steps(seeded):
    """BR-MET-110, PO 2026-08-25: *"Work order will send the data and confirm
    from field; utility staff will review these work order, accept them and use
    data from them to activate these services."*

    A completed order in this fixture carries what the field sent, WHO accepted
    it and WHEN — because a seed that set `state = 'completed'` directly would
    put the demo in a state the product's own rule says cannot exist.
    """
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        done = work_tables.WorkOrder.objects.filter(
            tenant_id=tenant.id, state=work_tables.WO_COMPLETED
        )
        assert done.exists()
        for order in done:
            assert order.outcome == work_tables.OUTCOME_PASSED, order.order_no
            assert order.field_data, order.order_no
            assert order.accepted_at is not None, order.order_no
            assert order.accepted_by_id is not None, order.order_no


def test_the_dates_are_anchored_on_the_tenant_s_own_today_not_on_a_literal(seeded):
    """DEF-629's ruling, PO 2026-08-24: *"whenever you do the migration cant you
    devcide the date at that time"*.

    `OLDEST · 19 days` is computed as `now - submitted_at`, so a literal
    `2026-08-05` would be right for one day and drift for ever. Every date in
    this fixture is an OFFSET from the day the seed ran, and `w6_anchor_on()`
    recovers that day from a STORED column so a replay re-dates nothing.
    """
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        anchor = metering_sample.w6_anchor_on()
        for row in metering_sample.w6_connection_report():
            assert row["planted"], row["connection_no"]
            assert row["seeded_target"] == row["expected_target"], row["connection_no"]
            assert date.fromisoformat(row["seeded_target"]) == anchor + timedelta(
                days=row["target_offset"]
            )


def test_replaying_the_seed_writes_nothing(seeded):
    """BR-TEN-063 — *"idempotent, audited"*. A second run must not double a row
    and must not re-date one."""
    tenant, actor, _ = seeded
    with tenant_ctx(tenant):
        before = {
            "connections": work_tables.Connection.objects.filter(tenant_id=tenant.id).count(),
            "services": work_tables.ConnectionService.objects.filter(tenant_id=tenant.id).count(),
            "orders": work_tables.WorkOrder.objects.filter(tenant_id=tenant.id).count(),
            "templates": work_tables.WorkOrderTemplate.objects.filter(tenant_id=tenant.id).count(),
            "units": metering_models.Unit.objects.filter(tenant_id=tenant.id).count(),
            "transfers": transfers.Transfer.objects.filter(tenant_id=tenant.id).count(),
            "cases": disconnects.DisconnectCase.objects.filter(tenant_id=tenant.id).count(),
            "protections": disconnects.AccountProtection.objects.filter(
                tenant_id=tenant.id
            ).count(),
        }
        targets_before = dict(
            work_tables.Connection.objects.filter(tenant_id=tenant.id).values_list(
                "connection_no", "target_activation"
            )
        )
        metering_sample.seed_sample_records(actor)
        customers_sample.seed_sample_records(actor)
        after = {
            "connections": work_tables.Connection.objects.filter(tenant_id=tenant.id).count(),
            "services": work_tables.ConnectionService.objects.filter(tenant_id=tenant.id).count(),
            "orders": work_tables.WorkOrder.objects.filter(tenant_id=tenant.id).count(),
            "templates": work_tables.WorkOrderTemplate.objects.filter(tenant_id=tenant.id).count(),
            "units": metering_models.Unit.objects.filter(tenant_id=tenant.id).count(),
            "transfers": transfers.Transfer.objects.filter(tenant_id=tenant.id).count(),
            "cases": disconnects.DisconnectCase.objects.filter(tenant_id=tenant.id).count(),
            "protections": disconnects.AccountProtection.objects.filter(
                tenant_id=tenant.id
            ).count(),
        }
        targets_after = dict(
            work_tables.Connection.objects.filter(tenant_id=tenant.id).values_list(
                "connection_no", "target_activation"
            )
        )
    assert after == before
    assert targets_after == targets_before


# ══════════════════════════════════════════════════════════════════════════
# W7 TASK 7.12 — THE FIVE TRANSFERS
# ══════════════════════════════════════════════════════════════════════════


# ⚠ `DEF-CUS-9072` — THESE FIVE CASES ASSERTED THE TRANSFER `BR-CUS-1030`
# RETIRED. Until 2026-09-01 a transfer closed one account and opened another
# (a customer MOVING); PO, that day: *"dont create new account - we reassing
# that account - bascailly I have sold my property … if I move to new location
# then it is new Service request"*. B18 §5.7.6's five rows are all moves, so the
# seed plants none and says why, and these cases assert that ruled state. They
# were red from `d1066469e` (2026-09-01), the commit that removed the steps the
# seed walked.


def test_the_five_drawn_transfers_are_moves_and_none_is_planted(seeded):
    """§5.7.6's five rows are each a customer moving house — under `BR-CUS-1030`
    no transfer does that, so each row is REPORTED by name, never silently
    missing (BR-TEN-066's posture)."""
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        report = [row for row in customers_sample.w7_fixture_report() if row["kind"] == "transfer"]
        payload = transfer_reads.list_transfers()
        stored = transfers.Transfer.objects.filter(tenant_id=tenant.id).count()
    assert [row["key"] for row in report] == [
        "trf-iversen", "trf-haddad", "trf-bianchi", "trf-park", "trf-osei",
    ]
    for row in report:
        assert row["planted"] is False, row["key"]
        assert row["seeded_state"] is None, row["key"]
        assert row["blocker"] == customers_sample.W7_TRANSFER_BLOCKER, row["key"]
        assert "BR-CUS-1030" in row["blocker_detail"], row["key"]
    assert stored == 0
    assert payload["total"] == 0


def test_the_transfer_kpi_strip_counts_no_seeded_move(seeded):
    """§5.7.1 draws `OPEN 2` · `MOVING THIS WEEK 1` · `ARREARS FOLLOWING 1` ·
    `COMPLETED THIS MONTH 3`, every one of them counted off the five moves. With
    none planted, every tile reads 0 — a tile showing a retired job would be a
    tile counting something the product cannot do."""
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        kpis = transfer_reads.list_transfers()["kpis"]
    assert kpis["open"] == 0
    assert kpis["moving_this_week"] == 0
    assert kpis["arrears_following"] == 0
    assert kpis["completed_this_month"] == 0
    assert kpis["deposits_carrying"] == 0


def test_no_seeded_account_was_closed_and_reopened_as_a_transfer(seeded):
    """`BR-CUS-1030`: *"dont create new account"* — the mirror of what TC-TRF-6
    asked of the retired job. Iversen's `A-10650` is still open, still holds its
    deposit, and no transfer starts from it."""
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        account = customers_models.Account.objects.get(tenant_id=tenant.id, account_no="A-10650")
        has_transfer = transfers.Transfer.objects.filter(
            tenant_id=tenant.id, from_account_id=account.id
        ).exists()
    assert account.closed_at is None
    assert account.deposit_on_file is not None
    assert has_transfer is False


def test_park_still_owes_the_542_10_the_accounts_tab_shows(seeded):
    """§5.7.6: *"the same $542.10 balance the Accounts tab shows at `60+ past`"*.
    The Accounts-tab half of that sentence does not depend on a transfer and
    still holds on the estate's own `A-11455`."""
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        account = customers_models.Account.objects.get(tenant_id=tenant.id, account_no="A-11455")
    assert Decimal(str(account.balance)) == Decimal("542.10")


# ══════════════════════════════════════════════════════════════════════════
# W7 TASK 7.12 — THE NINE DISCONNECTS
# ══════════════════════════════════════════════════════════════════════════


def test_every_tier_is_on_the_tab(seeded):
    """§5.8.6 draws all three ladder chips and task 7.12 asks for *"all
    tiers"*: TIER 1 on `A-11780`, TIER 2 on `A-11812`, TIER 3 on two rows.

    The ladder is walked through `disconnects.advance()` — the ONE gate — so a
    seeded tier is a tier the product agreed to hand out, not a string in a
    column.
    """
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        tiers = {
            row["key"]: row["seeded_tier"]
            for row in customers_sample.w7_fixture_report()
            if row["kind"] == "disconnect"
        }
    assert tiers["dsc-whitfield"] == disconnects.TIER_1
    assert tiers["dsc-bramble"] == disconnects.TIER_2
    assert tiers["dsc-northwind"] == disconnects.TIER_3
    assert tiers["dsc-calloway"] == disconnects.TIER_3


def test_all_three_built_protections_are_on_the_tab_and_only_three_exist(seeded):
    """BR-CUS-101, PO: *"3 is okay to start with"* — medical certificate,
    payment plan and weather moratorium. Task 7.12 asks for *"all
    protections"*, and all protections IS these three: the other seven of B18's
    ten do not exist to seed.
    """
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        kinds = set(
            disconnects.AccountProtection.objects.filter(tenant_id=tenant.id).values_list(
                "kind", flat=True
            )
        )
    assert kinds == set(disconnects.PROTECTIONS)
    assert len(disconnects.PROTECTIONS) == 3


def test_a_tier_3_cut_carries_a_recorded_proof_of_service(seeded):
    """BR-CUS-100 (PO 2026-08-25, closing DEF-692): *"a tier-3 cut must not be
    schedulable on an unrecorded service"*.

    Both scheduled rows therefore carry a PERSON's attestation — certified mail,
    a real USPS article number and the date it was served — and `delivery_state`
    stays NULL beside it, because the proof is a record of something that
    happened outside this product and never a delivery this product performed.
    """
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        for account_no in ("A-11340", "A-11721"):
            case = disconnects.open_case_for(
                customers_models.Account.objects.get(tenant_id=tenant.id, account_no=account_no).id
            )
            assert case.state == disconnects.STATE_SCHEDULED, account_no
            assert case.cut_scheduled_for is not None, account_no
            proof = disconnects.service_proof_for(case, tier=disconnects.TIER_3)
            assert proof["recorded"] is True, account_no
            assert proof["channel"] == disconnects.SERVE_CERTIFIED_MAIL, account_no
            notice = disconnects.latest_notice_at_tier(case, disconnects.TIER_3)
            assert notice.proof_reference
            assert notice.delivery_state is None, "task 7.10 — never a fabricated delivery"


def test_the_disconnect_kpi_strip_and_the_three_tiles_that_are_honestly_short(seeded):
    """§5.8.1: `AT NOTICE 4` · `DUE TO CUT THIS WEEK 2` · `ON HOLD 3` ·
    `CUT, AWAITING PAYMENT 1` · `RECONNECTIONS DUE 1`.

    ⚠ **THREE OF THE FIVE CANNOT COME OUT OF THIS TREE AND ARE ASSERTED AS WHAT
    THE PRODUCT SERVES.** `cut` and `reconnecting` have **no writer anywhere**
    (tasks 7.8 and 7.9 are unbuilt), and the payment-plan protection is stored
    and not in force because the fixture's one live plan is behind on its Aug 17
    instalment. Each has a measurement in `W7_ABSENCES`; none is tuned.
    """
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        kpis = disconnect_reads.list_disconnects()["kpis"]
    assert kpis["at_notice"] == 4
    assert kpis["due_to_cut_this_week"] == 2
    assert kpis["on_hold_protected"] == 2, "drawn 3 — the live plan is no longer CURRENT"
    assert kpis["cut_awaiting_payment"] == 0, "drawn 1 — nothing writes the `cut` state"
    assert kpis["reconnections_due"] == 0, "drawn 1 — nothing writes `reconnecting`"
    for absence in (
        "no_writer_for_cut_or_reconnecting",
        "the_live_payment_plan_is_no_longer_current",
    ):
        assert absence in customers_sample.W7_ABSENCES


def test_no_seeded_row_manufactures_a_state_the_product_cannot_write(seeded):
    """⚠ A NEGATIVE ASSERTION, AND IT MUST STAY NEGATIVE.

    `cut` and `reconnecting` are in `CASE_STATES`, in the migration's check
    constraint and in two KPI tiles — and in no assignment anywhere in this
    product. A later lane that makes the two tiles read 1 must do it by building
    tasks 7.8 and 7.9, not by writing the column from a seeder.
    """
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        states = set(
            disconnects.DisconnectCase.objects.filter(tenant_id=tenant.id).values_list(
                "state", flat=True
            )
        )
    assert not states & {disconnects.STATE_CUT, disconnects.STATE_RECONNECTING}


def test_the_two_taken_account_numbers_are_recorded_and_never_renumbered(seeded):
    """B18 §13 observation 4 — *"A fixture slip; the seed must pick one"* — and
    the second clash it does not record.

    `A-11780` keeps the estate's `Delgado, Pilar` and the drawn `Whitfield,
    Dana` rides the row. `A-11720` is held by `Ridge Property LLC`, whose EMPTY
    balance is load-bearing for `SR-26-0043`'s approval, so `Calloway, Brett` is
    seeded under a FIXTURE-NAMED `A-11721` with both numbers on the row.
    """
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        rows = {
            row["key"]: row
            for row in customers_sample.w7_fixture_report()
            if row["kind"] == "disconnect"
        }
        overflow = customers_models.Account.objects.get(tenant_id=tenant.id, account_no="A-11720")
    assert rows["dsc-whitfield"]["seeded_no"] == "A-11780"
    assert rows["dsc-whitfield"]["drawn_customer"] == "Whitfield, Dana"
    assert rows["dsc-calloway"]["drawn_no"] == "A-11720"
    assert rows["dsc-calloway"]["seeded_no"] == "A-11721"
    # The reason A-11720 could not be used, asserted rather than trusted.
    assert overflow.balance in (None, 0)


def test_the_two_unplantable_rows_name_their_blocker(seeded):
    """BR-TEN-066's posture applied to seeding: *"remove what is free, report
    the rest BY NAME"*. A row nothing can plant is not silently missing."""
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        rows = {
            row["key"]: row
            for row in customers_sample.w7_fixture_report()
            if row["kind"] == "disconnect"
        }
    for key in ("dsc-greaves", "dsc-doyle"):
        assert rows[key]["planted"] is False, key
        assert rows[key]["blocker"] == "no_writer_for_cut_or_reconnecting", key
        assert rows[key]["blocker_detail"], key


def test_neither_list_depends_on_a_segment_filter(seeded):
    """OQ-371 and OQ-374 are OPEN — both lists serve `segment=all` only. The
    seed must be readable without one, which is what these two calls prove."""
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        assert connection_reads.list_connections(segment="all", per=50)["total"] == 8
        assert disconnect_reads.list_disconnects(segment="all")["total"] == 6
        with pytest.raises(NotImplementedError):
            connection_reads.list_connections(segment="waiting")
        with pytest.raises(NotImplementedError):
            disconnect_reads.list_disconnects(segment="on_hold")


def test_no_seeded_row_names_a_chased_party(seeded):
    """OQ-366 is OPEN — J08 step 2b: *"a green assertion naming either party is
    a FAILURE."* Every case here is an ordinary SERVICE sequence against the
    account that owes the money; none is a post-closure collections sequence."""
    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        sequences = set(
            disconnects.DisconnectCase.objects.filter(tenant_id=tenant.id).values_list(
                "sequence", flat=True
            )
        )
    assert sequences == {disconnects.SEQ_SERVICE}


# ══════════════════════════════════════════════════════════════════════════
# CR-168-BRC10 lane FLOW-FIX — what the demo says RAISED a job, and what each
# customer flow is offered (`DEF-WRK-9627`, `DEF-WRK-9626`)
# ══════════════════════════════════════════════════════════════════════════
def test_def_wrk_9627_no_seeded_work_order_reads_raised_by_dash(seeded):
    """RED before the fix: 40 of 40 seeded orders carried ``source = NULL``."""
    from apps.work import connection_models as work_tables

    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        rows = work_tables.WorkOrder.objects.filter(tenant_id=tenant.id)
        assert rows.exists()
        assert list(rows.filter(source__isnull=True).values_list("order_no", flat=True)) == []
        build_job = rows.filter(connection__isnull=False).first()
        assert build_job.source == "new_connect"
        assert build_job.source_ref == build_job.connection.connection_no


def test_def_wrk_9626_each_customer_flow_is_offered_its_own_visit_on_the_demo(seeded):
    """RED before the fix: every flow was offered only *Meter exchange —
    residential*, the one sequence-0 template the demo had."""
    from apps.customers import models as cmodels
    from apps.work import from_flows

    tenant, _, _ = seeded
    with tenant_ctx(tenant):
        from apps.customers import services as customer_services

        account = cmodels.Account.objects.filter(
            tenant_id=tenant.id,
            status__behavior_class__in=customer_services.OCCUPYING_BEHAVIOR_CLASSES,
            unit__isnull=False,
        ).first()
        offered = {
            kind: [row["name"] for row in from_flows.propose(kind, account.id)["proposed"]]
            for kind in ("move_out", "move_in", "transfer", "reconnect")
        }
    for kind, names in offered.items():
        assert names, f"{kind} is offered nothing"
        assert "Meter exchange — residential" not in names, f"{kind} offered {names}"
    assert "Final read" in offered["move_out"]
    assert "Reconnect visit" in offered["reconnect"]
