# ── Trace ──────────────────────────────────────────────
# Change:   CR-053 task 14 — *"build the PDF set first and the extract behind a
#           named format parameter"*. The PDF set, the manifest and the
#           held-back list shipped as task 13 (v2.109.0); this is the NAMED
#           FORMAT PARAMETER and nothing else.   Screens: the Print bills screen
# Rules:    BR-NOT-029 (the print hand-over is a PDF set plus a manifest, and
#           its FOURTEEN columns — the one field list this repo has ratified;
#           clause (a) discrete address columns; clause (c) no mail standard we
#           do not perform) · BR-NOT-1030 (an unregistered format is REFUSED by
#           name and never substituted) · BR-SHL-020 (a refusal a human can act
#           on) · B14 rule 32 (no rule id in clerk-facing copy)
# Questions: OQ-1167 — OPEN, and it stays open. WHICH format a print vendor
#           wants, WHICH fields in which order, and HOW a period's bills are
#           delimited are all facts only the vendor holds. This module is the
#           mechanism that lets their answer arrive as a REGISTRATION; it does
#           not answer any of the three.
# Defects:  DEF-2847 (two manifest columns have no column to read)
# Tests:    06-backend/tests/test_cr053_task14_print_formats.py
# Impacts:  apps/billing/print_set.py (writes the manifest THROUGH this) ·
#           apps/billing/print_api.py (accepts `format`, lists what exists) ·
#           apps/integrations/codecs.py (the registry mechanism this instantiates
#           — lifted there by CR-069 wave D, 2026-09-03; US-INT-039 TC-6)
# ───────────────────────────────────────────────────────
"""CR-053 task 14 — the named-format registry for the print hand-over.

WHAT THIS IS, IN ONE SENTENCE
════════════════════════════════════════════════════════════════════════════
A print vendor's loader reads ONE file per batch, and different vendors want
that file in different shapes. This is the registry of shapes: **asking for a
format is asking for a name**, a name nobody has registered is REFUSED with the
list of names that exist, and adding a vendor's shape is a registration —
`register(PrintFormat(...))` — rather than a change to the print set.

⚠ **WHAT IS STILL THE VENDOR'S, SAID PLAINLY SO NOBODY READS A WORKING DEFAULT
AS THE QUESTION BEING CLOSED (`OQ-1167`, OPEN).** Three things, and the vendor
answers all three:

  (a) **WHICH FORMAT.** XML, a fixed-width file and a CSV are all plausible and
      the answer comes from the vendor, not from us.
  (b) **WHICH FIELDS, IN WHICH ORDER, WITH WHICH ADDRESS FORM.** A fixed-width
      spec IS a field spec — every column has an offset, a width, a
      justification and a pad character, and none of those exist until the
      vendor states them. An XML schema names its elements. So a vendor format
      arrives carrying its own field list, and this registry is built to let it
      (`PrintFormat.columns`).
  (c) **HOW A PERIOD'S BILLS ARE DELIMITED** — one file per batch with a
      header/trailer record, or one file per bill in an archive.

**None of the three is decided here and none may be guessed.** Handing a
printer a file in a shape they did not ask for is bills posted wrong, and
`BR-CUS-674`'s instinct applies to a vendor's spec exactly as it applies to a
customer's address: it is theirs to state.

WHY THERE IS ONE FORMAT AND WHY IT IS NOT AN INVENTION
════════════════════════════════════════════════════════════════════════════
The one registered format is the file this product ALREADY HANDS OVER: the
manifest `BR-NOT-029` ratified on 2026-08-30, **one row per bill, fourteen
columns, in the ruled order**, as a CSV. Not one field is added, removed or
renamed — the columns are `print_set.MANIFEST_HEADER` and they are passed IN
rather than restated here, so there is exactly one place in this repository
that says what a print vendor receives.

That makes the default honest in a way an empty registry could not be. The
decision log of 2026-08-30 refused to mount this route over an empty registry,
and its reason was specific: *"that route can only ever refuse, and this repo
has already rejected exactly that shape by name — a route that answers 501 is a
promise"*. A registry with one real, already-ratified, already-shipping format
is not a promise; it is the mechanism working on the only answer we have.

WHY A REGISTRY AND NOT AN `if format == "csv"` (the thing this replaces)
════════════════════════════════════════════════════════════════════════════
Because the SHAPE of the answer is what task 14 was asked to build. When the
vendor says *"fixed width, these offsets, one file per batch with a trailer"*,
the work is a `PrintFormat` with an encoder and a `columns` tuple, plus the row
that puts its name in front of a clerk. Nothing in `print_set.py` changes, no
route moves, and the fourteen-column CSV keeps working for every other tenant.

A SILENT FALLBACK IS THE ONE THING THIS MUST NEVER DO
════════════════════════════════════════════════════════════════════════════
`get()` REFUSES an unregistered name and names the registered ones. It does not
fall back to the default, and the reason is the whole of `BR-NOT-1030`: a
vendor's loader that receives a file in a shape it did not expect either stops
— which is a bad day — or **reads the wrong field into the wrong place**, which
is bills posted to the wrong people and money chased from the wrong customers.
A refusal costs a clerk one attempt; a silent substitution costs a mailing.

THE ENCODER CONTRACT
════════════════════════════════════════════════════════════════════════════
    writer = fmt.open(path, header)      # a `RowWriter`
    writer.writerow(["AC-2026-00001", ...])
    writer.close()

`header` is the column names in order. A format whose file has no header row
(a fixed-width file does not) simply ignores it — it is passed for the field
ORDER, which every format needs, not for a header line, which only some write.
The writer is opened on a real path rather than handed rows, because the print
set writes ONE BILL AT A TIME and holds none of them (a 10,000-bill set costs
the same resident memory as a one-bill set) — a format that wanted every row in
memory first would undo that.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Protocol, Sequence

from apps.billing.exceptions import BillingRuleError
from apps.integrations import codecs as _codecs


class RowWriter(Protocol):
    """One open output file. `print_set` writes to it row by row and closes it."""

    def writerow(self, cells: Sequence[str]) -> Any: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class PrintFormat:
    """One shape a print vendor's loader reads.

    `name` is what a caller asks for and what a refusal lists — a short
    lowercase token, because it travels in a request and a clerk may one day
    pick it from a list.

    `filename` is what the file is called INSIDE the archive. It is part of the
    vendor's specification as much as the columns are: a loader that globs
    `*.TXT` does not find `manifest.csv`.

    `summary` is ONE SENTENCE for a person, in plain words, with no rule id and
    no register id (B14 rule 32) — it is what a screen would put beside the
    name, and what the refusal below prints.

    `columns` is the field list, or **None** meaning *the fourteen columns
    `BR-NOT-029` ratified*, which the caller supplies. It is here rather than
    assumed because `OQ-1167` (b) says a vendor's format arrives carrying its
    own field list, and a registry that could not hold one would have to be
    rebuilt on the day the answer came.
    """

    name: str
    filename: str
    summary: str
    open_writer: Callable[[Path, Sequence[str]], RowWriter]
    columns: tuple[str, ...] | None = None

    def open(self, path: Path, header: Sequence[str]) -> RowWriter:
        """Start writing this format at `path`. `header` is the caller's order."""
        return self.open_writer(path, self.columns or tuple(header))

    def header_for(self, ratified: Sequence[str]) -> tuple[str, ...]:
        """The columns this format actually writes — its own, or the ratified list."""
        return self.columns or tuple(ratified)

    def describe(self) -> dict[str, Any]:
        """What a screen would need to offer this format. No internal ids."""
        return {"name": self.name, "filename": self.filename, "summary": self.summary}


