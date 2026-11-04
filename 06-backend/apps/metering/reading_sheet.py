# ── Trace ──────────────────────────────────────────────
# Change:   CR-054 W1 tasks 4 and 5 — *"the reads upload: hand the clerk the
#           file instead of asking them to build it"*.   Screens: RDS-03 stage 2
# Rules:    BR-MET-049 (plan-driven read-set completeness — the unit's plan
#           determines the required read set per meter; TOU → per-window
#           records, demand → +demand record) · BR-MET-059 (the channel model;
#           an absent channel cell ⇒ the flat meter's one `total` register) ·
#           BR-MET-057 (the cycle read window drives expectations) ·
#           BR-MET-052 (a retired meter expects no read) · BR-AST-029 (a net
#           meter's cycle is consumption + export) · BR-MET-016/053 (committed
#           LINEAGE HEADS only) · BR-MET-106 (an unread month is ABSENT, never
#           a zero) · BR-MET-028 (an estimate carries consumption and NO
#           register value) · BR-MET-143 (a register's unit — kWh on the energy
#           register, kW on demand) · BR-MET-144 (a quantity DISPLAYS at most
#           two decimals, trailing zeros trimmed) · BR-MET-032 (ONE published
#           template and ONE parser — this file must re-upload through the
#           importer that already exists) · BR-MET-014 (batch tags inherit to
#           rows unless a row overrides) · BR-MET-020 (no threshold is invented
#           here) · CLAUDE.md hard rule 1 (tenant scoping) · hard rule 3 (a
#           quantity never travels without an explicit unit)
# Golden:   none. This file states no money, no rate and no rounding of money;
#           every figure on it is a QUANTITY. ❄️ B4/B5 untouched.
# Tests:    06-backend/tests/test_cr054_w1_reading_sheet.py
# Impacts:  apps/metering/read_import.py (the `row_key` column, the channel
#           LABELS, the key grammar) · apps/metering/selectors.py
#           (register_heads_for_assets) · apps/metering/api.py (the two cycle
#           routes) · 07-frontend RDS-03 stage 2 (CR-054 task 6, another lane)
# ───────────────────────────────────────────────────────
"""**CR-054 W1 — THE PRE-FILLED READING SHEET.** One row per expected meter per
required register, for one cycle and one reading month.

WHAT THIS REPLACES, AND WHY IT IS NOT A NICER TEMPLATE
=======================================================
Today a clerk downloads `reads_template.csv` and gets eight columns and two
worked rows. To turn that into a file they must work out **six things the
product never tells them**, every one of which the system already knows:

  1. which meters are in the cycle;
  2. which of them need more than one row;
  3. that a time-of-use tariff needs FOUR rows;
  4. how to spell `tou_on` — **a word that appears on no screen in the
     product**, because every screen says *On-peak*;
  5. that a peak is measured in kW and not kWh;
  6. which service each meter is on.

The PO's ruling, verbatim (2026-08-30, CR-054): *"on step 1 we have given cycle
and details - on step 2 we have ready csv file - with all meters and existing
data that is availale - only details clark has to fill is readings and correct
any data they want and upload the file - so instead of they figuring out what to
do we have hande dthem all details"*.

So the fix is not to teach the register model — CR-054 rejects that explicitly —
it is to **stop asking**. Every one of those six answers is computed here and
written into the file.

THE THREE COLUMN GROUPS, AND THE THREE DIFFERENT RULES
=======================================================
This grouping IS the design (CR-054 task 5), and each group has its own
contract. A column that changes group changes what a clerk is allowed to do
with it, so the group is stated here rather than left to be inferred from the
order.

**IDENTITY** — `row_key` · `meter_id` · `channel`.
    Says WHICH READING the row is. `row_key` is stamped by us and comes back
    unchanged so a swapped meter is caught by name (task 7,
    `validation._row_key_outcome`). `channel` prints the word the SCREENS use,
    and `read_import.CHANNEL_LABEL_ALIASES` reads it back — see that module for
    why the map lives there and not here.

**CONTEXT** — `premise` · `unit_of_measure` · `previous_reading` ·
`previous_read_date` · `issue`.
    **Ignored on upload.** Not one of these headers is an alias of any
    `TEMPLATE_COLUMNS` target, so `detect_mapping` never picks them up and
    `parse_row` never reads them. They are there so the clerk can tell it is the
    right meter — and, in `issue`, so that anything the sheet could not resolve
    is STATED on the row rather than left as a silence.

**THEIRS** — `reading` · `read_date` · `read_method` · `demand_reset` · `notes`.
    Pre-filled where the system holds a fact, and correctable everywhere. Two
    of them are deliberately EMPTY, and the emptiness is the honest pre-fill:

      * `reading`, because it is the one fact only the clerk holds — the whole
        point of the sheet;
      * `demand_reset`, because `read_import` already argues the case in its
        own words: *"`false` is a claim ('the register was not zeroed'), and a
        demand customer whose reset went unnoticed is billed against a peak
        that belongs to the previous cycle"*. Pre-filling `no` would
        manufacture exactly that claim on every demand row in the cycle.

THE JUDGMENTS THIS FILE MAKES, STATED RATHER THAN BURIED
=========================================================
All four are recorded in `12-governance/02-decision-log.md` (2026-08-30, CR-054
W1) with their reasoning. In short:

  * **The read date is pre-filled with the cycle's window START** in the named
    month — `schedule.derive_read_window`'s own worked figure for start day 1
    and 5 days to complete is *1 Aug 2026 … 5 Aug 2026*. It is inside the window
    by construction, so a row the clerk does not correct never manufactures an
    `out_of_window` warning about a date the product itself supplied. A route
    walked over five days is corrected per row, which is what "correctable"
    means.
  * **`read_method` is pre-filled only from an explicit argument** (the stage-1
    choice), and is otherwise LEFT BLANK. BR-MET-014 makes a row-level method an
    OVERRIDE of the batch tag; stamping one on every row would silently retire
    the batch-level choice the wizard just asked for. Blank means inherit, which
    is the rule working as signed.
  * **A meter whose register set cannot be resolved still gets a row**, with the
    reason in `issue` and an entry in `unresolved`. `completeness._meter_rows`
    drops such a meter, correctly, because it is computing a percentage. A
    reading sheet is a WORK LIST: the meter is physically in the cycle and
    somebody is going to walk to it, so dropping it is the silent pass this
    whole CR exists to remove (the DEF-075 posture).
  * **A register already read in this window is still listed**, with the date it
    was read in `issue`. Dropping it would make the sheet disagree with the
    completeness bar, which counts that register as collected.

QUERIES: BOUNDED, NEVER PER METER (DEF-324)
============================================
A cycle here is up to a few thousand meters and this is one download button.
Four bounded queries plus one rating read per DISTINCT PLAN:

  1. the cycle's meters — `completeness._expected_meters` (one query);
  2. those units' rate plans — one `values_list`;
  3. the committed heads for every register of every one of those meters —
     `selectors.register_heads_for_assets` (one query);
  4. `PlanRegisterResolver`, cached per (plan, service, date) for this one
     computation.

⚠ **`PlanRegisterResolver.for_asset` IS NOT USED, AND THAT IS DELIBERATE.** It
resolves the unit's plan itself, caching per unit — one query per UNIT, which is
right for an import batch of 500 rows standing on a handful of units and wrong
for a cycle of three thousand. `for_meter_row` is the same resolver and the same
cache fed facts already in hand, and it is what `completeness._meter_rows` uses
for exactly this reason.

NOTHING HERE IS MONEY. No rate is read, no amount is computed and no rounding
rule of B4's is touched. Every figure on the sheet is a quantity, displayed
through `quantity_display.quantity_text` (BR-MET-144) — which is DEF-894, the
defect that printed `1016.000000 · 8.000000 kgal` on all 41 stops of a route
sheet somebody carried around in the rain.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from typing import Any

from apps.metering import (
    completeness,
    models,
    quantity_display,
    read_import,
    register_units,
    selectors,
)

#: The absent fact, written the way the printed route sheet writes it
#: (`route_sheet._cell`) so one product does not use two dashes. **Never a
#: zero** — BR-MET-106: an unread month is ABSENT, and a `0` in a column headed
#: *previous reading* is the number a clerk would subtract from.
DASH = "—"

#: The sheet's columns, in the three groups the CR names. ORDER IS FREE for the
#: importer (`detect_mapping` matches by NAME and never by position), so this is
#: ordered for the human filling it in: what the row IS, then what confirms it,
#: then what they type.
SHEET_HEADERS: tuple[str, ...] = (
    # IDENTITY
    "row_key",
    "meter_id",
    "channel",
    # CONTEXT — ignored on upload
    "premise",
    "unit_of_measure",
    "previous_reading",
    "previous_read_date",
    "issue",
    # THEIRS — pre-filled and correctable
    "reading",
    "read_date",
    "read_method",
    "demand_reset",
    "notes",
)

#: The CONTEXT columns, named so a test can assert that not one of them maps to
#: an importer target. They are the group whose contract is *"ignored on
#: upload"*, and the only thing that keeps that true is that none of these words
#: is an alias in `read_import.TEMPLATE_COLUMNS`.
CONTEXT_COLUMNS: tuple[str, ...] = (
    "premise",
    "unit_of_measure",
    "previous_reading",
    "previous_read_date",
    "issue",
)


@dataclass(frozen=True)
class ReadingSheet:
    """One cycle's sheet for one reading month — rows, and what could not be
    resolved to make them.

    `unresolved` is beside `rows` and never folded into them, the same posture
    `completeness._meter_rows` takes: a sheet built while four meters have no
    resolvable register set must SAY so, or it lies by omission. Those four
    meters appear in `rows` as well, each with its reason in `issue`, because a
    clerk still has to walk to them.
    """

    cycle_id: str
    cycle_code: str
    period_start: date | None
    period_end: date | None
    rows: list[dict[str, Any]]
    unresolved: list[dict[str, Any]]
    #: ⚠ **THE CYCLE HAS NO SCHEDULE, SO THERE IS NO WINDOW TO EXPECT READS IN.**
    #: `"cycle_schedule_not_set"` — the SAME word `completeness.cycle_coverage`
    #: and `chase_list` already answer with, so a screen groups on one string
    #: rather than three spellings of one fact. `period_start` and `period_end`
    #: are then None and `rows` is empty: an empty sheet with a stated reason,
    #: never a sheet built on an invented window (BR-MET-020 — the read date
    #: every row is pre-filled from would be a number this file made up).
    window_absent_reason: str | None = None


def _premise_label(point: Any) -> str:
    """`1408 Bluestem Ln · Unit 3F` — the two labels a person recognises a stop
    by, in one cell.

    ONE cell rather than two, which departs from `apps/metering/exports.py`'s
    *"a CSV consumer needs the parts in their own columns"* — and the departure
    is the point: that precedent is about a LIST EXPORT a spreadsheet computes
    on. Nothing computes on this cell; a clerk reads it to confirm they are at
    the right door, and two half-empty columns read worse than one.
    """
    unit = getattr(point, "unit", None)
    premises = getattr(unit, "premises", None)
    parts = [
        str(getattr(premises, "address_line", "") or "").strip(),
        str(getattr(unit, "label", "") or "").strip(),
    ]
    return " · ".join(part for part in parts if part)


def _issue_text(parts: list[str]) -> str:
    return "; ".join(part for part in parts if part)


def build_reading_sheet(
    cycle: Any,
    *,
    period_anchor: date,
    read_method: str | None = None,
) -> ReadingSheet:
    """**THE SHEET.** One row per expected meter per required register.

    `cycle` is a tenant-scoped `Cycle` (callers reach it through
    `selectors.cycle_row`, which denies a foreign id as NOT FOUND — hard rule
    1). `period_anchor` is any date in the reading month; the window is derived
    in THAT month by `completeness.window_for_period`, which is the *"month
    already picked"* path `schedule.derive_read_window` documents and NOT the
    occurrence generator OQ-339 governs.

    `read_method` is the stage-1 collection method, written onto every row. Left
    None, the column is blank and BR-MET-014's batch-tag inheritance applies —
    see the module docstring for why that is the default rather than a guess.

    **A cycle with no schedule answers a STATED ABSENCE, not an exception** —
    `window_for_period` returns None and this returns an empty sheet carrying
    `window_absent_reason="cycle_schedule_not_set"`. That is the shape
    `completeness.cycle_coverage` and `chase_list` already use for the identical
    situation, and it is what lets the download button say why it is not offered
    without a failed request. Building the sheet anyway would mean inventing the
    window, and with it the read date every row is pre-filled from (BR-MET-020).
    """
    window = completeness.window_for_period(cycle, period_anchor)
    if window is None:
        return ReadingSheet(
            cycle_id=str(cycle.id),
            cycle_code=cycle.code,
            period_start=None,
            period_end=None,
            rows=[],
            unresolved=[],
            window_absent_reason="cycle_schedule_not_set",
        )
    window_start, window_end = window

    # ── the four bounded reads (DEF-324) ───────────────────────────────────
    meters = completeness._expected_meters(cycle.id, window_end)
    unit_ids = {meter.service_point.unit_id for meter in meters if meter.service_point is not None}
    plans = dict(
        models.Unit.objects.filter(tenant_id=cycle.tenant_id, id__in=unit_ids).values_list(
            "id", "rate_plan_id"
        )
    )
    heads = selectors.register_heads_for_assets([meter.id for meter in meters])
    resolver = completeness.PlanRegisterResolver()

    rows: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    method_cell = (read_method or "").strip()

    for meter in meters:
        point = meter.service_point
        expected = resolver.for_meter_row(
            unit_rate_plan_id=plans.get(getattr(point, "unit_id", None)),
            service_code=getattr(getattr(point, "service", None), "code", None),
            # The window's OPEN day is the service date the plan is resolved
            # on — the same anchor `completeness._meter_rows` uses, so the
            # sheet and the completeness bar can never expect different sets.
            service_date=window_start,
            net_metering=bool(getattr(meter, "net_metering", False)),
        )
        premise = _premise_label(point)

        if expected.channels is None:
            # STATED ABSENCE, never an empty set pretending to be an answer
            # (the DEF-075 posture). The meter still gets its row — see the
            # module docstring.
            unresolved.append(
                {
                    "meter": meter.asset_no,
                    "asset_id": str(meter.id),
                    "reason": expected.absent_reason,
                }
            )
            rows.append(
                _row(
                    cycle=cycle,
                    meter=meter,
                    channel=None,
                    premise=premise,
                    head=heads.get((str(meter.id), models.CHANNEL_TOTAL)),
                    window=window,
                    method_cell=method_cell,
                    extra_issue=(
                        f"register set unresolved ({expected.absent_reason}) — no "
                        "plan-required registers could be listed for this meter"
                    ),
                )
            )
            continue

        for channel in expected.channels:
            rows.append(
                _row(
                    cycle=cycle,
                    meter=meter,
                    channel=channel,
                    premise=premise,
                    head=heads.get((str(meter.id), channel)),
                    window=window,
                    method_cell=method_cell,
                )
            )

    return ReadingSheet(
        cycle_id=str(cycle.id),
        cycle_code=cycle.code,
        period_start=window_start,
        period_end=window_end,
        rows=rows,
        unresolved=unresolved,
    )


def _row(
    *,
    cycle: Any,
    meter: Any,
    channel: str | None,
    premise: str,
    head: dict[str, Any] | None,
    window: tuple[date, date],
    method_cell: str,
    extra_issue: str = "",
) -> dict[str, Any]:
    """One sheet row. Every cell is a string — this is a CSV, and a `None`
    reaching `csv.writer` prints as an empty cell that means nothing in
    particular.

    ⚠ **THE UNIT AND THE PREVIOUS READING STAND OR FALL TOGETHER** (CLAUDE.md
    hard rule 3). `register_units.register_unit` answers None where no unit is
    DECLARED for this register — a demand register on a meter whose energy unit
    has no declared demand unit — and a bare number in a column headed *previous
    reading* would then be read as the tenant's own unit by whoever is looking
    at it. So the quantity is withheld and the blocker is named in `issue`,
    which is `quantity_display.quantity_with_unit`'s own posture: *"A caller
    holding a quantity and no unit has a data problem"*.
    """
    window_start, window_end = window
    unit_of_measure = register_units.register_unit(meter.unit, channel) or ""

    issues: list[str] = [extra_issue] if extra_issue else []
    previous_reading = DASH
    previous_read_date = DASH

    if head is not None:
        previous_read_date = head["read_at"] or DASH
        if head["estimated"]:
            # BR-MET-028 — an estimate carries consumption and no register
            # value; nobody read the dial. The dash is the truth, and the
            # sentence is what makes it a useful row rather than a blank one.
            issues.append("last reading was an estimate — no register value on file")
        elif not unit_of_measure:
            issues.append(
                "no unit of measure is declared for this register — the reading "
                "will be refused until the meter's UoM is set (rule 3)"
            )
        else:
            previous_reading = quantity_display.quantity_text(head["current_value"]) or DASH
        read_day = head["read_at"]
        if read_day and window_start.isoformat() <= read_day <= window_end.isoformat():
            # Listed anyway — the sheet must not disagree with the completeness
            # bar about which registers this cycle expects.
            issues.append(f"already read {read_day} in this window")
    elif not unit_of_measure:
        issues.append(
            "no unit of measure is declared for this register — the reading "
            "will be refused until the meter's UoM is set (rule 3)"
        )

    return {
        # ── IDENTITY ───────────────────────────────────────────────────────
        "row_key": read_import.build_row_key(cycle.code, channel, meter.asset_no),
        "meter_id": meter.asset_no,
        "channel": read_import.channel_label(channel),
        # ── CONTEXT — ignored on upload ────────────────────────────────────
        "premise": premise,
        "unit_of_measure": unit_of_measure,
        "previous_reading": previous_reading,
        "previous_read_date": previous_read_date,
        "issue": _issue_text(issues),
        # ── THEIRS — pre-filled and correctable ────────────────────────────
        "reading": "",  # the one fact only the clerk holds
        "read_date": window_start.isoformat(),
        "read_method": method_cell,
        "demand_reset": "",  # a blank is an ABSENCE; `no` would be a CLAIM
        "notes": "",
    }


def reading_sheet_csv(sheet: ReadingSheet) -> str:
    """The file. Same writer settings as `read_import.template_csv` so the two
    files a clerk can download differ in CONTENT and in nothing else."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(SHEET_HEADERS)
    for row in sheet.rows:
        writer.writerow([row[column] for column in SHEET_HEADERS])
    return buffer.getvalue()


