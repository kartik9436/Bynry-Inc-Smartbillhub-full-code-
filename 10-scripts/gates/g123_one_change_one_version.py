#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects: DEF-GOV-5139 (two lanes both published 2.246.0, 2026-09-13) ·
#          DEF-GOV-3756 (two lanes both shipped 2.141.0) ·
#          the 2.248.0/2.249.0 pair the same afternoon, and 2.174.0, which has
#          been published twice since 2026-09-05 and which nothing noticed for
#          eight days
# Rules:   12-governance/13-change-process.md step 7 (ONE version, derived
#          everywhere, recorded on every CR and defect fix) · CLAUDE.md
#          hard-won law 7 (proved RED first, in the harness that runs it) and
#          law 11 (an allocated number is a blob)
# Tests:   selftest() below — the arithmetic on synthetic input, never on the
#          real CHANGELOG
# Impacts: CHANGELOG.md · 10-scripts/allocate.py (the other half of the fix)
# ───────────────────────────────────────────────────────
"""G123 — one change is published under one version, and one version names one change.

WHY THIS GATE EXISTS
--------------------
`13-change-process.md` step 7 exists because the PO said versioning is *"many
times not followed correctly"*. Its whole point is that a person reporting a
defect can say **which build** — so a version number has to answer with exactly
one change.

On 2026-09-13, with eight lanes in one shared tree, it answered with two. Three
times in one afternoon:

  * **`2.246.0` twice, two different changes** — *"a customer's own details can
    be corrected"* and *"Adjust works, and it always could"* (`DEF-GOV-5139`).
  * **`2.248.0` and `2.249.0`, ONE change** — the statement entry written as a
    draft under the first number, renumbered, and the draft published by a
    sibling's whole-file commit before it was cleared.
  * **`2.174.0` twice, since 2026-09-05** — one lane appending its own entry
    twice, eight days earlier, and nothing anywhere noticed.

⚠ **THE TWO SHAPES ARE DIFFERENT AND A CHECK FOR ONE MISSES THE OTHER, WHICH IS
THE WHOLE REASON THIS FILE READS BODIES AND NOT JUST HEADINGS.** The first and
third are a repeated HEADING. The second is two DIFFERENT headings over one
body — and the heading check passes over it without a word. The fix proposed
when `DEF-GOV-5139` was filed was the heading check alone; it would have caught
two of the three and reported PASS on the one that happened next.

WHY `allocate.py` CANNOT CLOSE THIS ON ITS OWN
----------------------------------------------
It is the other half and it is not a substitute. `allocate.py version --bump`
already takes the maximum over the working tree AND every remote branch, and it
is correct. `--verify` deliberately does NOT read the working tree
(`DEF-GOV-3843`: at push time a lane's own number is already written there, so
counting it answered *TAKEN* for every number a lane could ask about).

**So a version is CLAIMED by editing three tracked files in a shared tree, long
before anybody pushes — and that is the one place `--verify` cannot look.** With
one lane that is a rare race. With eight it is the ordinary case. `allocate.py`
now PRINTS what the tree holds beside its verdict, which is what a person needs;
this gate is what catches the damage however it arose, including from a whole-
file commit that nobody ran the allocator for at all.

WHAT IT ASSERTS
---------------
1. **No `## [x.y.z]` heading appears twice.**
2. **No two entries carry the same body**, compared on the body's text with
   whitespace collapsed — two numbers for one change.
3. **It is not an empty loop** (`DEF-057`'s shape): fewer than 50 versioned
   entries in a changelog this size means the parse broke, and a parse that
   finds nothing would otherwise report a confident PASS.

It prints the number of entries scanned beside its verdict, so a reader can tell
a pass from a parse that found nothing — hard-won law 7's third habit.

PROVED RED BEFORE TRUSTED GREEN, THROUGH `run_gates` AND NOT `__main__`
----------------------------------------------------------------------
`DEF-GOV-3733`: a gate proved only through `python3 <file>` exercises a path the
suite never takes. The transcripts for both shapes are in the lane report and
`selftest()` holds the arithmetic for both.

Python 3.12 stdlib only. Safe to run from any cwd. Nothing here ever writes.
"""

from __future__ import annotations

import hashlib
import re

import common

CHANGELOG = common.REPO_ROOT / "CHANGELOG.md"

#: A released heading. `## [Unreleased]` is deliberately NOT matched — it is not
#: a version and it legitimately recurs across the file's history.
HEADING = re.compile(r"^## \[([0-9]+\.[0-9]+\.[0-9]+)\][^\n]*$", re.M)

