# ── Trace ──────────────────────────────────────────────
# Change:  **PO ruling 2026-09-07** — *"now your reading model is correct - add
#          seed data accordingly"*, asked for in the same conversation as *"you
#          will have to do some variation for datys, for consumptions ; for
#          Electric if rates scheudule is TOU, Seaosnal or Demadn then reading
#          should be in like with that"*. Decision log 2026-09-07, *"TWO
#          RULINGS IN ONE BREATH"* part (2), and the build row of the same day.
# Rules:   BR-MET-051 (**a demand register is a MAXIMUM read at the cycle read,
#          not a counter** — `DEF-797`: $154.00 billed against a correct
#          $4,532.00) · BR-MET-049 (plan-driven read-set completeness: *"TOU →
#          per-window records; demand → +demand record"*) · BR-MET-059 / B2 r8
#          (the channel model) · BR-AST-029 (an export record belongs to a
#          net-metering asset and no other) · BR-MET-019 (consumption is the
#          delta of a running total) · BR-MET-121 (the run judges the span it
#          prices) · CLAUDE.md hard rule 3 (an explicit unit, never assumed)
# Golden:  ❄️ GT-17 — water $39.50 / sewer $15.80 on unit 0's **8 kgal**, and
#          `CR-062` addendum J2's **$129.70** on the government building's
#          **12 kgal**. Both are asserted here BY NAME because this change
#          rewrites the consumption of every other customer on the estate.
# Tests:   this file
# Impacts: core/sample_fixture.py · apps/metering/sample_data.py ·
#          apps/assets/sample_data.py
# ───────────────────────────────────────────────────────
"""**THE READING MODEL, SEEDED — AND THE TWO CUSTOMERS IT MUST NOT TOUCH.**

Every case here is PURE: it reads the fixture and the row builders and needs no
database, because the thing being asserted is what the seeder would WRITE. The
browser walkthrough (`10-scripts/po_20260907_reading_model_walkthrough.mjs`)
is what proves it renders.

Three parts, and each one replaces a measured "before":

  (a) **427 readings over 8 dates, `days_since_prior` only ever 14, 30 or 31.**
      One route held all 100 service points of the estate and was walked on one
      day. Five routes now, walked on the last five working days of the cycle.
  (b) **One formula with a flat ±1 drift** — every customer's July exactly one
      unit above their June, on every service at once. A seasonal curve per
      service, a response per customer, three named oddities.
  (c) **4 on-peak, 4 mid-peak, 4 off-peak, 2 demand and 2 export readings in
      the whole product**, all on three hand-authored meters of one tenant.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.metering import sample_data as metering_sample
from core import sample_fixture as fixture

# ══════════════════════════════════════════════════════════════════════════
# (a) THE WALK IS SPREAD ACROSS FIVE ROUTES
# ══════════════════════════════════════════════════════════════════════════


def test_the_estate_has_one_walk_route_per_street() -> None:
    """Five streets, five rounds — and the round is what a walk date is a fact
    ABOUT, which is why one route could not have satisfied the ruling."""
    assert len(fixture.READ_ROUTES) == len(fixture.STREETS) == 5
    assert [row["street"] for row in fixture.READ_ROUTES] == list(fixture.STREETS)
    assert [row["walk_offset"] for row in fixture.READ_ROUTES] == [0, 1, 2, 3, 4]


def test_route_one_is_walked_on_the_cycle_close_and_has_not_moved() -> None:
    """⚠ **THE GUARD ON EVERY PINNED DATE IN THE SUITE.** Offset 0 is the
    period's own `read_on`, unshifted, so `CASE_REFERENCE_BILL` — unit 0, at
    101 Silver Creek Rd — is still read on 30 June, 31 July and 14 August."""
    assert fixture.opening_read_on(0) == fixture.OPENING_READ_ON == date(2026, 5, 31)
    assert fixture.route_read_on("june", 0) == date(2026, 6, 30)
    assert fixture.route_read_on("july", 0) == date(2026, 7, 31)
    assert fixture.route_read_on("august", 0) == date(2026, 8, 14)
    unit_zero = next(u for u in fixture.units_flat() if u["unit_index"] == 0)
    assert fixture.walk_route_index(unit_zero["street"]) == 0


def test_no_route_is_ever_walked_on_a_weekend() -> None:
    """A crew does not read meters on a Saturday, and it is the weekend skip
    that makes the spans move rather than a fixed offset."""
    for key in ("june", "july", "august"):
        for route in fixture.READ_ROUTES[1:]:
            day = fixture.route_read_on(key, route["walk_offset"])
            assert day.weekday() < 5, f"{route['name']} walks {key} on a weekend: {day}"


def test_the_period_lengths_now_spread_from_29_to_33_days() -> None:
    """**THE MEASURED BEFORE AND AFTER.** `days_since_prior` took only 14, 30
    and 31 across the whole product; the estate's own walk-to-walk spans are
    now 29, 30, 31 and 33 days.

    ⚠ **AUGUST IS 14 ON EVERY ROUTE AND THAT IS DELIBERATE** — the fixture's
    "today" is mid-August, so the August period is a fortnight for everybody
    and both ends of it shift together.
    """
    june_spans, july_spans, august_spans = set(), set(), set()
    for route in fixture.READ_ROUTES:
        offset = route["walk_offset"]
        opening = fixture.opening_read_on(offset)
        june = fixture.route_read_on("june", offset)
        july = fixture.route_read_on("july", offset)
        august = fixture.route_read_on("august", offset)
        june_spans.add((june - opening).days)
        july_spans.add((july - june).days)
        august_spans.add((august - july).days)
    assert june_spans == {29, 30, 31}
    assert july_spans == {31, 33}
    assert august_spans == {14}
    # Every full-month span is inside the seeded 25–35 day flag bounds
    # (`_0031_helpers`), so the spread adds material to the Days tab without
    # falsely warning a single reading.
    assert all(25 <= span <= 35 for span in june_spans | july_spans)


def test_each_route_reads_only_its_own_street() -> None:
    seen: set[int] = set()
    for route in fixture.READ_ROUTES:
        rows = metering_sample._rows_for(
            fixture.period_row("july"), "water", False, route["walk_offset"]
        )
        dates = {row["read_date"] for row in rows}
        assert len(dates) == 1, f"{route['name']} handed in two dates: {dates}"
        assert dates == {fixture.route_read_on("july", route["walk_offset"]).isoformat()}
        for row in rows:
            index = int(str(row["meter_id"]).split("-")[-1]) - 5000
            seen.add(index)
    # Every unit is walked exactly once — no unit is on two rounds and none is
    # dropped, which is the failure a per-street split could silently cause.
    assert len(seen) == fixture.UNIT_COUNT


# ══════════════════════════════════════════════════════════════════════════
# (b) THE CONSUMPTION CURVE — AND THE TWO CUSTOMERS THAT MUST NOT MOVE
# ══════════════════════════════════════════════════════════════════════════


def test_the_reference_bill_customer_draws_eight_kgal_every_month() -> None:
    """❄️ **GT-17.** The signed reference bill's own consumption. A drift of
    ±1 would make `$39.50` true in June and false in July."""
    for key in ("june", "july", "august"):
        assert fixture.water_consumption_kgal(fixture.CASE_REFERENCE_BILL, key) == Decimal("8")
        assert fixture.consumption(fixture.CASE_REFERENCE_BILL, key, "water") == Decimal("8")


def test_the_government_building_draws_twelve_kgal_every_month() -> None:
    """`CR-062` addendum J2 — 12 kgal is what makes the `$65.50` usage, and
    therefore the `$157.50` subtotal and the `$31.50` Municipal discount, come
    out. It is a figure the Product Owner was shown and can check by hand.
    ⚠ It was `$129.70` / `$25.94` until `CR-081` (2026-09-08) moved this seat's
    sewer line from `$26.20` to `$54.00`; the 12 kgal did not move."""
    for key in ("june", "july", "august"):
        assert (
            fixture.water_consumption_kgal(fixture.CASE_GOVERNMENT_ACCOUNT, key)
            == fixture.GOVERNMENT_WATER_KGAL
            == Decimal("12")
        )


def test_the_pinned_customers_are_flat_on_every_service_not_only_on_water() -> None:
    """The conservative reading of *"exactly 8 kgal every single month"*: the
    two pinned seats are answered before any curve is consulted, so their
    electric and gas readings are as flat as their water ones."""
    for unit in (fixture.CASE_REFERENCE_BILL, fixture.CASE_GOVERNMENT_ACCOUNT):
        for service in ("water", "electric", "gas"):
            values = {fixture.consumption(unit, key, service) for key in ("june", "july", "august")}
            assert len(values) == 1, f"unit {unit} varies on {service}: {values}"


def test_gas_peaks_in_winter_and_water_peaks_in_summer() -> None:
    """The curve is per SERVICE, which is the whole reason it does not live in
    `water_consumption_kgal`: one shape scaled into every service would give a
    gas utility its highest demand in July."""
    water = fixture.SEASONAL_SHAPE["water"]
    gas = fixture.SEASONAL_SHAPE["gas"]
    assert water.index(max(water)) == 6, "water should peak in July"
    assert gas.index(max(gas)) == 0, "gas should peak in January"
    assert gas.index(min(gas)) in (6, 7), "gas should trough in midsummer"
    # Each curve averages about a month, so a customer's SIZE does not move.
    for service, shape in fixture.SEASONAL_SHAPE.items():
        total = sum(Decimal(factor) for factor in shape)
        assert Decimal("11") <= total <= Decimal("13"), f"{service} sums to {total}"


def test_customers_no_longer_move_in_lock_step() -> None:
    """**THE DEFECT THIS REPLACES, STATED AS A TEST.** Every customer's July
    was exactly one unit above their June — fifty households moving as one."""
    deltas = {
        fixture.water_consumption_kgal(index, "july")
        - fixture.water_consumption_kgal(index, "june")
        for index in range(fixture.UNIT_COUNT)
        if index not in (fixture.CASE_REFERENCE_BILL, fixture.CASE_GOVERNMENT_ACCOUNT)
    }
    assert deltas != {Decimal("1")}
    assert len(deltas) >= 8, f"only {len(deltas)} distinct July movements: {sorted(deltas)}"


def test_the_seasonal_response_is_not_locked_in_step_with_the_walk_routes() -> None:
    """⚠ **WHY `SEASONAL_RESPONSE` HAS SEVEN ENTRIES AND NOT FOUR OR FIVE.** A
    premises takes its street from `index % 5` and the first 36 units sit one
    to a premises, so a response list whose length shared a factor with 5 would
    give every customer on one crew's round the same response — and the spread
    would vanish exactly where a clerk looks at it, one route at a time."""
    by_route: dict[int, set[str]] = {}
    for unit in fixture.units_flat():
        route = fixture.walk_route_index(unit["street"])
        response = fixture.SEASONAL_RESPONSE[
            unit["unit_index"] % len(fixture.SEASONAL_RESPONSE)
        ]
        by_route.setdefault(route, set()).add(response)
    for route, responses in by_route.items():
        assert responses == set(fixture.SEASONAL_RESPONSE), (
            f"route {route + 1} carries only {sorted(responses)}"
        )


def test_the_three_oddities_land_where_they_are_declared() -> None:
    """*"Deliberate oddities are worth more than smooth data — they are what a
    clerk learns the exception screens on."* A leak, a fortnight away, and an
    empty house."""
    leak_june = fixture.water_consumption_kgal(fixture.CASE_LEAK, "june")
    leak_july = fixture.water_consumption_kgal(fixture.CASE_LEAK, "july")
    leak_august = fixture.water_consumption_kgal(fixture.CASE_LEAK, "august")
    assert leak_july > leak_june * 4, f"the leak is not a leak: {leak_june} → {leak_july}"
    assert leak_august < leak_july / 3, "the leak was supposed to be fixed before August"

    away_june = fixture.water_consumption_kgal(fixture.CASE_HOLIDAY_DROP, "june")
    away_july = fixture.water_consumption_kgal(fixture.CASE_HOLIDAY_DROP, "july")
    assert away_july < away_june / 2, f"the holiday drop is not a drop: {away_june} → {away_july}"

    # `CASE_MOVED_OUT`'s final bill is cut in mid-July, so August is an empty
    # house. This is an existing case being made true, not a fourth oddity.
    assert fixture.water_consumption_kgal(fixture.CASE_MOVED_OUT, "august") == Decimal("1")

    # None of the three sits on a seat that already carries a story.
    assert fixture.CASE_LEAK not in fixture.AWKWARD_UNITS
    assert fixture.CASE_HOLIDAY_DROP not in fixture.AWKWARD_UNITS


def test_no_month_is_ever_zero_or_negative() -> None:
    """A register never goes backwards between two reads: `validation`'s
    negative-usage verdict is a hard ERROR and would refuse the whole batch."""
    for index in range(fixture.UNIT_COUNT):
        for service in ("water", "electric", "gas"):
            for key in ("june", "july", "august"):
                assert fixture.consumption(index, key, service) >= 1


# ══════════════════════════════════════════════════════════════════════════
# (c) THE REGISTERS AN ELECTRIC METER CARRIES
# ══════════════════════════════════════════════════════════════════════════


def test_a_flat_or_tiered_customer_still_reads_one_total() -> None:
    assert fixture.electric_tariff_shape(0) == fixture.SHAPE_TIERED
    assert fixture.read_channels(0, "electric") == ("total",)
    # And no non-electric service ever grows a second register.
    for service in ("water", "gas", "thermal_heat"):
        for index in sorted(fixture.TOU_UNITS | fixture.DEMAND_UNITS):
            assert fixture.read_channels(index, service) == ("total",)


def test_a_time_of_use_customer_reads_three_windows_and_they_sum_to_the_total() -> None:
    """`BR-MET-049` — *"TOU → per-window records"* — and the sum is what makes
    `validation.tou_sum_sanity` report **0.000000 %** rather than a rounding
    wobble against the tenant's seeded 1 % tolerance."""
    assert len(fixture.TOU_UNITS) == 6
    for index in sorted(fixture.TOU_UNITS):
        assert fixture.electric_tariff_shape(index) == fixture.SHAPE_TIME_OF_USE
        channels = fixture.read_channels(index, "electric")
        assert set(fixture.TOU_WINDOW_CHANNELS) < set(channels)
        assert fixture.CHANNEL_TOTAL in channels
        for key in ("june", "july", "august"):
            total = Decimal(fixture.consumption(index, key, "electric"))
            split = fixture.tou_window_split(total)
            assert sum(split.values()) == total, f"unit {index} {key}: {split} != {total}"
            assert all(amount > 0 for amount in split.values())


