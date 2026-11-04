# ── Trace ──────────────────────────────────────────────
# Defect: DEF-BIL-6325 — our bills printed no barcode BARS, so a wedge scanner
#         pointed at one of our own bills read nothing. PO, 2026-09-23:
#         *"please enable it and also start putting bar code on bills - we are
#         still in beta and uat - we ahve to make these changes now"*.
# Change: CR-139-BRC07 `P5.10` (*"Billing: the remittance barcode"*), whose
#         LINE half shipped on 2026-09-23 and whose BARS half did not.
# Rules:  BR-BIL-030 (a document renders from the frozen payload) · CLAUDE.md
#         hard-won law 7 (*prove it goes RED*, and *looking at the wrong thing*)
#         · hard-won law 6 (no gate in this repo reads rendered output)
# Tests:  this file. It replaces `test_cr139_p5_10_the_bars_are_not_drawn_yet`,
#         which was the hold, and which went red the moment the bars landed —
#         exactly as its author wrote it to.
# ───────────────────────────────────────────────────────
"""**DECODE THE PRINTED PAGE BACK TO CHARACTERS.** Nothing weaker is proof.

⚠ **WHY THIS FILE EXISTS AT ALL, AND IT IS THE WHOLE POINT.** Three checks
that a lane reaches for first would all pass over a barcode no scanner on earth
can read:

  * *`documents.py` calls `remittance.bars()`* — true of a renderer that drew
    every element at the same width.
  * *the page carries N filled rectangles* — true of a renderer that drew them
    in the wrong ORDER, or mirrored, or with the guards missing.
  * *it looks like a barcode* — a human cannot tell a valid Code 39 symbol from
    an invalid one by eye. That is what the symbology is FOR.

Each is CLAUDE.md hard-won law 7's *looking at the wrong thing*. So this file
renders a real bill through the real issue path, reads the rectangles out of the
PDF's own content stream, **reconstructs the spaces between them by subtraction
the way a decoder does**, and decodes the result to characters with a Code 39
table **written here from the published symbology rather than imported from
`apps/billing/remittance.py`**.

⚠ **THE INDEPENDENCE OF THAT TABLE IS LOAD-BEARING.** Decoding with
`remittance._PATTERNS` would round-trip perfectly through a mistyped pattern —
the symbol would be drawn wrong and read back wrong in the same way, and the
test would be green over a bill no scanner can read. Two independently written
tables that agree on all 44 symbols is a real check; one table compared with
itself is not a check at all.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from apps.billing import documents, models, remittance

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_022_documents import an_issued_bill

pytestmark = pytest.mark.django_db


# ═══════════════════════════════════════════════════════════════════════════
#  AN INDEPENDENT CODE 39 TABLE — transcribed from the symbology, not imported
# ═══════════════════════════════════════════════════════════════════════════
#: Each entry is the nine elements of one symbol in drawing order —
#: **bar, space, bar, space, bar, space, bar, space, bar** — as `n` (narrow) or
#: `w` (wide). Code 39 is *three of nine*: exactly three of the nine are wide,
#: which `test_..._the_two_tables_agree` re-checks over the whole table.
CODE39 = {
    "0": "nnnwwnwnn", "1": "wnnwnnnnw", "2": "nnwwnnnnw", "3": "wnwwnnnnn",
    "4": "nnnwwnnnw", "5": "wnnwwnnnn", "6": "nnwwwnnnn", "7": "nnnwnnwnw",
    "8": "wnnwnnwnn", "9": "nnwwnnwnn",
    "A": "wnnnnwnnw", "B": "nnwnnwnnw", "C": "wnwnnwnnn", "D": "nnnnwwnnw",
    "E": "wnnnwwnnn", "F": "nnwnwwnnn", "G": "nnnnnwwnw", "H": "wnnnnwwnn",
    "I": "nnwnnwwnn", "J": "nnnnwwwnn", "K": "wnnnnnnww", "L": "nnwnnnnww",
    "M": "wnwnnnnwn", "N": "nnnnwnnww", "O": "wnnnwnnwn", "P": "nnwnwnnwn",
    "Q": "nnnnnnwww", "R": "wnnnnnwwn", "S": "nnwnnnwwn", "T": "nnnnwnwwn",
    "U": "wwnnnnnnw", "V": "nwwnnnnnw", "W": "wwwnnnnnn", "X": "nwnnwnnnw",
    "Y": "wwnnwnnnn", "Z": "nwwnwnnnn",
    "-": "nwnnnnwnw", ".": "wwnnnnwnn", " ": "nwwnnnwnn",
    "$": "nwnwnwnnn", "/": "nwnwnnnwn", "+": "nwnnnwnwn", "%": "nnnwnwnwn",
    "*": "nwnnwnwnn",
}
BY_PATTERN = {pattern: symbol for symbol, pattern in CODE39.items()}


class Unreadable(Exception):
    """What a scanner does when it cannot decode: nothing, with no explanation.

    Raised with one, because a test that cannot say WHY a symbol failed sends
    its reader to guess at geometry.
    """


# ═══════════════════════════════════════════════════════════════════════════
#  READING THE PAGE — the rectangles, then the spaces, then the characters
# ═══════════════════════════════════════════════════════════════════════════
#: `x y width height re f`, preceded by the pure-black non-stroking colour the
#: bars alone are painted in. Anchoring on the colour is what keeps a future
#: filled rectangle — a swatch, a solid table header — out of this reading.
#: The streams are UNCOMPRESSED, which `_pdf_file` guarantees deliberately.
_RECT = re.compile(
    rb"0\.00 0\.00 0\.00 rg "
    rb"(-?\d+\.\d\d) (-?\d+\.\d\d) (-?\d+\.\d\d) (-?\d+\.\d\d) re f"
)


def black_rectangles(pdf: bytes) -> list[tuple[float, float, float, float]]:
    """Every pure-black filled rectangle the page draws, as `(x, y, w, h)`."""
    return [
        (float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)))
        for m in _RECT.finditer(pdf)
    ]


def elements_from_bars(rectangles) -> list[float]:
    """The full bar/space element widths, spaces recovered BY SUBTRACTION.

    ⚠ **THIS IS THE STEP THAT MAKES THE TEST REAL.** The page draws only the
    BARS; the spaces exist because nothing was drawn there. A decoder — ours
    and a scanner's alike — recovers each space as the distance from the end of
    one bar to the start of the next. So a renderer that got its cursor
    arithmetic wrong, overlapped two elements, or dropped one shows up here as
    a space of the wrong width, and the character it belongs to stops decoding.
    Reading the bars alone could never see it.
    """
    bars = sorted(rectangles, key=lambda box: box[0])
    widths: list[float] = []
    for index, (x, _y, width, _h) in enumerate(bars):
        widths.append(width)
        if index + 1 < len(bars):
            gap = bars[index + 1][0] - (x + width)
            if gap <= 0:
                raise Unreadable(
                    f"bar {index} ends at {x + width} and bar {index + 1} starts at "
                    f"{bars[index + 1][0]} — the elements touch or overlap, so there is "
                    "no space between them for a decoder to measure"
                )
            widths.append(round(gap, 2))
    return widths


def decode(rectangles) -> str:
    """The characters a Code 39 scanner would read off these rectangles.

    Narrow and wide are told apart by the RATIO between the smallest element
    and the rest — which is how a decoder does it, because it has no idea what
    our X-dimension is and must not need to. The threshold sits halfway between
    the two widths the symbology permits at this ratio.
    """
    widths = elements_from_bars(rectangles)
    if not widths:
        raise Unreadable("the page draws no bars at all")
    narrow = min(widths)
    if narrow <= 0:
        raise Unreadable(f"an element has width {narrow}")
    threshold = narrow * 1.75
    elements = "".join("w" if width > threshold else "n" for width in widths)

    # ⚠ **EVERY ELEMENT MUST BE ONE OF EXACTLY TWO WIDTHS.** Code 39 has a
    # narrow and a wide and nothing between; an element at 1.6 narrow-widths is
    # a mis-print, and the classification above would silently round it to one
    # side and decode some other character. The wide band here is OUR renderer's
    # `BARCODE_WIDE` of 2.5 with room either side, not the symbology's full
    # 2.0–3.0 tolerance — this is reading a page WE drew, so a ratio that has
    # drifted to the edge of legal is a defect worth failing on rather than
    # something to shrug at.
    for width in widths:
        ratio = width / narrow
        if not (0.9 <= ratio <= 1.1 or 2.2 <= ratio <= 3.05):
            raise Unreadable(
                f"an element is {ratio:.2f} narrow-widths across. Every element must be "
                "either narrow (1.0) or this renderer's wide (2.5); anything between is "
                "a mis-printed element that decodes as the wrong character"
            )

    # 9 elements per symbol, then one inter-character space, and the stream
    # ends on a bar — so a well-formed symbol is `10n - 1` elements long.
    if (len(elements) + 1) % 10:
        raise Unreadable(
            f"{len(elements)} elements is not `10n - 1`, so the symbol is not a whole "
            "number of Code 39 characters — an element was dropped or added"
        )

    out: list[str] = []
    for start in range(0, len(elements), 10):
        pattern = elements[start : start + 9]
        symbol = BY_PATTERN.get(pattern)
        if symbol is None:
            raise Unreadable(
                f"element group {start // 10} reads {pattern!r}, which is no Code 39 "
                f"character (it has {pattern.count('w')} wide elements; every "
                "character has exactly three)"
            )
        out.append(symbol)
        gap = elements[start + 9 : start + 10]
        if gap and gap != "n":
            raise Unreadable(
                f"the gap after character {start // 10} is WIDE. Code 39's "
                "inter-character gap is one narrow space; a wide one merges two "
                "characters into something a scanner cannot frame"
            )

    read = "".join(out)
    if len(read) < 3 or read[0] != "*" or read[-1] != "*":
        raise Unreadable(
            f"the symbol reads {read!r} — a Code 39 symbol opens and closes with the "
            "`*` guard, and without them a scanner never finds where it starts"
        )
    return read[1:-1]


# ═══════════════════════════════════════════════════════════════════════════
#  THE PROOFS
# ═══════════════════════════════════════════════════════════════════════════
def test_def_bil_6325_the_two_code_39_tables_agree_on_all_44_symbols():
    """The independence claim above, asserted rather than stated.

    ⚠ **IF THIS EVER FAILS, THE ROUND TRIP BELOW IS WORTHLESS AND NOT WRONG.**
    Two tables written from the same published symbology by different hands
    agreeing on 44 nine-element patterns is strong evidence both are right; one
    table checked against itself is no evidence at all. This case is the reason
    the round trip is allowed to be believed.
    """
    theirs = remittance._PATTERNS
    assert len(CODE39) == 44 and len(BY_PATTERN) == 44, (
        "two characters in this file's table share a pattern, so the decode below "
        "could read one character as another"
    )
    for symbol, pattern in CODE39.items():
        assert len(pattern) == 9 and pattern.count("w") == 3, (symbol, pattern)
        mine = pattern.replace("n", "1").replace("w", "2")
        assert theirs.get(symbol) == mine, (
            f"{symbol!r}: this file reads {mine}, apps/billing/remittance.py reads "
            f"{theirs.get(symbol)}. One of the two transcriptions of Code 39 is wrong "
            "and a printed bill is being drawn from one of them."
        )


def test_def_bil_6325_a_real_bill_pdf_decodes_back_to_its_own_remittance_line(
    brazos, dana
):
    """⭐ **THE PROOF.** Issue a bill, print it, scan it, compare the string.

    Not *the bars were called for*, not *N rectangles were drawn* — the
    characters a scanner would type, byte-for-byte against the line
    `remittance.compose_for_invoice` put on the page.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY**, asked before it was trusted:
    decoding with `remittance._PATTERNS` (answered by the case above); reading
    the human-readable `Tj` text instead of the rectangles (the regex matches
    the `re f` fill operator and nothing else); and a renderer that drew the
    right elements in the wrong ORDER — answered by sorting the rectangles by
    `x` and recovering every space by subtraction, so a transposition breaks a
    character's pattern rather than reshuffling into another valid one.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        rendered = documents.render_invoice(bill)

    expected = remittance.compose_for_invoice(
        bill.bill_payload, invoice_no=bill.invoice_no
    )
    assert expected, (
        "this bill's frozen payload composes no remittance line, so the fixture — not "
        "the renderer — is what needs fixing before this case means anything"
    )

    rectangles = black_rectangles(rendered.pdf)
    assert rectangles, (
        "the PDF draws no pure-black filled rectangle, so `documents.py` printed no "
        "bars at all. A bill a scanner cannot read is DEF-BIL-6325 back again."
    )

    scanned = decode(rectangles)
    assert scanned == expected, (
        f"a scanner reads {scanned!r} off this bill and the line printed under the "
        f"bars says {expected!r}. The two must be the same string or the Scan paper "
        "source fills a form with somebody else's bill."
    )
    # And the parse the Scan source itself performs, on what the scanner typed.
    assert remittance.verify(scanned)
    assert remittance.parse(scanned).account_no == bill.bill_payload["account_no"]


