# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-007 (batch context, CSV upload & column mapping, steps 1–2,
#           incl. manual entry) · US-MET-010 (compliance stamp: file hash +
#           the file+tags idempotency key) · US-MET-017 (one row per channel)
#           Screens: S28 steps 1–2
# Rules:    BR-MET-032 (import is a STANDARD, rules-based process: published
#           template + validate-then-accept; NO fuzzy per-vendor mapping
#           memory) · BR-MET-013 (auto-detect by header, remappable, meter/
#           date/value required, re-detected every upload) · BR-MET-059
#           (channel column optional → `total`) · BR-MET-012 (staged only) ·
#           BR-MET-018 🔒 (file+tags idempotency — OQ-044 closure option b,
#           DB-12) · BR-MET-014 (batch tags inherit unless a row overrides) ·
#           BR-MET-051 (CR-038 W4 — the demand reset, NOTED: the 7th published
#           column, refused BY NAME rather than guessed at) · BR-MET-049
#           (a demand meter is TWO records, which is why the template ships
#           two worked rows)
# Tests:    06-backend/tests/test_us_met_007_010_read_import.py ·
#           06-backend/tests/test_cr038_w4_demand.py (BR-MET-051)
# Impacts:  apps/metering/services.py (stages what this parses) · the S28
#           template download · apps/metering/api.py
# ───────────────────────────────────────────────────────
"""Parsing half of the S28 read upload — the published template, the header
auto-detector, the row parser and the 🔒 file+tags idempotency key.

BR-MET-032 is the whole design brief: import is a STANDARD, rules-based
process. There is exactly one published template, mapping is re-detected
against it on EVERY upload, and no per-tenant or per-vendor mapping is ever
persisted (OQ-040 CLOSED) — so this module holds no state between calls and
offers no "remember this mapping" API to call.

Validate THEN accept: nothing here coerces a value to make it fit. A date that
will not parse is kept VERBATIM in `read_at_raw` with a parse error attached
(US-MET-007/TC-7); an unknown channel is a parse error, never snapped to the
nearest valid one (US-MET-017/TC-7). Every row that enters comes out — accepted,
flagged or rejected, each with its reason. A row is never silently dropped.
"""

import csv
import hashlib
import io
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from apps.metering.models import (
    CHANNEL_DEMAND,
    CHANNEL_EXPORT,
    CHANNEL_GENERATION,
    CHANNEL_TOTAL,
    CHANNELS,
)

# BR-MET-055 keeps imports async and bounded; the row cap mirrors the ONE
# runner's (`import_runs.CSV_ROW_CAP`) so one wizard cannot stage an unbounded
# batch and so a meter file is not refused at a size a premises file is
# accepted at.
#
# ⛔ **50,000 UNTIL 2026-09-18 (`DEF-MET-5756`), WHICH WAS BELOW THE PRODUCT'S
# OWN CEILING AND BELOW WHAT THE PO ASKED FOR.** It "mirrored the assets lane's
# BR-AST-034" — and that lane's importer is RETIRED, while the runner it was
# replaced by carries 100,000. So the number was copied from a file that no
# longer runs, and reads alone stopped at half the size every other target
# takes. A utility cutting over 60,000 meters met a refusal nothing in the
# product justified.
#
# ⚠ **NOT IMPORTED FROM `import_runs`, DELIBERATELY.** These two modules are
# separate paths with separate rules (BR-MET-055 here, BR-MET-038 there) and a
# cross-module import for a constant would make one module's cap silently move
# when the other's does — the same coupling `apps/audit/services.py` avoids for
# the export cap. `tests/test_import_scale_80k.py` asserts the relation instead,
# which is the check without the coupling.
CSV_ROW_CAP = 100_000

# US-MET-007 §5 wrote ≤10 MB when a reads file was a few thousand rows.
# ⚠ **A READS ROW IS THE NARROWEST FILE THIS PRODUCT TAKES — 54.5 BYTES,
# MEASURED from `template_csv()` (9 columns)** — so 100,000 rows is only 5.2 MB
# and the byte cap was never what stopped a reads import; the row cap was. It
# is raised anyway so the two caps cannot disagree, on the reasoning
# `import_runs.CSV_BYTE_CAP` carries at length: the cap an operator meets must
# be the one the product tells them about, and a reads row with long notes and
# a long meter id is wider than our sample.
CSV_BYTE_CAP = CSV_ROW_CAP * 128

# ── the PUBLISHED standard template (BR-MET-032) ────────────────────────────
# target → accepted header aliases (lower-cased, trimmed). The FIRST alias of
# each target is the published header itself — `template_csv()` writes exactly
# those, so the file we hand out is the file we parse best.
TEMPLATE_COLUMNS: dict[str, tuple[str, ...]] = {
    # ── CR-054 W1 task 7 — THE ROW KEY ─────────────────────────────────────
    # The generated reading sheet (apps/metering/reading_sheet.py) writes one
    # row per expected meter per required register and stamps each with the
    # meter and register it was GENERATED FOR. The key comes back on upload so
    # a row whose meter no longer matches it is caught BY NAME rather than
    # imported in silence — CR-054 task 7's own sentence, *"row 412 was
    # M-4021, now M-4099 — was the meter replaced?"*.
    #
    # OPTIONAL, and it must stay optional: a hand-built file and the blank
    # published template carry no key, and `validation._row_key_outcome`
    # reports `not_evaluated` for those rather than manufacturing a warning.
    #
    # FIRST in the dict because it is the row's IDENTITY, and `PUBLISHED_
    # HEADERS` below derives its order from this one — see `template_csv`'s
    # comment about the week two lanes each appended a column and the worked
    # rows slid sideways.
    "row_key": ("row_key", "key", "row key", "sheet_key", "sheet key"),
    "meter_id": ("meter_id", "meter #", "meter no", "meter_no", "meter", "meter number"),
    "read_date": ("read_date", "read date", "date", "reading date"),
    "reading": ("reading", "read value", "read_value", "value", "register", "current"),
    "channel": ("channel", "register", "read_type"),
    "service": ("service", "service (override)", "utility", "utility service"),
    # BR-MET-014's row-level SOURCE override (CR-038 W3, 2026-08-26). The rule
    # has named `source` among the inheriting tags since 2026-08-08 and no
    # column ever carried one, so the method was chosen once per FILE — a cycle
    # read half by AMI and half on foot could not say so. The aliases are the
    # three things a collector export realistically calls this column.
    "read_method": ("read_method", "read method", "method", "source", "read source"),
    "notes": ("notes", "note", "flags", "comment", "comments"),
    # BR-MET-051 (CR-038 W4) — *"Demand: manual demand-register value at cycle
    # read + reset noted"*. The field existed on the staged row and on
    # `meter_reads` from the day both were declared, and NOTHING set either,
    # because the published template had no column for it. This is that column.
    # OPTIONAL, like `channel`: a water file never carries one.
    "demand_reset": (
        "demand_reset",
        "demand reset",
        "demand_reset_noted",
        "reset noted",
        "reset_noted",
        "demand reset noted",
        "peak reset",
    ),
}
REQUIRED_TARGETS: tuple[str, ...] = ("meter_id", "read_date", "reading")
# Two lanes added an optional column on the same day: W3's `read_method`
# (BR-MET-014's row-level override, finally built) and W4's `demand_reset`
# (BR-MET-051's noted reset). Both are optional and independent; the order
# here is the order the template prints them.
OPTIONAL_TARGETS: tuple[str, ...] = (
    "row_key",
    "channel",
    "service",
    "read_method",
    "notes",
    "demand_reset",
)
PUBLISHED_HEADERS: tuple[str, ...] = tuple(aliases[0] for aliases in TEMPLATE_COLUMNS.values())

