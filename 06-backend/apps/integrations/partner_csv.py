# ── Trace ──────────────────────────────────────────────
# Story:    CR-111-BRC04 — `format=csv` on /bills, /payments and /accounts
#           (`/customers` until `DEF-INT-5623`, 2026-09-17).
# Rules:    NFR-3 (universal server pagination — no unpaginated list, ever) ·
#           NFR-5 (no hard caps anywhere) · B6 (no code path may enforce a
#           maximum account count per tenant) · CLAUDE.md hard rule 2 (money
#           is text, never a float) · BR-INT-044 (the refusal is the same
#           bytes every time)
# Tests:    06-backend/tests/test_cr111_partner_csv.py
# Impacts:  apps/integrations/partner_api.py (the one caller)
# ───────────────────────────────────────────────────────
"""The same page, as CSV — generated from the SAME records, never a second query.

WHAT THIS IS
-------------
`&format=csv` on `/partner/v1/bills`, `/partner/v1/payments` and
`/partner/v1/accounts`. A finance system that would rather load a file than
parse JSON gets one, and gets **exactly the rows the JSON would have given it**.

    records ──► shapes.apply_records ──► render()  ──►  text/csv
                                    └──► JsonResponse

⚠ **ONE QUERY, ONE PAGE, TWO SERIALISATIONS — AND THE ALTERNATIVE IS WHAT MAKES
THIS WORTH SAYING.** The obvious build is a second view with its own queryset,
and then `?format=csv` and the JSON call drift: a filter fixed in one, an order
changed in the other, and a partner reconciling the two finds rows in one that
are not in the other. `partner_api` composes the page ONCE, shapes it ONCE, and
hands the same list to this renderer or to `JsonResponse`. There is no queryset
in this file and no import that could produce one.

⚠ **PAGED EXACTLY AS THE JSON IS — `NFR-3`, AND THE BREACH IT IS AVOIDING HAS A
NAME.** `GET /outstandings` is unpaginated *on purpose*, documented as *"one row
per DEBTOR at a utility under 3,000 connections"*, and it sorts in Python rather
than SQL: correct at T7 and **13× short of T5**, which is `DEF-PAY-4221`. A CSV
export is exactly where that mistake gets made a second time, because *"it's a
download, they want all of it"* is so reasonable. **It is not offered here at
any size.** 40,000 accounts is forty calls of a thousand, the same forty the
JSON takes, and a partner that wants one file concatenates forty bodies —
dropping the header row of all but the first, which the headers below let them
do without parsing anything.

⚠ **THE COUNTS MOVE TO HEADERS BECAUSE A CSV BODY HAS NO ENVELOPE.**

    X-Total-Records   what `total_records` says in the JSON
    X-Page            what `page` says
    X-Total-Pages     what `total_pages` says

A partner loops until `X-Page == X-Total-Pages` and checks the rows it received
against `X-Total-Records`, which is the same check the JSON envelope invites and
is what turns *did I reach the end* into arithmetic rather than a guess. ⚠ They
are the **native** names and are NOT re-keyed by the shape: a shape re-keys a
PAYLOAD, and these are transport metadata on a response whose body is a table.
A partner reading `X-Total-Records` reads the same header whichever dialect its
key selects, which is one fewer thing to get wrong.

⚠ **THE HEADER ROW IS THE SAME FIELD NAMES AS THE JSON, WHICH MEANS THE SHAPED
ONES.** A key whose shape renames `id` to `invoiceNo` gets a column called
`invoiceNo`. The two serialisations of one page therefore name every field
identically, and a partner can move between them without a mapping table —
which is the whole reason the header row exists rather than being optional.

ONE ROW PER BILL, OR `&rows=lines` FOR ONE ROW PER LINE
--------------------------------------------------------
A bill is nested and a CSV is flat, so something has to give. The default is
**one row per bill** with the line detail left out, because that is what the
JSON record's own top level says and because a finance system importing a
receivable wants one row per document. `&rows=lines` gives **one row per line,
with its GL code**, each carrying its bill's identifying columns so a row stands
on its own.

⚠ **`&rows=lines` DOES NOT CHANGE THE PAGE, AND THAT IS THE TRAP IT AVOIDS.**
The page is still a page of BILLS — `X-Total-Records` still counts bills, and
page 3 holds the lines of the same thousand bills page 3 of the JSON holds. If
the page were a page of LINES, the two serialisations would page differently
over the same window and a partner comparing them would find neither the same
rows nor the same count. The CSV body simply has more rows than the page has
records, and `X-Total-Records` says so by disagreeing with the row count — which
is honest and is why the header is named `Records` rather than `Rows`.

⚠ **A VALUE IS WRITTEN AS IT ARRIVES.** Money is already a string with four
decimals (hard rule 2, and JSON's one numeric type is binary floating point);
dates are already spelled in the shape's format; a `null` is an EMPTY CELL and
never the four letters `None`, which a spreadsheet would import as a word. A
nested value that survived shaping is written as compact JSON in the cell rather
than flattened, so nothing is lost and nothing is invented.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

#: The query value that asks for this. ⚠ **ONE SPELLING.** `csv`, lower case,
#: and nothing else — no `CSV`, no `text/csv`, no `.csv` suffix on the path. A
#: second accepted spelling is two names for one thing (`DEF-014`), and on a
#: surface where an unrecognised value falls back to JSON it is worse than that:
#: a partner sending `CSV` would silently receive JSON and parse it as a table.
FORMAT_CSV = "csv"

#: The header names. Native on every dialect — see the module docstring.
HEADER_TOTAL_RECORDS = "X-Total-Records"
HEADER_PAGE = "X-Page"
HEADER_TOTAL_PAGES = "X-Total-Pages"

CONTENT_TYPE = "text/csv; charset=utf-8"

#: `&rows=lines` — one row per bill LINE. Anything else, including absent, is
#: one row per record.
ROWS_LINES = "lines"

#: Which key holds a bill's lines. Named once: `partner_csv` does not know what
#: a bill is, and a shape may rename this key, so the caller says which key to
#: expand rather than this file guessing (`shapes.INVOICE_CLOUD` omits `lines`
#: entirely, and then there is nothing to expand and the default applies).
DEFAULT_LINES_KEY = "lines"


def wants_csv(raw: Any) -> bool:
    """Is this request asking for CSV? Exact, lower case, nothing clever."""
    return str(raw or "").strip() == FORMAT_CSV


def wants_line_rows(raw: Any) -> bool:
    """Is this request asking for one row per LINE?"""
    return str(raw or "").strip() == ROWS_LINES


def _cell(value: Any) -> str:
    """One value → one cell.

    `None` is an empty cell, not `"None"`. A bool is `true`/`false` rather than
    Python's `True`/`False`, so a partner's importer reads the same words it
    reads in the JSON. A list or mapping that survived shaping is compact JSON,
    which keeps the value recoverable — flattening it here would be composing.
    Everything else is `str()`, and money is already a string by the time it
    reaches this file.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (Mapping, list, tuple)):
        return json.dumps(value, separators=(",", ":"), default=str)
    return str(value)


