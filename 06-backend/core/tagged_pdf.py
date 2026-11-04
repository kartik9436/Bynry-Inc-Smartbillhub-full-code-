# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-10546 (portal accessibility F-06 — every customer PDF fails
#           PDF/UA-1: no structure tree, no /Lang, no DisplayDocTitle, fonts
#           not embedded)
# Ruling:   decision log 2026-10-23, "Portal accessibility, Group H (bill PDF,
#           F-06): tagged PDFs through a PDF library, Liberation Sans, new
#           documents only, every customer PDF" — PO/QA verbatim *"1 … B … 2 …
#           A. Liberation Sans … 3 … A. New bills only. The old ones stay as
#           issued.; 4 … A. Everything a customer receives"*
# Rules:    CLAUDE.md hard rule 4 (an issued document is write-once; this file
#           makes bytes and stores nothing) · B4/BR-RAT-003 (money is rounded
#           for display BEFORE it reaches here — this file never sees a number)
# Tests:    06-backend/tests/test_def_bil_f06_tagged_pdf.py
# Impacts:  apps/billing/documents.py (the bill, final bill and statement) ·
#           apps/customers/agreement_pdf.py (the agreement, sent and stamped)
# ───────────────────────────────────────────────────────
"""HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-10-23 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). It is on the bill's
document path (money display, frozen documents), so it carries the same marker
as `apps/billing/documents.py`; row in `12-governance/09-human-review-ledger.md`.

THE ONE TAGGED-PDF RENDERER. A document's HTML serialisation in, a PDF/UA-1
tagged PDF out.

WHY HERE. `core/` holds what every module shares and owns no table. Billing
(the bill) and customers (the agreement) both call it; neither may import the
other's renderer for this (B2 §2 — the agreement used to borrow billing's
`page_print` by name, which was the hand-written Base-14 engine).

WHAT IT GUARANTEES, AND REFUSES TO RETURN WITHOUT
-------------------------------------------------
WeasyPrint (`pdf_variant="pdf/ua-1"`) writes the structure tree from the HTML:
headings become `H1`/`H2`, tables become `Table`/`TH`/`TD` with `scope` honoured,
`<img alt>` becomes a `Figure` with `/Alt`, borders and backgrounds become
artifacts, and the reading order is the document order. This module adds:

  * **the font.** Liberation Sans, embedded and subset by WeasyPrint, from the
    four files in `core/fonts/liberation/` (SIL OFL 1.1, licence beside them).
    It is declared under a family name nothing on the host can also answer to
    (`FONT_FAMILY`) and forced on every element, so a system font can never be
    picked instead — the host's fontconfig is not consulted for the face.
  * **the characters the font cannot draw.** Liberation Sans has no Devanagari,
    Japanese or Korean glyphs (nor did the Base-14 fonts the old writers used).
    Left alone, Pango would FALL BACK to whatever other font the host carries,
    which is a second font the PO ruled out (Group H item 2) and a page that
    differs between hosts. So every character outside the font's own cmap is
    replaced by `UNREPRESENTABLE_MARK` before layout and named on the result —
    exactly the old writers' OQ-150 posture (*"print a substitution"*, PO
    2026-08-12), so those languages are no worse than before. The gap is filed
    as a defect rather than patched with another font.
  * **a refusal instead of an untagged file.** After rendering, the catalogue is
    checked for `/StructTreeRoot`, a non-empty `/Lang`, `/DisplayDocTitle true`,
    a `/Title`, and no unembedded font. A file missing any of them raises
    `TaggedPdfError` rather than being returned, so the caller's render fails
    (for a bill: BR-BIL-033, the bill stays a correctable draft) instead of an
    inaccessible document being kept write-once for seven years.

DETERMINISM. The same HTML renders the same bytes: no creation or modification
date is written (WeasyPrint writes them only from `<meta name=dcterms.*>`, which
no serialisation here emits), and `/ID` is passed explicitly as a hash of the
input, never left to the library. `tests/test_def_bil_f06_tagged_pdf.py` asserts
two renders are byte-identical.

WHAT IT COSTS. Measured in this container on 2026-10-23 (median of 5 renders of
the Ann Arbor-like sample bill): see the decision log entry for this build. A
bill run renders each bill once, at issue.
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

#: The four Liberation Sans faces, shipped with the source tree (the image
#: copies `core/` whole — see `06-backend/Dockerfile`).
FONT_DIR = Path(__file__).resolve().parent / "fonts" / "liberation"
FONT_FILES = {
    ("normal", "normal"): "LiberationSans-Regular.ttf",
    ("bold", "normal"): "LiberationSans-Bold.ttf",
    ("normal", "italic"): "LiberationSans-Italic.ttf",
    ("bold", "italic"): "LiberationSans-BoldItalic.ttf",
}

#: A family name no host font answers to, so fontconfig cannot substitute.
FONT_FAMILY = "SBH Liberation Sans"

#: What a character the font cannot draw prints as — the old writers' mark.
UNREPRESENTABLE_MARK = "?"

PDF_VARIANT = "pdf/ua-1"


class TaggedPdfError(Exception):
    """The renderer produced a file that is not the tagged PDF it promises."""


@dataclass(frozen=True)
class TaggedPdf:
    """A tagged PDF and what it could not show."""

    data: bytes
    page_count: int
    #: Characters replaced by `UNREPRESENTABLE_MARK`, deduplicated and sorted.
    characters: tuple[str, ...] = ()


@lru_cache(maxsize=1)
def _font_css() -> str:
    faces = []
    for (weight, style), name in FONT_FILES.items():
        path = FONT_DIR / name
        faces.append(
            f'@font-face{{font-family:"{FONT_FAMILY}";src:url("{path.as_uri()}");'
            f"font-weight:{weight};font-style:{style}}}"
        )
    # `!important` on every element: the documents' own stylesheets name
    # Archivo/Helvetica/Arial for the SCREEN, and on paper the ruling is one face.
    faces.append(f'*{{font-family:"{FONT_FAMILY}" !important}}')
    return "".join(faces)


@lru_cache(maxsize=1)
def _cmap() -> frozenset[int]:
    """Every code point all four faces can draw (their intersection)."""
    from fontTools.ttLib import TTFont

    common: set[int] | None = None
    for name in FONT_FILES.values():
        with TTFont(str(FONT_DIR / name), lazy=True) as font:
            points = set(font.getBestCmap())
        common = points if common is None else common & points
    return frozenset(common or ())


#: Characters that never need a glyph: line breaks, tabs, joiners and marks the
#: layout engine consumes rather than draws.
_INVISIBLE = frozenset({0x09, 0x0A, 0x0D, 0x200B, 0x200C, 0x200D, 0xFEFF})


def representable(html: str) -> tuple[str, tuple[str, ...]]:
    """`html` with every character the font cannot draw replaced, and the list.

    Markup is ASCII and every ASCII printable is in the font, so only text and
    attribute values (a title, an alt text) can carry a missing character, and
    both should show the same mark the page shows.
    """
    cmap = _cmap()
    lost: set[str] = set()

    def fix(match: re.Match[str]) -> str:
        char = match.group(0)
        if ord(char) in cmap or ord(char) in _INVISIBLE:
            return char
        lost.add(char)
        return UNREPRESENTABLE_MARK

    cleaned = re.sub(r"[^\x00-\x7f]", fix, html)
    return cleaned, tuple(sorted(lost))


_STREAM_HEAD = re.compile(rb"(?:(\d+) 0 obj\s*)?<<((?:(?!endobj).)*?)>>\s*stream\r?\n", re.S)


def _streams(data: bytes):
    """Yield `(object number or None, raw stream bytes)` for every stream.

    Sliced by the stream's own `/Length`, never by searching for `endstream`:
    a compressed stream may itself end in a CR byte, and a regex that eats an
    optional CR before `endstream` then cuts the stream one byte short — which
    loses a page's text without an error (found on the first run of the parity
    test, where a bill's second page came back empty).
    """
    for head in _STREAM_HEAD.finditer(data):
        length = re.search(rb"/Length\s+(\d+)(?!\s+\d+\s+R)", head.group(2))
        start = head.end()
        if length:
            raw = data[start : start + int(length.group(1))]
        else:
            end = data.find(b"endstream", start)
            raw = data[start:end].rstrip(b"\r\n") if end != -1 else b""
        number = int(head.group(1)) if head.group(1) else None
        yield number, raw


def _decoded(raw: bytes) -> bytes | None:
    import zlib

    try:
        return zlib.decompress(raw)
    except zlib.error:
        return None


def inflated(data: bytes) -> bytes:
    """The file with every Flate stream's contents appended, inflated.

    WeasyPrint packs the catalogue and most dictionaries into compressed object
    streams, so a plain byte search of the file finds none of the markers this
    module checks — a check that would REFUSE EVERY CORRECT FILE, or, written
    the other way round, pass every broken one. Inflating every stream and
    searching the result is the whole file's dictionaries, in any order.
    """
    parts = [data]
    for _number, raw in _streams(data):
        decoded = _decoded(raw)
        if decoded is not None:
            parts.append(decoded)
    return b"\n".join(parts)


_TYPE0 = re.compile(rb"/BaseFont\s*/([A-Z]{6})\+[^<>]*?/ToUnicode\s+(\d+) 0 R", re.S)
_TYPE0_REV = re.compile(rb"/ToUnicode\s+(\d+) 0 R[^<>]*?/BaseFont\s*/([A-Z]{6})\+", re.S)


def _unicode_maps(data: bytes) -> dict[bytes, dict[int, str]]:
    """`{font resource name: {glyph code: text}}` from each font's ToUnicode."""
    streams: dict[int, bytes] = {}
    for number, raw in _streams(data):
        if number is not None:
            streams[number] = _decoded(raw) or raw
    text = inflated(data)
    refs = {m.group(1): int(m.group(2)) for m in _TYPE0.finditer(text)}
    refs.update({m.group(2): int(m.group(1)) for m in _TYPE0_REV.finditer(text)})
    maps: dict[bytes, dict[int, str]] = {}
    for tag, ref in refs.items():
        cmap: dict[int, str] = {}
        body = streams.get(ref, b"")
        for block in re.findall(rb"beginbfchar(.*?)endbfchar", body, re.S):
            for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
                cmap[int(src, 16)] = bytes.fromhex(dst.decode()).decode("utf-16-be")
        for block in re.findall(rb"beginbfrange(.*?)endbfrange", body, re.S):
            for lo, hi, dst in re.findall(
                rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block
            ):
                start = int(dst, 16)
                for offset, code in enumerate(range(int(lo, 16), int(hi, 16) + 1)):
                    cmap[code] = chr(start + offset)
        maps[tag] = cmap
    return maps