# Accepted date shapes. ISO first (the template's own), then the two forms a
# US collector export realistically emits. An input matching none of them is a
# PARSE ERROR — "13/45/2026" must never become a date (US-MET-007/TC-7).
_DATE_FORMATS: tuple[str, ...] = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d-%b-%Y")

# Parse-error codes (they surface verbatim next to the row).
ERR_ENCODING = "file_not_utf8"
ERR_TOO_LARGE = "file_too_large"
ERR_NO_HEADER = "file_has_no_header_row"
ERR_UNMAPPED = "required_column_not_mapped"
ERR_TOO_MANY_ROWS = "row_cap_exceeded"
ERR_METER_MISSING = "meter_id_missing"
ERR_DATE_MISSING = "read_date_missing"
ERR_DATE_UNPARSEABLE = "read_date_unparseable"
ERR_VALUE_MISSING = "reading_missing"
ERR_VALUE_UNPARSEABLE = "reading_unparseable"
ERR_VALUE_NEGATIVE = "reading_negative"
#: DEF-MET-8109 — more whole digits than the column holds. `NUMERIC(18,6)` is
#: twelve whole digits; PostgreSQL refuses a thirteenth with `numeric field
#: overflow`, inside `stage_read_batch`'s one transaction, so before this code
#: existed one such cell failed the WHOLE file with a 500. SQLite stored it.
ERR_VALUE_TOO_LARGE = "reading_too_large"
ERR_CHANNEL_UNKNOWN = "channel_unknown"
# BR-MET-051 · CR-038 W4. A reset the parser cannot read is REFUSED BY NAME and
# never guessed at: `false` is a claim ("the register was not zeroed"), and a
# demand customer whose reset went unnoticed is billed against a peak that
# belongs to the previous cycle. Same posture as ERR_CHANNEL_UNKNOWN above.
ERR_DEMAND_RESET_UNKNOWN = "demand_reset_unrecognised"
ERR_DEMAND_RESET_NOT_DEMAND = "demand_reset_not_demand_channel"
#: CR-038 W3 — the row named a method the TENANT's `read_methods` list does not
#: hold. Raised by services (which can see the list), not here: this module is
#: pure and deliberately knows no tenant data.
ERR_READ_METHOD_UNKNOWN = "read_method_unknown"

#: B2 r7's `read_type` vocabulary → the r8 channel it generalized into.
#: `export` needs no entry: r7 and r8 spell it identically.
READ_TYPE_VALUE_ALIASES: dict[str, str] = {"consumption": CHANNEL_TOTAL, "import": CHANNEL_TOTAL}


# ── CR-054 W1 — THE REGISTER, IN THE WORDS THE SCREENS USE ──────────────────
#
# **WHY THIS MAP LIVES HERE, AND NOT IN THE SHEET GENERATOR OR THE FRONT END.**
# The PO's finding that raised CR-054, verbatim: a clerk must work out *"how to
# spell `tou_on`, which appears on NO screen — every screen says On-peak"*. So
# the generated reading sheet prints **On-peak**.
#
# The moment it does, the words become a PARSING problem rather than a copy
# problem. A label the WRITER knows and the PARSER does not is a file that
# cannot be re-uploaded — which is precisely the second importer CR-054's own
# hard constraint forbids. Both directions therefore live in ONE module, this
# one, so the round trip is a property of one dict instead of an agreement
# between two files that nothing checks (hard-won law 5).
#
# It is NOT in `apps/metering/reading_sheet.py` for that reason. It is not in
# the front end either: the sheet is generated server-side and handed to a
# clerk who is looking at a spreadsheet, not at a screen, while they fill it in.
#
# ⚠ **THE WORDS ARE NOT THIS FILE'S — THEY ARE THE LOCALE CATALOGUE'S**, and
# this is a TRANSCRIPTION of `metering.reads.channel.*` in
# `07-frontend/src/i18n/locales/en.json`. Copy has one owner (IS-8), and a
# second spelling of a vocabulary is how a sheet starts printing a word no
# screen shows — the very defect this CR was raised about. So the duplication
# is made safe rather than hidden: `test_cr054__the_channel_labels_are_the_
# screens_own_words` reads that catalogue and asserts these seven strings
# against it, and drift goes RED.
#
# ⚠ **AND `apps/metering/exports.py` TAKES THE OPPOSITE POSTURE ON PURPOSE** —
# *"the file writes the same machine token … rather than the screen's
# translated copy, because copy belongs to IS-8 and a CSV must stay
# parseable"*. That precedent stands for a LIST EXPORT, which is read by a
# spreadsheet. This file is read by a PERSON and typed back in, and the
# parseability objection is answered below: every word it prints is a word
# `parse_row` reads back to its code.
CHANNEL_LABELS: dict[str, str] = {
    CHANNEL_TOTAL: "Total register",
    "tou_on": "On-peak",
    "tou_mid": "Mid-peak",
    "tou_off": "Off-peak",
    CHANNEL_EXPORT: "Export",
    CHANNEL_DEMAND: "Demand",
    CHANNEL_GENERATION: "Generation",
}

#: The inverse, folded the way `parse_row` folds a channel cell. Derived, never
#: hand-written, so a label and its alias cannot disagree.
#:
#: This is NOT the fuzzy snapping BR-MET-032 forbids: exactly the seven words
#: the screens already show are translated, and an unknown value still raises
#: `ERR_CHANNEL_UNKNOWN` verbatim (`test_cr054__an_unknown_register_word_is_
#: still_refused_verbatim` pins that).
CHANNEL_LABEL_ALIASES: dict[str, str] = {
    label.strip().lower(): channel for channel, label in CHANNEL_LABELS.items()
}


def channel_label(channel: str | None) -> str:
    """The word a person reads for `channel`, or the code itself when this repo
    has no word for it.

    Falling back to the CODE rather than to a blank is deliberate: a register
    with no word is a gap to notice, and an empty cell in the sheet's identity
    group would read as "no register", which is a different and false fact.
    """
    if not channel:
        return ""
    return CHANNEL_LABELS.get(channel, channel)


# ── CR-054 W1 task 7 — THE ROW KEY'S GRAMMAR, WRITTEN AND READ IN ONE PLACE ──
#
# `<cycle code>|<channel code>|<meter number>`, e.g. `CY-001|tou_on|M-4021`.
#
# THE METER IS LAST, AND THAT IS THE WHOLE REASON FOR THE ORDER. Both other
# segments are ours (a cycle code and a channel code never contain the
# separator); a METER NUMBER is the utility's own string and may contain
# anything. Parsing with `split(SEP, 2)` therefore returns the meter WHOLE
# however it is spelled, and a key that cannot be read back is a key that
# reports a false mismatch against a meter nobody touched.
#
# The channel segment carries the CODE, not the label: the key is machine
# identity and must survive a copy change. The LABEL is what the sheet's
# `channel` column shows a person.
ROW_KEY_SEPARATOR = "|"