def columns_for(records: Sequence[Mapping[str, Any]]) -> list[str]:
    """The header row: every key any record on this page carries, in
    first-appearance order.

    ⚠ **THE UNION AND NOT THE FIRST RECORD'S KEYS.** A record may legitimately
    carry a key its neighbour does not — `records_note` on the ledger, a field a
    shape omitted for one row and not another — and taking the first record's
    keys would drop it from the whole page. First-appearance rather than sorted,
    so the column order matches the order the JSON record reads in, which is the
    seam's own order and is stable between calls.

    ⚠ **AN EMPTY PAGE IS AN EMPTY HEADER, AND THAT IS HONEST.** With no records
    there is no way to know what the columns would have been without asking the
    seam, which is a second query. A partner receives a body of zero bytes and
    `X-Total-Records: 0`, which says everything a header row would have.
    """
    seen: dict[str, None] = {}
    for record in records:
        for name in record:
            seen.setdefault(name, None)
    return list(seen)


def _expanded(
    records: Sequence[Mapping[str, Any]], *, lines_key: str
) -> list[dict[str, Any]]:
    """One row per LINE, each carrying its bill's own columns.

    A bill with no lines still produces ONE row — the bill's own columns with
    the line columns empty. ⚠ **DROPPING IT WOULD BE DECIDING WHICH ROWS COME
    BACK**, which is the door's job and not a renderer's, and a partner whose
    row count disagreed with `X-Total-Records` by exactly the number of
    line-less bills would have no way to find out why.

    A line's own keys are prefixed `line_` so a line's `id` cannot collide with
    the bill's, which would silently overwrite the bill's identity on every row.
    """
    rows: list[dict[str, Any]] = []
    for record in records:
        head = {name: value for name, value in record.items() if name != lines_key}
        lines = record.get(lines_key)
        if not isinstance(lines, (list, tuple)) or not lines:
            rows.append(dict(head))
            continue
        for line in lines:
            row = dict(head)
            if isinstance(line, Mapping):
                for name, value in line.items():
                    row[f"line_{name}"] = value
            else:  # pragma: no cover — a line is always a mapping
                row["line_value"] = line
            rows.append(row)
    return rows