def test_a_demand_customer_reads_a_peak_in_kw_and_it_is_a_value_not_a_counter() -> None:
    """⚠ **`BR-MET-051` AND `DEF-797`.** A maximum register bills its VALUE.
    A seeder that accumulated it would re-commit the defect that billed
    **$154.00 where the correct charge was $4,532.00** — from the fixture side,
    where every test would pass because the arithmetic would be consistent and
    simply wrong."""
    assert fixture.DEMAND_UNITS == frozenset({46, 47, 49})
    for index in sorted(fixture.DEMAND_UNITS):
        assert fixture.electric_tariff_shape(index) == fixture.SHAPE_DEMAND
        assert fixture.read_channels(index, "electric")[-1:] == (fixture.CHANNEL_DEMAND,)
    # The register does NOT accumulate: three months of the same draw give the
    # same peak, not a rising one.
    plant = fixture.CASE_INDUSTRIAL_ACCOUNT
    peaks = [
        metering_sample._register_value(plant, key, "electric", False, fixture.CHANNEL_DEMAND)
        for key in ("june", "july", "august")
    ]
    assert peaks == [Decimal("100"), Decimal("100"), Decimal("100")], peaks


def test_the_plants_peak_is_the_stated_one_hundred_kilowatts() -> None:
    """**DERIVED FROM A FIGURE THIS FIXTURE ALREADY STATES, NOT CHOSEN.**
    `CR-062` addendum J4 puts the seeded plant at a **100 kW** peak on 54,000
    kWh over a 730-hour month, so peak ÷ average is 1.35 — and applied back to
    its own 54,000 kWh it returns its own 100 kW."""
    assert fixture.UNIT_SERVICE_CONSUMPTION[(fixture.CASE_INDUSTRIAL_ACCOUNT, "electric")] == (
        Decimal("54000")
    )
    assert fixture.demand_peak_kw(Decimal("54000")) == Decimal("100")
    # A small commercial suite lands in the tens of kW, not the hundreds.
    suite = Decimal(fixture.consumption(46, "july", "electric"))
    assert Decimal("5") <= fixture.demand_peak_kw(suite) <= Decimal("40")