def text_of(data: bytes) -> str:
    """Every string a tagged PDF from this module draws, in draw order,
    whitespace-collapsed — page furniture included.

    For tests and the a11y script: WeasyPrint writes text as glyph codes
    (`Identity-H`) and this maps them back through each font's own ToUnicode
    CMap, which is also exactly what a screen reader and a copy-paste rely on —
    so text that comes out wrong here is text a reader would get wrong too.
    """
    maps = _unicode_maps(data)
    drawn: list[str] = []
    for _number, raw in _streams(data):
        content = _decoded(raw)
        if content is None or b" Tf" not in content or b"begincmap" in content:
            continue
        font: dict[int, str] = {}
        for op in re.finditer(
            rb"/([A-Za-z0-9]+)\s+[\d.]+\s+Tf|\[((?:<[0-9A-Fa-f]*>|[-\d.\s])*)\]\s*TJ|<([0-9A-Fa-f]*)>\s*Tj",
            content,
        ):
            if op.group(1) is not None:
                font = maps.get(op.group(1), {})
                continue
            hexes = re.findall(rb"<([0-9A-Fa-f]*)>", op.group(2) or b"") if op.group(2) is not None else [op.group(3)]
            run = []
            for chunk in hexes:
                for index in range(0, len(chunk), 4):
                    run.append(font.get(int(chunk[index : index + 4], 16), ""))
            drawn.append("".join(run))
    return " ".join(" ".join(drawn).split())


