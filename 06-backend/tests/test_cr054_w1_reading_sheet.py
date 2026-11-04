# ── Trace ──────────────────────────────────────────────
# Change:   CR-054 W1 tasks 4, 5 and 7 — the pre-filled reading sheet, and the
#           row key that survives the round trip.
# Rules:    BR-MET-049 (plan-driven read-set completeness — TOU → per-window
#           records, demand → +demand record) · BR-MET-059 (channel model; an
#           absent channel column ⇒ the flat meter's one `total` register) ·
#           BR-MET-052/057 (the cycle read window drives expectations) ·
#           BR-MET-106 (an unread month is ABSENT, never a zero) · BR-MET-143
#           (a register's unit — kWh on the energy register, kW on demand) ·
#           BR-MET-144 (a quantity displays at most two decimals, trailing
#           zeros trimmed) · BR-MET-122's SHAPE, followed exactly for the row
#           key (a pure rule that only judges; the service layer resolves the
#           context) · BR-MET-032 (ONE published template, ONE parser — the
#           sheet must re-upload through the importer that already exists) ·
#           BR-MET-020 (no threshold is invented here) · CLAUDE.md hard rule 1
#           (tenant scoping) · hard rule 3 (a quantity never travels without an
#           explicit unit) · DEF-324 (one bounded query per fact, never one per
#           meter) · DEF-894 (`1016.000000` reached a printed route sheet)
# Tests:    this file. Every guard was proved RED FIRST; each failing run is
#           quoted verbatim in the docstring of the test it belongs to.
# Impacts:  apps/metering/reading_sheet.py (new) · apps/metering/read_import.py
#           (the `row_key` column, the channel LABELS and the key grammar) ·
#           apps/metering/validation.py (RULE_ROW_KEY) · apps/metering/
#           services.py (stage + _build_context carry the key) ·
#           apps/metering/selectors.py (register_heads_for_assets) ·
#           apps/metering/api.py (the two cycle routes)
# ───────────────────────────────────────────────────────
"""CR-054 W1 — the clerk is handed the file instead of being asked to build it.

The PO's finding, verbatim: *"on step 1 we have given cycle and details - on
step 2 we have ready csv file - with all meters and existing data that is
availale - only details clark has to fill is readings and correct any data they
want and upload the file - so instead of they figuring out what to do we have
hande dthem all details"*.

Six decisions were asked of a clerk and the product told them none of them.
This suite pins the four that are register-shaped — which meters are in the
cycle, which need more than one row, that a time-of-use tariff needs four, and
that a peak is kW and not kWh — plus the two the sheet's own existence creates:
that the words it prints must be words the parser can read back, and that a row
whose meter was swapped is caught by name rather than imported in silence.

HOW THE `RED FIRST` QUOTES BELOW WERE OBTAINED
-----------------------------------------------
Two ways, and the difference is stated because it matters.

**Every test in this file was written and run BEFORE the code existed** — one
run on the pre-change tree, `26 failed, 7 passed`. The seven that passed are
the parametrized channel-CODE cases and the unknown-word refusal, which the
importer already satisfied; they are pinned here so the new alias map cannot
weaken them.

**Then each headline guard was broken ON PURPOSE in the finished code and run
again**, one sabotage at a time, so that the quote in its docstring is a
failure somebody actually watched rather than one a lane predicted. Four of the
predictions were word-for-word right; three were not, and those three were
corrected to the observed text. Every file was restored byte-for-byte after
each run (hashed before and after).
"""

from datetime import date

import pytest

from apps.metering import models, read_import, services, validation

from tests.test_us_met_018_plan_registers import (  # noqa: F401
    plan_with_version,
)
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    commit_read,
    csv_body,
    seed_config,
    stage,
    tenant_ctx,
)
from tests.test_us_met_helpers import (  # noqa: F401
    make_premises,
    make_unit,
)

pytestmark = pytest.mark.django_db

AUGUST = date(2026, 8, 1)


# ── fixture plumbing ────────────────────────────────────────────────────────


def seed_cycle(tenant, code="CY-001", **overrides):
    """A cycle definition written directly — the past a test starts from.

    Start day 1, five days to complete: `schedule.derive_read_window` places
    that at **1 Aug 2026 … 5 Aug 2026** in August, which is the module's own
    worked figure and the window every assertion below reads.
    """
    fields = dict(
        frequency="Monthly", start_day=1, days_to_complete=5, bill_day=31, status="active"
    )
    fields.update(overrides)
    return models.Cycle.objects.create(tenant=tenant, code=code, **fields)


