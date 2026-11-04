# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-003 (EP-RBS-01) — CR-075 wave D task D1: 07-endpoints.md
#           row 14, `GET /runbooks/runs/{id}/results/{done|not-done}.csv`.
#           Screen: RBS-006 (the Downloads block)
# Rules:    BR-RBS-011 (a failure names its fix route; one without a route is a
#           defect in the runbook) · BR-RBS-010 (every record states the rule
#           that decided it, in words a clerk can read) · B14 rule 31 (no
#           database id is ever the visible value of a field) · B14 rule 32 (no
#           rule id or internal code in clerk-facing copy) · CLAUDE.md hard rule
#           2 (money 4 stored, 2 displayed, CHAR(3) currency, never a float) ·
#           NFR-3 · NFR-5 (no cap, and nothing materialised)
# Tests:    06-backend/tests/test_us_rbs_003_endpoints.py
# Impacts:  apps/runbooks/api.py (the two CSV routes) ·
#           10-scripts/render-checks/rbs-d-endpoints.mjs
# ───────────────────────────────────────────────────────
"""The two result files — **what the run did, and what it did not**.

`07-endpoints.md` row 14: *the two result files, each row carrying **its reason
and its fix***. `RBS-006`'s Downloads block is the button, and every runbook
except 4, 6 and 13 draws it.

WHY TWO FILES AND NOT ONE WITH A COLUMN
----------------------------------------
Because they answer different questions and are opened by different people on
different days. *Done* is the receipt — what went out, to whom, for how much.
*Not done* is the worklist — and `BR-RBS-011` is why every row of it carries a
fix route: **a failure with no route is a defect in the runbook**, since a
finding a clerk cannot act on is a finding we should not have shown them.

⚠ **IT STREAMS AND NOTHING IS MATERIALISED.** A file with a page 2 is not a
file, so this is the one read in this module that is deliberately not paged —
which is exactly the shape `DEF-PAY-4221` describes, `GET /outstandings` being
unpaginated *"ON PURPOSE … one row per DEBTOR at a utility under 3,000
connections"* **and sorting in Python**. The difference is that `stream()` is a
generator over a queryset iterator: the peak memory is one row whatever the
tenant's size, so there is no cap on how many rows the file may carry (`NFR-5`)
and no `list(...)` waiting to become one at 40,000 accounts.

⚠ **NO UUID IS EVER WRITTEN INTO A CELL** (B14 rule 31 — *"no database id is
ever the visible value of a field"*, PO 2026-08-30: *"no Databse ID on screen -
that is a rule"*). A downloaded CSV is a screen: it is opened, read and printed
by the same clerk. So the **Subject** column carries the record's own LABEL —
`SubjectRef.label`, which `contract.SubjectRef` already declares and which a
record row carries in `data["label"]` — and where a runbook wrote none the cell
is EMPTY, with **Subject type** beside it saying what kind of thing it was.

⚠ **AND THAT EMPTY CELL IS A REAL GAP RATHER THAN A TIDY CHOICE, SO IT IS
NAMED.** No runbook writes a record row yet — `runbook_run_records` cannot be
written until `OQ-RBS-1737` says how `idempotency_key` is composed
(`DEF-RBS-4246`), and wave C's per-record evaluation is what will do it. **The
convention this file establishes is that the label travels in `data["label"]`,
taken from the `SubjectRef` the scope was pinned from.** A wave that writes
records without it produces a *not done* file whose rows a clerk cannot act on,
which is `BR-RBS-011` failing through a different door.

⚠ **NO RULE ID REACHES A CELL EITHER** (B14 rule 32). `decided_by_rule` holds
*"the rule that decided it, in words a clerk can read"* (`BR-RBS-010`) — the
column exists to carry a SENTENCE, and a runbook writing `BR-RBS-014` into it is
the defect, not this writer's problem to paper over.

⚠ **MONEY IS WRITTEN FROM THE `Decimal`, AT TWO DECIMALS, WITH ITS CURRENCY IN
ITS OWN COLUMN.** Hard rule 2: stored to 4, displayed at 2, `CHAR(3)` currency,
never a float. `str(Decimal)` would print the four stored decimals into a
clerk's spreadsheet; `float(...)` would be a hard-rule-2 breach and `G6` would
refuse the line. `quantize` at two is the display rule, applied at the one
moment this value becomes something a person reads.
"""

