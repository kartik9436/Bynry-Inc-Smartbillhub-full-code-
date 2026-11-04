#!/usr/bin/env python3
"""G39 — NO TRACKED FILE MAY CONTAIN A GIT CONFLICT MARKER.

WHY THIS EXISTS (DEF-490, 2026-08-21)
-------------------------------------
The rating module's canonical `02-business-rules.md` — the file that IS the
module's law — carried this, on the branch, for two commits:

    <<<<<<< HEAD
    | BR-RAT-103 | A CHARGE CODE PRICES ONE CUSTOMER CLASS …
    =======
    | BR-RAT-103 | A TAX HAS FOUR STATUSES …
    >>>>>>> worktree-agent-a7ae54cb8c1aba33d

An unresolved merge, committed and pushed. **Nothing objected.** A markdown
table is not compiled, imported, linted or rendered by any test in this repo,
so `tsc`, `vitest`, `pytest` and every content gate were green over a file that
said two different things under one rule number.

⚠ AND THIS GATE IS THE CHEAP HALF OF THE FIX. The expensive half is G17's
baseline: G17 *did* name the duplicate ids, in its own output, on the commit
that introduced them, and was not read because it had been red for weeks. Read
that story in `g17_duplicate_ids.py`. This gate exists because it catches the
same defect ONE STEP EARLIER — at the marker, before anyone has to reason about
which of two rows is the real rule — and because it is a single grep.

WHAT IT CHECKS
--------------
Every tracked file, for the three seven-character markers git writes. Binary
files and this gate's own source are skipped; a file that legitimately DISCUSSES
markers (this docstring, DEF-490's register row) writes them shorter or in prose
rather than as a line start, which is exactly what git's own markers never do:
git always writes them at column 0, followed by a space or end-of-line.

WHY THE CHECK IS ANCHORED AT COLUMN 0
-------------------------------------
`<<<<<<<` inside a sentence is prose. `<<<<<<<` at the start of a line, seven
characters, then a space or nothing, is git. Anchoring is what lets the register
row that DESCRIBES this defect quote the marker without failing the gate that
was written for it — a check whose own defect report cannot be filed is a check
nobody keeps.
"""

from __future__ import annotations

import re
import subprocess

import common

#: git writes exactly seven of each, always at column 0.
#:
#: ⚠ THE DIVIDER IS SPLIT OUT AND THE SELF-TEST IS WHY. A line of seven `=`
#: with nothing after it is ALSO a legal markdown setext heading underline, so
#: `=======` alone cannot be evidence of anything. The first draft of this gate
#: flagged it unconditionally and its own fixture B3 went BLIND — a false
#: positive waiting for the first document that underlines a heading that way.
#: A divider counts only in a file that ALSO carries an ours- or theirs-marker,
#: which is the only shape git can actually produce.
SIDES = re.compile(r"^(<{7}|>{7})(\s|$)")
DIVIDER = re.compile(r"^={7}(\s|$)")

#: Named, not guessed: the two places the markers are legitimately WRITTEN OUT
#: as line-anchored text — this gate's own docstring, and the RED PROBE below.
EXEMPT = {
    "10-scripts/gates/g39_conflict_markers.py",
}

MAX_NAMED = 8


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=common.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    # ⚠ DEDUPED, AND THE FIRST RUN IS WHY. During an unresolved merge `git
    # ls-files` prints a conflicted path ONCE PER STAGE — base, ours, theirs —
    # so the gate reported the same three markers three times and claimed 18
    # where there were 6. The count is the thing a reader acts on; a count that
    # triples under exactly the condition the gate exists to detect is worse
    # than no count. Order preserved so the report reads in tree order.
    return list(dict.fromkeys(p for p in out.split("\0") if p))


def offenders(paths: list[str]) -> list[str]:
    """`path:line` for every conflict marker found. Pure over the path list."""
    found: list[str] = []
    for rel_path in paths:
        if rel_path in EXEMPT:
            continue
        full = common.REPO_ROOT / rel_path
        try:
            text = full.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # binary or unreadable — git's markers are text
        lines = text.split("\n")
        sides = [(n, l) for n, l in enumerate(lines, 1) if SIDES.match(l)]
        if not sides:
            continue  # no ours/theirs marker → any `=======` here is markdown
        divs = [(n, l) for n, l in enumerate(lines, 1) if DIVIDER.match(l)]
        for lineno, line in sorted(sides + divs):
            found.append(f"{rel_path}:{lineno}  {line[:60]}")
    return found


def run() -> tuple[str, str]:
    paths = tracked_files()
    if not paths:
        return "SKIP", "no tracked files — nothing to scan"
    bad = offenders(paths)
    if bad:
        return "FAIL", (
            f"{len(bad)} git conflict marker(s) in {len({b.split(':')[0] for b in bad})} "
            f"tracked file(s): {common.summarize(bad, MAX_NAMED)} — an unresolved merge was "
            "committed. Resolve it as CONTENT (DEF-490: two rule rows under one id are two "
            "different rules, not a formatting problem), never by deleting one side unread."
        )
    return "PASS", f"{len(paths)} tracked file(s), no conflict markers"


def self_test() -> list[tuple[str, bool, str]]:
    """Law 7 — prove it bites before trusting it green.

    The fixtures are STRINGS, not files: the checker is anchored per line, so
    planting a marker in memory exercises exactly the code the real scan runs
    without writing a byte into a tree five other lanes are reading.
    """
    # (tag, file content, how many markers the scan must find)
    ours, div, theirs = "<" * 7, "=" * 7, ">" * 7
    cases = [
        ("A1 whole conflict ", f"a\n{ours} HEAD\nb\n{div}\nc\n{theirs} branch\nd\n", 3),
        ("A2 ours only      ", f"a\n{ours} HEAD\nb\n", 1),
        ("A3 theirs only    ", f"a\n{theirs} branch\nb\n", 1),
        ("B1 prose          ", "a table drawn with <<<<<<< inside a sentence\n", 0),
        ("B2 setext heading ", f"A Heading\n{div}\nbody text\n", 0),
        ("B3 six chars      ", "<" * 6 + " not seven\n", 0),
        ("B4 indented       ", f"  {ours} HEAD\n", 0),
    ]
    results = []
    for tag, text, expected in cases:
        lines = text.split("\n")
        sides = [n for n, l in enumerate(lines, 1) if SIDES.match(l)]
        found = len(sides) + (len([n for n, l in enumerate(lines, 1) if DIVIDER.match(l)]) if sides else 0)
        results.append((tag, found == expected, f"found {found}, expected {expected}"))
    return results


if __name__ == "__main__":
    status, detail = run()
    print(f"{status}: {detail}")
    print()
    print("--- Part 0: self-test (law 7 — prove the guard goes RED before trusting it green) ---")
    for tag, ok, text in self_test():
        print(f"  {'BITES' if ok else 'BLIND'} {tag}  {text}")
    raise SystemExit(0 if status in {"PASS", "SKIP"} and all(ok for _, ok, _ in self_test()) else 1)