def routed_planned_meter(
    actor,
    tenant,
    cycle,
    plan,
    *,
    asset_no,
    service="electric",
    uom="kWh",
    label=None,
    net_metering=False,
):
    """A meter that is BOTH in the cycle (BR-MET-033's `service_points.cycle_id`
    stamp, through the real route machinery) and on a unit that holds `plan`
    (BR-CUS-014's binding unit plan) — the two facts the sheet joins.

    Written from `test_cr038_w2_mixed_cycle.routed_meter` and
    `test_us_met_018_plan_registers.planned_meter`; neither alone produces a
    meter this lane can ask about, because one has no plan and the other has no
    cycle.
    """
    premises = make_premises(
        actor, address_line=f"1408 Bluestem Ln {asset_no}", services_available=[service]
    )
    unit = make_unit(actor, premises["id"], label=label or f"Unit {asset_no}", services=[service])
    if plan is not None:
        services.assign_unit_plan(
            actor,
            unit["id"],
            {"tariff_id": str(plan.id), "effective_from": "2026-06-01", "reason": "fixture"},
        )
    asset = a_meter(actor, asset_no, unit_id=unit["id"], service=service, uom=uom)
    if net_metering:
        from apps.assets import models as asset_models

        asset_models.Asset.objects.filter(pk=asset["id"]).update(net_metering=True)
    services.create_route(
        actor,
        {
            "code": f"R-{asset_no}",
            "cycle_id": str(cycle.id),
            "premises_ids": [str(premises["id"])],
        },
    )
    return unit, asset


def rows_for(sheet, meter_no):
    return [row for row in sheet.rows if row["meter_id"] == meter_no]


def cell(sheet, meter_no, channel_label, column):
    row = next(r for r in rows_for(sheet, meter_no) if r["channel"] == channel_label)
    return row[column]


# ═══════════════════════════════════════════════════════════════════════════
# 1 · TASK 4 — ONE ROW PER EXPECTED METER PER REQUIRED REGISTER
# ═══════════════════════════════════════════════════════════════════════════


def test_cr054_t4__a_time_of_use_meter_yields_four_rows_named_in_screen_words(brazos, dana):
    """BR-MET-049: *"TOU → per-window records"*, and BR-MET-049's resolver adds
    `total` because BR-MET-052's sum-sanity needs it. So a time-of-use meter is
    **four rows**, and the clerk is never asked to know that.

    And the register is named in the words the SCREENS use. The PO's complaint
    is that `tou_on` *"appears on NO screen — every screen says On-peak"*, so
    the sheet prints `On-peak` and `read_import` accepts it back.

    RED FIRST (verbatim, before apps/metering/reading_sheet.py existed):

        E   ModuleNotFoundError: No module named 'apps.metering.reading_sheet'
    """
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos)
        plan = plan_with_version(
            brazos,
            name="TOU Residential",
            model="time_of_use",
            windows=("tou_on", "tou_mid", "tou_off"),
        )
        routed_planned_meter(dana, brazos, cycle, plan, asset_no="M-7451")

        sheet = reading_sheet.build_reading_sheet(cycle, period_anchor=AUGUST)

        labels = [row["channel"] for row in rows_for(sheet, "M-7451")]
        assert labels == ["Total register", "On-peak", "Mid-peak", "Off-peak"], (
            "a time-of-use meter must yield one row per required register, named "
            f"in the words the screens use — got {labels!r}"
        )
        # Every one of the four carries the meter's own energy unit (rule 3).
        assert {row["unit_of_measure"] for row in rows_for(sheet, "M-7451")} == {"kWh"}


def test_cr054_t4__a_demand_meter_yields_two_rows_and_the_peak_is_kw(brazos, dana):
    """BR-MET-049: *"demand → +demand record"* — two rows. BR-MET-143 (PO
    2026-08-27, closing OQ-391): *"A demand reading carries kW"*, recorded per
    REGISTER, so one meter holds kWh on its energy register and kW on its
    demand register. That is the fifth thing the clerk was never told.

    RED FIRST (verbatim, with `unit_of_measure` taken from `asset.unit` instead
    of `register_units.register_unit` — the exact shape of DEF-797's label
    half):

        E   AssertionError: BR-MET-143: the demand register is priced per kW
            (rate_schedules.demand_rate_per_kw) and must not print the energy
            register's unit — got 'kWh'
        E   assert 'kWh' == 'kW'
    """
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos)
        plan = plan_with_version(brazos, name="Industrial Demand", model="demand", demand=True)
        routed_planned_meter(dana, brazos, cycle, plan, asset_no="M-8010")

        sheet = reading_sheet.build_reading_sheet(cycle, period_anchor=AUGUST)

        labels = [row["channel"] for row in rows_for(sheet, "M-8010")]
        assert labels == ["Total register", "Demand"]
        assert cell(sheet, "M-8010", "Total register", "unit_of_measure") == "kWh"
        demand_uom = cell(sheet, "M-8010", "Demand", "unit_of_measure")
        assert demand_uom == "kW", (
            "BR-MET-143: the demand register is priced per kW "
            "(rate_schedules.demand_rate_per_kw) and must not print the energy "
            f"register's unit — got {demand_uom!r}"
        )