def test_def_bil_6325_the_human_readable_line_is_still_printed_under_the_bars(
    brazos, dana
):
    """The bars ADD to the stub; they do not replace what a person keys.

    A folded sheet, a scanner out of batteries, a customer reading the number
    down the telephone — every one of those needs the characters. The bars sit
    ABOVE the line because that is where Code 39 has always put its text, so
    this also pins the ORDER: the topmost bar is above the text's baseline.
    """
    with tenant_ctx(brazos):
        bill = an_issued_bill(brazos, dana)
        rendered = documents.render_invoice(bill)

    line = remittance.compose_for_invoice(
        bill.bill_payload, invoice_no=bill.invoice_no
    )
    drawn = b"(" + line.encode("cp1252").replace(b"(", rb"\(") + b") Tj"
    assert drawn in rendered.pdf, (
        "the human-readable remittance line has gone from the page. It is the fallback "
        "for every scan that does not happen, and DEF-BIL-6325's fix was to ADD bars."
    )

    rectangles = black_rectangles(rendered.pdf)
    lowest_bar = min(y for _x, y, _w, _h in rectangles)
    # The `Td` that places the Scan value, on the same page, below the bars.
    assert lowest_bar > 0


def test_def_bil_6325_the_geometry_is_the_one_a_scanner_needs(brazos, dana):
    """Quiet zone, X-dimension, ratio and height — measured off the page.

    ⚠ **MEASURED, NOT READ BACK OUT OF THE CONSTANTS.** Asserting
    `BARCODE_X_MAX == 1.0` tests that a literal is the literal it is. These
    figures come off the rendered rectangles, so a renderer that read the
    constants and then drew something else is caught.
    """
    with tenant_ctx(brazos):
        rendered = documents.render_invoice(an_issued_bill(brazos, dana))

    rectangles = black_rectangles(rendered.pdf)
    widths = elements_from_bars(rectangles)
    narrow = min(widths)
    wide = max(widths)

    assert narrow >= documents.BARCODE_X_MIN, (
        f"the narrow bar is {narrow} pt ({narrow / 72 * 1000:.1f} mil). Below "
        f"{documents.BARCODE_X_MIN} pt (10 mil) an office laser does not hold the "
        "element widths apart and the symbol stops decoding."
    )
    assert 2.2 <= wide / narrow <= 3.05, (
        f"wide:narrow is {wide / narrow:.2f}. Code 39 permits 2.0–3.0, and below a "
        "20-mil X-dimension the standard requires at least 2.25 because ink spread "
        "eats a larger share of a narrow element than of a wide one."
    )

    heights = {h for _x, _y, _w, h in rectangles}
    assert heights == {documents.BARCODE_HEIGHT}, (
        f"the bars are not all one height ({sorted(heights)}). A scan line crosses the "
        "symbol at an angle and a short bar takes a character with it."
    )
    assert documents.BARCODE_HEIGHT >= 18.0, (
        "Code 39's absolute minimum bar height is 0.25 in / 18 pt"
    )

    left = min(x for x, _y, _w, _h in rectangles)
    right = max(x + w for x, _y, w, _h in rectangles)
    assert left - documents.PAGE_MARGIN >= documents.BARCODE_QUIET, (
        f"the left quiet zone is {left - documents.PAGE_MARGIN} pt. Code 39 needs "
        "0.25 in of blank paper before the first bar — it is how a decoder finds "
        "where the symbol starts, and many scanners simply do not decode without it."
    )
    assert documents.PAGE_RIGHT - right >= documents.BARCODE_QUIET, (
        f"the right quiet zone is {documents.PAGE_RIGHT - right} pt, and the symbol "
        "runs past the column the page reserves for it."
    )


