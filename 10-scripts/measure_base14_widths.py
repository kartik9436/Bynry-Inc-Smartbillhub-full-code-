#!/usr/bin/env python3
"""MEASURE the Base-14 advance widths the bill's PDF sets its type on.

WHY THIS EXISTS AND WHY IT IS NOT A COMMENT
--------------------------------------------
`06-backend/apps/billing/documents.py` writes the printed bill with the standard
library and no PDF dependency, and until 2026-09-07 it set every line in
COURIER — fixed pitch, so a column position was integer arithmetic on characters
and no font metrics were needed at all. That is why the page looked like
terminal output, which is `DEF-BIL-4524`.

Setting it in Helvetica needs an advance-width table, and `documents.py`'s own
module docstring had already named the risk, as its reason for rejecting
ReportLab: *"a font-metric table to transcribe and get subtly wrong"*. It is
exactly right. A wrong width for `1` moves every money column on every bill by a
hair; nothing in this repo reads rendered output (hard-won law 6), so nothing
would ever report it.

**So the table was not typed in. It was measured, and this is the measurement.**
It draws eight copies of each WinAnsi character at 100pt, reads back the word
box a PDF text layer reports for that run, and divides. The reader used is
`pdftotext` (poppler), which carries the standard Base-14 metrics — so the
number that comes back IS the AFM advance, obtained rather than believed.

⚠ **IT PRINTS THE LITERAL `documents.py` HOLDS.** Re-run it and diff; that is
the check, and it is why this is a script in the repo instead of a paragraph
saying the numbers were verified once (law 1).

VERIFY, DON'T TRUST — the script checks itself before it prints
----------------------------------------------------------------
Per-character measurement can go wrong quietly (a word box that merged two
lines, a character the reader drops). So `--check` measures four whole STRINGS
independently and compares each against the sum of the per-character widths. On
2026-09-07 all four agreed to the hundredth of a point:

    'Brazos Bend Utilities'        measured=922.50   computed=922.50
    'Total due 22 Aug 2026'        measured=1011.80  computed=1011.80
    '1,234.56 USD'                 measured=628.10   computed=628.10
    'Service period 1 Jul … 31 Jul 2026'  measured=1756.50  computed=1756.50

USAGE
-----
    python3 10-scripts/measure_base14_widths.py            # print both literals
    python3 10-scripts/measure_base14_widths.py --check    # prove them first

Requires `pdftotext` (poppler-utils). It writes only into a temporary directory.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys
import tempfile
from collections import defaultdict

#: The Base-14 faces `documents.py` names. Helvetica-Oblique shares Helvetica's
#: advances (it is the same outlines sheared), so it needs no third table.
FONTS = (b"Helvetica", b"Helvetica-Bold")

#: cp1252's own re-mapping of the C1 range. WinAnsiEncoding is cp1252, so a
#: character like `—` is byte 0x97 on the page and not its Unicode code point.
CP1252 = {
    0x20AC: 0x80,
    0x201A: 0x82,
    0x0192: 0x83,
    0x201E: 0x84,
    0x2026: 0x85,
    0x2020: 0x86,
    0x2021: 0x87,
    0x02C6: 0x88,
    0x2030: 0x89,
    0x0160: 0x8A,
    0x2039: 0x8B,
    0x0152: 0x8C,
    0x017D: 0x8E,
    0x2018: 0x91,
    0x2019: 0x92,
    0x201C: 0x93,
    0x201D: 0x94,
    0x2022: 0x95,
    0x2013: 0x96,
    0x2014: 0x97,
    0x02DC: 0x98,
    0x2122: 0x99,
    0x0161: 0x9A,
    0x203A: 0x9B,
    0x0153: 0x9C,
    0x017E: 0x9E,
    0x0178: 0x9F,
}

#: Every character a bill can print. The space is measured separately (a reader
#: reports words, so a run of spaces has no box of its own).
CHARS = (
    [chr(c) for c in range(33, 127)]
    + [chr(c) for c in range(161, 256)]
    + list("‘’“”–—•…†‰€™ŠŒŽšœžŸƒ‹›„‚ˆ˜")
)

REPS = 8
SIZE = 100.0
SPACING = 140
ROWS_PER_PAGE = 34


def _byte(character: str) -> int:
    return CP1252.get(ord(character), ord(character))


def _pdf(font: bytes, pages: list[list[str]]) -> bytes:
    """A probe PDF: one row per character, `REPS` copies of it, at `SIZE`pt."""
    streams: list[bytes] = []
    for page in pages:
        ops = []
        y = 5000
        for character in page:
            body = bytes([_byte(character)]) * REPS
            escaped = (
                body.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
            )
            ops.append(b"BT /F1 %d Tf 60 %d Td (%s) Tj ET\n" % (int(SIZE), y, escaped))
            y -= SPACING
        streams.append(b"".join(ops))
    count = len(streams)
    first_page, first_stream = 4, 4 + count
    kids = " ".join(f"{first_page + i} 0 R" for i in range(count)).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, count),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>"
        % font,
    ]
    for index in range(count):
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 2000 5200] /Resources "
            b"<< /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % (first_stream + index)
        )
    for stream in streams:
        objects.append(
            b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)
        )
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(b"%d 0 obj\n%s\nendobj\n" % (number, body))
    xref = len(out)
    out.extend(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.extend(b"%010d 00000 n \n" % offset)
    out.extend(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, xref)
    )
    return bytes(out)


def _boxes(pdf: bytes, workdir: pathlib.Path) -> list[list[tuple[float, float, float]]]:
    """Every word box the reader reports, grouped per page and ordered down the page."""
    path = workdir / "probe.pdf"
    path.write_bytes(pdf)
    xml = subprocess.run(
        ["pdftotext", "-bbox", str(path), "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    pages = []
    for page in xml.split("<page ")[1:]:
        rows: dict[float, list[tuple[float, float]]] = defaultdict(list)
        for x0, y0, x1, _y1, _text in re.findall(
            r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>',
            page,
            re.S,
        ):
            rows[round(float(y0), 1)].append((float(x0), float(x1)))
        pages.append(
            [
                (min(x for x, _ in r), max(x for _, x in r), 0.0)
                for _, r in sorted(rows.items())
            ]
        )
    return pages


def measure(font: bytes) -> dict[str, float]:
    """The advance of every printable character, in 1/1000 em."""
    usable = [c for c in CHARS if _byte(c) <= 255]
    pages = [
        usable[i : i + ROWS_PER_PAGE] for i in range(0, len(usable), ROWS_PER_PAGE)
    ]
    with tempfile.TemporaryDirectory() as tmp:
        boxes = _boxes(_pdf(font, pages), pathlib.Path(tmp))
    widths: dict[str, float] = {}
    for page, page_boxes in zip(pages, boxes):
        if len(page) != len(page_boxes):
            raise SystemExit(
                f"{font.decode()}: the reader returned {len(page_boxes)} rows for "
                f"{len(page)} characters — the measurement is not trustworthy"
            )
        for character, (x0, x1, _) in zip(page, page_boxes):
            widths[character] = round((x1 - x0) / REPS / SIZE * 1000)
    # The space has no word box of its own — a reader reports WORDS — so it is
    # measured as the gap a run of them opens between two characters that do.
    widths[" "] = float(_space(font))
    return widths


def _space(font: bytes) -> int:
    """The space advance, as the gap ten of them open between two `M`s."""

    def run(text: str) -> tuple[float, float]:
        body = text.encode("cp1252")
        escaped = (
            body.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
        )
        stream = b"BT /F1 100 Tf 60 500 Td (%s) Tj ET\n" % escaped
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [4 0 R] /Count 1 >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>"
            % font,
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 4000 900] /Resources "
            b"<< /Font << /F1 3 0 R >> >> /Contents 5 0 R >>",
            b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        ]
        out = bytearray(b"%PDF-1.4\n")
        offsets = []
        for number, body_ in enumerate(objects, start=1):
            offsets.append(len(out))
            out.extend(b"%d 0 obj\n%s\nendobj\n" % (number, body_))
        xref = len(out)
        out.extend(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
        for offset in offsets:
            out.extend(b"%010d 00000 n \n" % offset)
        out.extend(
            b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objects) + 1, xref)
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "p.pdf"
            path.write_bytes(bytes(out))
            xml = subprocess.run(
                ["pdftotext", "-bbox", str(path), "-"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
        found = re.findall(r'<word xMin="([\d.]+)" yMin="[\d.]+" xMax="([\d.]+)"', xml)
        return float(found[0][0]), float(found[-1][1])

    spaced = run("M" + " " * 10 + "M")
    tight = run("MM")
    return round(((spaced[1] - spaced[0]) - (tight[1] - tight[0])) / 10 / SIZE * 1000)


def string_width(text: str, table: dict[str, float], size: float) -> float:
    return sum(table.get(c, 556.0) for c in text) * size / 1000.0


def check(tables: dict[bytes, dict[str, float]]) -> int:
    """Measure four whole strings and compare each with the per-character sum."""
    samples = [
        "Brazos Bend Utilities",
        "Total due 22 Aug 2026",
        "1,234.56 USD",
        "Service period 1 Jul 2026 – 31 Jul 2026",
    ]
    bad = 0
    for font, table in tables.items():
        for sample in samples:
            measured = _whole(font, sample)
            computed = string_width(sample, table, SIZE)
            agree = abs(measured - computed) < 0.05
            bad += 0 if agree else 1
            print(
                f"  {font.decode():16} {sample!r:45} measured={measured:9.2f} "
                f"computed={computed:9.2f} {'ok' if agree else 'DISAGREE'}"
            )
    return bad


def _whole(font: bytes, text: str) -> float:
    """One whole string's width, straight off the reader."""
    body = text.encode("cp1252")
    escaped = body.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    stream = b"BT /F1 100 Tf 60 500 Td (%s) Tj ET\n" % escaped
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [4 0 R] /Count 1 >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>"
        % font,
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 6000 900] /Resources "
        b"<< /Font << /F1 3 0 R >> >> /Contents 5 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body_ in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(b"%d 0 obj\n%s\nendobj\n" % (number, body_))
    xref = len(out)
    out.extend(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.extend(b"%010d 00000 n \n" % offset)
    out.extend(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, xref)
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "w.pdf"
        path.write_bytes(bytes(out))
        xml = subprocess.run(
            ["pdftotext", "-bbox", str(path), "-"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    found = re.findall(r'<word xMin="([\d.]+)" yMin="[\d.]+" xMax="([\d.]+)"', xml)
    return float(found[-1][1]) - float(found[0][0])


def literal(name: str, widths: dict[str, float]) -> str:
    """The grouped `{advance: characters}` mapping `documents.py` holds."""
    groups: dict[int, list[str]] = defaultdict(list)
    for character, advance in sorted(widths.items(), key=lambda kv: ord(kv[0])):
        groups[int(advance)].append(character)
    lines = [f"{name} = _widths(", "    {"]
    for advance in sorted(groups):
        text = "".join(groups[advance]).replace("\\", "\\\\")
        quote = "'" if '"' in text else '"'
        if quote == "'":
            text = text.replace("'", "\\'")
        lines.append(f"        {advance}: {quote}{text}{quote},")
    lines += ["    }", ")"]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="prove the table on whole strings"
    )
    args = parser.parse_args(argv)
    tables = {font: measure(font) for font in FONTS}
    if args.check:
        print("verifying the per-character table against whole strings:")
        bad = check(tables)
        if bad:
            print(f"{bad} disagreement(s) — do NOT paste this table", file=sys.stderr)
            return 1
        print("all agree\n")
    print(literal("HELVETICA_WIDTHS", tables[b"Helvetica"]))
    print()
    print(literal("HELVETICA_BOLD_WIDTHS", tables[b"Helvetica-Bold"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