def test_cr054_t4__a_meter_with_no_plan_is_listed_with_the_absence_reported(brazos, dana):
    """The DEF-075 posture, on the sheet. `ExpectedRegisters.channels is None`
    means *"the set could not be resolved"* and NEVER *"this meter expects
    nothing"* — so the meter appears (it is physically in the cycle and a clerk
    walking the route will read it) with the reason STATED in its own column,
    and it is counted in `unresolved` so the summary cannot claim a clean sheet.

    Dropping it would be the silent pass this whole lane exists to remove.

    RED FIRST (verbatim, when the builder `continue`d on an unresolved set the
    way `completeness._meter_rows` does):

        E   AssertionError: a meter physically in the cycle vanished from the
            sheet because its register set could not be resolved — that is the
            DEF-075 posture inverted
        E   assert [] != []
    """
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos)
        routed_planned_meter(dana, brazos, cycle, None, asset_no="M-9001")

        sheet = reading_sheet.build_reading_sheet(cycle, period_anchor=AUGUST)

        rows = rows_for(sheet, "M-9001")
        assert rows != [], (
            "a meter physically in the cycle vanished from the sheet because its "
            "register set could not be resolved — that is the DEF-075 posture inverted"
        )
        assert len(rows) == 1
        assert rows[0]["channel"] == ""  # nothing is guessed into it
        assert "no_plan" in rows[0]["issue"], rows[0]["issue"]
        assert [entry["meter"] for entry in sheet.unresolved] == ["M-9001"]
        assert sheet.unresolved[0]["reason"] == "no_plan"


# ═══════════════════════════════════════════════════════════════════════════
# 2 · TASK 5 — THE THREE COLUMN GROUPS, AND THE THREE DIFFERENT RULES
# ═══════════════════════════════════════════════════════════════════════════


def test_cr054_t5__the_previous_reading_prints_at_two_decimals(brazos, dana):
    """DEF-894 is exactly this bug on the printed route sheet, which shipped
    `1016.000000 · 8.000000 kgal` on all 41 stops. BR-MET-144 (PO 2026-08-27):
    *"2 decimals max, trailing zeros trimmed - this is correct"*.

    Storage does not move — `current_value` stays NUMERIC(18,6). This is the
    last step before a person reads it.

    RED FIRST (verbatim, with the register value written straight into the cell
    instead of through `quantity_display.quantity_text`):

        E   AssertionError: BR-MET-144 / DEF-894: a quantity displays at most
            two decimals with trailing zeros trimmed
        E   assert '42864.000000' == '42864'
    """
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos)
        plan = plan_with_version(brazos, name="Residential Flat", model="flat")
        _unit, asset = routed_planned_meter(dana, brazos, cycle, plan, asset_no="M-7001")
        commit_read(dana, asset["id"], day="2026-07-04", value="42864.000000", unit="kWh")

        sheet = reading_sheet.build_reading_sheet(cycle, period_anchor=AUGUST)
        row = rows_for(sheet, "M-7001")[0]

        assert row["previous_reading"] == "42864", (
            "BR-MET-144 / DEF-894: a quantity displays at most two decimals "
            "with trailing zeros trimmed"
        )
        assert row["previous_read_date"] == "2026-07-04"
        # rule 3 — the number and its unit are on the same row, never apart.
        assert row["unit_of_measure"] == "kWh"


def test_cr054_t5__a_meter_never_read_prints_a_dash_and_never_a_zero(brazos, dana):
    """BR-MET-106: an unread month is **ABSENT**, never a zero.
    `quantity_display.quantity_text` says the same in its own docstring —
    *"Returning `0` for a missing reading would state that a meter measured
    nothing, which is a different and false fact"*.

    A `0` in this column is worse than a blank: it is the previous reading a
    clerk would subtract from.

    RED FIRST (verbatim, with `previous_reading` defaulting to `"0"`):

        E   AssertionError: BR-MET-106: a meter never read is ABSENT — a zero
            here is a measurement claim nobody made
        E   assert '0' == '—'
    """
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos)
        plan = plan_with_version(brazos, name="Residential Flat", model="flat")
        routed_planned_meter(dana, brazos, cycle, plan, asset_no="M-7002")

        sheet = reading_sheet.build_reading_sheet(cycle, period_anchor=AUGUST)
        row = rows_for(sheet, "M-7002")[0]

        assert row["previous_reading"] == reading_sheet.DASH, (
            "BR-MET-106: a meter never read is ABSENT — a zero here is a "
            "measurement claim nobody made"
        )
        assert row["previous_read_date"] == reading_sheet.DASH