def render(
    records: Sequence[Mapping[str, Any]],
    *,
    rows: str | None = None,
    lines_key: str = DEFAULT_LINES_KEY,
) -> str:
    """The page, as CSV text. **The records are already shaped; this only
    writes them.**

    `\\r\\n` line endings, which is what RFC 4180 says and what every
    spreadsheet and every `csv` reader expects; `QUOTE_MINIMAL`, so a cell is
    quoted when it holds a comma, a quote or a newline and is left alone
    otherwise.
    """
    table = (
        _expanded(records, lines_key=lines_key) if wants_line_rows(rows) else [dict(one) for one in records]
    )
    columns = columns_for(table)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    if columns:
        writer.writerow(columns)
        for row in table:
            writer.writerow([_cell(row.get(name)) for name in columns])
    return buffer.getvalue()


def paging_headers(*, total_records: int, page: int, total_pages: int) -> dict[str, str]:
    """The three headers that carry what the JSON envelope carries.

    ⚠ **THE SAME NUMBERS THE JSON ENVELOPE WOULD HAVE CARRIED, PASSED IN RATHER
    THAN RECOMPUTED.** `partner_api` computes `total_records` and `total_pages`
    once for the page and hands them to whichever serialiser answers, so the two
    cannot disagree. Recomputing them here from `len(records)` is the obvious
    shortcut and it is wrong on every page but the last.
    """
    return {
        HEADER_TOTAL_RECORDS: str(total_records),
        HEADER_PAGE: str(page),
        HEADER_TOTAL_PAGES: str(total_pages),
    }


__all__ = [
    "CONTENT_TYPE",
    "DEFAULT_LINES_KEY",
    "FORMAT_CSV",
    "HEADER_PAGE",
    "HEADER_TOTAL_PAGES",
    "HEADER_TOTAL_RECORDS",
    "ROWS_LINES",
    "columns_for",
    "paging_headers",
    "render",
    "wants_csv",
    "wants_line_rows",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-111-BRC04 (PO rulings of 2026-09-17, verbatim in the CR)
# generated: 2026-09-17 by the CR-111-BRC04 Invoice Cloud lane
# checklist: A✔ B=n/a(no screen — this is a partner payload) C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_cr111_partner_csv.py
# exceptions: this module imports no model, no queryset and no Django — it is
#   handed a list of already-shaped dicts, which is what makes "the same records
#   as the JSON, never a second query" structural rather than a claim
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
