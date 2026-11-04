#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2804 (2026-08-31) — every four-digit OQ was invisible to the gate
#          suite, and worse, `OQ_ID_RE.findall("OQ-1190")` returned `["OQ-119"]`,
#          so a stub blocked on one question was silently recorded against a
#          different, real question.
# Ruling:  PO 2026-08-31, verbatim: *"next question make them 5 digital"* — the
#          repo's id tooling reads FIVE digits. Existing ids are NOT renumbered
#          and NOT zero-padded; this is about what the tooling can READ.
# Rules:   CLAUDE.md hard-won law 7 (prove a guard goes RED before trusting it
#          green) · DEF-182 (a check whose output cannot distinguish pass from
#          fail is worse than no check, because it is trusted) · DEF-1651 (the
#          same one-character bug, `\d{3}` where `\d{3,}` was meant)
# Impacts: 10-scripts/gates/common.py · every gate and script that parses an id
# ───────────────────────────────────────────────────────
"""The id patterns must read a WIDE id as ONE id — never as a shorter one.

WHY THIS FILE EXISTS, AND WHY THE OBVIOUS TEST IS NOT ENOUGH
------------------------------------------------------------
A test asserting *"the pattern accepts five digits"* passes on a pattern that
also accepts garbage, and — much more importantly — it passes on the **broken**
pattern too. `re.compile(r"OQ-\\d{3}")` matches inside `OQ-123456` perfectly
happily. It is a SEARCH pattern, so it finds `OQ-123`, reports success, and
hands the caller a different, real question's id.

**So the case that matters is not acceptance, it is ATTRIBUTION**, and every
assertion below is written that way: the id that comes back must be the id that
was written down. Measured on the code as it stood on 2026-08-31:

    common.OQ_ID_RE.findall("OQ-1190")           ->  ['OQ-119']
    common.US_ID_RE.findall("US-BIL-1234")       ->  ['US-BIL-123']
    common.BR_ID_RE.findall("BR-RAT-1000")       ->  ['BR-RAT-100']

`OQ-119`, `US-BIL-123` and `BR-RAT-100` are all REAL ids belonging to other
subjects. Nothing raised, nothing was skipped, and both readings are
indistinguishable to every caller — which is exactly the shape of failure this
repo keeps paying for.

WHY THE `BR-` CASE IS THE URGENT ONE
------------------------------------
No `BR-` or `US-` id in `04-docs/` exceeded three digits when this was written,
so nothing was misattributed yet. But `BR-RAT` stood at **962** with three rules
minted that afternoon, and `BR-MET` at **941** — 37 and 58 ids from the cliff.
The day `BR-RAT-1000` is minted, every reader in this repo silently resolves it
to `BR-RAT-100`: a rule citation pointing at the wrong rule, on a money path.
A dropped row is invisible; a misattributed money rule is worse than invisible.

WHAT THIS FILE DELIBERATELY DOES NOT ASSERT
-------------------------------------------
It does not assert any existing id has been widened or zero-padded. Nothing is
renumbered by this change — `OQ-291` stays `OQ-291`. The register-count check
below reads the LIVE register on purpose (it is the one thing that cannot be
proved with synthetic text: that no row of the real file falls out of the
parser), and every other case is synthetic so it still means something on the
day the live register no longer contains these ids.

Runs both ways::

    python3 10-scripts/tests/test_def2804_id_width.py
    pytest 10-scripts/tests/test_def2804_id_width.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "10-scripts" / "gates"))

import common  # noqa: E402


# ── The attribution cases — (pattern, text, the ONE id that must come back) ──
#: Each pair is a WIDE id and the SHORTER, REAL id a three-digit pattern
#: silently returns instead. The second element of each tuple is the value the
#: broken code actually produced, quoted so a future reader can tell this test
#: from one that merely checks acceptance.
ATTRIBUTION_CASES = [
    ("OQ_ID_RE", "OQ-1190", "OQ-119"),
    ("OQ_ID_RE", "OQ-1201", "OQ-120"),
    ("OQ_ID_RE", "OQ-123456", "OQ-123"),
    ("US_ID_RE", "US-BIL-1234", "US-BIL-123"),
    ("US_ID_RE", "US-CUS-10000", "US-CUS-100"),
    ("BR_ID_RE", "BR-RAT-1000", "BR-RAT-100"),
    ("BR_ID_RE", "BR-MET-1000", "BR-MET-100"),
    ("BR_ID_RE", "BR-BIL-99999", "BR-BIL-999"),
]


def test_a_wide_id_resolves_to_itself_and_never_to_a_shorter_real_one() -> None:
    """DEF-2804's core: `OQ-1190` must be `OQ-1190`, never `OQ-119`."""
    for attr, wide, truncated in ATTRIBUTION_CASES:
        found = getattr(common, attr).findall(wide)
        assert found == [wide], (
            f"{attr}.findall({wide!r}) returned {found!r}. "
            f"{truncated!r} is a DIFFERENT, REAL id — a citation of {wide} is being "
            f"silently recorded against it, and nothing raises (DEF-2804)."
        )


