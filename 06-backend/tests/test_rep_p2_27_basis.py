# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 2 · P2.27 (as-was where history exists) ·
#           P2.19 (state the basis on screen).  Screens: 2·1 head.
# Rules:    brief §7.2.4 p85-p86 read as images (B14 rule 42) · B14 rule 33
# ───────────────────────────────────────────────────────
"""ONE REPORT STATES BOTH BASES, AND THAT IS CORRECT RATHER THAN UNTIDY."""

import pytest

from apps.reports import basis


def test_p2_27__every_row_dated_answers_as_was():
    served = basis.classify(dated=1904, undated=0)
    assert served.code == basis.AS_WAS
    assert served.undated == 0


def test_p2_27__no_row_dated_falls_back_to_as_is_and_says_so():
    """*"Before `P0.18`'s table ships, it falls back to as-is and says so on
    the face of the report."*"""
    served = basis.classify(dated=0, undated=1904)
    assert served.code == basis.AS_IS
    assert served.sentence == "Based on today's customer details"


def test_p2_27__a_mixed_report_states_both_and_counts_what_it_could_not_date():
    """p86: *"One report will state **both bases** for the first year, and that
    is correct rather than untidy: the alternative is a single confident basis
    line that is true of half the rows."*

    The outcome row on p13 — *"revenue by class for July 2026 puts $184.52
    under Residential **and says which rows it could not date**"* — is this
    count. A boolean could not answer it.
    """
    served = basis.classify(dated=1492, undated=412)
    assert served.code == basis.MIXED
    assert (served.dated, served.undated) == (1492, 412)
    assert served.as_dict()["undated"] == 412


def test_p2_27__an_empty_report_claims_the_weaker_basis():
    """⚠ Zero rows has answered nobody's question. Claiming as-was over no
    rows is a claim the product cannot support, so the weaker statement is the
    true one — and a version that returned AS_WAS here would make every empty
    report in the product claim regulatory provenance."""
    assert basis.classify(0, 0).code == basis.AS_IS


def test_p2_27__the_count_is_taken_row_by_row_and_never_sampled():
    """A report that checked the FIRST row and declared the whole thing as-was
    would be right most of the time and wrong exactly in the month the table
    started recording — the month somebody is most likely to be checking."""
    calls: list[object] = []

    def fake(account_id, *, on):
        calls.append(account_id)
        return (None, account_id != "old")

    original = basis.account_class_on
    basis.account_class_on = fake
    try:
        served = basis.over(["new", "old", "new"], on=None)
    finally:
        basis.account_class_on = original
    assert len(calls) == 3, "every row is asked, not the first one"
    assert (served.dated, served.undated) == (2, 1)
    assert served.code == basis.MIXED


@pytest.mark.parametrize("code", sorted(basis.SENTENCES))
def test_p2_19__every_basis_sentence_is_six_words_or_fewer(code):
    """B14 rule 33: a FACT is ≤ 6 words. *"Based on today's customer details"*
    is p84's own drawn wording and is five."""
    assert len(basis.SENTENCES[code].split()) <= 6


def test_p2_19__no_basis_sentence_explains_WHY(the_forbidden=("audit", "retention", "because", "history table", "recording")):
    """⚠ **RATIONALE IS ZERO WORDS ON SCREEN** (B14 rule 33), and CLAUDE.md
    hard rule 4 adds that no screen may describe the audit path as a permanent
    record of an old value. A screen explaining the retention policy would
    break rule 33 while trying to obey hard rule 4."""
    for code, sentence in basis.SENTENCES.items():
        lowered = sentence.lower()
        for word in the_forbidden:
            assert word not in lowered, f"{code} explains itself: {sentence!r}"


def test_p2_19__every_basis_the_module_declares_has_a_sentence():
    """A basis with no sentence renders as an empty head line, which is the one
    thing `P2.19` forbids — a report that does not say which question it
    answered is one a reader assumes about."""
    assert set(basis.BASES) == set(basis.SENTENCES)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 2 · P2.27 · P2.19
# generated: 2026-09-27 by lane REP-P2-MODEL
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
