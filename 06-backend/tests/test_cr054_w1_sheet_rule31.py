# ── Trace ──────────────────────────────────────────────
# Change:   CR-054 W1 tasks 4/5/7 — the pre-filled reading sheet
#           (12-governance/11-change-requests.md, PO 2026-08-30).
# Rules:    B14 rule 31 (RATIFIED 2026-08-30 — *"no Databse ID on screen - that
#           is a rule"*; the fuller 2026-08-19 wording governs: nothing
#           internal is ever visible to a utility user) · BR-MET-032 (ONE
#           published template and ONE parser) · BR-MET-059 (the channel model)
# Screens:  RDS-03 / S28 stage 2 — the file the button downloads
# ───────────────────────────────────────────────────────
"""**IS THE READING SHEET A SCREEN, AND DOES RULE 31 REACH IT?**

**Yes to both, and this file is the check that settles it.** A clerk opens
`reading_sheet_CY-002_2026-08.csv` in Excel and reads it exactly as they read a
page of the product — so a primary key in one of its cells is the same defect as
a primary key in a table cell, and rule 31's own scope sentence names *"a
primary or foreign key"* first.

**WHY IT NEEDED ITS OWN FILE.** `G28` is rule 31's gate and it has three parts,
all of which read STRINGS: the eleven catalogues, backend strings served
verbatim, and `raise` sites. **A uuid-shaped VALUE is the one thing it cannot
see**, because a value is not a string in a catalogue — it is whatever the
database happened to put there. `DEF-2716` built that half for the bill surface
on 2026-08-31 by reading rendered cells in Chromium and refusing a uuid in any
of them (7 leaked cells before, 0 after). This is the same check for the one
surface of this CR that a person reads, and it is done here rather than in the
browser because the sheet is generated server-side and the browser only saves
it.

── THE KEY COLUMN, AND THE DECISION THIS FILE PINS ─────────────────────────
`row_key` is the one column that exists to be read by a MACHINE — it round-trips
so that a row whose meter no longer matches it is caught by name (task 7). So it
is exactly the column where an id would be convenient, and it carries none:

    CY-002|tou_on|M-7450

Three segments, and each is checked below:

  * **`CY-002` is the cycle's issued CODE**, the value the stage-1 picker shows,
    never `cycles.id`;
  * **`M-7450` is the meter's issued ASSET NUMBER**, the number stamped on the
    meter itself, never `assets.id`;
  * **`tou_on` is the register's enum token** — internal, and the ONE internal
    thing on the sheet. Rule 31's own escape is what makes it lawful: *"where
    the reference is genuinely what a user needs … it has a HUMAN-FACING number
    and that is what is shown"*, and the human-facing word **is** shown, in the
    `channel` cell immediately beside it, reading `On-peak`.

**AND THE ALTERNATIVE IS WORSE, WHICH IS THE REAL ARGUMENT.** Putting `On-peak`
in the key instead would make the key LOCALISED — `channel_label` is transcribed
from the locale catalogue, and eleven catalogues means eleven spellings. A key
whose text changes with a copy edit or with the clerk's language cannot survive
a round trip, and a key that cannot round-trip reports a false *"was the meter
replaced?"* against a meter nobody touched. The code's own comment says this in
one line — *"the key is machine identity and must survive a copy change"* — and
this file is that sentence made falsifiable.
"""

import re
from datetime import date

import pytest

from apps.metering import models, read_import, services  # noqa: F401

from tests.test_us_met_018_plan_registers import (  # noqa: F401
    plan_with_version,
)
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    commit_read,
    seed_config,
    tenant_ctx,
)
from tests.test_us_met_helpers import (  # noqa: F401
    make_premises,
    make_unit,
)

pytestmark = pytest.mark.django_db

AUGUST = date(2026, 8, 1)

#: Both shapes a uuid reaches a cell in. The hyphenated form is what `str(uuid)`
#: produces and what DRF serialises; the bare 32-hex form is what `.hex` and a
#: hand-built cache key produce, and it is the one a reader skims past.
#: ⚠ `[0-9a-f]{32}` also matches a sha-256 PREFIX, which is deliberate — a file
#: hash has no business in a cell a clerk types into either.
UUID_ANY = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|\b[0-9a-fA-F]{32}\b")


def seed_cycle(tenant, code="CY-001", **overrides):
    fields = dict(
        frequency="Monthly", start_day=1, days_to_complete=5, bill_day=31, status="active"
    )
    fields.update(overrides)
    return models.Cycle.objects.create(tenant=tenant, code=code, **fields)


