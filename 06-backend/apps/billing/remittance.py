# ── Trace ──────────────────────────────────────────────
# Change:   CR-139-BRC07 — the payments blueprint's phase 5, task `P5.10`.
#           Verbatim: *"Billing: the remittance barcode. On the three-to-five
#           standard layouts, carrying account, invoice, amount and a check
#           digit. **No schema change** — it is drawn from the bill's existing
#           payload."* Outcome: *"Without it a scanner reads nothing. Which is
#           why it ships in this phase."* Reference `documents.py:111` ·
#           `OQ-149` (CLOSED 2026-08-12).
# Story:    no story — the consumer is `P5.8`, the Scan source on 4·3a, and it
#           is another lane's. **This is the half `P5.8` cannot invent.**
# Rules:    BR-BIL-030 (a document renders from `invoices.bill_payload` and the
#           invoice's own rows — it never joins back to master data) · BR-BIL-036
#           · CLAUDE.md hard rule 2 (money is a Decimal; the payload carries
#           MINOR UNITS so no decimal separator can be read two ways) ·
#           hard-won law 1 (the absence below is registered, not commented) ·
#           hard-won law 2 (`P5.8` is the consumer; a payload nothing scans is
#           dead weight, and the row that names it is in the phase 5 board)
# Tests:    06-backend/tests/test_cr139_p5_remittance.py
# Impacts:  apps/billing/documents.py (`_stub` prints the line; the STUB is the
#           only place on the page it may appear) · the `P5.8` scan input,
#           which parses exactly what `compose()` writes
# ───────────────────────────────────────────────────────
"""The remittance line a scanner reads — **and a scanner is a keyboard.**

WHY THIS IS A MODULE AND NOT TWENTY LINES INSIDE `documents.py`
-----------------------------------------------------------------
**Two halves of this live in different modules and they must agree exactly.**
Billing PRINTS the line; payments' Scan source (`P5.8`) READS it back and fills
a form from it. A composer written inside the renderer would leave the reader
with a format to re-derive by eye, and the day the two disagreed the symptom
would be a clerk scanning a bill and getting somebody else's account.

So the grammar, the check character and the verification are one file, and both
sides import it. `P5.8` calls `parse()`; nothing about the string is guessed at
the other end.

⚠ **"A SCANNER IS A KEYBOARD" IS THE WHOLE DESIGN, AND IT IS THE BLUEPRINT'S
OWN SENTENCE** (`P5.8`: *"A focused input behind the Scan paper card on Extract
— a scanner is a keyboard. Everything after it is the runner."*). A hand-held
barcode scanner is an HID device: it decodes the bars and TYPES the decoded
characters, then presses Enter. Nothing in this product ever sees an image.
**So the artefact that crosses between the two modules is a STRING**, and
getting the string right is the whole of the interoperability problem.

THE GRAMMAR
-----------
    <account>$<invoice>$<amount in minor units><check>

Three fields, `$` between them, one check character at the end. Worked, on a
bill for **$142.18**:

    ACC-1042$BL-2608-0117$14218    →  payload
                                %  →  the mod-43 check character
    ACC-1042$BL-2608-0117$14218%   →  what the scanner types

⚠ **THAT CHECK CHARACTER IS COMPUTED, NOT CHOSEN, AND THIS DOCSTRING FIRST SAID
`Y`.** It was written before the function existed and was wrong; the test asserts
the computed value, so the worked example above is now the code's own answer
rather than a plausible one. A worked figure nothing recomputes is a comment
claiming a guarantee (hard-won law 1).

⚠ **THE AMOUNT IS IN MINOR UNITS AND CARRIES NO SEPARATOR.** `14218`, never
`142.18`. A decimal point is a character two locales read two ways and a
scanner's keyboard layout can substitute; an integer of cents cannot be
misread, and `CLAUDE.md` hard rule 2's *display 2* is a rendering rule about
what a person sees, not about what a machine carries.

⚠ **`$` IS THE SEPARATOR BECAUSE CODE 39 HAS IT AND NOTHING ELSE USES IT.** The
Code 39 repertoire is `0-9 A-Z - . SPACE $ / + %` and **`*` is the start/stop
character**, so it can never appear inside a payload. Account and invoice
numbers in this product use letters, digits and `-`; a space would be eaten by
some scanner configurations and `.` appears in amounts people type. `$` is
present in the symbology, absent from every identifier the product mints, and
obvious to a human reading the line under the bars.

THE CHECK CHARACTER IS **MOD 43**, NOT LUHN, AND THE REASON IS THE ALPHABET
-----------------------------------------------------------------------------
Luhn (mod 10) is the reflex and it is wrong here: it is defined over DIGITS and
this payload carries letters. Mod 43 is Code 39's own standard check character
— sum the values of every character in the 43-symbol alphabet, take the
remainder modulo 43, and the symbol at that index is the check. It is what a
scanner configured to verify one will compute, which means **a mis-scan can
fail at the scanner as well as at our end**.

⚠ **IT CATCHES A SINGLE SUBSTITUTION ALWAYS, AND A TRANSPOSITION SOMETIMES —
SAID PLAINLY BECAUSE THE SECOND HALF IS USUALLY LEFT OUT.** A positional-sum
check is blind to two characters swapping places when their values are equal
modulo 43, which for a two-character swap means *always* for this scheme: it is
an UNWEIGHTED sum. So `AB` and `BA` carry the same check character. That is the
real Code 39 standard and we do not "improve" it, because a non-standard check
character is one no scanner in the world can verify — but `P5.8` must not be
written as though a good check digit means a good read.

WHAT IS HERE AND WHAT IS NOT — READ THIS BEFORE CALLING IT DONE
------------------------------------------------------------------
  * **HERE:** the payload, the check character, `parse`, `verify`, and
    `bars()` — the black/white module-width sequence Code 39 defines for the
    payload, which is the complete specification of the printed symbol.
  * ⚠ **THE BARS ARE NOW DRAWN — `DEF-BIL-6325`, 2026-09-23.** This entry read
    *"NOT HERE: the bars are not yet DRAWN on the page"* until the PO said
    *"please enable it and also start putting bar code on bills - we are still
    in beta and uat"*. `documents.py` grew a `PageFill` primitive, and
    `_barcode_rows` draws this function's output on the remittance stub of
    every layout that has one. **The hold test that guarded this sentence went
    red on the day it landed, exactly as its author wrote it to**, and is
    replaced by `tests/test_def_bil_6325_barcode_round_trip.py` — which renders
    a real bill, reads the rectangles out of the PDF's own content stream and
    **decodes them back to characters with a Code 39 table written
    independently of the one above**. Nothing weaker is proof that a symbol
    scans: *the function was called* and *N rectangles were drawn* are both
    true of a barcode no scanner can read.
  * **STILL NOT HERE: the HTML serialisation draws no bars.** The PDF is
    `BR-BIL-036`'s print floor and is what a tenant prints; the HTML is the
    other frozen serialisation and carries the human-readable line only. That
    is `DEF-BIL-6340`, filed rather than commented.
  * **AND WHAT `P5.8` NEEDS IS HERE IN FULL.** A scanner types the payload; the
    Scan source parses it with `parse()` and checks it with `verify()`. Neither
    needs a bar to exist. What the missing bars cost is that a clerk cannot
    scan **our own** printed bill yet — a real gap, on the paper, and named.

NO SCHEMA CHANGE, AND NO JOIN EITHER
-------------------------------------
`P5.10` says *"no schema change — it is drawn from the bill's existing
payload"*, and `BR-BIL-030` is the stronger rule underneath it: the document
renders from `invoices.bill_payload` and the invoice's own rows and **never
joins back to master data**. So `compose_for_invoice` takes the payload dict and
the invoice's own columns and reaches nothing else. A renderer that went and
found a missing account number would rewrite an issued financial document by
reading.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

#: Code 39's full 43-symbol alphabet, IN ITS STANDARD ORDER. The order is the
#: standard — index IS the character's value — so this tuple may not be sorted,
#: tidied or re-spelled.
ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-. $/+%"

#: Code 39's start and stop character. It is NOT in `ALPHABET` and never
#: appears inside a payload, which is what makes the framing unambiguous.
GUARD = "*"

#: The field separator. See the module docstring: present in Code 39, absent
#: from every identifier this product mints.
SEPARATOR = "$"

#: Every symbol's nine elements as widths, `1` narrow and `2` wide, in
#: bar/space/bar/space… order starting with a BAR. Code 39 is "three of nine":
#: exactly three of the nine elements are wide in every symbol.
#:
#: ⚠ **THIS TABLE IS THE STANDARD AND IS NOT DERIVED.** A generated version
#: would be shorter and would be one transcription error away from a symbol no
#: scanner recognises, with nothing in this repository able to tell.
_PATTERNS: dict[str, str] = {
    "0": "111221211",
    "1": "211211112",
    "2": "112211112",
    "3": "212211111",
    "4": "111221112",
    "5": "211221111",
    "6": "112221111",
    "7": "111211212",
    "8": "211211211",
    "9": "112211211",
    "A": "211112112",
    "B": "112112112",
    "C": "212112111",
    "D": "111122112",
    "E": "211122111",
    "F": "112122111",
    "G": "111112212",
    "H": "211112211",
    "I": "112112211",
    "J": "111122211",
    "K": "211111122",
    "L": "112111122",
    "M": "212111121",
    "N": "111121122",
    "O": "211121121",
    "P": "112121121",
    "Q": "111111222",
    "R": "211111221",
    "S": "112111221",
    "T": "111121221",
    "U": "221111112",
    "V": "122111112",
    "W": "222111111",
    "X": "121121112",
    "Y": "221121111",
    "Z": "122121111",
    "-": "121111212",
    ".": "221111211",
    " ": "122111211",
    "$": "121212111",
    "/": "121211121",
    "+": "121112121",
    "%": "111212121",
    GUARD: "121121211",
}


class RemittanceError(ValueError):
    """A line that cannot be composed, or one that came back wrong.

    Refuses rather than composing something shorter (`PaymentKeyError`'s
    posture in payments, for the same reason): a line missing its invoice
    number would print, scan cleanly and fill a form with the wrong bill.
    """


@dataclass(frozen=True)
class Remittance:
    """What one scanned line said. `P5.8` fills its form from exactly this."""

    account_no: str
    invoice_no: str
    #: Minor units, as an int. The caller converts to a `Decimal` for money —
    #: never the other way round, and never a float (hard rule 2).
    amount_minor: int
    check: str

    @property
    def amount(self) -> Decimal:
        """The amount as money. `14218` → `Decimal('142.18')`.

        `Decimal(int) / 100` is exact — there is no float in this path and no
        rounding decision to make, which is why it is safe to publish as a
        property rather than as a service call.
        """
        return Decimal(self.amount_minor) / Decimal(100)


def _normalise(value: str, *, what: str) -> str:
    """Upper-cased, trimmed, and refused if it carries a character Code 39 lacks.

    ⚠ **REFUSED, NOT STRIPPED.** Silently dropping an unencodable character
    would print a line that scans perfectly into the WRONG account number —
    which is worse than a bill with no barcode, because nothing downstream can
    tell that it happened.
    """
    text = (value or "").strip().upper()
    if not text:
        raise RemittanceError(
            f"{what} is empty, so no remittance line can be composed. A line missing one "
            "of its three fields would still scan and would fill a form with the wrong "
            "bill, so it is refused rather than shortened."
        )
    if SEPARATOR in text:
        raise RemittanceError(
            f"{what} {text!r} contains {SEPARATOR!r}, which is the field separator. The "
            "line would parse into four fields and the reader would take the wrong one."
        )
    bad = sorted({one for one in text if one not in ALPHABET})
    if bad:
        raise RemittanceError(
            f"{what} {text!r} contains {bad!r}, which Code 39 cannot encode (its "
            f"repertoire is {ALPHABET!r}). The character is REFUSED rather than dropped: "
            "a stripped character prints a line that scans cleanly into a different "
            "account, and nothing downstream could tell."
        )
    return text


def check_character(payload: str) -> str:
    """Code 39's own mod-43 check character for `payload`.

    Sum each character's index in `ALPHABET`, take it modulo 43, and answer the
    symbol at that index. **Not Luhn** — Luhn is defined over digits and this
    payload carries letters; see the module docstring.
    """
    total = 0
    for one in payload:
        try:
            total += ALPHABET.index(one)
        except ValueError:  # pragma: no cover — `_normalise` refuses first
            raise RemittanceError(f"{one!r} is not a Code 39 character") from None
    return ALPHABET[total % len(ALPHABET)]


def compose(*, account_no: str, invoice_no: str, amount: Decimal) -> str:
    """The full line, check character included. This is what gets printed.

    `amount` is a `Decimal` of major units and becomes MINOR units in the line
    — `Decimal('142.18')` → `14218`. A float is refused rather than converted
    (hard rule 2): a payload is a sum of money and `0.1 + 0.2` is not `0.3`.
    """
    if not isinstance(amount, Decimal):
        raise RemittanceError(
            f"the amount {amount!r} is not a Decimal — money is never a float "
            "(CLAUDE.md hard rule 2). Refused rather than converted."
        )
    if amount < 0:
        raise RemittanceError(
            f"the amount {amount} is negative. A remittance line says what to PAY; a "
            "credit balance is not something a customer hands over at a shop counter, "
            "and a minus sign is not in the Code 39 repertoire either."
        )
    account = _normalise(account_no, what="the account number")
    invoice = _normalise(invoice_no, what="the bill number")
    minor = int((amount * 100).to_integral_value())
    payload = f"{account}{SEPARATOR}{invoice}{SEPARATOR}{minor}"
    return payload + check_character(payload)


def parse(line: str) -> Remittance:
    """What a scanner typed, taken apart — **and checked.**

    ⚠ **IT VERIFIES AND RAISES; THERE IS NO "PARSE LOOSELY" MODE.** `P5.15`'s
    outcome is *"the empty case is designed, not discovered"* and `P5.14`'s is
    *"a mis-scan fails visibly"*. A parser that returned a best guess for a
    damaged line would put the failure somewhere nobody is looking.
    """
    text = (line or "").strip().upper().strip(GUARD)
    if not text:
        raise RemittanceError(
            "nothing was scanned. A scanner that reads no barcode sends no characters at "
            "all, so an empty input is the ordinary shape of a failed scan and it is "
            "reported rather than treated as a blank form."
        )
    payload, check = text[:-1], text[-1]
    expected = check_character(payload)
    if check != expected:
        raise RemittanceError(
            f"the check character is {check!r} and this line computes {expected!r}, so it "
            "was mis-read. It is refused: a line one character wrong points at a real "
            "account belonging to somebody else."
        )
    parts = payload.split(SEPARATOR)
    if len(parts) != 3:
        raise RemittanceError(
            f"the line has {len(parts)} fields and a remittance line has three "
            f"(account{SEPARATOR}bill{SEPARATOR}amount). Refused rather than guessed."
        )
    account, invoice, minor = parts
    if not minor.isdigit():
        raise RemittanceError(
            f"the amount field is {minor!r} and a remittance line carries MINOR UNITS as "
            "digits — `14218`, never `142.18`. A decimal separator is a character two "
            "locales read two ways."
        )
    return Remittance(account_no=account, invoice_no=invoice, amount_minor=int(minor), check=check)


def verify(line: str) -> bool:
    """`True` when `line` parses and its check character holds. Never raises.

    For a caller that wants a boolean — a screen deciding whether to enable a
    control — rather than the reason, which `parse()` gives.
    """
    try:
        parse(line)
    except RemittanceError:
        return False
    return True


def bars(line: str) -> tuple[tuple[bool, int], ...]:
    """The printed symbol, as `((is_bar, width_in_modules), …)`.

    Start guard, the payload, stop guard, one narrow space between symbols.
    `width` is `1` for a narrow element and `2` for a wide one; a renderer
    multiplies by whatever module width the page can afford.

    ⚠ **`width` IS A MODULE COUNT, NOT A DRAWING INSTRUCTION** (`DEF-BIL-6325`).
    A renderer that multiplied a `2` by exactly twice the narrow width would be
    drawing a 2:1 ratio, which the symbology puts out of spec below a 20-mil
    X-dimension — ink spread eats a larger share of a narrow element than of a
    wide one, so the standard asks for at least 2.25 down there.
    `documents.BARCODE_WIDE` is where that decision lives, because it is a
    property of the PAPER and this function is a property of the SYMBOLOGY.

    ⚠ **THE PDF DRAWS THIS SINCE 2026-09-23** — `documents._barcode_rows`, on
    the remittance stub. The HTML serialisation still does not (`DEF-BIL-6340`).
    """
    out: list[tuple[bool, int]] = []
    symbols = GUARD + (line or "").strip().upper().strip(GUARD) + GUARD
    for index, symbol in enumerate(symbols):
        pattern = _PATTERNS.get(symbol)
        if pattern is None:
            raise RemittanceError(
                f"{symbol!r} has no Code 39 pattern. `compose()` refuses such a character, "
                "so a line reaching here with one did not come from this module."
            )
        for position, width in enumerate(pattern):
            out.append((position % 2 == 0, int(width)))
        if index != len(symbols) - 1:
            out.append((False, 1))  # the inter-character gap, one narrow space
    return tuple(out)


def compose_for_invoice(payload: dict, *, invoice_no: str | None) -> str | None:
    """The line for one bill, from **the bill's own frozen payload**.

    `BR-BIL-030`, and it is the reason this signature takes a dict rather than
    an invoice: *the document renders from `invoices.bill_payload` and the
    invoice's own rows; it never joins to customers, premises, units, rating or
    tenancy.* A renderer that reached back for a missing account number would
    rewrite an issued financial document by reading — the failure hard rule 4
    alone does not catch, because no `UPDATE` is involved.

    ⚠ **THE AMOUNT IS THE SNAPSHOT'S `total_due` AND NEVER `invoices.total`.**
    A19 §1.3: `invoices.total` is THIS PERIOD'S CHARGES and total due is
    previous balance − payments + this period. They are equal only for a
    standalone-format tenant. A line carrying the current charges would take a
    payment that leaves the customer in arrears and looks paid.

    ⚠ **`None` IS AN HONEST ABSENCE, NOT AN ERROR.** A snapshot without an
    account number or without a stamped `total_due` (`OQ-117`, PO 2026-08-12 —
    the bill ISSUES with a dash) gets **no line**, the same posture
    `documents.py` keeps everywhere with `ABSENT_MARK`. Printing a line with a
    placeholder in it would produce a perfectly scannable barcode for an
    account that does not exist.
    """
    data = payload or {}
    account_no = data.get("account_no")
    raw_total = data.get("total_due")
    if not account_no or not invoice_no or raw_total in (None, ""):
        return None
    # ⚠ A SNAPSHOT'S MONEY IS A STRING OR A `Decimal`, NEVER A FLOAT — and a
    # float arriving here is refused rather than converted (hard rule 2). The
    # `str()` is what makes a stored `"142.1800"` exact; `Decimal(float)` would
    # not be, and is the one conversion this line exists to avoid.
    if isinstance(raw_total, float):
        return None
    try:
        amount = raw_total if isinstance(raw_total, Decimal) else Decimal(str(raw_total))
    except (ArithmeticError, ValueError):
        return None
    try:
        return compose(account_no=str(account_no), invoice_no=str(invoice_no), amount=amount)
    except RemittanceError:
        # An account or bill number this symbology cannot carry is a real fact
        # about that tenant's numbering, not a crash. The bill still prints.
        return None


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-139-BRC07 `P5.10` (05-prototype/06 Payments Page Blueprint.pdf p024 · 12-governance/01-open-questions.md OQ-149 CLOSED 2026-08-12 · 04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-030/036 · CLAUDE.md hard rule 2)
# generated: 2026-09-23 by LANE P5-BACK (the payments blueprint's phase 5, backend half)
# checklist: A✔ B✔ C✔ D=deferred(no endpoint — `P5.8`'s Scan source is another lane) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr139_p5_remittance.py
# exceptions: the bars are SPECIFIED (`bars()`) and NOT DRAWN — `documents.py`
#         has no filled-rectangle primitive. Registered in the phase 5 board
#         and held by a test that goes red when one arrives, rather than left
#         as a comment (hard-won law 1)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
