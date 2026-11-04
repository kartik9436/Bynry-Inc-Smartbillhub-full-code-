# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-615 (2026-08-24) — the import-run number series seeds as
#           `IMP-` while CR-023's own test asserted `RUN-`. The catalogue entry
#           and the expectation live in different modules
#           (`core/numbering.SERIES_CATALOG` and a test file), they drifted at
#           birth, and NOTHING RELATED THEM: no check renders a series' seeded
#           default and looks at what comes out, so the two could disagree for
#           as long as nobody ran that one test.
# Rules:    BR-TEN-035 (the format grammar) · CR-005 (every category offers a
#           bare counter; no default may duplicate another series' prefix) ·
#           OQ-342 (PO 2026-08-23 — `RUN-` belongs to the BILL RUN series, and
#           `import_run` opens on `IMP-{YY}{MM}{DD}-{00}` because of it)
# Tests:    this file IS the prevention DEF-615's row asks for.
# Impacts:  core/numbering.py · apps/tenancy/services.SERIES_DEFAULTS
# ───────────────────────────────────────────────────────
"""Every series' SEEDED DEFAULT, rendered once, with its prefix pinned.

⚠ **THIS ASSERTS THE RENDERED STRING, NOT THE FORMAT LITERAL.** A test that
compared format strings would have passed on the day DEF-615 was born: both
`IMP-{YY}{MM}{DD}-{00}` and `RUN-{0000}` are in the catalogue's option list for
`import_run`, and the bug was about which one is FIRST. What a tenant is
actually seeded with is the first option rendered — `IMP-260824-01` — and that
is the string a test elsewhere in this repo was asserting `RUN-` about.

⚠ **AND IT PINS PREFIXES, NOT WHOLE NUMBERS.** The sequence pad and the date
tokens are a tenant's to change on S8 (BR-TEN-035); the PREFIX is the part other
tests, screens and PO screenshots quote, and the part a silent catalogue edit
would move. Pinning the whole rendered number would fail every time somebody
legitimately widened a pad.

A series added to the catalogue with no row here fails `test_every_series_is_pinned`,
so a new series cannot arrive unexamined — which is the other half of how
DEF-615 escaped.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.tenancy.services import SERIES_DEFAULTS
from core import numbering

#: series key → the prefix its SEEDED DEFAULT renders, with the source of the
#: prefix where a ruling named it. A bare counter renders "" and is written as
#: such rather than omitted, so "no prefix" is a stated fact.
EXPECTED_PREFIX: dict[str, str] = {
    numbering.ACCOUNT: "AC-",
    numbering.PREMISES: "P-",
    numbering.UNIT: "U-",
    numbering.SERVICE_REQUEST: "SR-",
    numbering.CUSTOMER: "C-",  # CR-030 W0 — the id a clerk quotes down a phone
    # ⚠ CR-032 added the connection series and its seeded default
    # `CON-{YY}-{0000}` — the string the PO's own New Connect screens draw
    # (`CON-26-0110`) — and THIS LIST NEVER LEARNED IT, so this test has
    # been red ever since. Added by the merge lane 2026-08-26 with DEF-807,
    # which is the same staleness in a sibling file: three tests pin the
    # numbering catalogue by hand and a series was added to the catalogue
    # without any of them being told.
    numbering.CONNECTION: "CON-",
    numbering.BILL: "BL-",
    numbering.PAYMENT: "PY-",
    numbering.RECEIPT: "R-",
    numbering.ADJUSTMENT: "ADJ-",
    numbering.CREDIT_MEMO: "CM-",
    numbering.WRITE_OFF: "WOF-",
    # ⛔ OQ-342 (PO 2026-08-23), verbatim: *"A: a real series (RUN-0001, like
    # RT-001)"*. This is the series that owns `RUN-`, and it is the reason
    # DEF-615 could not be fixed by moving `import_run` onto that prefix.
    numbering.BILL_RUN: "RUN-",
    numbering.DEPOSIT_BATCH: "DEP-",
    numbering.JOURNAL_ENTRY: "JE-",  # BR-LED-021 names this string as the seed
    numbering.COLLECTIONS_NOTICE: "CN-",
    numbering.EXPORT_BATCH: "EXP-",
    numbering.WORK_ORDER: "WO-",
    numbering.SERVICE_TEMPLATE: "ST-",
    numbering.DISPATCH_BATCH: "DSP-",
    numbering.ASSET: "AST-",
    numbering.READ_BATCH: "RB-",
    numbering.ROUTE: "RT-",  # PO Q&A D5
    numbering.CYCLE: "CY-",  # PO Q&A D5
    # ⛔ DEF-615's own row. `import_run` numbers a read-import batch and was
    # moved off `RUN-` by OQ-342 in the same breath that gave the prefix to the
    # bill run — two series opening on one prefix would greet every new tenant
    # with CR-005's duplicate-prefix warning.
    numbering.IMPORT_RUN: "IMP-",
    # ⛔ OQ-426 (PO ruling 2026-08-27), verbatim: *"Transfer TRF-26-0001 …
    # follow same logic that we are following for other numbers we have did in
    # settings"*. The PO named the RENDERED STRING, which is exactly what this
    # file pins — `TRF-{YY}-{0000}` at counter 1 in 2026 is `TRF-26-0001`.
    # RED first, verbatim:
    #     AssertionError: {'in the catalogue and not pinned here': ['transfer'],
    #                      'pinned here and not in the catalogue': []}
    numbering.TRANSFER: "TRF-",
    # ⛔ OQ-427 (PO ruling 2026-08-27), verbatim and in full: *"it needs its own
    # series"*. ⚠ **UNLIKE THE ROW ABOVE, THE PO DID NOT NAME THIS STRING.** The
    # ruling settled that a disconnect case is its own document rather than r10's
    # `WO-4833` work order, and DELEGATED the format; `DSC-` is therefore the
    # BUILD's choice, recorded as such in the decision log, and what is pinned
    # here is a lane's decision that must go RED if a later lane quietly changes
    # it. `DSC-{YY}-{0000}` at counter 1 in 2026 is `DSC-26-0001`.
    # ⚠ `DSP-` (dispatch batch, four rows up) is ONE CHARACTER AWAY and that is
    # accepted, not solved — see `core/numbering.py`'s own note.
    # RED first, verbatim:
    #     AssertionError: {'in the catalogue and not pinned here':
    #                      ['disconnect_case'], 'pinned here and not in the
    #                      catalogue': []}
    numbering.DISCONNECT_CASE: "DSC-",
    # ⛔ CR-039 wave D task 18 — and these two are pinned with the LOUDEST
    # caveat in this file, because they are the only rows here that no PO ever
    # named, not even as a delegation. The PO ruled that a move-in and a
    # move-out ARE records (*"you cna keep them as records for audit
    # perpuses"*) and the decision log states in as many words that the ruling
    # *"DOES NOT SETTLE D18's NUMBERING"*. The build gave them numbers as a
    # flagged EXTENSION of the disconnect ruling above — a disconnect is a
    # one-account job and got its own series, which kills the argument that a
    # one-account job needs none. **ONE WORD FROM THE PO REVERSES BOTH ROWS.**
    # ⚠ TWO series and not one shared `MV-`: `MV-26-0004` would not tell a
    # clerk whether somebody arrived or left. They differ in their LAST
    # character, which is the `DSC-`/`DSP-` hazard again and is named, not
    # solved. RED first, verbatim:
    #     AssertionError: {'in the catalogue and not pinned here':
    #                      ['move_in', 'move_out'], 'pinned here and not in the
    #                      catalogue': []}
    numbering.MOVE_IN: "MVI-",
    numbering.MOVE_OUT: "MVO-",
    # ⚠ **`interruption_report` WAS MISSING HERE AND THIS FILE HAD BEEN RED FOR
    # IT SINCE THE SERIES LANDED (CR-068 wave B).** It is added by the `P0.13`
    # lane rather than left, because a guard that is already failing cannot
    # prove anything about the row `P0.13` adds beside it — and this file's own
    # header records the shape: *"a catalogue pinned by hand in three places
    # goes stale in three places."* `RP-26-0412` is the string every CR-068
    # portal document names.
    numbering.INTERRUPTION_REPORT: "RP-",
    # ── payments blueprint `P0.13` (PO 2026-09-22, verbatim: *"(a) STL-26-0001"*).
    # A RULED prefix rather than the build's: the Product Owner was shown the
    # rendered string and chose it. `STL-` must stay distinct from `DEP-`, which
    # is what a PERSON carried to a bank — see
    # `tests/test_p013_settlement_series.py` for the money reason.
    numbering.SETTLEMENT: "STL-",
    # ── G3 (PO 2026-10-14): a correction case is numbered at Send from the
    # Correction case series, default `CC-{YYYY}-{000}` — `CC-2026-001`. A RULED
    # prefix (`DEF-BIL-10147`).
    numbering.CORRECTION_CASE: "CC-",
}

ISSUE_DATE = date(2026, 8, 24)


def _rendered(series: str) -> str:
    return numbering.render(SERIES_DEFAULTS[series], 1, ISSUE_DATE)


def test_every_series_is_pinned():
    """A catalogue entry with no expectation here is a series nobody looked at."""
    assert set(SERIES_DEFAULTS) == set(EXPECTED_PREFIX), {
        "in the catalogue and not pinned here": sorted(set(SERIES_DEFAULTS) - set(EXPECTED_PREFIX)),
        "pinned here and not in the catalogue": sorted(set(EXPECTED_PREFIX) - set(SERIES_DEFAULTS)),
    }


@pytest.mark.parametrize("series", sorted(EXPECTED_PREFIX))
def test_the_seeded_default_renders_the_prefix_its_readers_expect(series):
    rendered = _rendered(series)
    expected = EXPECTED_PREFIX[series]
    assert rendered.startswith(expected), (
        f"the seeded default for `{series}` is {SERIES_DEFAULTS[series]!r}, which renders "
        f"{rendered!r} — and the prefix this repo's tests, screens and PO rulings quote is "
        f"{expected!r}. One of the two moved without the other (DEF-615)."
    )


def test_def615__the_import_run_default_is_IMP_and_the_bill_run_default_is_RUN():
    """The exact pair DEF-615 is about, spelled out rather than parametrised.

    `RUN-{0000}` is still OFFERED on `import_run` — a duplicate prefix is a
    CR-005 warning and never a block, so a tenant may choose it. What is pinned
    is the SEEDED DEFAULT, which is what a fresh tenant gets and what
    `tests/test_cr023_import_stages.py` reads back off a stored run.
    """
    assert _rendered(numbering.IMPORT_RUN) == "IMP-260824-01"
    assert _rendered(numbering.BILL_RUN).startswith("RUN-")
    assert "RUN-{0000}" in numbering.SERIES_CATALOG[numbering.IMPORT_RUN][1]


def test_def615__no_two_series_open_on_the_same_prefix():
    """CR-005's duplicate-prefix rule, asserted over the LIVE seeded set.

    ⚠ **DERIVED FROM `SERIES_DEFAULTS`, NOT FROM `EXPECTED_PREFIX` ABOVE.** A
    version of this that read the hand-written map could not fail when the
    CATALOGUE moved — which is DEF-615's own mechanism reproduced inside its own
    guard. The prefix here is taken off each default's format string: everything
    before its first `{` token, which is exactly what CR-005's warning compares.

    This is the reason DEF-615 could not be fixed by pointing `import_run` at
    `RUN-`: OQ-342 gave that prefix to the bill-run series, and moving import_run
    onto it would ship CR-005's duplicate-prefix warning to every new tenant.
    """
    by_prefix: dict[str, list[str]] = {}
    for series, format_string in SERIES_DEFAULTS.items():
        prefix = format_string.split("{", 1)[0]
        if not prefix:
            continue  # a bare counter has no prefix to collide on
        by_prefix.setdefault(prefix, []).append(series)
    collisions = {prefix: sorted(names) for prefix, names in by_prefix.items() if len(names) > 1}
    # Empty is what CR-005 asks for, and a new default landing on a prefix
    # another series already opens on shows up here BY NAME.
    assert collisions == {}, collisions
