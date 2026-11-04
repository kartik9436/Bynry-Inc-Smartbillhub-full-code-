#!/usr/bin/env python3
"""Resolve a conflict in an APPEND-ONLY register by keeping both sides — and
refuse when "both sides" would mean the same id twice.

WHY THIS EXISTS.  Six lanes work one branch at a time through a merge lane, and
every one of them appends to `12-governance/10-defect-log.csv`,
`01-open-questions.md` and `09-human-review-ledger.md`.  Git cannot merge those:
two lanes appending different rows at the same offset is a textual conflict
every single time, and the resolution is always the same — keep both.  Doing it
by hand is how a lane's row gets dropped without anyone noticing.

WHY IT REFUSES.  "Keep both" is right for two APPENDS and catastrophic for two
lanes that took the same id: the register's primary key silently doubles, and
the id stops naming one thing.  That happened on 2026-08-27 with a fixture
serial (two lanes both took `V2.48.0.3`), which is what this script was first
written for.

⚠ AND THE FIRST VERSION'S CHECK WAS THE WRONG SHAPE (DEF-975, the same day).
It compared the two sides of each conflict HUNK.  That cannot see the case that
actually bites: a lane which EDITS an existing row (`open` → `fixed`) makes git
read the edited copy as an ADDITION and leave the original as CONTEXT, one side
of a hunk against a line outside it.  `DEF-902` was duplicated exactly so, the
check printed "no id collision" over it, and it reached a pushed commit.  So the
check is over the WHOLE RESOLVED FILE — the only form that can answer "does any
id now appear twice".

It cannot tell you WHICH copy to keep; when it refuses, look at the two rows and
decide (usually: keep the edited one, in the original's position, so the
register stays chronological).

⚠ **AND A DUPLICATE THAT IS ALREADY IN THE FILE TURNS THIS WHOLE TOOL OFF FOR
EVERY LANE ON THE BRANCH — `DEF-GOV-7650`, 2026-09-28, fixed in `2.391.1`.**
The check above is over the WHOLE RESOLVED FILE, which is the only shape that
can answer *"does any id now appear twice"* — and the price of that correctness
is that a duplicate nobody on this branch created still makes every register
merge refuse. `DEF-GOV-6930` and `DEF-RAT-6960` each sat in
`12-governance/10-defect-log.csv` twice, one copy `fixed` with a version and the
other `open` with nothing, and for days this script answered *"Nothing was
written. Decide which copy survives, by hand."* to every lane that reached it —
on days when three lanes took the same id. **A safety tool that always refuses
is a safety tool nobody uses** (hard-won law 7: a guard is a claim only while
somebody reads its output).

Nothing changed here, deliberately — the refusal is right. What changed is
WHEN the duplicate is caught: `10-scripts/push_register_guard.py` now refuses a
push that makes any id appear more times than it does at the tip, so a duplicate
is named by the lane that creates it instead of by the next lane that merges.
That check is a RATCHET, not a ban — a duplicate already on the branch blocks
nobody, and removing one passes silently, because removing one is the repair.

    python3 10-scripts/merge_register.py <path> [<path> ...]
"""

from __future__ import annotations

import re
import sys

# Each register names its rows differently; the id is what we count.
#
# ⚠ **THESE READ THE MODULE SEGMENT SINCE 2026-09-10, AND UNTIL THEY DID THIS
# WHOLE SCRIPT WAS A CHECK THAT COULD NOT CHECK.** The PO ruled on 2026-09-03
# that a question or a defect carries its module — `OQ-<MOD>-nnnn`,
# `DEF-<MOD>-nnnn` — and every id filed since is that shape. `(?:DEF|OQ|CR)-\d+`
# matches **none** of them: `"DEF-RAT-4826"` yields `[]`, not a partial match, so
# the collision guard counted ZERO ids over a register whose entire recent tail
# it could not see, and printed *"no duplicate id"* over a live duplicate.
#
# **Proved red on a real one, not a hypothetical:** on 2026-09-10 two lanes both
# took `DEF-RAT-4826` in the shared tree; this script read the file and reported
#
#     12-governance/10-defect-log.csv -> 0 conflict(s) resolved, no duplicate id
#
# which is hard-won law 7's *reporting zero over a scope it silently excludes* —
# and the worst version of it, because the scope excluded is the only part of the
# register anybody is still writing to.
#
# The pattern is CLAUDE.md's own, module segment optional so the eighty-nine
# hundred bare ids still resolve and nothing is renumbered. **The `{3,5}` and its
# lookahead are load-bearing**: without `(?!\d)`, `DEF-123456` reads as
# `DEF-12345` — the same bug one order of magnitude up.
_ID = r"(?:[A-Z]{3}-)?\d{3,5}(?!\d)"
PATTERNS = (
    (".csv", rf'^"((?:DEF|OQ|CR)-{_ID})"'),
    (".md", rf"\|\s*((?:OQ|DEF|CR|HR)-{_ID})\s*\|"),
)


def _pattern(path: str) -> str:
    for suffix, pattern in PATTERNS:
        if path.endswith(suffix):
            return pattern
    raise SystemExit(f"no id pattern for {path}")


def keep_both(path: str) -> int:
    pattern = _pattern(path)
    text = open(path, encoding="utf-8", newline="").read()

    out: list[str] = []
    ours: list[str] = []
    theirs: list[str] = []
    state = 0
    conflicts = 0
    for line in text.split("\n"):
        if line.startswith("<<<<<<< "):
            state, ours, theirs, conflicts = 1, [], [], conflicts + 1
            continue
        if state == 1 and line.startswith("======="):
            state = 2
            continue
        if state == 2 and line.startswith(">>>>>>> "):
            out.extend(ours)
            out.extend(theirs)
            state = 0
            continue
        (ours if state == 1 else theirs if state == 2 else out).append(line)
    if state != 0:
        raise SystemExit(f"  !! unterminated conflict marker in {path}")

    resolved = "\n".join(out)
    seen: dict[str, int] = {}
    for found in re.findall(pattern, resolved, re.M):
        seen[found] = seen.get(found, 0) + 1
    duplicates = sorted(i for i, count in seen.items() if count > 1)
    if duplicates:
        print(f"  !! DUPLICATE id(s) after resolving {path}: {duplicates}")
        print("     Nothing was written. Decide which copy survives, by hand.")
        return -1

    open(path, "w", encoding="utf-8", newline="").write(resolved)
    return conflicts


def main(paths: list[str]) -> int:
    failed = False
    for path in paths:
        count = keep_both(path)
        if count < 0:
            failed = True
            continue
        print(f"  {path} -> {count} conflict(s) resolved, no duplicate id")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
