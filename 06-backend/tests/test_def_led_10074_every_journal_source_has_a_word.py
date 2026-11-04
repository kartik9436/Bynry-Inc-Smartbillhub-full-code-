# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-LED-10074 — the Journal's SOURCE column printed
#           "unrecognized source: counter_session" to a clerk
# Ruling:   12-governance/02-decision-log.md 2026-10-12 "FINANCE: JOURNAL
#           SEARCH AND THE PERIOD CONTROLS", fault (B), CONFIRMED (PO: *"this
#           good please start and fix it"*) — the word is **Counter session**
# Rules:    BR-REP-008 (nothing invisible) · B14 rule 32 (no internal code in
#           clerk-facing copy) · OQ-LED-12657 (OPEN for the other five)
# Tests:    this file; the screen half is `journalView.test.tsx`
# ───────────────────────────────────────────────────────
"""Every `source_type` the posting code writes has a WORD a clerk can read.

A source reaches the Journal's SOURCE column one of two ways: through the
server's BR-REP-008 vocabulary (`source_mapped=true`), or — for a source that
vocabulary has no word for — through the screen's own catalogue key
`finance.journal.sourceCode.<source_type>`, in all eleven languages.

⚠ **`counter_session` IS LABELLED ON SCREEN AND IS NOT ADDED TO BR-REP-008.**
The PO ruled the WORD (*Counter session*). BR-REP-008 is a ten-word GROUPING
vocabulary that other reports total under, and the ruling said nothing about
which group a drawer difference totals in — so the grouping is untouched and
`test_def_led_6702_counter_receipt_source.py` still pins it unmapped there.

⚠ **FIVE SOURCES STILL HAVE NO WORD, AND THAT IS `OQ-LED-12657`, OPEN.** They
are pinned here BY NAME, so a lane that labels one without an answer, or a new
posting caller writing a sixth unlabelled string, goes red and is told which.

**What would make this pass wrongly:** a key present in English and missing in
another catalogue (each of the eleven is read), or an `UNLABELLED` list that
quietly grows (it is compared for equality, not as a subset).
"""

import json
import pathlib

import pytest

from apps.ledger import reporting

from tests.test_def_led_6702_counter_receipt_source import WRITTEN_TODAY

LOCALES = pathlib.Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
KEY = "finance.journal.sourceCode.{}"

#: `OQ-LED-12657`, OPEN — the five the PO has not yet named.
UNLABELLED = (
    "allowance_for_doubtful_accounts",
    "depreciation",
    "supplier_invoice",
    "unbilled_revenue_accrual",
    "unpaid_cost_accrual",
)


def _catalogues():
    found = sorted(LOCALES.glob("*.json"))
    assert len(found) == 11, f"expected the eleven catalogues, found {len(found)}"
    return {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in found}


def test_counter_session_reads_counter_session_in_english():
    """RED BEFORE: the key is absent and the column says *unrecognized source*."""
    assert _catalogues()["en"].get(KEY.format("counter_session")) == "Counter session"


@pytest.mark.parametrize("source_type", WRITTEN_TODAY)
def test_every_written_source_has_a_word_or_is_named_as_open(source_type):
    if reporting.source_vocabulary_for(source_type)[1]:
        return  # the server's BR-REP-008 word reaches the column
    if source_type in UNLABELLED:
        return  # OQ-LED-12657
    missing = [
        lang for lang, catalogue in _catalogues().items()
        if not catalogue.get(KEY.format(source_type))
    ]
    assert missing == [], f"{source_type!r} has no word in: {missing}"


def test_the_open_list_is_exactly_the_unlabelled_set():
    catalogue = _catalogues()["en"]
    unlabelled = tuple(
        value
        for value in WRITTEN_TODAY
        if not reporting.source_vocabulary_for(value)[1] and KEY.format(value) not in catalogue
    )
    assert unlabelled == UNLABELLED
