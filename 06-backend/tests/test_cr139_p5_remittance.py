# ── Trace ──────────────────────────────────────────────
# Change:  CR-139-BRC07 — the payments blueprint's phase 5, task `P5.10` (the
#          remittance barcode) and the two TEST rows that belong to it:
#          `P5.14` *"a barcode check digit rejects a mis-read, with the worked
#          case in the test"* and `P5.15` *"a scan with no barcode fails
#          visibly rather than silently keying nothing"*.
# Rules:   BR-BIL-030 (a document never joins back to master data) ·
#          CLAUDE.md hard rule 2 (never a float; minor units on the wire) ·
#          hard-won law 1 (the missing BARS are registered and held by a test,
#          not left as a comment) · hard-won law 7 (what would make each of
#          these pass wrongly is answered in its docstring)
# Tests:   this file. It needs no database — the grammar is pure.
# ───────────────────────────────────────────────────────
"""The remittance line, and the two things a scanner gets wrong.

⚠ **NO `django_db` MARK, DELIBERATELY.** `apps/billing/remittance.py` reads no
row and holds no state, which is what lets `P5.8`'s front end and a print vendor
both reason about the same string. A test that needed a database here would be
evidence the module had grown a dependency it must not have.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from apps.billing import remittance

BACKEND = Path(__file__).resolve().parents[1]

#: The worked bill, and it is the one in the module's own docstring so the two
#: cannot drift: **$142.18** on bill `BL-2608-0117` for account `ACC-1042`.
ACCOUNT = "ACC-1042"
INVOICE = "BL-2608-0117"
AMOUNT = Decimal("142.18")
LINE = "ACC-1042$BL-2608-0117$14218%"


def test_cr139_p5_10_the_worked_line_is_exactly_this():
    """**The worked case, pinned.** Account, bill, amount, check character.

    ⚠ **THE CHECK CHARACTER IS `%` AND THE MODULE DOCSTRING FIRST SAID `Y`** —
    written before the function existed, and wrong. This case is what makes the
    docstring's worked example the code's own answer instead of a plausible
    one; a worked figure nothing recomputes is a comment claiming a guarantee
    (hard-won law 1).

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** asserting `compose(...) ==
    compose(...)`, which is true of any function at all. The literal is spelled
    out here on purpose, so a change to the grammar breaks a test rather than
    silently re-spelling every bill in the product.
    """
    line = remittance.compose(account_no=ACCOUNT, invoice_no=INVOICE, amount=AMOUNT)
    assert line == LINE
    assert line[-1] == remittance.check_character(line[:-1])


def test_cr139_p5_10_it_round_trips_and_the_amount_comes_back_as_money():
    """`compose` → `parse` gives back the three facts, and `142.18` is exact.

    `Decimal(int) / 100` has no float in it and no rounding decision, which is
    why `Remittance.amount` is a property rather than a service call.
    """
    parsed = remittance.parse(LINE)
    assert parsed.account_no == ACCOUNT
    assert parsed.invoice_no == INVOICE
    assert parsed.amount_minor == 14218
    assert parsed.amount == AMOUNT


def test_cr139_p5_10_minor_units_only_no_decimal_point():
    """`14218`, never `142.18`, and a line carrying a point is refused.

    A decimal separator is a character two locales read two ways and a
    scanner's keyboard layout can substitute. An integer of cents cannot be
    misread.
    """
    assert "$14218" in LINE and "142.18" not in LINE
    with pytest.raises(remittance.RemittanceError, match="MINOR UNITS"):
        payload = "ACC-1042$BL-2608-0117$142.18"
        remittance.parse(payload + remittance.check_character(payload))


# ═══════════════════════════════════════════════════════════════════════════
#  P5.14 — a mis-scan fails visibly
# ═══════════════════════════════════════════════════════════════════════════
def test_cr139_p5_14_one_wrong_character_is_refused():
    """**The whole reason a check character is on the line.**

    `ACC-1042` mis-read as `ACC-1043` is a real account belonging to somebody
    else, and the payment would look perfectly ordinary in every screen in the
    product. The check character is what turns a silent wrong payment into a
    visible failed scan.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** corrupting a character AND
    recomputing the check, which is what a careless test does and which proves
    only that the function is consistent with itself. Here the check character
    is left as it was, which is exactly what a mis-read produces.
    """
    misread = LINE.replace("ACC-1042", "ACC-1043")
    assert misread != LINE
    assert remittance.verify(misread) is False
    with pytest.raises(remittance.RemittanceError, match="mis-read"):
        remittance.parse(misread)


def test_cr139_p5_14_the_check_is_mod_43_and_not_luhn():
    """Mod 43 over Code 39's own alphabet — **stated, because Luhn is the reflex.**

    Luhn is defined over digits and this payload carries letters. The assertion
    is the arithmetic itself on a payload whose sum is easy to follow: `0` is
    index 0 and `Z` is index 35, so `0Z` sums to 35 and the check is `ALPHABET[35]`
    — `Z` again.
    """
    assert remittance.check_character("0Z") == remittance.ALPHABET[35] == "Z"
    assert remittance.check_character("") == "0"
    assert len(remittance.ALPHABET) == 43


def test_cr139_p5_14_a_transposition_is_not_caught_and_the_docstring_says_so():
    """**The limit of an unweighted mod-43 sum, asserted rather than assumed.**

    `AB` and `BA` carry the same check character, because the sum does not
    depend on position. That is the real Code 39 standard and we do not
    "improve" it — a non-standard check character is one no scanner in the
    world can verify. **The test exists so `P5.8` is never written as though a
    good check character means a good read.**

    ⚠ This case asserts a WEAKNESS. If a future lane strengthens the scheme,
    this goes red and names the trade-off, which is the correct outcome: the
    change is deliberate and needs saying out loud.
    """
    assert remittance.check_character("AB") == remittance.check_character("BA")


# ═══════════════════════════════════════════════════════════════════════════
#  P5.15 — a scan with no barcode fails visibly
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("scanned", ["", "   ", "**"])
def test_cr139_p5_15_an_empty_scan_is_designed_not_discovered(scanned):
    """*"Fails visibly rather than silently keying nothing."*

    A scanner that reads no barcode sends no characters at all, so an empty
    input is the ORDINARY shape of a failed scan — not an edge case. `"**"` is
    the same thing wearing the guard characters, which some scanners emit even
    when the payload between them decoded to nothing.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a parser that answered a blank
    `Remittance`. It would put the failure somewhere nobody is looking — a
    clerk pointing a scanner at a coffee-stained bill would get a form that
    simply did not fill, and would try again.
    """
    with pytest.raises(remittance.RemittanceError, match="nothing was scanned"):
        remittance.parse(scanned)
    assert remittance.verify(scanned) is False


def test_cr139_p5_15_a_line_with_the_wrong_number_of_fields_is_refused():
    """Two fields, or four, is not a remittance line. Refused, not guessed."""
    payload = "ACC-1042$14218"
    with pytest.raises(remittance.RemittanceError, match="three"):
        remittance.parse(payload + remittance.check_character(payload))


# ═══════════════════════════════════════════════════════════════════════════
#  What may not be encoded, and what may not be dropped
# ═══════════════════════════════════════════════════════════════════════════
def test_cr139_p5_10_an_unencodable_character_is_refused_not_stripped():
    """⚠ **STRIPPING IS THE DANGEROUS FIX AND IT IS THE OBVIOUS ONE.**

    Dropping a character Code 39 cannot carry prints a line that scans
    perfectly into a DIFFERENT account number, and nothing downstream can tell
    it happened — which is worse than a bill with no barcode at all.
    """
    with pytest.raises(remittance.RemittanceError, match="REFUSED rather than dropped"):
        remittance.compose(account_no="ACC#1042", invoice_no=INVOICE, amount=AMOUNT)


def test_cr139_p5_10_a_separator_inside_a_field_is_refused():
    """A `$` in an account number would parse into four fields."""
    with pytest.raises(remittance.RemittanceError, match="field separator"):
        remittance.compose(account_no="ACC$1042", invoice_no=INVOICE, amount=AMOUNT)


def test_cr139_p5_10_a_float_amount_is_refused():
    """Hard rule 2. `0.1 + 0.2` is not `0.3`, and a payload is a sum of money."""
    with pytest.raises(remittance.RemittanceError, match="never a float"):
        remittance.compose(account_no=ACCOUNT, invoice_no=INVOICE, amount=142.18)


# ═══════════════════════════════════════════════════════════════════════════
#  BR-BIL-030 — from the frozen payload, and from nothing else
# ═══════════════════════════════════════════════════════════════════════════
def test_cr139_p5_10_it_reads_total_due_and_never_the_current_charges():
    """**A19 §1.3: they are different figures, and the difference is arrears.**

    `invoices.total` is THIS PERIOD'S charges; total due is previous balance −
    payments + this period. A line carrying the current charges would take a
    payment that leaves the customer in arrears **and looks paid** — the worst
    shape this feature can fail in, because every screen shows a paid bill.
    """
    line = remittance.compose_for_invoice(
        {"account_no": ACCOUNT, "total_due": "142.1800", "total": "45.0000"},
        invoice_no=INVOICE,
    )
    assert line == LINE


@pytest.mark.parametrize(
    "payload, invoice_no",
    [
        ({"total_due": "142.1800"}, INVOICE),  # no account on the snapshot
        ({"account_no": ACCOUNT}, INVOICE),  # OQ-117's dash: no total_due
        ({"account_no": ACCOUNT, "total_due": "142.1800"}, None),  # no bill number
        ({"account_no": ACCOUNT, "total_due": 142.18}, INVOICE),  # a float in the snapshot
    ],
)
def test_cr139_p5_10_an_incomplete_snapshot_gets_no_line_at_all(payload, invoice_no):
    """**`None`, never a placeholder** — and it never goes and finds the value.

    `BR-BIL-030`: the document renders from the frozen payload and the
    invoice's own rows and never joins back to master data. A renderer that
    reached for a missing account number would rewrite an issued financial
    document **by reading**, which is the failure hard rule 4 alone does not
    catch because no `UPDATE` is involved.

    Printing a line with `—` in it would produce a perfectly scannable barcode
    for an account that does not exist.
    """
    assert remittance.compose_for_invoice(payload, invoice_no=invoice_no) is None


# ═══════════════════════════════════════════════════════════════════════════
#  The bars: specified, not drawn — and the hold has a test that expires it
# ═══════════════════════════════════════════════════════════════════════════
def test_cr139_p5_10_the_bar_pattern_is_the_code_39_standard():
    """Start guard, payload, stop guard, a narrow gap between symbols.

    Code 39 is *three of nine*: **exactly three of every symbol's nine elements
    are wide.** That property is what a scanner uses to synchronise, and it is
    checked here over the whole table rather than on one symbol — a single
    mistyped pattern in a 44-entry transcription is otherwise invisible to
    everything in this repository.
    """
    for symbol, pattern in remittance._PATTERNS.items():
        assert len(pattern) == 9, symbol
        assert pattern.count("2") == 3, f"{symbol!r} is not three-of-nine: {pattern}"

    drawn = remittance.bars(LINE)
    # 9 elements per symbol + 1 gap between symbols; 28 payload characters plus
    # two guards is 30 symbols → 30*9 + 29 gaps.
    assert len(drawn) == 30 * 9 + 29
    assert drawn[0] == (True, 1), "a Code 39 symbol starts with a BAR"


def test_cr139_p5_10_the_bars_are_drawn_and_the_hold_is_spent():
    """⚠ **THIS WAS THE HOLD. IT FIRED, AND IT IS NOW ITS OWN INVERSE.**

    It read `test_cr139_p5_10_the_bars_are_not_drawn_yet` and asserted
    `"remittance.bars" not in source` — the blueprint's p025 rule, *"when a
    phase writes a hold, it writes the test that fires when the hold expires"*.
    On 2026-09-23 the PO said *"please enable it and also start putting bar
    code on bills - we are still in beta and uat - we ahve to make these
    changes now"*, the bars were drawn (`DEF-BIL-6325`), and **this case went
    red naming the three things to correct.** It did its job.

    ⚠ **INVERTED RATHER THAN DELETED, WHICH IS THE POINT.** Its own message
    said *delete this test*, and deleting it would leave nothing asserting that
    the renderer still calls the shared symbol specification. A second Code 39
    derivation inside `documents.py` is the failure `remittance.py`'s own
    docstring exists to prevent — printer and reader drifting apart until a
    clerk scans a bill and gets somebody else's account.

    **What PROVES the bars scan is not here**: it is
    `tests/test_def_bil_6325_barcode_round_trip.py`, which decodes a rendered
    page back to characters. This case only proves there is ONE symbol
    specification in the product.
    """
    source = (BACKEND / "apps" / "billing" / "documents.py").read_text()
    assert "remittance.bars(" in source, (
        "`documents.py` no longer calls `remittance.bars()`. Either the bars have gone "
        "off the bill — DEF-BIL-6325 again — or the renderer has grown a SECOND Code 39 "
        "derivation of its own, which is what remittance.py exists to prevent."
    )
    assert " re f" in source, (
        "the filled-rectangle operator has gone from the PDF writer, so nothing on the "
        "page can be a bar"
    )


def test_cr139_p5_10_the_line_is_on_the_stub_and_the_claim_was_corrected():
    """The absence that HAS gone is struck from all three places that claimed it.

    ⚠ **THIS IS HARD-WON LAW 2's MIRROR, WHICH IS WHAT COST THE PORTAL SIX OF
    ITS EIGHT FRONT DOORS.** `documents.py` said *no remittance barcode* in
    three separate places — the module docstring, `DOCUMENT_UNAVAILABLE`'s
    first entry and its layout-library entry. A sentence that is no longer true
    is a live screen behind a dead control, and **nothing in this product
    re-checks a refusal**, so the check is written here.
    """
    source = (BACKEND / "apps" / "billing" / "documents.py").read_text()
    assert "from apps.billing import models, remittance" in source
    # ⚠ **`LABEL_SCAN`, NOT THE LITERAL** — `DEF-BIL-6325` gave the label a name
    # because two places read it now: `_stub()` writes the field and `_pdf_flow`
    # draws the BARS above the field carrying it. Two literals would have drifted
    # silently, and the symptom would be a bill with no symbol on a page nothing
    # in this repo reads (hard-won law 6).
    assert 'LABEL_SCAN = "Scan"' in source
    assert "DocumentField(label=LABEL_SCAN" in source
    assert "no remittance barcode, no colour" not in source
    assert "no logo, no remittance barcode" not in source