def test_only_a_roof_with_panels_exports() -> None:
    """`BR-AST-029` — an export record belongs to a net-metering asset and no
    other, and `validation.export_not_net` is a hard ERROR otherwise. The set
    is DERIVED from the panel plan, so the roof and the meter cannot get out of
    step, and the solar seat with NO panels is correctly absent."""
    assert fixture.EXPORT_UNITS == frozenset(
        {fixture.SOLAR_UNIT_WITH_THREE_PANELS, fixture.SOLAR_UNIT_WITH_ONE_PANEL}
    )
    assert fixture.SOLAR_UNIT_WITH_NO_PANELS not in fixture.EXPORT_UNITS
    for index in sorted(fixture.EXPORT_UNITS):
        assert fixture.CHANNEL_EXPORT in fixture.read_channels(index, "electric")
    for index in range(fixture.UNIT_COUNT):
        if index not in fixture.EXPORT_UNITS:
            assert fixture.CHANNEL_EXPORT not in fixture.read_channels(index, "electric")


def test_no_seasonal_register_is_ever_written() -> None:
    """⚠ **OF THE THREE SHAPES THE PO NAMED, TWO CHANGE THE READING AND ONE
    DOES NOT.** Seasonal changes only how the same single total is PRICED —
    that is `OQ-234`'s closure, in `apps/rating/pricing/models/seasonal.py`.
    A lane reading the ruling without that distinction would invent a `season`
    channel that nothing may ever write, so it is asserted here."""
    lawful = {
        fixture.CHANNEL_TOTAL,
        *fixture.TOU_WINDOW_CHANNELS,
        fixture.CHANNEL_DEMAND,
        fixture.CHANNEL_EXPORT,
    }
    for index in range(fixture.UNIT_COUNT):
        for service in ("water", "electric", "gas"):
            assert set(fixture.read_channels(index, service)) <= lawful