#: Below this, the parse is broken rather than the changelog empty.
MIN_ENTRIES = 50


def entries(text: str) -> list[tuple[str, str]]:
    """Every (version, body) in the file, in order, bodies not normalised."""
    parts = HEADING.split(text)
    # split() with one capture group gives [prefix, v1, body1, v2, body2, ...]
    return [(parts[i], parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


def fingerprint(body: str) -> str:
    """A body's identity, insensitive to how it was wrapped or indented.

    ⚠ **WHITESPACE IS COLLAPSED ON PURPOSE.** The 2.248.0/2.249.0 pair differed
    by nothing at all, but a lane that re-wraps a paragraph while renumbering
    would otherwise slip past — and a duplicate that survives one reflow is the
    same defect wearing a different diff.
    """
    return hashlib.sha256(" ".join(body.split()).encode("utf-8")).hexdigest()


def duplicate_headings(found: list[tuple[str, str]]) -> list[str]:
    seen: dict[str, int] = {}
    for version, _ in found:
        seen[version] = seen.get(version, 0) + 1
    return sorted(v for v, n in seen.items() if n > 1)


def duplicate_bodies(found: list[tuple[str, str]]) -> list[tuple[str, ...]]:
    by_body: dict[str, list[str]] = {}
    for version, body in found:
        if not body.strip():
            continue  # an empty body is a stub, not a duplicated change
        by_body.setdefault(fingerprint(body), []).append(version)
    return sorted(tuple(v) for v in by_body.values() if len(set(v)) > 1)


def run():
    text = common.read_text(CHANGELOG)
    found = entries(text)

    if len(found) < MIN_ENTRIES:
        return "FAIL", (
            f"only {len(found)} versioned entr(ies) parsed out of "
            f"{common.rel(CHANGELOG)} — below the floor of {MIN_ENTRIES}, which "
            f"means the heading pattern stopped matching rather than the file "
            f"being short. A parse that finds nothing reports a confident PASS "
            f"(DEF-057's shape), so it is refused instead."
        )

    repeated = duplicate_headings(found)
    twinned = duplicate_bodies(found)
    problems: list[str] = []

    if repeated:
        problems.append(
            "published TWICE under one number: "
            + ", ".join(repeated)
            + " — a person reporting a defect says 'which build?' and that number "
              "answers with two different products (DEF-GOV-5139)"
        )
    for group in twinned:
        problems.append(
            "one change published under "
            + " AND ".join(group)
            + " — two numbers, one body. Almost always a draft written under the "
              "first number, renumbered, and the draft left behind; the heading "
              "check alone passes over this one"
        )

    if problems:
        return "FAIL", f"{len(problems)} version-publication problem(s): " + "; ".join(problems)

    print(f"note: {len(found)} versioned entries scanned, newest {found[0][0]}")
    return "PASS", (
        f"{len(found)} versioned entries, each number used once and each change "
        f"published once"
    )


def selftest() -> int:
    """Both shapes, on synthetic input — never on the real changelog."""
    failed = 0
    same_twice = "## [1.2.0] — a\n\nbody one\n\n## [1.2.0] — b\n\nbody two\n"
    two_numbers = "## [1.3.0] — a\n\nthe same words\n\n## [1.2.0] — b\n\nthe  same\nwords\n"
    clean = "## [1.3.0] — a\n\nfirst change\n\n## [1.2.0] — b\n\nsecond change\n"
    cases = [
        (same_twice, duplicate_headings, ["1.2.0"], "a repeated heading is caught"),
        (same_twice, duplicate_bodies, [], "two different bodies are not a duplicate"),
        (two_numbers, duplicate_headings, [], "the heading check CANNOT see two numbers for one change"),
        (two_numbers, duplicate_bodies, [("1.3.0", "1.2.0")], "one body under two numbers is caught, reflowed or not"),
        (clean, duplicate_headings, [], "a clean file has no repeated heading"),
        (clean, duplicate_bodies, [], "a clean file has no twinned body"),
    ]
    for text, fn, want, label in cases:
        got = fn(entries(text))
        if got != want:
            print(f"selftest FAILED: {label} — got {got!r}, wanted {want!r}")
            failed = 1
        else:
            print(f"selftest ok — {label}")
    return failed


def main() -> int:
    if "--selftest" in __import__("sys").argv:
        return selftest()
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