def test_cr054_t5__the_three_groups_are_what_the_sheet_carries(brazos, dana):
    """Identity says which reading the row is · context lets the clerk confirm
    the meter and is IGNORED on upload · theirs is pre-filled and correctable,
    with the reading itself blank because it is the one fact only they hold.

    The read DATE is pre-filled with the cycle's window START in the named
    month — `schedule.derive_read_window`'s own worked figure for start day 1
    and 5 days to complete is **1 Aug 2026 … 5 Aug 2026**. It is inside the
    window by construction, so a row the clerk does not correct never
    manufactures an `out_of_window` warning about a date the product supplied.
    """
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos)
        plan = plan_with_version(brazos, name="Residential Flat", model="flat")
        routed_planned_meter(dana, brazos, cycle, plan, asset_no="M-7003", label="Unit 3F")

        sheet = reading_sheet.build_reading_sheet(
            cycle, period_anchor=AUGUST, read_method="walk_by"
        )
        row = rows_for(sheet, "M-7003")[0]

        assert list(row) == list(reading_sheet.SHEET_HEADERS)
        # IDENTITY
        assert row["row_key"] == "CY-001|total|M-7003"
        assert row["meter_id"] == "M-7003"
        assert row["channel"] == "Total register"
        # CONTEXT
        assert "1408 Bluestem Ln M-7003" in row["premise"] and "Unit 3F" in row["premise"]
        # THEIRS
        assert row["reading"] == ""  # the one fact only the clerk holds
        assert row["read_date"] == "2026-08-01"
        assert row["read_method"] == "walk_by"
        assert row["demand_reset"] == ""  # a blank is an absence; `no` is a CLAIM
        assert row["notes"] == ""
        assert (sheet.period_start, sheet.period_end) == (date(2026, 8, 1), date(2026, 8, 5))


def test_cr054_t5__the_demand_reset_cell_is_left_empty_and_never_pre_claimed(brazos, dana):
    """`read_import`'s own reasoning, verbatim: *"`false` is a claim ('the
    register was not zeroed'), and a demand customer whose reset went unnoticed
    is billed against a peak that belongs to the previous cycle"*.

    So the reset is the second cell (with the reading) that the sheet leaves
    empty: the system holds no fact, and an empty cell is the only honest
    pre-fill for a fact nobody has stated. `_parse_demand_reset` reads a blank
    as False — the ABSENCE — which is what it has always meant.
    """
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos)
        plan = plan_with_version(brazos, name="Industrial Demand", model="demand", demand=True)
        routed_planned_meter(dana, brazos, cycle, plan, asset_no="M-8011")

        sheet = reading_sheet.build_reading_sheet(cycle, period_anchor=AUGUST)
        assert {row["demand_reset"] for row in rows_for(sheet, "M-8011")} == {""}


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE HARD CONSTRAINT — ONE PARSER. THE SHEET RE-UPLOADS THROUGH IT.
# ═══════════════════════════════════════════════════════════════════════════


def test_cr054_t4__the_sheet_round_trips_through_the_existing_importer(brazos, dana):
    """BR-MET-032: ONE published template, ONE parser, mapping re-detected on
    every upload. A generated sheet that needs its own parser is a second
    importer wearing a different name.

    Every column the clerk fills maps by NAME through `detect_mapping`, and the
    screen words come back as the channel CODES the engine stores.

    RED FIRST — the `CHANNEL_LABEL_ALIASES` line deleted from
    `read_import.parse_row`, run 2026-08-30, verbatim:

        tests/test_cr054_w1_reading_sheet.py:444: in test_cr054_t4__the_sheet_
        round_trips_through_the_existing_importer
        E   AssertionError: assert [[{'code': 'c... 'off-peak'}]] == [[], [], [], []]
        E     At index 0 diff: [{'code': 'channel_unknown', 'field': 'channel',
        E     'value': 'total register'}] != []
        1 failed, 32 deselected

    ALL FOUR rows are refused, and the first names `total register` — which is
    the point: without that one line the sheet's own words are unknown values
    to the sheet's own parser.
    """
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos)
        plan = plan_with_version(
            brazos,
            name="TOU Residential",
            model="time_of_use",
            windows=("tou_on", "tou_mid", "tou_off"),
        )
        routed_planned_meter(dana, brazos, cycle, plan, asset_no="M-7451")

        sheet = reading_sheet.build_reading_sheet(
            cycle, period_anchor=AUGUST, read_method="walk_by"
        )
        # The clerk does the one thing the sheet asks of them.
        for index, row in enumerate(sheet.rows):
            row["reading"] = str(1000 + index)
        body = reading_sheet.reading_sheet_csv(sheet)

        mapping, headers, rows = read_import.parse_csv(body.encode("utf-8"))

        assert read_import.missing_required(mapping) == []
        for target in ("meter_id", "read_date", "reading", "channel", "read_method", "notes"):
            assert mapping[target] is not None, f"{target} did not map from the sheet's own header"
        assert mapping["row_key"] == "row_key"
        assert len(rows) == 4
        assert [r.errors for r in rows] == [[], [], [], []]
        assert [r.channel for r in rows] == ["total", "tou_on", "tou_mid", "tou_off"]
        assert [r.row_key for r in rows] == [
            "CY-001|total|M-7451",
            "CY-001|tou_on|M-7451",
            "CY-001|tou_mid|M-7451",
            "CY-001|tou_off|M-7451",
        ]
        assert rows[0].read_method == "walk_by"
        # The CONTEXT columns are ignored on upload — they are there so the
        # clerk can tell it is the right meter, and nothing more.
        for column in ("premise", "unit_of_measure", "previous_reading", "previous_read_date"):
            assert column in headers
            assert column not in [m for m in mapping.values() if m]