def test_a_three_digit_id_still_reads_as_itself() -> None:
    """Widening must not swallow the neighbouring text of a NARROW id."""
    for attr, text, expected in [
        ("OQ_ID_RE", "blocked_by: OQ-291", ["OQ-291"]),
        ("OQ_ID_RE", "OQ-001, OQ-002", ["OQ-001", "OQ-002"]),
        ("US_ID_RE", "id: US-BIL-031", ["US-BIL-031"]),
        ("BR_ID_RE", "see BR-RAT-962 and BR-MET-941", ["BR-RAT-962", "BR-MET-941"]),
    ]:
        assert getattr(common, attr).findall(text) == expected, (
            f"{attr} stopped reading an ordinary three-digit id in {text!r}"
        )


def test_a_run_too_long_to_be_an_id_matches_NOTHING() -> None:
    """The `(?!\\d)` half — the one that stops DEF-2804 recurring at 100,000.

    There are two wrong ways to bound this and only one right one:

      * `\\d{3}`    reads `OQ-1190`   as `OQ-119`   — the defect.
      * `\\d{3,6}`  reads `OQ-12345667` as `OQ-123456` — THE SAME DEFECT, one
                    order of magnitude later, and it would be found the same
                    way: by a person noticing a citation pointing somewhere odd.
      * `\\d{3,6}(?!\\d)` reads `OQ-12345667` as nothing at all.

    Matching nothing is the honest answer, because there is no such id. A
    pattern that invents a shorter id from a longer number is the whole bug.
    """
    for text in ("OQ-12345667", "OQ-123456677"):
        assert common.OQ_ID_RE.findall(text) == [], (
            f"OQ_ID_RE.findall({text!r}) returned {common.OQ_ID_RE.findall(text)!r}. "
            "A digit run too long to be an id must match NOTHING — inventing a "
            "five-digit id out of a six-digit number is DEF-2804 again."
        )
    assert common.BR_ID_RE.findall("BR-RAT-1000000") == []


def _three_digit_literals_in_code(source: str) -> list[str]:
    """The fixed-three-digit id literals in `source`, COMMENTS EXCLUDED.

    ⚠ THE COMMENTS MUST BE STRIPPED OR THIS CHECK CANNOT PASS EVEN WHEN THE
    CODE IS RIGHT — and that is not a hypothetical: the first version of this
    file searched the raw source, and `common.py`'s new comment *explaining* the
    bug quotes `re.compile(r"OQ-\\d{3}")` verbatim. The check failed on correct
    code, which is the mirror image of a check that cannot fail and just as
    useless. Prose about a pattern is not a pattern.
    """
    import io
    import tokenize

    code = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type not in (tokenize.COMMENT, tokenize.NL):
            code.append(tok.string)
    joined = "\n".join(code)
    return [bad for bad in ('OQ-\\d{3}"', 'US-[A-Z]{3}-\\d{3}"', 'BR-[A-Z]{3}-\\d{3}"')
            if bad in joined]