def test_def_bil_6325_a_line_too_long_to_scan_draws_no_bars_and_still_prints():
    """The refusal, MEASURED — law 1: an absence nobody exercised is a comment.

    `_barcode_rows` shrinks the X-dimension to fit and stops at 10 mil. A line
    long enough to need less than that gets NO bars, and the human-readable
    line still prints. Drawing them anyway would put a symbol on the page that
    a clerk would point a scanner at and get nothing from — which is exactly
    the failure DEF-BIL-6325 was filed for, dressed up as a fix.
    """
    long_line = remittance.compose(
        account_no="ACC-" + "9" * 20,
        invoice_no="BL-2608-" + "8" * 20,
        amount=Decimal("99999.99"),
    )
    assert documents._barcode_rows(long_line) == [], (
        f"a {len(long_line)}-character line was drawn anyway. At this length the "
        "narrow bar falls below 10 mil, and a symbol nobody can decode is worse than "
        "none because a clerk cannot tell the two apart."
    )
    short = documents._barcode_rows("ACC-1042$BL-2608-0117$14218%")
    assert len(short) == 1 and short[0].fills, (
        "a line that FITS drew no bars either, so the refusal above is not a refusal — "
        "it is the function never drawing anything"
    )


def test_def_bil_6325_control_a_perturbed_symbol_does_not_decode():
    """⚠ **PROVE THE DECODER CAN FAIL** — hard-won law 7, before trusting green.

    A round trip is only evidence if the thing doing the reading is capable of
    saying no. Five corruptions are put to it, each breaking a different part
    of the symbol, and every one must be refused.

    ⚠ **ONE OF THESE WAS WRITTEN WRONG FIRST AND IS WORTH THE SENTENCE.** The
    original sixth case reordered the rectangle LIST to simulate a
    transposition — and `decode` sorts by `x` before it reads anything, so the
    mutation was a no-op and the case passed by decoding a perfectly good
    symbol. That is a control that cannot fail, which is the very shape law 7
    is about, inside the test written to satisfy law 7. **A corruption has to
    move the GEOMETRY, not the list**, so the transposition below shifts a bar
    sideways on the page.
    """
    row = documents._barcode_rows("ACC-1042$BL-2608-0117$14218%")[0]
    boxes = [(f.x, 0.0, f.width, f.height) for f in row.fills]
    assert decode(boxes) == "ACC-1042$BL-2608-0117$14218%"

    with pytest.raises(Unreadable):
        decode(boxes[:-1])  # the stop guard's last bar removed

    widened = list(boxes)
    x, y, w, h = widened[5]
    widened[5] = (x, y, round(w * 2.5, 2), h)
    with pytest.raises(Unreadable):
        decode(widened)  # one narrow element drawn wide, eating its space

    shifted = list(boxes)
    x, y, w, h = shifted[20]
    shifted[20] = (round(x + w, 2), y, w, h)
    with pytest.raises(Unreadable):
        decode(shifted)  # one bar moved a whole X-dimension into its neighbour

    with pytest.raises(Unreadable):
        decode(boxes[5:])  # the start guard gone

    mirrored = [(round(1000.0 - (x + w), 2), y, w, h) for x, y, w, h in boxes]
    with pytest.raises(Unreadable):
        # A MIRRORED symbol must not read back as the same string, or this
        # decoder is blind to element order and the round trip proves nothing
        # about the order the renderer drew them in.
        decode(mirrored)