def test_cr054__the_channel_labels_are_the_screens_own_words(brazos):
    """The words are the locale catalogue's — `metering.reads.channel.*` in
    `07-frontend/src/i18n/locales/en.json` — and this test is what keeps the
    server copy from drifting away from them.

    Two spellings of one vocabulary is how a sheet starts printing a word no
    screen shows, which is the defect this whole CR was raised about.

    RED FIRST — `CHANNEL_TOTAL` transcribed as `"Total"` rather than the
    catalogue's `"Total register"`, run 2026-08-30, verbatim:

        tests/test_cr054_w1_reading_sheet.py:487: in test_cr054__the_channel_
        labels_are_the_screens_own_words
        E   AssertionError: read_import.CHANNEL_LABELS has drifted from
        E   metering.reads.channel.* in en.json
        E   assert {'total': 'To...ff-peak', ...} == {'total': 'To...ff-peak', ...}
        E     Omitting 6 identical items, use -vv to show
        E     Differing items:
        E     {'total': 'Total'} != {'total': 'Total register'}
        1 failed, 32 deselected

    One word out of seven, and it is named. That is the whole job of this test:
    the other six being right is exactly why drift is easy to miss by eye.
    """
    import json
    from pathlib import Path

    catalogue = Path(__file__).resolve().parents[2] / "07-frontend/src/i18n/locales/en.json"
    # The catalogue is FLAT — one dotted key per string, not a nested tree.
    words = json.loads(catalogue.read_text(encoding="utf-8"))
    from_screens = {
        channel: words[f"metering.reads.channel.{channel}"]
        for channel in models.CHANNELS
        if f"metering.reads.channel.{channel}" in words
    }

    assert (
        read_import.CHANNEL_LABELS == from_screens
    ), "read_import.CHANNEL_LABELS has drifted from metering.reads.channel.* in en.json"
    # Every channel the model can hold has a word — a register with no word
    # would print its code and re-teach `tou_on` to the next clerk.
    assert set(read_import.CHANNEL_LABELS) == set(models.CHANNELS)


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("On-peak", "tou_on"),
        ("on-peak", "tou_on"),
        ("Mid-peak", "tou_mid"),
        ("Off-peak", "tou_off"),
        ("Total register", "total"),
        ("Demand", "demand"),
        ("Export", "export"),
        ("Generation", "generation"),
        # the CODES never stop working — a hand-built file is still lawful
        ("tou_on", "tou_on"),
        ("total", "total"),
    ],
)
def test_cr054__a_screen_word_parses_back_to_its_channel_code(written, expected):
    """A label the WRITER knows and the PARSER does not is a file that cannot be
    re-uploaded. Both directions live in one module for exactly that reason.

    This is NOT the snapping BR-MET-032 forbids: only the seven words the
    screens already show are translated, and an unknown value still errors
    verbatim (the test below).
    """
    parsed = read_import.parse_row(
        1,
        {"meter_id": "M-1", "read_date": "2026-08-03", "reading": "10", "channel": written},
        {t: t for t in read_import.TEMPLATE_COLUMNS},
    )
    assert parsed.errors == []
    assert parsed.channel == expected


def test_cr054__an_unknown_register_word_is_still_refused_verbatim():
    """BR-MET-032 validate-then-accept: an unknown channel is a parse error,
    never snapped to the nearest valid one (US-MET-017/TC-7). Adding the seven
    screen words must not have opened a fuzzy door."""
    parsed = read_import.parse_row(
        1,
        {"meter_id": "M-1", "read_date": "2026-08-03", "reading": "10", "channel": "peak-ish"},
        {t: t for t in read_import.TEMPLATE_COLUMNS},
    )
    assert parsed.channel == "peak-ish"  # kept VERBATIM
    assert [e["code"] for e in parsed.errors] == [read_import.ERR_CHANNEL_UNKNOWN]


# ═══════════════════════════════════════════════════════════════════════════
# 4 · TASK 7 — THE ROW KEY ROUND TRIP
# ═══════════════════════════════════════════════════════════════════════════


def test_cr054_t7__the_key_grammar_round_trips_a_meter_number_containing_the_separator():
    """`build_row_key` / `parse_row_key` are one grammar in one module, and the
    meter number is the LAST segment so a `split(maxsplit=2)` returns it whole
    however it is spelled. A key that cannot be read back is a key that reports
    a false mismatch on a meter nobody touched."""
    key = read_import.build_row_key("CY-001", "tou_on", "M-40|21")
    assert read_import.parse_row_key(key) == ("CY-001", "tou_on", "M-40|21")
    assert read_import.parse_row_key("nonsense") is None
    assert read_import.parse_row_key("") is None
    assert read_import.parse_row_key(None) is None