def build_row_key(cycle_code: str, channel: str | None, meter_no: str) -> str:
    """The key stamped on one generated sheet row. Pure; no tenant, no clock."""
    return ROW_KEY_SEPARATOR.join([str(cycle_code), str(channel or ""), str(meter_no)])


def parse_row_key(raw: Any) -> tuple[str, str, str] | None:
    """`(cycle_code, channel, meter_no)`, or **None** when this grammar cannot
    read the cell.

    None is a stated absence, never a guess: the caller reports
    `row_key_unrecognised` with the value shown back, exactly as
    `_parse_demand_reset` refuses a cell it cannot read rather than falling
    through to a plausible answer.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    parts = text.split(ROW_KEY_SEPARATOR, 2)
    if len(parts) != 3:
        return None
    cycle_code, channel, meter_no = (part.strip() for part in parts)
    if not cycle_code or not meter_no:
        return None
    return cycle_code, channel, meter_no


# ── the READ METHOD (BR-MET-123 · BR-MET-014 · CR-038 W3, 2026-08-26) ────────
#
# BR-MET-123, VERBATIM (PO 2026-08-26): *"we are only selectiing the soruce and
# accepting the CSV or excel file; thats is the scope right now; there is no
# integration yet; but it should not stop us from tagging the soruce and
# accepting the CSV or excel file"*.
#
# BR-MET-014, VERBATIM (PO closure batch 2026-08-08): *"Batch tags (month/cycle/
# route/service/source) inherit to every row unless a row-level column
# overrides; effective tags recorded on batch + rows"*.
#
# THE VOCABULARY IS NOT DEFINED HERE AND MUST NEVER BE. The words — Manual,
# Walk-by, AMI, AMR, Mobile, and since BR-MET-142 also Drive-by, Self-read and
# Field visit — are the tenant's `read_methods` reference list (BR-AST-043,
# tenant-extensible per BR-TEN-036). This module is pure and sees no tenant
# data, so it FOLDS a spelling and stops; `services._resolve_read_method` asks
# the list whether the folded word exists.
#
# ⚠ **THIS COMMENT SAID "The five words" UNTIL 2026-08-27.** It was a count in
# prose about a list that is DATA, which is the shape that goes stale — and it
# did, the day the PO ruled OQ-392. No number is written here now.


def normalize_read_method(raw: Any) -> str | None:
    """Fold a written method to the shape a `read_methods` CODE takes.

    "Walk-By", "walk by" and "WALK_BY" are three spellings of ONE word, and the
    meter side already folds them identically (apps/assets/services.
    _flat_catalog_row: *"case-insensitively, '-' and '_' interchangeable"*).
    Anything else survives untouched — folding a spelling is not the snapping
    BR-MET-032 forbids, and `teleportation` comes back out as `teleportation`
    so the clerk is told the word they actually wrote.
    """
    text = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    return text or None


#: **THE LEGACY MAPPING - DECLARED, TESTED, AND APPLIED ON READ.**
#:
#: Readings on file before CR-038 W3 carry the OLD vocabularies:
#: `meter_reads.source` in (ami, manual, import), and a `source_detail` from
#: the batch's six. This is the whole translation, in two dicts a reviewer can
#: read in one glance rather than a function they have to trace.
#:
#: WHY ON READ AND NOT AS A MIGRATION - the decision, stated so the next agent
#: does not "finish the job":
#:
#:   1. **CLAUDE.md hard rule 4.** A committed read is append-only; the only
#:      UPDATE the rules permit on one sets `superseded_by_id`. A backfill is
#:      that forbidden write, in bulk, over rows some of which are BILLED.
#:   2. ⚠ **ALL SIX LEGACY DETAIL WORDS NOW MAP, AND EACH TO ITS OWN WORD -
#:      AMENDED 2026-08-27 BY BR-MET-142 (PO ruling closing `OQ-392`).** This
#:      clause read *"Three of the six legacy detail words name no PO method
#:      … Choosing one would be resolving an open question by picking a value"*,
#:      and that refusal was right: `drive_by` is NOT `amr`, `self_read` is NOT
#:      `manual`, `field_visit` is NOT `mobile`. **The answer was not to pick a
#:      neighbour - it was that the vocabulary GREW.** The PO delegated
#:      (*"(a) Rule each onto one of the five or you can add new categories"*)
#:      and the build added all three as categories, because each states a
#:      different fact: `self_read` WHO read the meter, `field_visit` WHY
#:      somebody went, `mobile` WHAT DEVICE was used.
#:
#:      **So nothing here is guessed and nothing is re-labelled.** `walk_by`,
#:      `ami_itron` and `ami_sensus` still map because they ARE the same word;
#:      `drive_by`, `self_read` and `field_visit` now map because they are ALSO
#:      the same word, seeded in `read_methods` under exactly the code they were
#:      already written as. A reading that said `drive_by` now serves
#:      `drive_by`, which is what it always said.
#:   3. **`import` is a TRANSPORT.** BR-MET-123's own point: a file is how the
#:      reading ARRIVED, never how it was COLLECTED. It maps to None.
#:
#: So a historical row keeps exactly what it carries, `read_method` stays NULL
#: on it, and `selectors.read_dict` reports the derived value WITH its origin
#: (recorded / derived / not_stated) so nothing ever renders a guess as a
#: record. ⚠ **THE ORIGIN OF A TRANSLATED ROW IS STILL `derived`, NOT
#: `recorded`, AND THAT DOES NOT CHANGE WITH BR-MET-142.** The three new words
#: make the derivation EXACT; they do not make it a thing somebody typed at
#: upload. What changes is that a `drive_by` reading stops serving `not_stated`
#: - an absence - and starts serving the method it was collected under.
#: A ruling that wants history REWRITTEN is still a NEW flagged migration with
#: the PO's word on it - REPORTED, not done, and BR-MET-142 clause (7) says so.
LEGACY_READ_METHOD_BY_SOURCE: dict[str, str | None] = {
    "ami": "ami",
    "manual": "manual",
    "import": None,  # a TRANSPORT, not a method - never guessed
    "estimated": None,  # nobody collected an estimate (BR-MET-028)
}

LEGACY_READ_METHOD_BY_DETAIL: dict[str, str] = {
    "walk_by": "walk_by",
    "ami_itron": "ami",
    "ami_sensus": "ami",
    # ── BR-MET-142 (PO 2026-08-27, closing OQ-392). These three were
    # DELIBERATELY ABSENT until today and the absence was correct: no method
    # existed that they meant. Three now do, under the SAME codes these words
    # were always written as, so each maps to ITSELF and nothing is guessed.
    "drive_by": "drive_by",
    "self_read": "self_read",
    "field_visit": "field_visit",
}


def legacy_read_method(source: str | None, source_detail: str | None) -> str | None:
    """The method a pre-CR-038 read can be said to have, or None.

    The DETAIL is consulted first because it is the more specific fact: a batch
    tagged `source_kind='csv'` writes `source='import'`, which says nothing,
    while its `source_detail='walk_by'` says exactly who walked. Neither is
    ever invented - an unmapped value on either side yields None, which the
    serving layer renders as "not stated".
    """
    detail_key = normalize_read_method(source_detail)
    if detail_key in LEGACY_READ_METHOD_BY_DETAIL:
        return LEGACY_READ_METHOD_BY_DETAIL[detail_key]
    return LEGACY_READ_METHOD_BY_SOURCE.get(normalize_read_method(source) or "")


class ImportFileError(Exception):
    """The FILE is unusable — size, encoding, header or mapping. Distinct from
    a row-level parse error: a bad file stages NOTHING (US-MET-007/TC-5,6),
    while a bad ROW stages WITH its error attached."""

    def __init__(self, code: str, **detail: Any) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass
class ParsedRow:
    """One staged row's parse result. `errors` empty ⇒ it parsed; it may still
    fail the VALIDATION rules afterwards (that is validation.py's job)."""

    row_no: int
    #: CR-054 W1 task 7 — the key the generated reading sheet stamped on this
    #: row, VERBATIM. None when the file carried none (a hand-built file, the
    #: blank published template, the manual grid), which the rule reads as
    #: "there is no key to judge" and never as a mismatch.
    row_key: str | None = None
    meter_no_raw: str | None = None
    read_at: datetime | None = None
    read_at_raw: str | None = None
    channel: str = CHANNEL_TOTAL
    value: Decimal | None = None
    service: str | None = None
    #: The row's OWN method, or None when the row stated none (BR-MET-014: it
    #: then inherits the batch tag). Case- and separator-folded ("Walk-By" →
    #: "walk_by") and NOTHING ELSE — an unrecognised word survives verbatim so
    #: services can name it back to the clerk.
    read_method: str | None = None
    note: str | None = None
    #: BR-MET-051 — was the demand register RESET at this read? `False` is the
    #: absence AND the explicit "no"; an unreadable value is an ERROR, never a
    #: False (see `_parse_demand_reset`). `demand_reset_raw` keeps what the
    #: file actually said, so the report can show it back verbatim.
    demand_reset: bool = False
    demand_reset_raw: str | None = None
    #: CR-161-BRC10 W4 — the utility's OWN reading fields as this row carried
    #: them: one CSV column per field (matched by key or label, see
    #: `custom_field_mapping`), or the manual entry's `custom_data`. RAW here —
    #: this module is pure and reads no definitions; `services.stage_read_batch`
    #: checks them through tenancy's one validator before anything is staged.
    custom: dict[str, Any] = field(default_factory=dict)
    #: True when the row CARRIED `custom_data` at all (the manual entry always
    #: does, `{}` included) — which is what names the screen it was typed on.
    custom_sent: bool = False
    errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def parsed(self) -> bool:
        return not self.errors


# ══════════════════════════════════════════════════════════════════════════
# `CR-077` — THE READING STARTERS: **FOUR** SHAPES, AND SEASONAL IS NOT ONE
# ══════════════════════════════════════════════════════════════════════════
#
# **THE RULING, VERBATIM (PO 2026-09-07):** *"it is required for - Premises,
# Units, Meters, Sub meter,s Assets, Parts, Accounts, Reading - including all
# readings - Flat, Demand based, Seasonal, Peak , off peak, etc"*.
#
# Six of the seven targets got their starter that day and `Parts` followed on
# 2026-09-07. This is the seventh and last: the reads importer is a SEPARATE
# mechanism with its own published template (`BR-MET-032`), so it grows worked
# examples rather than joining `import_runs.sample_csv`.
#
# ⚠ **THE COUNT IS FOUR AND THE LIST IN THE RULING IS FIVE — THE DIFFERENCE IS
# MEASURED, NOT PREFERRED.** A read shape is a FILE LAYOUT: how many rows one
# meter contributes for one date, and which register each carries. Measured
# from the rating side (`CR-077`'s row and the decision log of 2026-09-07):
#
#   · flat AND tiered  — ONE row per meter. A tier is a bracket in the PRICE
#     LIST; the file that feeds it is one number, so a second template would
#     teach a layout that does not exist.
#   · time of use      — THREE rows, one per window (`tou_on`/`tou_mid`/
#     `tou_off`). *"Peak, off peak"* in the ruling is this shape, not two.
#   · demand           — TWO rows, energy plus the peak register, and the reset
#     flag means something ONLY on the peak row (`BR-MET-051`, and `parse_row`
#     refuses `demand_reset` on any other channel BY NAME).
#   · net metering     — TWO rows, energy plus `export` (`BR-AST-029`: a net
#     cycle is one `total` record and one `export` record sharing a `read_at`).
#
# ⚠ **SEASONAL IS NOT A READ SHAPE AND A FIFTH TEMPLATE WOULD TEACH A FILE
# LAYOUT THAT DOES NOT EXIST.** A season is a property of the PRICE LIST,
# resolved from the date on the reading — so a seasonal read is a flat read on
# a date, and its file is the flat one above. Building a `reads_seasonal.csv`
# would invite a clerk to look for a column that no parser reads.
#
# ⚠ **AND CAPACITY SERVICES READ NO METER AT ALL** — fire, trash, storm water
# and the rest are billed on a size class and a count, so there is no reading
# file for them and none is offered here.
#
# ⚠ **WHY THE ROWS ARE DICTS AND NOT TUPLES, WHICH IS THE ONE MECHANICAL
# LESSON IN THIS BLOCK.** The old worked rows were positional lists, and the
# comment above them recorded what that cost: W3 appended `read_method`, W4
# appended `demand_reset`, each lane wrote its row against the template it
# could see, and merging them left cells slid one column sideways —
# `read_method` reading *"Access ok"*. `_shape_row` builds every row from
# `PUBLISHED_HEADERS` instead, so a column appended tomorrow lands in every
# starter as an empty cell rather than as a silent shift.
#
# ⚠ **AND IT READS THE ALLOW LIST RATHER THAN A COPY OF IT** — the trap the
# Parts import hit, where a template offered a column its writer refuses and
# every row came back rejected at the write with no stage-3 rule able to catch
# it. Here the allow list is `TEMPLATE_COLUMNS`, which is the same dict
# `parse_csv` maps a header against, and `_shape_row` RAISES on a target that
# is not in it — at import time, so a starter naming a column this parser
# cannot read cannot reach a clerk at all.
SHAPE_FLAT = "flat"
SHAPE_TOU = "tou"
SHAPE_DEMAND = "demand"
SHAPE_NET = "net"


def _shape_row(**cells: str) -> tuple[str, ...]:
    """One worked row, IN `PUBLISHED_HEADERS` ORDER, from named target cells.

    A name that is not a target of `TEMPLATE_COLUMNS` — this parser's own allow
    list — raises. A target with no cell here is written EMPTY, which is what
    "optional" looks like in a worked example.
    """
    unknown = sorted(set(cells) - set(TEMPLATE_COLUMNS))
    if unknown:
        raise ValueError(
            f"read starter names {unknown}, which parse_row does not read; "
            f"the columns are {list(TEMPLATE_COLUMNS)}"
        )
    return tuple(str(cells.get(target, "")) for target in TEMPLATE_COLUMNS)


#: One READING DATE for every starter. A constant rather than `date.today()`,
#: for `import_runs.SAMPLE_DATE`'s reason: a sample whose contents change with
#: the calendar cannot be diffed, and it is also the date the shipped template
#: has carried since `BR-MET-032`.
STARTER_DATE = "2026-08-03"

#: The four shapes, in the order a screen offers them: the commonest first.
#:
#: ⚠ **`service` IS STATED ON THE THREE ELECTRIC LAYOUTS AND LEFT EMPTY ON THE
#: FLAT ONE, AND THAT IS DELIBERATE.** Time of use, demand and net metering are
#: electric register layouts, so `E` is a fact about them; flat and tiered is
#: every service this product sells, and stating one would teach a water
#: utility to write `E`. An empty cell inherits the batch tag, which is
#: `BR-MET-014`'s own default and the honest thing for a shape that is not
#: about a service at all.
#:
#: ⚠ **THE `row_key` CELL IS EMPTY IN ALL FOUR (`CR-054` W1 task 7).** These
#: are the files a clerk builds BY HAND; no key was ever generated for their
#: rows, and stamping a plausible one would teach the wrong thing about a
#: column whose only job is to say which GENERATED row this was.
READ_SHAPES: dict[str, dict[str, Any]] = {
    SHAPE_FLAT: {
        "filename": "reads_flat.csv",
        "rows": (
            _shape_row(
                meter_id="M-7001",
                read_date=STARTER_DATE,
                reading="42864",
                channel="total",
                read_method="walk_by",
                notes="Access ok",
            ),
        ),
    },
    SHAPE_TOU: {
        "filename": "reads_time_of_use.csv",
        "rows": (
            _shape_row(
                meter_id="M-7002",
                read_date=STARTER_DATE,
                reading="18420",
                channel="tou_on",
                service="E",
                read_method="ami",
                notes="On-peak register",
            ),
            _shape_row(
                meter_id="M-7002",
                read_date=STARTER_DATE,
                reading="9610",
                channel="tou_mid",
                service="E",
                read_method="ami",
                notes="Mid-peak register",
            ),
            _shape_row(
                meter_id="M-7002",
                read_date=STARTER_DATE,
                reading="31255",
                channel="tou_off",
                service="E",
                read_method="ami",
                notes="Off-peak register",
            ),
        ),
    },
    SHAPE_DEMAND: {
        # `reads_template.csv` KEEPS ITS NAME: it is the file `GET /reads/
        # template` has served since BR-MET-032, it is cited by name in the
        # spec and in the front end, and a starter is not a reason to move a
        # published address.
        "filename": "reads_template.csv",
        "rows": (
            _shape_row(
                meter_id="M-7001",
                read_date=STARTER_DATE,
                reading="42864",
                channel="total",
                service="E",
                read_method="walk_by",
                notes="Access ok",
                demand_reset="no",
            ),
            _shape_row(
                meter_id="M-7001",
                read_date=STARTER_DATE,
                reading="412",
                channel="demand",
                service="E",
                read_method="walk_by",
                notes="Peak noted",
                demand_reset="yes",
            ),
        ),
    },
    SHAPE_NET: {
        "filename": "reads_net_metering.csv",
        "rows": (
            _shape_row(
                meter_id="M-7003",
                read_date=STARTER_DATE,
                reading="27140",
                channel="total",
                service="E",
                read_method="ami",
                notes="Energy taken from the grid",
            ),
            _shape_row(
                meter_id="M-7003",
                read_date=STARTER_DATE,
                reading="6380",
                channel="export",
                service="E",
                read_method="ami",
                notes="Energy sent back to the grid",
            ),
        ),
    },
}
SHAPE_CODES: tuple[str, ...] = tuple(READ_SHAPES)


def starter_csv(shape: str) -> tuple[str, str]:
    """`(filename, body)` for one read shape — the `CR-077` starter.

    Header row plus that shape's worked rows, written by the same writer
    settings the reading sheet uses, so a file downloaded here and a file
    generated there parse identically.

    An unknown shape is REFUSED BY NAME with the four codes listed, the same
    posture `import_runs.sample_csv` takes for an unknown target: a starter
    quietly falling back to the flat one is how a clerk ends up with the wrong
    file and no way to tell.
    """
    entry = READ_SHAPES.get(shape)
    if entry is None:
        raise ValueError(f"unknown read shape {shape!r} — the shapes are {list(READ_SHAPES)}")
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(PUBLISHED_HEADERS)
    for row in entry["rows"]:
        writer.writerow(row)
    return str(entry["filename"]), buffer.getvalue()


def with_custom_columns(body: str, custom_fields: list[dict[str, Any]] | None) -> str:
    """CR-161-BRC10 W4 — the template or a starter with ONE trailing column per
    active reading field the utility has defined, headed by its key, cells
    left empty (PO 2026-10-02: *"every import includes one column per custom
    field (premises, units, assets, accounts, readings)"*).

    ⚠ **A UTILITY WITH NO READING FIELDS GETS THE EXACT BYTES IT ALWAYS DID.**
    BR-MET-032's *"exactly one published template"* still holds for the
    published columns — they are never reordered or renamed — and the PO's
    ruling adds only the utility's own trailing columns, which `parse_csv`
    reads back through `custom_field_mapping`.
    """
    headers = custom_field_headers(custom_fields)
    if not headers:
        return body
    rows = list(csv.reader(io.StringIO(body)))
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    for index, row in enumerate(rows):
        writer.writerow([*row, *(headers if index == 0 else [""] * len(headers))])
    return buffer.getvalue()


def template_csv() -> str:
    """`reads_template.csv` — the published standard template (BR-MET-032).

    ⚠ TWO worked rows since CR-038 W4, where it shipped ONE since BR-MET-032.
    The second is not decoration: BR-MET-049 says *"demand → +demand record"*,
    so a demand meter is TWO rows in this file, and BR-MET-051 puts the reset
    on the DEMAND row — a template that showed only an energy row would teach
    the wrong file shape to exactly the customers a mis-read peak mis-bills.

    ⚠ **IT IS `SHAPE_DEMAND`'s STARTER AND NOT A SECOND COPY OF IT (`CR-077`).**
    The bytes are unchanged — this is the file this function has returned since
    CR-038 W4 — but they are now written from `READ_SHAPES`, so the demand
    starter and the published template cannot drift into two spellings of one
    file. That is `DEF-616`'s lesson (one list maintained next to another) and
    `sample_csv`'s own posture one importer over.

    ⚠ **AND THE STALE CITATION IS FIXED RATHER THAN REPORTED AGAIN.** This
    docstring used to end by reporting that `apps/metering/import_runs.py` and
    `tests/test_cr025_sample_csv.py` cite *"header plus ONE worked row"* as this
    file's precedent, and that the citation was one row out of date. It had
    been out of date since CR-038 W4; reporting it a second time would have
    been a comment claiming a plan (hard-won law 1), so both citations now say
    what this file actually ships.
    """
    return starter_csv(SHAPE_DEMAND)[1]


def file_sha256(payload: bytes) -> str:
    """The compliance stamp's SHA-256 (US-MET-010 §5) — computed SERVER-side,
    never accepted from the client."""
    return hashlib.sha256(payload).hexdigest()


# ── 🔒 file+tags idempotency (BR-MET-018 · OQ-044 closure option b · DB-12) ──
# HUMAN-OWNED — idempotency keys are a CLAUDE.md 🔒 sensitive path.
# HUMAN-REVIEW-PENDING — AI-authored 2026-08-10 under the PO ruling of
# 2026-08-09 ("AI will do it; we will review it later as human"). Row appended
# to 12-governance/09-human-review-ledger.md; not RATIFIED without a human
# sign-off. The POLICY is signed and is NOT reinterpreted here: the key is
# file + tags, and a collision BLOCKS the commit naming who posted the original
# and when (option b) — it never silently no-ops and never double-posts.
#
# Key mechanics, stated so a reviewer can check them in one read:
#   · the file half is the SHA-256 of the exact bytes uploaded (so one changed
#     row makes a different batch — US-MET-010/TC-6);
#   · the tag half is the step-1 tag set that BR-MET-014 says every row
#     inherits: reading month, cycle, route, service, source kind + detail.
#     Tags are serialised in a FIXED order with explicit nulls, so key
#     equality means tag equality and dict ordering cannot change a key;
#   · the digest is SHA-256 of that canonical JSON, hex — a stable string, safe
#     in a unique index, and carrying no tenant data in the clear;
#   · the structural half is the partial unique on `read_import_batches`
#     (tenant, file_hash, tag_fingerprint) WHERE status='posted' (DB-12), so a
#     race that beats the service-layer check still cannot double-post.
# Eng-Lead note: if the key ever needs to live beside the other B2 unique-key
# shapes, its home is core/idempotency.py — moving it is a rename, not a
# redesign, because everything above is computed in this one function.
#
# CR-038 W3 BOUNDARY (2026-08-26) - `read_method` IS DELIBERATELY NOT HERE.
# BR-MET-014 counts the read method among the batch tags every row inherits, so
# on the RULE's reading it belongs in "the tag half". It is left out anyway,
# and the reason is measurable rather than cautious: this key is compared
# against fingerprints ALREADY STORED on posted batches. Adding a field changes
# what an identical re-upload computes, so every batch posted before today
# would stop colliding with itself and BR-MET-018's double-post block would
# quietly stop protecting the history it was built for. The mechanics are the
# OQ-044 closure's and this stanza is HUMAN-REVIEW-PENDING, so this lane
# REPORTS the question to the Eng-Lead instead of answering it.
# The consequence, stated: two uploads of the SAME FILE tagged with DIFFERENT
# methods are one batch, and the second is blocked. Guarded by
# tests/test_cr038_w3_read_method.py::test_the_idempotency_key_is_untouched_by
# _this_lane so the omission cannot drift into an accident.
IDEMPOTENCY_TAG_FIELDS: tuple[str, ...] = (
    "period_month",
    "cycle_id",
    "route_id",
    "service",
    "source_kind",
    "source_detail",
)


def read_batch_idempotency_key(tags: dict[str, Any]) -> str:
    """The TAG half of BR-MET-018's file+tags key (the file half is the stored
    `file_hash`). Deterministic, order-independent, explicit about nulls."""
    canonical = json.dumps(
        {name: _tag_value(tags.get(name)) for name in IDEMPOTENCY_TAG_FIELDS},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _tag_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


# ── header auto-detection (BR-MET-013, re-detected every upload) ────────────


def detect_mapping(headers: list[str]) -> dict[str, str | None]:
    """target → the CSV header that supplies it, or None.

    Detection is by NAME against the published template only (BR-MET-032). It
    reads no stored preference and writes none — call it again on the next
    upload and it starts from zero, which is exactly US-MET-007/TC-9.
    """
    normalized = {(h or "").strip().lower(): h for h in headers}
    mapping: dict[str, str | None] = {}
    for target, aliases in TEMPLATE_COLUMNS.items():
        mapping[target] = next(
            (normalized[alias] for alias in aliases if alias in normalized), None
        )
    return mapping


#: CR-161-BRC10 W4 — a custom column's mapping target is `custom_data.<key>`,
#: the same spelling the ONE import runner uses for premises and units.
CUSTOM_TARGET_PREFIX = "custom_data."


def custom_field_mapping(
    headers: list[str],
    custom_fields: list[dict[str, Any]] | None,
    taken: dict[str, str | None] | None = None,
) -> dict[str, str]:
    """`custom_data.<key>` → the CSV header that supplies it (PO 2026-10-02,
    Part 2 row 11: *"Reading import (column mapping)"*).

    A header matches a field by its KEY (`seal_number`) or its LABEL (*Seal
    number*), case- and space-folded — the two names a utility sees for the
    field, one in an export and one on a screen. A header the published
    template already claims (`meter_id`, `notes`, …) is never re-read as a
    custom field, so a field labelled *Notes* cannot steal the notes column.
    Like `detect_mapping` it remembers nothing between uploads (BR-MET-032).
    """
    if not custom_fields:
        return {}
    claimed = {header for header in (taken or {}).values() if header}
    by_name: dict[str, str] = {}
    for header in headers:
        if header in claimed:
            continue
        folded = " ".join((header or "").strip().lower().replace("_", " ").split())
        if folded:
            by_name.setdefault(folded, header)
    out: dict[str, str] = {}
    for definition in custom_fields:
        for name in (definition.get("key"), definition.get("label")):
            folded = " ".join(str(name or "").strip().lower().replace("_", " ").split())
            if folded and folded in by_name:
                out[f"{CUSTOM_TARGET_PREFIX}{definition['key']}"] = by_name[folded]
                break
    return out


def custom_field_headers(custom_fields: list[dict[str, Any]] | None) -> list[str]:
    """The header a utility's own field takes in the published template — its
    KEY, which `custom_field_mapping` reads back and which BR-TEN-049 keeps
    from ever being renamed (*"Exports and old bills keep working"*)."""
    return [str(definition["key"]) for definition in (custom_fields or [])]


def missing_required(mapping: dict[str, str | None]) -> list[str]:
    """BR-MET-013: meter id, read date and read value must be mapped before
    Continue. Channel/service/notes are optional by law, not by leniency."""
    return [target for target in REQUIRED_TARGETS if not mapping.get(target)]


def _decode(payload: bytes) -> str:
    if len(payload) > CSV_BYTE_CAP:
        raise ImportFileError(ERR_TOO_LARGE, size=len(payload), cap=CSV_BYTE_CAP)
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:  # US-MET-007/TC-6 — stated, never guessed at
        raise ImportFileError(ERR_ENCODING, position=exc.start) from None


def _parse_date(raw: str) -> datetime | None:
    """A read DATE becomes 00:00:00Z of that day.

    Eng disposition, REPORTED: B2 types `read_at` as timestamptz while the
    template, the rules and every fixture speak in whole DATES ("M-7001 · Aug
    3 · total"). Normalising to midnight UTC is what makes B2 r8's UNIQUE
    (asset, read_at, channel) BE the per-date key BR-MET-052 describes — with a
    free-running clock time, two uploads of the same reading would not collide
    and the duplicate rule would silently never fire.
    """
    text = raw.strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return parsed.replace(tzinfo=timezone.utc)
    return None


def _parse_decimal(raw: str) -> Decimal | None:
    """NUMERIC(18,6) from a decimal STRING — never a float (CLAUDE.md rule 2's
    discipline applies to quantities too; a float register value would be a
    silent precision loss on a number that ends up on a bill)."""
    text = raw.strip().replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


#: `read_import_rows.value` and `meter_reads.current_value` are NUMERIC(18,6):
#: eighteen digits, six after the point, so TWELVE whole digits (DEF-MET-8109).
_REGISTER_LIMIT = Decimal(10) ** 12
_REGISTER_QUANTUM = Decimal("0.000001")


def fits_register_column(value: Decimal) -> bool:
    """Would PostgreSQL store this in NUMERIC(18,6)? Asked of a FINITE value.

    Rounded to the column's six places first, because that is what the
    database does: `999999999999.9999999` rounds up to a thirteenth digit and is
    refused, while `999999999999.999999` fits. A value too long for Python's
    own 28-digit context to round is refused too — it is far past the limit.
    """
    try:
        rounded = value.quantize(_REGISTER_QUANTUM, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return False
    return abs(rounded) < _REGISTER_LIMIT


# ── BR-MET-051's reset cell (CR-038 W4) ─────────────────────────────────────
# The value is written by a meter reader on a route sheet and typed by a clerk,
# so the spellings a HUMAN actually produces are all accepted. What is NOT
# accepted is anything else: `_parse_demand_reset` returns None for an
# unrecognised cell and the caller raises ERR_DEMAND_RESET_UNKNOWN rather than
# falling through to False. That asymmetry IS the rule — an absent cell is an
# absence and means "no reset noted"; a present cell nobody can read is a
# FAILURE TO KNOW, and a demand customer billed on an un-noticed reset pays for
# a peak that belongs to the previous cycle.
DEMAND_RESET_TRUE: frozenset[str] = frozenset(
    {"y", "yes", "true", "t", "1", "x", "reset", "noted", "reset noted", "yes - reset"}
)
DEMAND_RESET_FALSE: frozenset[str] = frozenset(
    {"n", "no", "false", "f", "0", "none", "not reset", "no reset", "-"}
)


def _parse_demand_reset(raw: str) -> bool | None:
    """`True` / `False` / None-for-unrecognised. A blank cell is False — the
    absence, which is what "no reset was noted" has always meant."""
    text = raw.strip().lower()
    if not text:
        return False
    if text in DEMAND_RESET_TRUE:
        return True
    if text in DEMAND_RESET_FALSE:
        return False
    return None


def parse_row(row_no: int, values: dict[str, Any], mapping: dict[str, str | None]) -> ParsedRow:
    """One CSV/manual row → a staged row with every parse failure ATTACHED.

    Nothing is dropped and nothing is coerced: a row with three parse errors
    still returns, carrying all three, so the batch's per-row outcome report is
    complete (the DEF-016 failure mode is a row that vanishes between the file
    and the summary).
    """
    parsed = ParsedRow(row_no=row_no)

    # CR-054 W1 task 7. Carried VERBATIM and never parsed into an error here:
    # a key this grammar cannot read is a JUDGMENT (`validation._row_key_
    # outcome` reports it by name), not a parse failure that would refuse a row
    # whose meter, date and value are all perfectly good.
    raw_row_key = str(values.get(mapping.get("row_key") or "", "") or "").strip()
    parsed.row_key = raw_row_key or None

    raw_meter = str(values.get(mapping.get("meter_id") or "", "") or "").strip()
    parsed.meter_no_raw = raw_meter or None
    if not raw_meter:
        parsed.errors.append({"code": ERR_METER_MISSING, "field": "meter_id"})

    raw_date = str(values.get(mapping.get("read_date") or "", "") or "")
    parsed.read_at_raw = raw_date.strip() or None
    if not raw_date.strip():
        parsed.errors.append({"code": ERR_DATE_MISSING, "field": "read_date"})
    else:
        parsed.read_at = _parse_date(raw_date)
        if parsed.read_at is None:
            parsed.errors.append(
                {"code": ERR_DATE_UNPARSEABLE, "field": "read_date", "value": raw_date.strip()}
            )

    raw_value = str(values.get(mapping.get("reading") or "", "") or "")
    if not raw_value.strip():
        parsed.errors.append({"code": ERR_VALUE_MISSING, "field": "reading"})
    else:
        parsed.value = _parse_decimal(raw_value)
        # ── DEF-MET-8109 — A VALUE THE COLUMN CANNOT HOLD IS A ROW ERROR ─────
        # `Decimal()` accepts `NaN`, `Infinity` and a number of any length, and
        # every one of them used to travel on to the database: `NaN < 0` below
        # raised `InvalidOperation` on the spot, and PostgreSQL refused the
        # other two inside `stage_read_batch`'s ONE transaction — so one cell
        # failed the whole file with a 500 and nothing staged. Each is now
        # refused HERE, where a row error is still possible, with the value the
        # clerk typed so the row can be found. The value is cleared, so nothing
        # downstream can try to store it.
        if parsed.value is not None and not parsed.value.is_finite():
            parsed.value = None
        if parsed.value is None:
            parsed.errors.append(
                {"code": ERR_VALUE_UNPARSEABLE, "field": "reading", "value": raw_value.strip()}
            )
        elif not fits_register_column(parsed.value):
            parsed.value = None
            parsed.errors.append(
                {"code": ERR_VALUE_TOO_LARGE, "field": "reading", "value": raw_value.strip()}
            )
        elif parsed.value < 0:
            # A register cannot read negative (US-MET-007 §5 "value ≥ 0"). This
            # is NOT the BR-MET-052 negative-USAGE rule — that one is about the
            # delta between two reads and is validation.py's.
            parsed.errors.append(
                {"code": ERR_VALUE_NEGATIVE, "field": "reading", "value": str(parsed.value)}
            )

    raw_channel = str(values.get(mapping.get("channel") or "", "") or "").strip().lower()
    # The column is published as `channel` and ALSO accepted as `read_type`
    # (TEMPLATE_COLUMNS above), because BR-AST-029 and every net-metering file
    # in the wild spell it that way. Its VALUES need the same treatment: B2 r7's
    # `consumption` is r8's `total` — the addendum says so itself ("read_type
    # GENERALIZES to channel"), so translating it implements the supersession.
    # This is NOT the snapping the docstring forbids: an unknown value below
    # still errors verbatim, and only r7's own two words are translated.
    raw_channel = READ_TYPE_VALUE_ALIASES.get(raw_channel, raw_channel)
    # CR-054 W1: and the SCREENS' OWN WORDS, for the same reason and by the
    # same mechanism — the generated reading sheet prints `On-peak` because
    # `tou_on` appears on no screen, so `On-peak` must read back as `tou_on` or
    # the sheet cannot be re-uploaded through this parser. Exactly the seven
    # words in CHANNEL_LABELS are translated; anything else still falls to the
    # verbatim refusal below.
    raw_channel = CHANNEL_LABEL_ALIASES.get(raw_channel, raw_channel)
    if not raw_channel:
        parsed.channel = CHANNEL_TOTAL  # BR-MET-059: absent ⇒ the flat meter's one channel
    elif raw_channel in CHANNELS:
        parsed.channel = raw_channel
    else:
        parsed.channel = raw_channel  # kept VERBATIM — never snapped to a valid value
        parsed.errors.append(
            {"code": ERR_CHANNEL_UNKNOWN, "field": "channel", "value": raw_channel}
        )

    raw_service = str(values.get(mapping.get("service") or "", "") or "").strip()
    parsed.service = raw_service or None  # row override beats the batch tag (BR-MET-014)
    # BR-MET-014's source override. Folded to the shape a `read_methods` CODE
    # takes ("Walk-By" and "walk by" are both `walk_by`) because that is a
    # SPELLING of the same word, not a different value — the same normalisation
    # apps/assets/services._flat_catalog_row already applies on the meter side.
    # Whether the folded word EXISTS in this tenant's list is judged in
    # services, which can see the list; an unknown one is kept and reported,
    # never snapped (BR-MET-032, and the docstring above says so for channel).
    raw_read_method = str(values.get(mapping.get("read_method") or "", "") or "").strip()
    parsed.read_method = normalize_read_method(raw_read_method)
    raw_note = str(values.get(mapping.get("notes") or "", "") or "").strip()
    parsed.note = raw_note or None

    # ── BR-MET-051: the demand reset, NOTED ────────────────────────────────
    raw_reset = str(values.get(mapping.get("demand_reset") or "", "") or "").strip()
    parsed.demand_reset_raw = raw_reset or None
    noted = _parse_demand_reset(raw_reset)
    if noted is None:
        # Kept VERBATIM and refused BY NAME — never snapped to False.
        parsed.errors.append(
            {"code": ERR_DEMAND_RESET_UNKNOWN, "field": "demand_reset", "value": raw_reset}
        )
    elif noted and parsed.channel != CHANNEL_DEMAND:
        # BR-MET-051 scopes the reset to the DEMAND register, and both columns
        # named `demand_reset_noted` have carried the comment "demand channel
        # only" since they were declared. A reset noted against the energy
        # register is a wrong-column mistake; storing it would put a fact about
        # a register that HAS no reset onto a row that bills as energy.
        # Eng disposition, REPORTED: no signed rule states this refusal in
        # words — it makes the scope BR-MET-051 already has mechanical.
        parsed.errors.append(
            {
                "code": ERR_DEMAND_RESET_NOT_DEMAND,
                "field": "demand_reset",
                "value": raw_reset,
                "channel": parsed.channel,
            }
        )
    else:
        parsed.demand_reset = noted
    return parsed


def parse_csv(
    payload: bytes, custom_fields: list[dict[str, Any]] | None = None
) -> tuple[dict[str, str | None], list[str], list[ParsedRow]]:
    """`(mapping, headers, rows)` for an uploaded file.

    `custom_fields` (CR-161-BRC10 W4) is the tenant's active reading fields as
    `{key, label}`; each one a header names is read into `ParsedRow.custom`
    and appears in `mapping` as `custom_data.<key>`.

    Raises ImportFileError for the whole-file refusals (size, encoding, no
    header, a required column unmapped, row cap) — those stage NOTHING, which
    is what "Continue blocked" means in US-MET-007/TC-5.
    """
    text = _decode(payload)
    reader = csv.reader(io.StringIO(text))
    try:
        headers = next(reader)
    except StopIteration:
        raise ImportFileError(ERR_NO_HEADER) from None
    if not any((h or "").strip() for h in headers):
        raise ImportFileError(ERR_NO_HEADER)

    mapping = detect_mapping(headers)
    missing = missing_required(mapping)
    if missing:
        raise ImportFileError(ERR_UNMAPPED, missing=missing, headers=headers)
    custom_mapping = custom_field_mapping(headers, custom_fields, mapping)

    rows: list[ParsedRow] = []
    for index, raw_row in enumerate(reader, start=1):
        if not any((cell or "").strip() for cell in raw_row):
            continue  # a blank line is whitespace, not a row — it reports nothing
        if len(rows) >= CSV_ROW_CAP:
            raise ImportFileError(ERR_TOO_MANY_ROWS, cap=CSV_ROW_CAP)
        values = {
            header: (raw_row[position] if position < len(raw_row) else "")
            for position, header in enumerate(headers)
        }
        parsed = parse_row(index, values, mapping)
        for target, header in custom_mapping.items():
            cell = (values.get(header) or "").strip()
            if cell:
                # An EMPTY cell is "not answered", never an empty string stored.
                parsed.custom[target[len(CUSTOM_TARGET_PREFIX) :]] = cell
        rows.append(parsed)
    return {**mapping, **custom_mapping}, headers, rows


def parse_manual_rows(entries: list[dict[str, Any]]) -> list[ParsedRow]:
    """The S28 manual grid (Meter # · Date · Channel · Reading · Notes) through
    the SAME parser as the CSV path, so a typed row and an uploaded row are
    judged identically (BR-MET-032 validate-then-accept, one code path)."""
    identity = {target: target for target in TEMPLATE_COLUMNS}
    rows: list[ParsedRow] = []
    for index, entry in enumerate(entries, start=1):
        values = {
            # CR-054 W1 task 7 — the manual grid states no key, and that is the
            # honest answer: nobody generated a row for it. The cell is read
            # through the same parser so a caller that DOES carry one (a
            # corrected sheet row re-typed by hand) keeps it.
            "row_key": entry.get("row_key") or "",
            "meter_id": entry.get("meter_id") or entry.get("meter_no") or "",
            "read_date": entry.get("read_date") or entry.get("read_at") or "",
            "reading": entry.get("reading") if entry.get("reading") is not None else "",
            "channel": entry.get("channel") or "",
            "service": entry.get("service") or "",
            "read_method": entry.get("read_method") or entry.get("method") or "",
            "notes": entry.get("notes") or entry.get("note") or "",
            # BR-MET-051 — the manual grid's own reset cell, through the SAME
            # parser, so a typed row and an uploaded row are judged identically.
            "demand_reset": entry.get("demand_reset") or entry.get("demand_reset_noted") or "",
        }
        parsed = parse_row(index, values, identity)  # type: ignore[arg-type]
        # CR-161-BRC10 W4 — the manual entry's own fields travel as they were
        # typed (a Yes/No stays a boolean, a multi-select a list) for the
        # validator to judge; only a door that SENT the key names a screen.
        if "custom_data" in entry:
            parsed.custom_sent = True
            submitted = entry.get("custom_data")
            parsed.custom = dict(submitted) if isinstance(submitted, dict) else {}
        rows.append(parsed)
    return rows


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-007@a4d93b5 (story+rules snapshot — EP-MET-03 steps 1–2; co-story US-MET-010 hash + 🔒 idempotency key)
# generated: 2026-08-10 by the W2 reads lane
# checklist: A✔ B✔ C✔ D=deferred(API half lands in apps/metering/api.py) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — the idempotency key is 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: see the lane report
# exceptions: read DATE normalised to 00:00Z so B2 r8's UNIQUE (asset, read_at, channel) IS the per-date duplicate key the rules describe — Eng disposition, REPORTED · the idempotency key lives here rather than core/idempotency.py because core/ is outside this lane's territory — relocation is a rename, FLAGGED for the Eng Lead
# AMENDED: 2026-08-26 by the CR-038 W4 demand lane — BR-MET-051's `demand_reset`
#   column (optional, 7th), its two named refusals, and a second worked template
#   row. Eng disposition REPORTED: a reset noted on a NON-demand row is refused
#   (`demand_reset_not_demand_channel`); no signed rule states that refusal in
#   words — it makes BR-MET-051's own scope mechanical, and the alternative was
#   storing a fact about a register that has no reset.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
