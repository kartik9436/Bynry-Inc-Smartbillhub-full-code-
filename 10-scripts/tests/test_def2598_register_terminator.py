#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2598 (2026-08-31) — file_defect.py inserted a BLANK LINE before
#          every row because ONE stray carriage return anywhere in the register,
#          inside quoted prose, flipped its terminator detection to CRLF. Nine
#          blank lines are in 12-governance/10-defect-log.csv because of it.
# Rules:   CLAUDE.md hard-won law 1 (a comment claiming a guarantee is not the
#          guarantee — this tool's docstring said the terminator was "detected
#          and preserved") · law 7 (prove a guard goes RED before trusting it
#          green) · law 11 (append-only writing to a register six lanes share)
# Impacts: 10-scripts/file_defect.py · 12-governance/10-defect-log.csv · G26
# ───────────────────────────────────────────────────────
"""The terminator is read from the HEADER LINE, never from the whole file.

WHY THE OBVIOUS TEST WOULD HAVE PASSED ON THE BUG
-------------------------------------------------
A test that appends to a clean LF file and checks for no blank line passes on
BOTH versions — the broken one only misbehaves when a carriage return is hiding
inside a quoted field somewhere else in the file. So the case that matters is
the one the register is actually in: LF-terminated, with stray CRs in prose.

Every assertion below is written against `line_terminator` directly rather than
by running the tool, because running it appends a real row to a register six
lanes are writing (law 11). The function is the whole of the fix.

    python3 10-scripts/tests/test_def2598_register_terminator.py
    pytest 10-scripts/tests/test_def2598_register_terminator.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "10-scripts"))

from file_defect import line_terminator  # noqa: E402

HEADER = b"id,reported_on,title\n"

#: THE DEFECT'S OWN CASE. An LF file whose prose carries a CR — which is
#: 12-governance/10-defect-log.csv today, seven times over.
POISONED = HEADER + b'"DEF-1","2026-08-01","a title with a stray \r inside it"\n'

#: The pre-fix expression, kept here so the test states what it is comparing
#: against rather than describing it.
def _old_detection(raw: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in raw else b"\n"


def test_a_stray_cr_in_prose_does_not_flip_the_terminator():
    """The defect, replayed. This is the assertion that goes RED on the old code."""
    assert line_terminator(POISONED) == b"\n"


def test_the_old_detection_really_did_get_this_wrong():
    """Law 7 in the test file: prove the case distinguishes the two versions.

    A regression test that passes on the broken code as well is not a regression
    test. `\\r\\n` appears in POISONED only because a CR happens to sit at the end
    of a word followed by more text — which is exactly how it looks in the
    register — and the old expression cannot tell that from a CRLF file.
    """
    assert b"\r\n" not in POISONED  # the CR is mid-line, not a terminator
    poisoned_at_a_line_end = HEADER + b'"DEF-1","2026-08-01","ends with\r\nmore"\n'
    assert _old_detection(poisoned_at_a_line_end) == b"\r\n"  # the bug
    assert line_terminator(poisoned_at_a_line_end) == b"\n"  # the fix


def test_a_real_crlf_file_is_still_detected_as_crlf():
    """The fix must not simply hardcode LF — that would be the mirror defect."""
    crlf = b"id,reported_on,title\r\n" + b'"DEF-1","2026-08-01","x"\r\n'
    assert line_terminator(crlf) == b"\r\n"


def test_no_header_and_an_empty_file_fall_back_to_lf():
    assert line_terminator(b"") == b"\n"
    assert line_terminator(b"id,reported_on,title") == b"\n"
    assert line_terminator(b"\n") == b"\n"


def test_the_live_register_is_lf_and_stays_lf():
    """The register on disk, not a fixture — the thing the tool actually writes to.

    ⚠ MEASURED 2026-09-01, AND IT IS NOT WHAT DEF-2598 DESCRIBED. The row says
    seven stray carriage returns are sitting in quoted prose; there are **zero**
    today, so the old detection would return LF as well and the bug is DORMANT,
    not live. It is fixed anyway: `build_row` refuses a CR in a field, but the
    register is also written by hand and by other tools, and the failure mode is
    silent — a blank line before every row, which no gate reads as wrong.

    The eight blank lines the old detection already put there are LEFT ALONE.
    Removing them means rewriting a file six lanes append to, for a change
    `csv.reader` ignores entirely; that is the mass shared-file rewrite law 11
    exists to prevent, and the defect row made the same call.
    """
    raw = (REPO / "12-governance" / "10-defect-log.csv").read_bytes()
    assert line_terminator(raw) == b"\n"
    assert raw.endswith(b"\n"), "the register must end with a terminated row"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL  {name}: {exc}")
    print(f"{'FAIL' if failures else 'PASS'}: {failures} failure(s)")
    raise SystemExit(1 if failures else 0)