def test_cr054_t7__a_swapped_meter_is_a_named_warning_never_a_silent_import():
    """The rule is PURE — it judges and nothing else, exactly as
    `_cycle_membership_outcome` (BR-MET-122, CR-038 W2) does; the service layer
    resolves the key and the meter onto the context.

    A swapped meter is legitimate and common — a meter replacement — so this is
    a WARNING with BOTH values named, never a hard refusal and never a silent
    import.

    RED FIRST (verbatim, before RULE_ROW_KEY existed):

        E   AttributeError: module 'apps.metering.validation' has no attribute
            '_row_key_outcome'
    """
    outcome = validation._row_key_outcome(
        validation.ReadContext(
            row_no=412, meter_no="M-4099", row_key="CY-001|total|M-4021", channel="total"
        )
    )
    assert outcome is not None
    assert outcome.severity == validation.WARNING
    assert outcome.rule == validation.RULE_ROW_KEY
    assert outcome.detail["keyed_meter"] == "M-4021"
    assert outcome.detail["meter"] == "M-4099"
    assert outcome.detail["summary"] == ("row 412 was M-4021, now M-4099 — was the meter replaced?")
    # BR-MET-015's disposition discipline, the same vocabulary BR-MET-122 uses.
    assert outcome.detail["resolutions"] == ["accept_with_flag", "fix_meter_id", "reject"]


def test_cr054_t7__a_matching_key_is_ok_and_an_unkeyed_row_is_not_judged():
    """Three postures, each stated rather than defaulted: a key that matches is
    OK, a row with NO key is `not_evaluated` (a hand-built file has no key to
    judge — the same posture BR-MET-122 takes for an untagged batch), and a key
    this grammar cannot read is `not_evaluated` with the value named, never a
    manufactured warning."""
    ok = validation._row_key_outcome(
        validation.ReadContext(row_no=7, meter_no="M-4021", row_key="CY-001|total|M-4021")
    )
    assert ok.severity == validation.OK and ok.detail["keyed_meter"] == "M-4021"

    assert validation._row_key_outcome(validation.ReadContext(row_no=7, meter_no="M-4021")) is None

    unreadable = validation._row_key_outcome(
        validation.ReadContext(row_no=7, meter_no="M-4021", row_key="garbage")
    )
    assert unreadable.severity == validation.NOT_EVALUATED
    assert unreadable.detail["reason"] == validation.REASON_ROW_KEY_UNREADABLE
    assert unreadable.detail["row_key"] == "garbage"


def test_cr054_t7__the_swapped_meter_warning_reaches_the_staged_row(brazos, dana):
    """End to end: the key survives the file, the staged row and the engine.

    RED FIRST — `row_key=parsed.row_key` deleted from the staging write in
    `services.stage_read_batch`, so the column exists and nothing fills it,
    run 2026-08-30, verbatim:

        tests/test_cr054_w1_reading_sheet.py:629: in test_cr054_t7__the_swapped_
        meter_warning_reaches_the_staged_row
        E   AssertionError: assert None == 'CY-001|total|M-4021'
        E    +  where None = <ReadImportRow: ReadImportRow object
        E       (01a05478-1015-74c8-998a-e595bcef676f)>.row_key
        1 failed, 32 deselected

    ⚠ That sabotage is the one worth keeping in mind, because it is the shape
    this feature fails in for real: nothing errors, the batch stages, the rule
    runs, and it reports NOTHING — a key that never arrives is indistinguishable
    from a file that never carried one. The rule's silence on an unkeyed row is
    correct and it is also what makes the wiring invisible when it breaks.
    """
    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos)
        plan = plan_with_version(brazos, name="Residential Flat", model="flat")
        routed_planned_meter(dana, brazos, cycle, plan, asset_no="M-4021")
        routed_planned_meter(dana, brazos, cycle, plan, asset_no="M-4099")

        header = "row_key,meter_id,read_date,reading,channel\n"
        body = header + "CY-001|total|M-4021,M-4099,2026-08-03,1200,total\n"
        batch = stage(dana, body, cycle_id=str(cycle.id))
        services.validate_read_batch(dana, batch["id"])

        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
        assert row.row_key == "CY-001|total|M-4021"
        outcome = next(o for o in row.rule_outcomes if o["rule"] == validation.RULE_ROW_KEY)
        assert outcome["severity"] == validation.WARNING
        assert outcome["detail"]["summary"] == (
            "row 1 was M-4021, now M-4099 — was the meter replaced?"
        )
        # A warning, so the row is not refused — BR-MET-129: warnings post.
        assert row.severity == validation.WARNING


# ═══════════════════════════════════════════════════════════════════════════
# 5 · THE TWO DISCIPLINES THIS CANNOT BREAK
# ═══════════════════════════════════════════════════════════════════════════


