# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 round 6, lane SRV-5 — P6.3 (*"Print a work order"*) and
#           ruling 3's *"a day's pack prints"*. The brief: *"Find the repo's
#           existing print or PDF path (bills and statements print). Reuse it."*
# Rules:    B14 rule 43 (one piece of code, not a copy per door) · B1 (another
#           module never reaches into billing's internals — it calls THIS
#           published file by name, through its own seam) · BR-BIL-026/033
#           untouched (nothing here renders, pins or rounds a bill)
# Tests:    06-backend/tests/test_cr168_srv5_print.py
# Impacts:  apps/work/seams/billing_seam.py (the one caller) ·
#           apps/billing/documents.py (READ ONLY — its page engine is reused,
#           not changed; `test_us_bil_022` proves the bill's bytes did not move)
# ───────────────────────────────────────────────────────
"""Billing's PAGE ENGINE, published for another module's printed page.

WHY BILLING PUBLISHES THIS RATHER THAN WORK WRITING A SECOND PDF WRITER
────────────────────────────────────────────────────────────────────────────
The product has ONE PDF writer: `documents.py`, which hand-writes the PDF
container with the standard library (no PDF dependency — its own docstring
holds the argument, and adding one is a deployment-image decision, not a
lane's). It is built from four pieces that know nothing about bills — a row of
placed text (`PageRow`, `PageCell`, `PageRule`), a measured break into pages
(`_pdf_pages`), one page's content stream with its footer (`_pdf_page_stream`)
and the file container (`_pdf_file`). A work order and a technician's day are
rows of text too.

A second writer in `apps/work` would be the copy B14 rule 43 forbids: two
places that can disagree about the font, the margin, a character the page
cannot encode, or the byte-stability a reprint depends on. Reaching into
`documents.py`'s underscore names from Work would be the cross-module reach B1
forbids. So billing publishes the four pieces HERE, by name, unchanged, and
Work calls this file through `apps/work/seams/billing_seam.py`.

⚠ **NOTHING HERE TOUCHES A BILL.** No money is formatted or rounded, no pin is
read, and `documents.py` is not edited — this file only re-exports. A bill
renders byte-for-byte as before (`test_us_bil_022` tc12).

TWO THINGS A CALLER GETS THAT A BILL DOES NOT NEED
────────────────────────────────────────────────────────────────────────────
* **Sections that each start a page.** A day's pack is a cover list and then
  one work order per sheet; a technician hands a customer THEIR sheet. So
  `render` takes a list of sections and breaks each with the bill's own
  measured break, then numbers the whole file *Page n of N*.
* **What the page could not print, named.** The Base-14 fonts are WinAnsi; a
  name in Vietnamese prints `?` for the characters it cannot encode, and the
  result says which characters — the posture `documents._pdf` takes (OQ-150's
  ruling: *"print a substitution"*).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from apps.billing import documents as _engine

# ── the vocabulary, re-exported unchanged ───────────────────────────────────
PageRow = _engine.PageRow
PageCell = _engine.PageCell
PageRule = _engine.PageRule

PAGE_WIDTH = _engine.PAGE_WIDTH
PAGE_HEIGHT = _engine.PAGE_HEIGHT
PAGE_MARGIN = _engine.PAGE_MARGIN
PAGE_RIGHT = _engine.PAGE_RIGHT
CONTENT_WIDTH = _engine.CONTENT_WIDTH

FONT_REGULAR = _engine.FONT_REGULAR
FONT_BOLD = _engine.FONT_BOLD
FONT_ITALIC = _engine.FONT_ITALIC

SIZE_TITLE = _engine.SIZE_UTILITY
SIZE_BODY = _engine.SIZE_BODY
SIZE_SMALL = _engine.SIZE_SMALL
SIZE_LABEL = _engine.SIZE_LABEL
SIZE_SECTION = _engine.SIZE_SECTION

INK = _engine.INK
MUTED = _engine.MUTED
FAINT = _engine.FAINT
HAIRLINE = _engine.HAIRLINE

LEAD_BODY = _engine.LEAD_BODY
LEAD_TIGHT = _engine.LEAD_TIGHT
LEAD_SECTION = _engine.LEAD_SECTION
LEAD_GAP = _engine.LEAD_GAP

ABSENT_MARK = _engine.ABSENT_MARK


def wrap(text: str, width: float, *, bold: bool = False, size: float = SIZE_BODY) -> list[str]:
    """Break `text` to `width` POINTS, measured — the bill's own wrap."""
    return _engine._wrap(text, width, FONT_BOLD if bold else FONT_REGULAR, size)


def text_width(text: str, *, bold: bool = False, size: float = SIZE_BODY) -> float:
    """How wide `text` prints, in points."""
    return _engine.text_width(text, FONT_BOLD if bold else FONT_REGULAR, size)


@dataclass(frozen=True)
class PrintedPages:
    """The file, how many sheets it is, and every character it could not print."""

    data: bytes
    page_count: int
    characters: tuple[str, ...] = ()


def render(sections: Iterable[list[PageRow]], *, footer: str) -> PrintedPages:
    """Rows → a PDF. Each section starts a fresh page; pages are numbered
    across the whole file; `footer` is printed on every sheet.

    Deterministic, like the bill: no clock, no `/Info` dates, a content hash for
    `/ID` — the same order printed twice is the same bytes.
    """
    pages: list[list[tuple[PageRow, float]]] = []
    for section in sections:
        pages.extend(page for page in _engine._pdf_pages(list(section)) if page)
    if not pages:
        pages = [[]]
    streams: list[bytes] = []
    lost: list[str] = []
    for index, page in enumerate(pages, start=1):
        stream, missing = _engine._pdf_page_stream(
            page, page_no=index, page_count=len(pages), footer=footer
        )
        streams.append(stream)
        lost.extend(missing)
    return PrintedPages(
        data=_engine._pdf_file(streams, len(pages)),
        page_count=len(pages),
        characters=tuple(sorted(set(lost))),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §5.8 P6.3 · §7.3 (`GET /work-orders/{id}/print`, `GET /work/print/day-pack`)
# generated: 2026-10-04 by CR-168 round 6 lane SRV-5
# checklist: A✔ B✔ C✔ D=n/a(no HTTP surface — Work serves the routes) E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr168_srv5_print.py · tests/test_us_bil_022_documents.py
# status: AI-AUTHORED
# ──────────────────────────────────────────────────────────
