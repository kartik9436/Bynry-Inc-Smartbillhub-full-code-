# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-WRK-4079 · DEF-MET-4081 (2026-09-05) — two rows filed with
#          severity `major` AFTER G46 had been taken green twice that day, the
#          second arriving between another lane building its fix and pushing it.
#          Seven rows on this branch carried the retired word; every one was
#          mapped by hand afterwards.
# Rules:   CLAUDE.md law 7 (prove a guard RED first, in the harness that will
#          run it) · 12-governance/15-defect-register-truth.md §7 (the status
#          vocabulary should be six values, ratcheted, with NO mass rewrite)
# Impacts: 10-scripts/register_vocabulary.py · 10-scripts/file_defect.py ·
#          10-scripts/close_defect.py · gates G30 and G46 (read side only)
# ───────────────────────────────────────────────────────
"""A ROW THAT G46 WILL REFUSE CANNOT BE WRITTEN IN THE FIRST PLACE.

WHY THIS TEST EXISTS
====================
G46 reads the register and refuses a severity from the second vocabulary. It
works, it has been green, and on 2026-09-05 it went red three separate times
against the SAME word — because a gate speaks only once the row is on the
branch, and by then the lane that knew what it meant has moved on. The lane that
cleared it wrote the conclusion down::

    "file_defect.py doesn't validate severity, so a lane filing from memory has
     an even chance of the wrong word and G46 can only speak once the row is on
     the branch. A validating allocator would end this; a gate never can,
     because it runs too late."

So the check moved to the moment of writing. This file is the proof that it
BITES, and it is deliberately built out of the real inputs of DEF-WRK-4079 and
DEF-MET-4081 rather than out of invented ones — a guard proved on a case
somebody made up is a guard proved against the author's imagination.

WHAT IS ASSERTED, AND WHY THESE CLAUSES
=======================================
1. **The two words that actually landed are refused, and the refusal names the
   survivor.** `major` and `minor` carry the mapping a lane made by hand on
   2026-09-05; the refusal repeats it so the filer retypes their own intent
   rather than looking anything up.
2. **`blocker` / `trivial` / `cosmetic` are refused with NO suggestion.** They
   were in the register too and nobody ever ruled what they become. A script
   that guessed would destroy the evidence the register exists for, which is the
   reason G46 gives for refusing to remap rows itself.
3. **The four live severities still file.** A guard that refuses good work gets
   switched off; this is the clause that says it does not.
4. **Read is WIDER than write, and the gates agree with it.** The 37 rows
   carrying a retired status stay lawful — this asserts the shared read set
   against G30's and G46's OWN constants, so the three copies cannot drift.
5. **A drifted header is refused.** `DEF-WRK-4051` put 23 fields against a
   14-column header and its `status` cell read `for the registry)`. If the
   register grows a column, every row this tool appends is one field short and
   downstream sees a SHORTER row rather than a broken one.
6. **A malformed serialisation is refused.** Insurance against the next change
   to `build_row`, stated as insurance (hard-won law 1) rather than implied to
   have teeth today.

    python3 -m pytest 10-scripts/tests/test_register_vocabulary.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "10-scripts"))
sys.path.insert(0, str(ROOT / "10-scripts" / "gates"))

import register_vocabulary as vocab  # noqa: E402


def _load(name: str):
    """Load a 10-scripts tool by path, with argv neutralised.

    Same shim as `test_def1221_allocates_upward.py`: these tools parse argv at
    import time under `__main__` only, but a stray argv still confuses argparse
    help generation, and importing by path is what keeps the test honest about
    WHICH file it is checking.
    """
    spec = importlib.util.spec_from_file_location(f"_t_{name}", ROOT / "10-scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, [name]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = argv
    return module


class _Args:
    """The namespace `validate_inputs` reads, filled with a row that is fine."""

    def __init__(self, **over):
        self.title = "a real fault, stated"
        self.surface = "06-backend/tests/test_us_wrk_044_sync_pg.py"
        self.module = "work"
        self.severity = "high"
        self.found_in = "2.194.0"
        self.introduced_in = "2026-09-05"
        # ⚠ THIS LITERAL MOVED ON 2026-09-10 AND THE MOVE IS THE POINT.
        # `category` became a fixed list of twelve that day (PO: "we cannot
        # manage what we cannot count"), so `check-that-cannot-fail` — a
        # perfectly good sentence and the 1,017th spelling — is now refused by
        # `file_defect.validate_inputs`, and every clause below that asserts
        # `== []` would fail for a reason it is not about. The vocabulary's own
        # bite-proof lives in `g46_register_vocabularies.selftest()`, which
        # `run()` calls on every suite run.
        self.category = "check-that-does-not-check"
        self.escape_reason = "nothing could have caught it"
        self.prevention = "the duplicate now arrives INSIDE the batch"
        self.__dict__.update(over)


# ── 1 · the two words that actually landed today ───────────────────────────
# The severities of DEF-WRK-4079 and DEF-MET-4081 as filed, before a lane mapped
# them by hand. Both were written by tools that could not refuse them.
@pytest.mark.parametrize("word,survivor", sorted(vocab.SEVERITY_RETIRED.items()))
def test_a_severity_from_the_old_vocabulary_is_refused_and_names_its_survivor(word, survivor):
    fd = _load("file_defect")
    problems = fd.validate_inputs(_Args(severity=word))
    assert problems, f"{word!r} was accepted — this is DEF-WRK-4079 all over again"
    said = " ".join(problems)
    assert survivor in said, f"the refusal must name {survivor!r}, not merely reject {word!r}"
    assert "allowed" in said, "the refusal must list the allowed values"


# ── 2 · and the ones nobody ruled a mapping for ────────────────────────────
@pytest.mark.parametrize("word", sorted(vocab.SEVERITY_RETIRED_UNMAPPED))
def test_a_retired_severity_with_no_ruling_is_refused_without_a_guess(word):
    fd = _load("file_defect")
    problems = fd.validate_inputs(_Args(severity=word))
    assert problems, f"{word!r} was accepted"
    said = " ".join(problems)
    # It must NOT propose a mapping — G46's own reason for never remapping a row.
    for invented in ("critical", "low"):
        assert f"write {invented!r}" not in said, (
            f"the refusal invented {word}->{invented}; nobody has ruled that, and a script "
            "that guesses destroys the evidence the register exists for"
        )


# ── 3 · good work still files ──────────────────────────────────────────────
@pytest.mark.parametrize("word", sorted(vocab.SEVERITY_WRITABLE))
def test_every_live_severity_still_files(word):
    fd = _load("file_defect")
    assert fd.validate_inputs(_Args(severity=word)) == []


def test_a_severity_sitting_in_the_module_column_is_refused():
    """G46 reports this shape on DEF-358 and will not guess the module."""
    fd = _load("file_defect")
    problems = fd.validate_inputs(_Args(module="high"))
    assert any("shifted" in p for p in problems)


def test_an_empty_required_field_is_refused():
    """`required=True` is satisfied by `--title ""`, which files an unreadable row."""
    fd = _load("file_defect")
    assert any("--title" in p for p in fd.validate_inputs(_Args(title="   ")))


# ── 4 · read is wider than write, and the gates agree ──────────────────────
def test_the_write_vocabulary_is_a_subset_of_what_the_gates_accept():
    """The 37 rows carrying a retired status must stay lawful.

    Asserted against the gates' OWN constants rather than against a copy: three
    modules holding three spellings of one vocabulary is how the register got
    two severity vocabularies, and a subset assertion is the cheapest thing that
    notices the day they part company.
    """
    import g26_defect_register as g26
    import g46_register_vocabularies as g46

    assert vocab.STATUS_WRITABLE < vocab.STATUS_ACCEPTED_ON_READ, (
        "the write set must be strictly narrower than the read set, or this is not a ratchet"
    )
    assert vocab.STATUS_ACCEPTED_ON_READ == set(g26.KNOWN_STATUS) == set(g46.STATUS), (
        "the shared read set and the two gates' sets have drifted apart"
    )
    assert vocab.SEVERITY_ACCEPTED_ON_READ == set(g46.SEVERITY)
    assert set(vocab.SEVERITY_RETIRED) | vocab.SEVERITY_RETIRED_UNMAPPED, "no retired words listed"
    assert not (set(vocab.SEVERITY_RETIRED) & vocab.SEVERITY_WRITABLE)


@pytest.mark.parametrize("word", sorted(vocab.STATUS_RETIRED))
def test_close_defect_refuses_a_retired_status_and_says_what_to_write(word):
    cd = _load("close_defect")
    assert word not in cd.STATUS_WRITABLE
    complaint = cd.explain_status(word)
    assert complaint and "allowed" in complaint


@pytest.mark.parametrize("word", sorted(vocab.STATUS_WRITABLE))
def test_close_defect_still_writes_every_live_status(word):
    cd = _load("close_defect")
    assert cd.explain_status(word) is None


# ── 5 · the register's own shape ───────────────────────────────────────────
HEADER = ",".join(
    "id reported_on reported_by title surface module severity found_in "
    "introduced_in category escape_reason status fixed_commit prevention".split()
)


def test_the_register_at_head_has_the_header_this_tool_writes():
    """The live file, not a fixture — this is the clause that goes red the day
    somebody adds a column and every appended row starts shifting."""
    fd = _load("file_defect")
    assert fd.validate_register_shape() == []


def test_a_drifted_header_is_refused(tmp_path):
    fd = _load("file_defect")
    register = tmp_path / "10-defect-log.csv"
    register.write_text(HEADER + ",owner\n", encoding="utf-8")
    fd.REGISTER = register
    problems = fd.validate_register_shape()
    assert problems, "a 15-column header accepted a 14-column append (DEF-WRK-4051's shape)"
    assert "owner" in problems[0]


def test_a_row_that_does_not_read_back_as_fourteen_fields_is_refused():
    """DEF-WRK-4051 read back as 23 fields and its `status` said `for the registry)`."""
    fd = _load("file_defect")
    assert fd.validate_row_round_trips(",".join(['"x"'] * len(fd.COLUMNS))) == []
    assert fd.validate_row_round_trips('"a","b"'), "a two-field row was accepted"


# ── 6 · the harness a lane actually uses ───────────────────────────────────
def test_the_command_line_refuses_todays_row_and_writes_nothing():
    """Drive `file_defect.py` exactly as a lane does, with DEF-WRK-4079's input.

    ⚠ **THIS CLAUSE EXISTS BECAUSE THE UNIT CLAUSES ABOVE FAIL FOR THE WRONG
    REASON.** Run against the tool as it stood before this guard, every one of
    them reports `AttributeError: module has no attribute 'validate_inputs'` —
    which proves the function is absent and says NOTHING about whether the fault
    is caught. A red that cannot tell "the guard is missing" from "the guard did
    not bite" is the shape law 11 records twice about `git --stat`.

    Through the CLI the same run is unambiguous: the old tool exits 0 and prints
    a row containing `"major"`; the new one exits 1 and prints no row at all.
    That is the difference that matters, and the CLI is the path a lane takes —
    for this tool `__main__` IS the harness, unlike a gate, where `DEF-GOV-3733`
    warns that running the file directly exercises a path nobody uses.

    Cheap in the green state: the refusal happens before the two `git fetch`
    calls, so nothing touches the network.
    """
    import subprocess

    result = subprocess.run(
        [
            sys.executable, str(ROOT / "10-scripts" / "file_defect.py"), "--dry-run",
            "--id-module", "WRK",
            "--title", "THE HEADLINE LAW-14 TEST COULD NOT FAIL",
            "--surface", "06-backend/tests/test_us_wrk_044_sync_pg.py",
            "--module", "work", "--severity", "major",
            "--found-in", "2.194.0", "--introduced-in", "2026-09-05",
            "--category", "check-that-does-not-check",
            "--escape-reason", "nothing could have caught it",
            "--prevention", "the duplicate now arrives INSIDE the batch",
        ],
        capture_output=True, text=True, timeout=300,
    )
    printed = result.stdout + result.stderr
    assert '"major"' not in printed, (
        "the tool built a row carrying the retired severity — this is exactly "
        "DEF-WRK-4079 and DEF-MET-4081, which were filed this way and mapped by hand"
    )
    assert result.returncode == 1, f"expected a refusal, got exit {result.returncode}"
    assert "nothing was written" in printed