def reading_sheet_filename(sheet: ReadingSheet) -> str:
    """`reading_sheet_CY-001_2026-08.csv` — the cycle and the month, because a
    clerk downloads one of these per cycle per month and a folder of files all
    called `reading_sheet.csv` is a folder of one file."""
    safe_code = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in sheet.cycle_code)
    month = f"{sheet.period_start:%Y-%m}" if sheet.period_start else "no-window"
    return f"reading_sheet_{safe_code}_{month}.csv"


def reading_sheet_summary(sheet: ReadingSheet) -> dict[str, Any]:
    """What the download button needs in order to name its own number —
    CR-054 task 6's *"↓ Reading sheet for CY-001 · 1,180 rows"*.

    Computed from the SAME builder, never from a second count: a button that has
    to download the file to learn its size is a button that downloads it twice,
    and two counting paths is how a button starts promising 1,180 rows over a
    file with 1,176 (hard-won law 5).
    """
    registers: dict[str, int] = {}
    for row in sheet.rows:
        _cycle, channel, _meter = read_import.parse_row_key(row["row_key"]) or ("", "", "")
        registers[channel] = registers.get(channel, 0) + 1
    return {
        "cycle_id": sheet.cycle_id,
        "cycle_code": sheet.cycle_code,
        "period_start": sheet.period_start.isoformat() if sheet.period_start else None,
        "period_end": sheet.period_end.isoformat() if sheet.period_end else None,
        "window_absent_reason": sheet.window_absent_reason,
        "rows": len(sheet.rows),
        "meters": len({row["meter_id"] for row in sheet.rows}),
        "registers": registers,
        "unresolved_meters": len(sheet.unresolved),
        "unresolved": sheet.unresolved,
        "filename": reading_sheet_filename(sheet),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-054 W1 tasks 4 + 5 (12-governance/11-change-requests.md, PO
#         2026-08-30) + BR-MET-049/057/059/106/143/144 quoted at each use
# generated: 2026-08-30 by the CR-054 W1 reading-sheet lane
# checklist: A✔ B=deferred(CR-054 task 6 is the RDS-03 button and is another
#   lane's — this lane is BACKEND ONLY by dispatch) C✔(tests/
#   test_cr054_w1_reading_sheet.py, every guard proved RED first) D✔ E✔ F✔ G✔
#   H=deferred(not a 🔒 path itself — no money, no rate, no RLS policy, no
#   idempotency key; the MIGRATION that carries the row key IS 🔒 and carries
#   the flag and a review-ledger row)
# exceptions: (1) the read DATE is pre-filled with the window START — a lane
#   judgment, no ruling names a day; decision log 2026-08-30 §1 · (2)
#   `read_method` is blank unless the caller states one, so BR-MET-014's
#   inheritance is not silently retired; decision log §2 · (3) an unresolvable
#   register set still gets a ROW (completeness drops it, because it computes a
#   percentage and this is a work list); decision log §3 · (4) the register's
#   plain-English words are transcribed into `read_import` from the locale
#   catalogue and pinned by a test; decision log §4
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