def _string(text: bytes, key: bytes) -> str | None:
    """The first `/Key (literal)` or `/Key <hex>` string, decoded."""
    match = re.search(rb"/" + key + rb"\s*(?:\(((?:\\.|[^\\)])*)\)|<([0-9A-Fa-f\s]*)>)", text)
    if not match:
        return None
    if match.group(2) is not None:
        raw = bytes.fromhex(match.group(2).decode("ascii").replace(" ", ""))
        if raw.startswith(b"\xfe\xff"):
            return raw[2:].decode("utf-16-be", errors="replace")
        return raw.decode("latin-1")
    raw = re.sub(rb"\\(.)", rb"\1", match.group(1))
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="replace")
    return raw.decode("latin-1")


def markers(data: bytes) -> dict[str, object]:
    """The PDF/UA markers a reader can check without a validator."""
    text = inflated(data)
    # The DOCUMENT's title is the one in the Info dictionary (the one carrying
    # /Producer) — not the first /Title in the file, which is an outline entry
    # (every heading becomes a bookmark with its own /Title).
    info = re.search(rb"<<(?:(?!<<|>>).)*?/Producer(?:(?!<<|>>).)*?>>", text, re.S)
    return {
        "struct_tree_root": b"/StructTreeRoot" in text,
        "lang": _string(text, b"Lang"),
        "display_doc_title": bool(re.search(rb"/DisplayDocTitle\s+true", text)),
        "title": _string(info.group(0), b"Title") if info else None,
        "embedded_fonts": bool(re.search(rb"/FontFile[23]?\b", text)),
        "base14_fonts": bool(
            re.search(rb"/BaseFont\s*/(Helvetica|Times|Courier|Symbol|ZapfDingbats)", text)
        ),
        "marked": bool(re.search(rb"/Marked\s+true", text)),
        "pages": len(re.findall(rb"/Type\s*/Page(?![s\w])", text)),
    }