def test_the_opening_batch_carries_a_baseline_for_every_counter_and_no_peak() -> None:
    """A demand register is a MAXIMUM and has no baseline to be measured from,
    so an opening peak would be a reading that means nothing. Every counter
    does need one — without it the first cycle's consumption is NULL."""
    rows: list[dict] = []
    for route in fixture.READ_ROUTES:
        rows += metering_sample._opening_rows("electric", False, route["walk_offset"])
    assert fixture.CHANNEL_DEMAND not in {row["channel"] for row in rows}
    for index in sorted(fixture.TOU_UNITS | fixture.EXPORT_UNITS):
        mine = {row["channel"] for row in rows if row["meter_id"] == f"E-{5000 + index}"}
        expected = set(fixture.read_channels(index, "electric")) - {fixture.CHANNEL_DEMAND}
        assert mine == expected, f"unit {index} opened on {sorted(mine)}"


def test_the_split_is_the_signed_shape_from_ep_met_03() -> None:
    """The three shares are `EP-MET-03` §4's own signed deltas rounded —
    *"tou_on 210 / tou_mid 118 / tou_off 96"* of 424 kWh is 49.5 / 27.8 / 22.6
    per cent — with off-peak taken as the REMAINDER so the sum is exact."""
    split = fixture.tou_window_split(Decimal("424"))
    assert split[fixture.CHANNEL_TOU_ON] == Decimal("212")
    assert split[fixture.CHANNEL_TOU_MID] == Decimal("119")
    assert split[fixture.CHANNEL_TOU_OFF] == Decimal("93")
    assert sum(split.values()) == Decimal("424")


# ── Lifecycle ─────────────────────────────────────────────
# packet: PO ruling 2026-09-07 (decision log, "TWO RULINGS IN ONE BREATH" (2))
# generated: 2026-09-07 by the reading-model seed lane
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