def test_cr054__the_sheet_is_bounded_queries_not_one_per_meter(
    brazos, dana, django_assert_max_num_queries
):
    """DEF-324's discipline: one bounded query per FACT, never one per meter.
    A cycle here is up to a few thousand meters, so a per-meter previous-read
    lookup is a few thousand round trips behind one download button.

    Six meters cost the same number of queries as one, and this test is what
    keeps it that way — the ceiling does not move with the meter count.
    """
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos)
        plan = plan_with_version(brazos, name="Residential Flat", model="flat")
        for index in range(6):
            _unit, asset = routed_planned_meter(
                dana, brazos, cycle, plan, asset_no=f"M-60{index:02d}"
            )
            commit_read(dana, asset["id"], day="2026-07-04", value=f"{1000 + index}", unit="kWh")

        with django_assert_max_num_queries(12):
            sheet = reading_sheet.build_reading_sheet(cycle, period_anchor=AUGUST)
        assert len(sheet.rows) == 6


def test_cr054__another_tenants_cycle_is_never_reachable(brazos, dana, lonestar, erin):
    """CLAUDE.md hard rule 1. Every query in the builder is tenant-scoped by the
    selectors it calls; this proves the whole path, not one of them."""
    from apps.metering import reading_sheet
    from core import errors
    from apps.metering import selectors

    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos)
        plan = plan_with_version(brazos, name="Residential Flat", model="flat")
        routed_planned_meter(dana, brazos, cycle, plan, asset_no="M-7009")
        brazos_cycle_id = str(cycle.id)

    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            selectors.cycle_row(brazos_cycle_id)

    with tenant_ctx(brazos):
        sheet = reading_sheet.build_reading_sheet(
            selectors.cycle_row(brazos_cycle_id), period_anchor=AUGUST
        )
        assert [row["meter_id"] for row in sheet.rows] == ["M-7009"]


def test_cr054__the_summary_counts_what_the_download_button_promises(brazos, dana):
    """Task 6's button reads *"↓ Reading sheet for CY-001 · 1,180 rows"*, and a
    button that has to download the file to learn its own number is a button
    that downloads the file twice. The summary is the same builder, counted."""
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos)
        tou = plan_with_version(
            brazos,
            name="TOU Residential",
            model="time_of_use",
            windows=("tou_on", "tou_mid", "tou_off"),
        )
        routed_planned_meter(dana, brazos, cycle, tou, asset_no="M-7451")
        routed_planned_meter(dana, brazos, cycle, None, asset_no="M-9001")

        summary = reading_sheet.reading_sheet_summary(
            reading_sheet.build_reading_sheet(cycle, period_anchor=AUGUST)
        )
        assert summary["cycle_code"] == "CY-001"
        assert summary["rows"] == 5  # four TOU registers + the one unresolved meter
        assert summary["meters"] == 2
        assert summary["unresolved_meters"] == 1
        assert summary["period_start"] == "2026-08-01"
        assert summary["period_end"] == "2026-08-05"
        assert summary["registers"] == {
            "total": 1,
            "tou_on": 1,
            "tou_mid": 1,
            "tou_off": 1,
            "": 1,
        }


def test_cr054__a_cycle_with_no_schedule_states_the_absence_rather_than_guessing(brazos, dana):
    """`window_for_period` answers None when the cycle has not been given both
    schedule facts (B17 §2). There is then no window to expect reads in, and a
    sheet built on a guessed window would pre-fill a read date out of thin air —
    `BR-MET-020` forbids inventing the number.

    So the sheet is EMPTY and says why, in the same word
    `completeness.cycle_coverage` and `chase_list` already answer with for the
    identical situation. One word, three surfaces — a screen groups on it rather
    than pattern-matching three spellings of one fact.
    """
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos, code="CY-777", start_day=None, days_to_complete=None)
        sheet = reading_sheet.build_reading_sheet(cycle, period_anchor=AUGUST)
        assert sheet.window_absent_reason == "cycle_schedule_not_set"
        assert (sheet.period_start, sheet.period_end, sheet.rows) == (None, None, [])
        summary = reading_sheet.reading_sheet_summary(sheet)
        assert summary["window_absent_reason"] == "cycle_schedule_not_set"
        assert summary["rows"] == 0


def test_cr054__a_register_already_read_this_window_says_so(brazos, dana):
    """The sheet lists every EXPECTED register, collected or not — the PO asked
    for *"all meters and existing data that is availale"*, and a clerk who has
    already walked half the route needs to see which half.

    So the row stays and the `issue` column names the date it was read. Silently
    dropping it would make the sheet disagree with the completeness bar, which
    counts the same register as collected.
    """
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos)
        plan = plan_with_version(brazos, name="Residential Flat", model="flat")
        _unit, asset = routed_planned_meter(dana, brazos, cycle, plan, asset_no="M-7004")
        commit_read(dana, asset["id"], day="2026-08-03", value="900", unit="kWh")

        sheet = reading_sheet.build_reading_sheet(cycle, period_anchor=AUGUST)
        row = rows_for(sheet, "M-7004")[0]
        assert "already read 2026-08-03" in row["issue"], row["issue"]
        assert row["previous_reading"] == "900"