def test_the_checker_above_actually_bites() -> None:
    """A check that cannot fail is worse than no check (DEF-182). So prove it.

    Synthetic source, so this stays true on the day `common.py` is rewritten.
    """
    broken = 'import re\n# a comment is not code\nOQ_ID_RE = re.compile(r"OQ-\\d{3}")\n'
    assert _three_digit_literals_in_code(broken) == ['OQ-\\d{3}"'], (
        "the three-digit detector did not flag a three-digit pattern — it would "
        "have reported the fix as present on the broken code"
    )
    prose_only = 'import re\n# we used to write re.compile(r"OQ-\\d{3}") and it truncated\nx = 1\n'
    assert _three_digit_literals_in_code(prose_only) == [], (
        "a COMMENT quoting the old pattern was read as code — this check would "
        "fail on a correct file and get switched off"
    )


def test_the_shared_patterns_are_not_hardcoded_to_three_digits() -> None:
    """The source itself, so a revert is caught rather than only its effect."""
    src = common.read_text(ROOT / "10-scripts" / "gates" / "common.py")
    found = _three_digit_literals_in_code(src)
    assert not found, (
        f"{found} back in common.py as CODE — a fixed three-digit id width. "
        "This is DEF-2804 and DEF-1651's one-character bug."
    )


def test_the_status_parser_keeps_the_whole_id() -> None:
    """`oq_status_by_id()` used `re.fullmatch(r"OQ-\\d{3}")` — a four-digit row
    matched nothing at all and was dropped from the dict with no message."""
    statuses = common.oq_status_by_id()
    wide = sorted(k for k in statuses if len(k.split("-")[1]) > 3)
    assert wide, (
        "no id wider than three digits reached oq_status_by_id(). Either the "
        "register genuinely has none (check it), or the fullmatch is still "
        "three-digit and 12 rows are silently absent (DEF-2804)."
    )


def test_every_register_row_reaches_the_parser() -> None:
    """The count check DEF-2804's own prevention column asked for.

    A future widening cannot silently drop rows again: this compares the rows
    the FILE has against the rows the PARSER returns, so a mismatch names a
    number instead of vanishing.
    """
    text = common.read_text(common.OQ_REGISTRY)
    rows = [ln for ln in text.splitlines() if ln.startswith("| OQ-")]
    ids_in_file = {ln.strip().strip("|").split("|")[0].strip() for ln in rows}
    parsed = set(common.oq_status_by_id())
    missing = sorted(ids_in_file - parsed)
    assert not missing, (
        f"{len(missing)} of {len(ids_in_file)} `| OQ-` rows never reach "
        f"oq_status_by_id(): {missing[:12]}. A row the parser cannot see is a "
        "question no gate can enforce."
    )


# ⚠ THE FIRST DRAFT OF THE SOURCE CHECK COULD NOT FAIL, and it is worth
# recording because it is the same shape this repo found seven instances of in a
# single day. Its needles were raw strings — `r"OQ-\d{3}\""` — and in a raw
# string `\"` is TWO characters, backslash and quote, so every needle ended in a
# backslash that appears nowhere in any file. All four "absent" assertions passed
# over the broken source they were pointed at. Fixing the escaping then exposed
# the OPPOSITE fault: the needle matched `common.py`'s new COMMENT, which quotes
# the old pattern to explain the bug, so the check failed on correct code. The
# version that survived strips comments with `tokenize` and carries its own
# bites-check above. Both faults were found by running it, not by reading it.


def test_the_defect_register_id_reader_handles_four_digits() -> None:
    """`file_defect.py` allocates `max + 1`; a truncating read hands out a
    number that is already taken. DEF is at four digits TODAY."""
    id_re = re.compile(rb'^"?DEF-(\d+)"?,')
    assert id_re.match(b'"DEF-2804","2026-08-31"').group(1) == b"2804"
    assert id_re.match(b'"DEF-12345","2026-08-31"').group(1) == b"12345"