from __future__ import annotations

import csv
import io
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterator

#: The two words the path accepts, and the only two. A third answers 404 through
#: the URL pattern rather than serving an empty file that reads like a clean run.
FILE_NAMES = ("done", "not-done")

#: `07-endpoints.md` row 14 — *each row carrying its reason and its fix*. The
#: last two are the ones that rule names, and they are last so a clerk widening
#: one column widens the one they came for.
COLUMNS = (
    "Subject",
    "Subject type",
    "Planned",
    "Outcome",
    "Amount",
    "Currency",
    "Decided by",
    "Reason",
    "Fix",
)

#: Hard rule 2 — money DISPLAYS at two decimals. `ROUND_HALF_UP` because that is
#: what B4 rounds with everywhere else in this product; a writer that picked
#: banker's rounding here would disagree with the invoice the same figure came
#: from, by a cent, on some rows and not others.
_TWO_PLACES = Decimal("0.01")


def name(run_id: Any, done: bool) -> str:
    """The downloaded file's name: `runbook-run-<id>-done.csv`.

    ⚠ **THE ID IS IN THE FILENAME AND THAT IS NOT A RULE-31 BREACH.** Rule 31
    governs *the visible value of a FIELD* — a cell, a form input, a column.
    A filename is an ADDRESS: two runs of the same runbook on the same day would
    otherwise overwrite each other in a clerk's downloads folder, and a run has
    no natural key to use instead. The cells carry no id at all, which is where
    the rule bites.
    """
    return f"runbook-run-{run_id}-{'done' if done else 'not-done'}.csv"


def _money(amount: Any) -> str:
    """A `Decimal` at two decimals, or an empty cell. **Never a float.**"""
    if amount is None:
        return ""
    return str(Decimal(amount).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP))


def _row(record: Any) -> list[str]:
    """One line of the file. Every cell is a string and none of them is an id."""
    data = record.data or {}
    return [
        str(data.get("label") or ""),
        record.subject_type or "",
        record.planned_action or "",
        record.outcome or "",
        _money(record.amount),
        record.currency or "",
        record.decided_by_rule or "",
        record.reason or "",
        record.fix_route or "",
    ]


def stream(records: Any) -> Iterator[str]:
    """Header, then one line per record, yielded as the reader pulls them.

    ⚠ **`iterator()` IS THE WHOLE POINT AND A `for record in records` WOULD
    UNDO IT.** Django's default queryset iteration fills the result cache, so
    the whole run would be in memory before the second row reached the client —
    a generator wrapping a cached queryset streams the RESPONSE and not the
    QUERY, which looks identical from the outside and is exactly the failure
    this file's docstring says it avoids. `chunk_size` is left at Django's
    default rather than tuned; the guarantee wanted here is *bounded*, not
    *optimal*.

    ⚠ **THE `csv` WRITER HERE IS NOT LAW 11's FORBIDDEN ONE.** CLAUDE.md's rule
    is *never round-trip a shared REGISTER through a `csv` writer*, because
    re-serialising 1,900 rows is a whole-file write wearing the costume of an
    append. This writes a fresh download to a socket and reads no file at all.
    Stated because a reader greping for `import csv` deserves the distinction
    rather than a second's alarm.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS)
    yield _drain(buffer)
    for record in records.iterator():
        writer.writerow(_row(record))
        yield _drain(buffer)


def _drain(buffer: io.StringIO) -> str:
    """Take what the writer just produced and reset the buffer to empty."""
    value = buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)
    return value


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-003 (EP-RBS-01; CR-075 wave D task D1; 07-endpoints.md row 14 verbatim)
# generated: 2026-09-06 by the CR-075 wave D build lane
# checklist: A✔ B✔ C✔ D✔(two routes in api.py) E=deferred(no-frontend-half — RBS-006's Downloads block is wave C's DownloadsBlock and is built) F✔ G✔ H=n/a(no 🔒 path)
# gates: pytest tests/test_us_rbs_003_endpoints.py · G6 (no float on money) · G115 (the import census)
# exceptions: the two files are UNPAGED on purpose and stream instead — argued in the module docstring against DEF-PAY-4221's shape
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