def test_cr054__an_estimated_head_shows_no_register_value_and_says_why(brazos, dana):
    """BR-MET-028: an estimate carries a consumption and **no `current_value`** —
    nobody read the dial. So the previous-reading cell is the dash (rule 3 and
    BR-MET-106 again) and the `issue` column says the last reading was an
    estimate, which is exactly the row a clerk should check on the ground."""
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos)
        plan = plan_with_version(brazos, name="Residential Flat", model="flat")
        _unit, asset = routed_planned_meter(dana, brazos, cycle, plan, asset_no="M-7005")
        commit_read(
            dana,
            asset["id"],
            day="2026-07-04",
            value="0",
            consumption="612",
            unit="kWh",
            estimated=True,
        )

        sheet = reading_sheet.build_reading_sheet(cycle, period_anchor=AUGUST)
        row = rows_for(sheet, "M-7005")[0]
        assert row["previous_reading"] == reading_sheet.DASH
        assert "estimate" in row["issue"]


def test_cr054__a_register_with_no_declared_unit_refuses_to_print_a_bare_quantity(brazos, dana):
    """CLAUDE.md hard rule 3 has no assume branch. `register_units.register_unit`
    returns None for a demand register on a meter whose energy unit declares no
    demand unit, and a bare number in a column headed *previous reading* would be
    read as the tenant's own unit by whoever is looking at it.

    The row still appears — the register IS expected — with the blocker named.
    """
    from apps.metering import reading_sheet
    from apps.assets import models as asset_models

    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos)
        plan = plan_with_version(brazos, name="Industrial Demand", model="demand", demand=True)
        _unit, asset = routed_planned_meter(dana, brazos, cycle, plan, asset_no="M-8012")
        # A tenant metering in a unit this repo has never been told about: the
        # demand unit is UNDECLARED, which `register_unit` answers with None.
        asset_models.Asset.objects.filter(pk=asset["id"]).update(unit="kVAh")
        commit_read(dana, asset["id"], day="2026-07-04", value="412", channel="demand", unit="kVA")

        sheet = reading_sheet.build_reading_sheet(cycle, period_anchor=AUGUST)
        demand_row = next(r for r in rows_for(sheet, "M-8012") if r["channel"] == "Demand")
        assert demand_row["unit_of_measure"] == ""
        assert demand_row["previous_reading"] == reading_sheet.DASH
        assert "no unit of measure" in demand_row["issue"]


def test_cr054__the_published_blank_template_still_parses_itself(brazos):
    """BR-MET-032's own invariant, re-asserted because this lane changed
    `TEMPLATE_COLUMNS`: the file we hand out is the file we parse best. Adding
    `row_key` must not have shifted a worked row's cells sideways — which is
    the exact merge accident `template_csv`'s own comment records from the week
    W3 and W4 both appended a column."""
    header, *examples = read_import.template_csv().splitlines()
    assert header.split(",") == list(read_import.PUBLISHED_HEADERS)
    for example in examples:
        assert len(example.split(",")) == len(read_import.PUBLISHED_HEADERS)
    mapping, _headers, rows = read_import.parse_csv(read_import.template_csv().encode("utf-8"))
    assert read_import.missing_required(mapping) == []
    assert [r.errors for r in rows] == [[], []]
    assert [r.channel for r in rows] == ["total", "demand"]


def test_cr054__the_sheet_never_leaves_a_quantity_without_its_unit(brazos, dana):
    """CLAUDE.md hard rule 3, asserted over the WHOLE sheet rather than one row:
    no row may carry a previous reading and no unit of measure. The pair travels
    together or the quantity is not printed at all."""
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        seed_config()
        cycle = seed_cycle(brazos)
        tou = plan_with_version(
            brazos,
            name="TOU Residential",
            model="time_of_use",
            windows=("tou_on", "tou_mid", "tou_off"),
        )
        demand = plan_with_version(brazos, name="Industrial Demand", model="demand", demand=True)
        _u1, a1 = routed_planned_meter(dana, brazos, cycle, tou, asset_no="M-7451")
        _u2, a2 = routed_planned_meter(dana, brazos, cycle, demand, asset_no="M-8010")
        routed_planned_meter(dana, brazos, cycle, None, asset_no="M-9001")
        commit_read(dana, a1["id"], day="2026-07-04", value="42864", unit="kWh")
        commit_read(dana, a2["id"], day="2026-07-04", value="412", channel="demand", unit="kW")

        sheet = reading_sheet.build_reading_sheet(cycle, period_anchor=AUGUST)
        for row in sheet.rows:
            if row["previous_reading"] != reading_sheet.DASH:
                assert row["unit_of_measure"] != "", (
                    f"hard rule 3: {row['meter_id']} / {row['channel']!r} prints a "
                    "quantity with no unit"
                )