def routed_planned_meter(actor, tenant, cycle, plan, *, asset_no, service="electric", uom="kWh"):
    """The same fixture `test_cr054_w1_reading_sheet.py` uses — a meter that is
    BOTH in the cycle and on a unit holding `plan`, which is the pair the sheet
    joins. Copied rather than imported because importing that module drags in
    its whole 880-line collection for two helpers."""
    premises = make_premises(
        actor, address_line=f"1408 Bluestem Ln {asset_no}", services_available=[service]
    )
    unit = make_unit(actor, premises["id"], label=f"Unit {asset_no}", services=[service])
    if plan is not None:
        services.assign_unit_plan(
            actor,
            unit["id"],
            {"tariff_id": str(plan.id), "effective_from": "2026-06-01", "reason": "fixture"},
        )
    asset = a_meter(actor, asset_no, unit_id=unit["id"], service=service, uom=uom)
    services.create_route(
        actor,
        {"code": f"R-{asset_no}", "cycle_id": str(cycle.id), "premises_ids": [str(premises["id"])]},
    )
    return unit, asset


def _sheet(brazos, dana):
    """A sheet with all three interesting shapes on it: a time-of-use meter
    (four registers), a demand meter (two, in two different units) and a meter
    with NO PLAN — whose row carries the `issue` text, which is the cell most
    likely to leak an internal value because it is the only free prose on the
    sheet."""
    from apps.metering import reading_sheet

    seed_config()
    cycle = seed_cycle(brazos, code="CY-002")
    tou = plan_with_version(
        brazos, name="TOU Residential", model="time_of_use", windows=("tou_on", "tou_mid", "tou_off")
    )
    demand = plan_with_version(brazos, name="Industrial Demand", model="demand", demand=True)
    _u1, a1 = routed_planned_meter(dana, brazos, cycle, tou, asset_no="M-7450")
    _u2, a2 = routed_planned_meter(dana, brazos, cycle, demand, asset_no="M-7210")
    routed_planned_meter(dana, brazos, cycle, None, asset_no="M-9001")
    commit_read(dana, a1["id"], day="2026-07-04", value="42864", unit="kWh")
    commit_read(dana, a2["id"], day="2026-07-04", value="412", channel="demand", unit="kW")
    return cycle, reading_sheet.build_reading_sheet(cycle, period_anchor=AUGUST)


def test_cr054_rule31__no_cell_of_the_sheet_carries_an_internal_id(brazos, dana):
    """**B14 rule 31 over EVERY cell of EVERY row**, not one column.

    ⚠ **GREATER THAN ZERO AS WELL AS CLEAN.** A sheet that failed to build has
    no rows, and *no rows* satisfies *no uuid in any row* perfectly — the
    "check that cannot fail" this CR found seven of in one day. So the row count
    and the register spread are asserted first, and only then their contents.

    RED FIRST (verbatim, with `_row` amended to write `str(meter.id)` into the
    `row_key`'s meter segment instead of `meter.asset_no` — a one-word change,
    and the one a lane makes when a meter number is null):

        E   AssertionError: B14 rule 31: row 1 column 'row_key' shows an
            internal id — 'CY-002|total|01a05825-c138-7fbf-9d8c-554e183022a2'
        E   assert None
    """
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        _cycle, sheet = _sheet(brazos, dana)

        # 4 (time-of-use) + 2 (demand) + 1 (no plan, listed with its reason) = 7
        assert len(sheet.rows) == 7, [r["row_key"] for r in sheet.rows]
        assert len({r["meter_id"] for r in sheet.rows}) == 3
        assert len(sheet.unresolved) == 1

        for n, row in enumerate(sheet.rows, start=1):
            for column in reading_sheet.SHEET_HEADERS:
                hit = UUID_ANY.search(str(row[column]))
                assert hit is None, (
                    f"B14 rule 31: row {n} column {column!r} shows an internal "
                    f"id — {row[column]!r}"
                )

        # …and over the FILE, which is what a person actually opens: a leak in
        # the header line or in a quoted cell would slip past the loop above.
        body = reading_sheet.reading_sheet_csv(sheet)
        assert body.count("\n") == 8  # header + 7 rows
        assert UUID_ANY.search(body) is None, UUID_ANY.search(body).group(0)  # type: ignore[union-attr]

        # The FILENAME is read out loud in a folder listing and in a download
        # toast, so it is a visible value too.
        assert UUID_ANY.search(reading_sheet.reading_sheet_filename(sheet)) is None