class _CsvWriter:
    """`csv.writer` over an open handle, plus the handle's own close.

    A tiny class rather than a closure so `close()` shuts the FILE and not just
    the writer — a manifest flushed but not closed is a truncated last row, and
    the archive would carry it without complaint.
    """

    def __init__(self, path: Path, header: Sequence[str]) -> None:
        self._handle = path.open("w", encoding="utf-8", newline="")
        self._writer = csv.writer(self._handle)
        self._writer.writerow(list(header))  # exactly one header row (IS-9)

    def writerow(self, cells: Sequence[str]) -> Any:
        return self._writer.writerow(list(cells))

    def close(self) -> None:
        self._handle.close()


def _open_manifest_csv(path: Path, header: Sequence[str]) -> RowWriter:
    return _CsvWriter(path, header)


#: THE ONE REGISTERED FORMAT, AND IT IS THE FILE THIS PRODUCT ALREADY HANDS
#: OVER — `BR-NOT-029`'s manifest, one row per bill, fourteen columns in the
#: ruled order, as a CSV. `columns=None` says *use the ratified list*, which is
#: `print_set.MANIFEST_HEADER`; nothing here restates it, so there is one place
#: in this repository that says what a vendor receives.
MANIFEST_CSV = PrintFormat(
    name="manifest-csv",
    filename="manifest.csv",
    summary=(
        "a comma-separated list, one row for every bill, with the column names on "
        "the first line. This is what a small mail house accepts with no set-up."
    ),
    open_writer=_open_manifest_csv,
)

#: What a caller gets when it asks for nothing. It is the format task 13
#: already ships, so an existing caller's archive is byte-for-byte what it was.
DEFAULT_FORMAT_NAME = MANIFEST_CSV.name