def _check(data: bytes) -> int:
    """Refuse a file that lacks the PDF/UA markers. Returns the page count."""
    found = markers(data)
    problems = []
    if not found["struct_tree_root"]:
        problems.append("no structure tree")
    if not (found["lang"] or "").strip():
        problems.append("no /Lang")
    if not found["display_doc_title"]:
        problems.append("DisplayDocTitle is not true")
    if not (found["title"] or "").strip():
        problems.append("no /Title")
    if found["base14_fonts"]:
        problems.append("an unembedded Base-14 font")
    if not found["embedded_fonts"]:
        problems.append("no embedded font program")
    if problems:
        raise TaggedPdfError("the tagged PDF is incomplete: " + ", ".join(problems))
    return int(found["pages"])


#: The moment written into a subset font's `head.modified` when the subset is
#: made by fontTools. 2026-10-23 00:00 UTC — a fixed point, never "now".
FONT_TIMESTAMP = "1792713600"

_CLOCK_LOCK = threading.Lock()


@contextmanager
def _no_clock():
    """Keep the wall clock out of the file.

    ⚠ FOUND BY THE DETERMINISM TEST, NOT BY READING: two renders of one bill
    differed by one byte. WeasyPrint subsets each font with HarfBuzz when the
    host has `libharfbuzz-subset0` (the image does — see the Dockerfile) and
    falls back to fontTools when it does not, and fontTools stamps the subset's
    `head.modified` with the current second. fontTools reads the reproducible-
    builds variable `SOURCE_DATE_EPOCH` instead when it is set, so it is set,
    for the duration of a render, when the process has not set it already.
    """
    with _CLOCK_LOCK:
        previous = os.environ.get("SOURCE_DATE_EPOCH")
        if previous is None:
            os.environ["SOURCE_DATE_EPOCH"] = FONT_TIMESTAMP
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop("SOURCE_DATE_EPOCH", None)


def _footer_css(footer: str) -> str:
    """The page furniture the hand-written writers drew on every page:
    `<footer text>` at the left, `Page n of N` at the right. Margin boxes are
    left out of the structure tree by WeasyPrint, which is right for furniture
    a screen reader should not read on every page."""
    text = footer.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    style = f'font-family:"{FONT_FAMILY}";font-size:7.5pt;color:#97918e'
    return (
        f'@page{{@bottom-left{{content:"{text}";{style}}}'
        f'@bottom-right{{content:"Page " counter(page) " of " counter(pages);{style}}}}}'
    )


def render(html: str, *, footer: str | None = None) -> TaggedPdf:
    """The HTML as a tagged PDF/UA-1 file.

    The HTML must declare `<html lang="…">` and a `<title>`: they become the
    document's `/Lang` and `/Title`, and the file is refused without them.
    `footer` is the text printed at the foot of every page beside its number.
    """
    from weasyprint import CSS, HTML
    from weasyprint.text.fonts import FontConfiguration

    cleaned, lost = representable(html)
    css = _font_css()
    if footer:
        footer_text, footer_lost = representable(footer)
        css += _footer_css(footer_text)
        lost = tuple(sorted(set(lost) | set(footer_lost)))
    fonts = FontConfiguration()
    stylesheet = CSS(string=css, font_config=fonts)
    identifier = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:32].encode("ascii")
    with _no_clock():
        data = HTML(string=cleaned, base_url=str(FONT_DIR)).write_pdf(
            stylesheets=[stylesheet],
            font_config=fonts,
            pdf_variant=PDF_VARIANT,
            pdf_identifier=identifier,
            uncompressed_pdf=False,
        )
    pages = _check(data)
    return TaggedPdf(data=data, page_count=pages, characters=lost)


__all__ = [
    "FONT_FAMILY",
    "TaggedPdf",
    "TaggedPdfError",
    "UNREPRESENTABLE_MARK",
    "render",
    "representable",
]