def test_cr054_rule31__the_key_is_issued_identifiers_and_never_primary_keys(brazos, dana):
    """The key column's THREE SEGMENTS, checked against the columns they claim
    to name — the positive half of the test above, which can only prove absence.

    RED FIRST (verbatim, with `build_row_key` called with `cycle.id` instead of
    `cycle.code`, which is the substitution a lane makes when the cycle is
    passed as an id):

        E   AssertionError: rule 31: the key's cycle segment must be the
            cycle's issued CODE, not its primary key — got
            '01a05824-8e1b-7f21-9d2e-6f1c7c9a4d33'
    """
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        cycle, sheet = _sheet(brazos, dana)
        assert len(sheet.rows) == 7

        for row in sheet.rows:
            parsed = read_import.parse_row_key(row["row_key"])
            assert parsed is not None, row["row_key"]
            keyed_cycle, keyed_channel, keyed_meter = parsed

            assert keyed_cycle == cycle.code, (
                "rule 31: the key's cycle segment must be the cycle's issued "
                f"CODE, not its primary key — got {keyed_cycle!r}"
            )
            assert keyed_cycle != str(cycle.id)
            assert keyed_meter == row["meter_id"], (
                "rule 31: the key's meter segment must be the meter's issued "
                f"asset number — got {keyed_meter!r}"
            )
            # ⚠ THE ESCAPE CLAUSE, EXERCISED AS A PAIR. The register segment is
            # the internal token AND the human word is on the same row. Neither
            # half alone is lawful: the token without the word is rule 31's
            # breach, and the word inside the key is a localised key that cannot
            # round-trip.
            assert row["channel"] == read_import.channel_label(keyed_channel or None)
            if keyed_channel:
                assert keyed_channel in models.CHANNELS
                assert row["channel"] != keyed_channel or keyed_channel not in (
                    read_import.CHANNEL_LABELS
                )


def test_cr054_rule31__the_registers_word_is_the_screens_word_and_the_key_is_not(brazos, dana):
    """The PO's own complaint, made falsifiable: *"how to spell `tou_on`, which
    appears on no screen"* — every screen says **On-peak**.

    So the sheet's `channel` COLUMN must never print `tou_on`, and the key must
    never print `On-peak`. One assertion each way, because a lane fixing either
    direction alone breaks the other.

    RED FIRST (verbatim, with `_row` writing `channel` instead of
    `read_import.channel_label(channel)` — the sheet as it would read if the
    CHANNEL_LABELS map had never been written):

        E   AssertionError: the sheet prints a register word no screen shows —
            {'tou_mid', 'tou_off', 'tou_on', 'total', 'demand'}
    """
    from apps.metering import reading_sheet

    with tenant_ctx(brazos):
        _cycle, sheet = _sheet(brazos, dana)
        words = {row["channel"] for row in sheet.rows if row["channel"] != ""}
        assert len(words) >= 5, words
        assert words <= set(read_import.CHANNEL_LABELS.values()), (
            f"the sheet prints a register word no screen shows — {words}"
        )
        assert "On-peak" in words and "Demand" in words

        keys = " ".join(row["row_key"] for row in sheet.rows)
        for label in read_import.CHANNEL_LABELS.values():
            assert label not in keys, (
                f"the key carries the localised word {label!r}; a key that "
                "changes with a copy edit cannot round-trip"
            )
        assert "tou_on" in keys and "demand" in keys


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-054 W1 tasks 4/5/7 (12-governance/11-change-requests.md) + B14
#         rule 31 (04-docs/02-decisions/14-ui-conventions.md, RATIFIED
#         2026-08-30) + DEF-2716's rendered-value precedent
# generated: 2026-08-31 by the CR-054 W1 record-and-task-9 lane
# checklist: A✔ B=n/a(test file) C✔(three guards, each proved RED first with
#   the failure quoted in its docstring) D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E3 the fixture helpers are COPIED from `test_cr054_w1_reading_sheet.py`
#      rather than imported: importing that module collects its 33 cases into
#      every run of this one, and two helpers is a cheaper duplicate than a
#      four-minute test run. If a third file needs them they move to
#      `test_us_met_reads_helpers.py`, which is where they belong.
# ──────────────────────────────────────────────────────────