#: ⚠ ONE REGISTRY MECHANISM IN THIS REPOSITORY, NOT TWO (US-INT-039 TC-6,
#: 2026-09-03). The name → format table below IS `apps.integrations.codecs`'s
#: `NamedRegistry` — the pattern this file shipped on 1 September, lifted into
#: the integrations module and instantiated here for the print vendor's list.
#: `_registry` is the same object under the name the tests have used since day
#: one; it is a `MutableMapping`, so `dict()` / `clear()` / `update()` still work.
NAMED_FORMATS: _codecs.NamedRegistry = _codecs.NamedRegistry("print file format")
_registry = NAMED_FORMATS


def register(fmt: PrintFormat) -> None:
    """Add a format. THIS is what a new vendor's answer costs.

    Refuses to replace a name that is already registered: two formats under one
    name is a file whose shape depends on import order, and a print vendor's
    loader would meet whichever won that race.
    """
    try:
        NAMED_FORMATS.register(fmt.name, fmt)
    except _codecs.AlreadyRegistered as clash:
        raise BillingRuleError(str(clash)) from clash


def names() -> tuple[str, ...]:
    """Every registered format name, in a stable order a refusal can print."""
    return NAMED_FORMATS.names()


def formats() -> tuple[PrintFormat, ...]:
    return tuple(_registry[name] for name in names())


def get(name: str | None) -> PrintFormat:
    """The format called `name`, or the default when nothing was asked for.

    ⚠ **AN UNKNOWN NAME IS REFUSED AND IS NEVER SUBSTITUTED** (`BR-NOT-1030`).
    The refusal names what was asked for and lists what exists, because a clerk
    who mistypes a format needs to know the right word and not that *something*
    went wrong — and because the alternative, quietly producing the default, is
    a print vendor receiving a file in a shape their loader does not read.
    """
    if name is None or str(name).strip() == "":
        return _registry[DEFAULT_FORMAT_NAME]
    asked = str(name).strip()
    found = NAMED_FORMATS.get(asked)
    if found is not None:
        return found
    available = ", ".join(f"{fmt.name} ({fmt.summary})" for fmt in formats())
    raise BillingRuleError(
        f"there is no print file format called {asked!r}, so nothing has been "
        f"produced. The formats this system can write are: {available}. If your "
        "printer needs a different one, tell us what it looks like and we will "
        "add it — we will not guess at it."
    )


def describe_all() -> list[dict[str, Any]]:
    """Every format, for a screen or a preview. Stable order, no internal ids."""
    return [fmt.describe() for fmt in formats()]


def _iter_registered() -> Iterator[PrintFormat]:  # pragma: no cover - convenience
    yield from formats()


register(MANIFEST_CSV)


__all__ = [
    "DEFAULT_FORMAT_NAME",
    "MANIFEST_CSV",
    "PrintFormat",
    "RowWriter",
    "describe_all",
    "formats",
    "get",
    "names",
    "register",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-053 task 14 (12-governance/11-change-requests.md) + BR-NOT-029
#         (04-docs/05-modules/10-notifications/02-business-rules.md) +
#         BR-NOT-1030 (same file) + OQ-1167 (12-governance/01-open-questions.md)
# generated: 2026-09-01 by the CR-051 task 30 / CR-053 task 14 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
#         ⚠ ONE LINE ON PURPOSE — G3 reads `checklist:` to the END OF THE LINE
#         and a continuation is invisible to it, so a wrapped checklist reports
#         its later letters MISSING. D is apps/billing/print_api.py; E is the
#         Print bills screen, unchanged — see exception 2.
# gates: ruff✔ black✔ · tests/test_cr053_task14_print_formats.py ·
#         tests/test_cr053_print_set.py unchanged and green · golden-verify
#         33 PASS / 0 FAIL before and after — nothing here computes money.
#         RED PROVED FIRST: with `get()` returning the default for an unknown
#         name instead of raising, the refusal case fails; quoted in the lane
#         report.
# exceptions: (1) `OQ-1167` IS STILL OPEN AND IS NOT CLOSED BY THIS FILE. The
#         mechanism is built and ONE format is registered — the field list this
#         repo has already ratified. Which format a vendor wants, which fields
#         in which order, and how a batch is delimited remain theirs.
#         (2) NO SCREEN OFFERS A CHOICE, and that is deliberate. There is one
#         format, and a picker with one option is content a clerk has to read
#         for no decision (B14 rule 32, PO 2026-08-31: *"too much content"*).
#         `GET /billing/print-sets` publishes the list so the picker is a
#         screen change and not a server change on the day a second is
#         registered.
#         (3) NO `columns` IS SET ON THE ONE REGISTERED FORMAT. It writes the
#         ratified fourteen, supplied by `print_set`. The field is present
#         because `OQ-1167` (b) says a vendor's format carries its own list.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