def test_the_register_readers_handle_a_module_segment() -> None:
    """PO 2026-09-03: `OQ-<MOD>-nnnn`, `DEF-<MOD>-nnnn` from that day on. Until the
    parsers learned the segment, 27 register rows were invisible to every gate
    (DEF-3552) — g08 named them and nothing else did."""
    assert common._OQ_ROW_ID_RE.fullmatch("OQ-INT-1470")
    assert common._OQ_ROW_ID_RE.fullmatch("OQ-1489")
    assert not common._OQ_ROW_ID_RE.fullmatch("OQ-INTX-1470")
    assert common.id_number("OQ-WRK-1490") == 1490 and common.id_number("DEF-3541") == 3541
    import importlib.util
    spec = importlib.util.spec_from_file_location("file_defect", ROOT / "10-scripts" / "file_defect.py")
    fd = importlib.util.module_from_spec(spec); spec.loader.exec_module(fd)
    assert fd.ID_RE.match(b'"DEF-WRK-3542","2026-09-03"').group(1) == b"3542"
    assert fd._BLOCK_RE.search("DEF-WRK-3542–3551").groups() == ("3542", "3551")
    statuses = common.oq_status_by_id()
    assert "OQ-INT-1470" in statuses and "OQ-WRK-1490" in statuses


def test_close_defect_matches_the_whole_id_not_just_the_number() -> None:
    """DEF-3616. Widening a pattern to FIND a module-tagged row is only half the
    job: this tool then rebuilt `DEF-{number}` and compared that, so
    `--id DEF-WRK-3571` matched nothing while `--id DEF-3571` silently edited
    that very row — a matcher that finds the right line and compares the wrong
    string. Both halves must read the same id."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("close_defect", ROOT / "10-scripts" / "close_defect.py")
    cd = importlib.util.module_from_spec(spec); spec.loader.exec_module(cd)

    m = cd.ID_RE.match('"DEF-WRK-3571","2026-09-03"')
    assert m.group(1) == "DEF-WRK-3571" and m.group(2) == "3571"
    assert cd.ID_RE.match('"DEF-3552","x"').group(1) == "DEF-3552"

    lines = [b'"DEF-3552","x",', b'"DEF-WRK-3571","x",']
    assert cd._find_line(lines, "DEF-WRK-3571") == 1
    assert cd._find_line(lines, "DEF-3552") == 0

    # The bare number must NOT reach a module-tagged row, and the refusal names
    # the id that IS there rather than reporting a bare absence.
    try:
        cd._find_line(lines, "DEF-3571")
    except SystemExit as exit_:
        assert "DEF-WRK-3571" in str(exit_), str(exit_)
    else:
        raise AssertionError("a bare id closed a module-tagged row — DEF-3616 again")


def test_close_defect_can_address_a_two_letter_module_code() -> None:
    """2026-09-08. `ID_RE` demanded EXACTLY three capitals, and the register
    holds one row filed before that rule existed: `DEF-FE-4058`, two letters.

    Asked to close it the tool matched nothing, fell through to the "near"
    branch — which reads the SAME pattern, so it found nothing there either —
    and printed *"DEF-FE-4058 is not in .../10-defect-log.csv — nothing to
    close"* over a row sitting in the file. That is `DEF-2804`'s shape one
    family over: a matcher too narrow for its own data, reporting absence
    rather than refusing, and sending the caller to hand-edit a 2,292-row
    register — the exact operation `close_defect.py` exists to prevent.

    ⚠ The bare-number guard must still hold, or widening the class would let
    `--id DEF-4058` edit a module-tagged row (`DEF-3616`)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("close_defect", ROOT / "10-scripts" / "close_defect.py")
    cd = importlib.util.module_from_spec(spec); spec.loader.exec_module(cd)

    m = cd.ID_RE.match('"DEF-FE-4058","2026-09-05"')
    assert m is not None, "a two-letter module code is invisible to close_defect.ID_RE"
    assert m.group(1) == "DEF-FE-4058" and m.group(2) == "4058"

    lines = [b'"DEF-4057","x",', b'"DEF-FE-4058","x",', b'"DEF-LED-4638","x",']
    assert cd._find_line(lines, "DEF-FE-4058") == 1
    assert cd._find_line(lines, "DEF-LED-4638") == 2
    assert cd._find_line(lines, "DEF-4057") == 0

    try:
        cd._find_line(lines, "DEF-4058")
    except SystemExit as exit_:
        assert "DEF-FE-4058" in str(exit_), str(exit_)
    else:
        raise AssertionError("a bare id closed a module-tagged row — DEF-3616 again")

    # And the register really does hold exactly one such row, so this is a fact
    # about the data and not a hypothetical. If it ever holds none, the class
    # may narrow again — but nothing renumbers a cited id to make that true.
    import csv, re
    register = ROOT / "12-governance" / "10-defect-log.csv"
    with register.open(newline="", encoding="utf-8") as handle:
        odd = [
            row["id"]
            for row in csv.DictReader(handle)
            if (hit := re.match(r"^DEF-([A-Z]+)-\d+$", row["id"])) and len(hit.group(1)) != 3
        ]
    assert odd == ["DEF-FE-4058"], f"the set of non-three-letter ids moved: {odd}"


def _main() -> int:
    failures = []
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
        except AssertionError as exc:
            failures.append(f"FAIL {name}\n      {exc}")
        else:
            print(f"PASS {name}")
    for line in failures:
        print(line)
    print(f"\n{'FAIL' if failures else 'PASS'}: {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())


def test_allocating_inside_a_block_counts_module_tagged_rows_as_taken() -> None:
    """DEF-3582, and it is a correction as much as a test.

    ⚠ **THE ROW'S STATED CAUSE DOES NOT HOLD, AND SAYING SO IS THE POINT.** It
    reads *"its id reader sees only the bare `DEF-nnnn` spelling"*, which was
    true until 2026-09-03 18:03 (`13c489a2`) and is not true now: `ID_RE` carries
    the optional module segment, and the two assertions below are the proof
    rather than the claim. What the lane hit was almost certainly `DEF-1787`'s
    documented shape instead — a sibling's row living in a private `git worktree`
    is in none of the places `known_ids()` reads (the working tree, `HEAD`, the
    remote refs), so two lanes compute `max + 1` correctly and get the same
    number. **That one is not a parsing bug and cannot be fixed by widening a
    pattern.**

    So this test exists to stop the half that IS fixable from regressing
    silently. A module-tagged row must count as TAKEN when the allocator walks a
    reserved block; if it ever stops counting, a lane holding `3620–3629` is
    handed `3620` on top of `DEF-INT-3620` and the register grows two rows with
    one number — which `G26` cannot catch, because `DEF-INT-3620` and
    `DEF-BIL-3620` are different strings.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("fd_block", ROOT / "10-scripts" / "file_defect.py")
    fd = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, ["file_defect"]
    try:
        spec.loader.exec_module(fd)
    finally:
        sys.argv = argv

    # 1 · the scanner counts a module-tagged row and a bare one alike.
    rows = (
        b'"DEF-INT-3620","2026-09-03","x","t","s","integrations","low","x","x","x","x","open","","p"\n'
        b'"DEF-3621","2026-09-03","x","t","s","governance","low","x","x","x","x","open","","p"\n'
    )
    assert fd._ids_in(rows) == {3620, 3621}

    # 2 · and the block walk therefore steps over both. Three rows are taken —
    #     two of them module-tagged — so the fourth id in the block is the answer.
    fd.reserved_blocks = lambda: [(3620, 3629, "the lane under test")]
    assert fd.next_id({3620, 3621, 3622}, "3620-3629") == "DEF-3623"

    # 3 · the negative: a scanner blind to the segment would return DEF-3620
    #     again, on top of a row that already exists. Prove the assertion above
    #     can fail by feeding it the blindness this row was filed about.
    narrow = re.compile(rb'^"?DEF-(\d+)"?,')
    blind = {int(m.group(1)) for m in (narrow.match(ln) for ln in rows.splitlines()) if m}
    assert blind == {3621}, "the narrow reader must miss the module-tagged row"
    assert fd.next_id(blind, "3620-3629") == "DEF-3620", "…and hand out a number already taken"
