#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects: DEF-CWP-4004 (the portal wrote MIN-width variants in a DESKTOP-FIRST
#          theme, so the directory carried both conventions across eight sites
#          in three files) · DEF-974 (a Tailwind utility in a file the
#          migration ledger does not list renders as NOTHING AT ALL) ·
#          DEF-182 (a check whose output cannot distinguish pass from fail)
# Rules:   B14 rule 21 (a new screen is written in Tailwind utilities) ·
#          `07-frontend/src/styles/tailwind.css`, verbatim in capitals:
#          *"DESKTOP-FIRST. Every responsive rule in this product is
#          max-width, so authoring reads `max-lg:grid-cols-1` — NEVER
#          `lg:grid-cols-2`"* · G36 (the same rule for `@media` queries in
#          stylesheets, ratchet 0 — this is its `.tsx` complement) ·
#          CLAUDE.md law 7 (proved RED first, through the harness that runs it)
# Tests:   self_test() below, exercised by run()
# Impacts: 07-frontend/src/**/*.tsx · g107_min_width_baseline.txt
# ───────────────────────────────────────────────────────
"""G107 — one responsive direction, and it is the one the theme is built for.

⚠ **G36 IS THE OTHER HALF OF THIS AND IT IS NOT A DUPLICATE.** `G36
breakpoint-direction` has enforced desktop-first since 2026-08-19 and holds a
ratchet at zero — but it reads `SRC.rglob("*.css")`, so it only ever sees a
`@media` query in a STYLESHEET. Under B14 rule 21 a new screen adds no
stylesheet class at all: its responsive rules are Tailwind variants in `.tsx`,
which G36 cannot open. That is the whole of DEF-CWP-4004's escape — the
convention was gated in the half of the codebase that is being migrated AWAY
from, and ungated in the half everything new is written in.

⚠ **THIS RESOLVES NO OPEN QUESTION.** `OQ-274` is OPEN and is about WHICH
WIDTHS the breakpoint set should hold; this gate is only about which DIRECTION
authoring is written in, which is already settled — stated in capitals by the
theme and ratcheted at zero by G36. No width moves here and no value is chosen.

WHY THIS EXISTS
---------------
`tailwind.css` does not merely prefer max-width, it explains why the min-width
namespace is CLEARED rather than extended:

    leaving the defaults in place gives two scales pointing in opposite
    directions with overlapping names, and the mismatch is silent — `lg:` and
    `max-lg:` would both compile and mean different viewports.

**Both forms compile.** A declared breakpoint generates `md:` and `max-md:`
alike, so `tsc`, eslint, `toContain` and even `routeBUtilities.test.ts` — which
asks the REAL Tailwind compiler whether a class is real — all pass on either.
`routeBUtilities` is the strongest class check in this repo and it cannot see
this, because the wrong-direction class is a perfectly real class.

And in the simple two-column case the two forms agree at the boundary:
`grid-cols-1 md:grid-cols-2` and `grid-cols-2 max-md:grid-cols-1` render the
same thing. **So nothing is visibly wrong, and that is precisely the problem** —
the cost is that a lane opening one component to learn the house style finds
the opposite of what the theme mandates, and copies it. That is how the portal
reached eight sites in three files while `KpiRow`, written the same week,
carried the correct form and a docstring explaining it.

⚠ **WHAT THIS GATE CANNOT SEE, SAID OUT LOUD (hard-won law 1).** It reads
STRING LITERALS in source. A class name built by interpolation — ``
`grid-cols-${n}` `` — is invisible to it, exactly as it is invisible to
Tailwind's own scanner. It also cannot tell a correct max-width layout from an
incorrect one; it only asks which DIRECTION the authoring is written in.

⚠ **AND IT IS NOT A RENAME CHECK.** Converting a `col-span` is a real layout
change: with a `grid-cols-12` base, a child still asking for `col-span-8` when
the grid collapses to one column spans into SEVEN IMPLICIT COLUMNS. That is why
the portal's conversion carried `max-md:col-span-1` on both `TwoCol` children,
and why this gate refuses new occurrences rather than offering to fix them.

WHAT IT ASSERTS
---------------
  1. **`07-frontend/src/portal/` is at ZERO and stays there.** Every site was
     converted with DEF-CWP-4004; a new one fails the merge and names the file
     and the class.
  2. **The rest of the front end may not grow.** The staff app carries the same
     drift and converting it is its own piece of work with a browser open — so
     its sites are recorded in `g107_min_width_baseline.txt` and a site that is
     NOT in that file fails. The count may fall and may never rise.
  3. **A baseline line that no longer matches anything FAILS**, so the file
     ratchets down instead of quietly recording history. A lane that fixes a
     site deletes its line; that is one line of work and it is what keeps the
     number honest.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

BASELINE = Path(__file__).resolve().parent / "g107_min_width_baseline.txt"

# The five names the theme declares. `2xl` is listed even though it owns one
# rule today: a gate that silently ignores a breakpoint is a gate with a hole.
BREAKPOINTS = ("sm", "md", "lg", "xl", "2xl")

# A bare min-width variant: the breakpoint name followed by a colon, not
# preceded by `max-` (or by any other word character, so `grid-cols-2xl:` and a
# stray `md` inside a longer token do not match).
MIN_WIDTH_RE = re.compile(r"(?<![\w:-])(" + "|".join(BREAKPOINTS) + r"):(?=[a-z\[])")

# String literals — the only place a class name can legitimately live. Scanning
# raw source would report the theme's own docstring quoting `lg:grid-cols-2`,
# which is prose ABOUT the rule, and a check that fires on the sentence
# explaining it teaches the next lane to delete the explanation (G100's lesson,
# recorded again in the 2026-09-05 decision log).
STRING_RE = re.compile(r'"([^"\n]*)"' r"|'([^'\n]*)'" r"|`([^`]*)`", re.DOTALL)

BLOCK_COMMENT_RE = re.compile(r"/\*[\s\S]*?\*/")
LINE_COMMENT_RE = re.compile(r"//[^\n]*")


def strip_comments(text: str) -> str:
    """Comments out. See STRING_RE's note — prose about a rule is not a use of it."""
    return LINE_COMMENT_RE.sub("", BLOCK_COMMENT_RE.sub("", text))


def variants_in(text: str) -> list[str]:
    """Every bare min-width variant used inside a string literal, in order."""
    found: list[str] = []
    for match in STRING_RE.finditer(strip_comments(text)):
        literal = match.group(1) or match.group(2) or match.group(3) or ""
        for hit in MIN_WIDTH_RE.finditer(literal):
            # Report the whole class token, which is what a person has to find.
            start = hit.start()
            tail = literal[start:]
            token = re.match(r"[^\s\"'`]+", tail)
            found.append(token.group(0) if token else hit.group(1) + ":")
    return found


def read_baseline() -> set[str]:
    if not BASELINE.is_file():
        return set()
    lines = common.read_text(BASELINE).splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}


def scan(files: list[tuple[str, str]]) -> set[str]:
    """`{"path\tclass"}` for every min-width variant found."""
    out: set[str] = set()
    for rel_path, text in files:
        for token in variants_in(text):
            out.add(f"{rel_path}\t{token}")
    return out


def check(files: list[tuple[str, str]], baseline: set[str]) -> list[str]:
    """The three assertions. Pure, so the self-test can drive it."""
    found = scan(files)
    problems: list[str] = []

    portal = sorted(s for s in found if s.split("\t")[0].startswith("07-frontend/src/portal/"))
    for site in portal:
        path, token = site.split("\t")
        problems.append(
            f"{path} writes `{token}` — a MIN-width variant in a DESKTOP-FIRST theme. "
            f"The portal was converted to zero of these by DEF-CWP-4004; authoring reads "
            f"`max-md:grid-cols-1`, never `md:grid-cols-2`. ⚠ On a `col-span` this is not a "
            f"rename: give the child its span as the BASE rule and add `max-md:col-span-1`, "
            f"or it spans into implicit columns when the grid collapses."
        )

    outside = {s for s in found if not s.split("\t")[0].startswith("07-frontend/src/portal/")}
    for site in sorted(outside - baseline):
        path, token = site.split("\t")
        problems.append(
            f"{path} writes `{token}` — a NEW min-width variant. This theme is desktop-first "
            f"(`tailwind.css`, in capitals). The staff app's existing sites are recorded in "
            f"g107_min_width_baseline.txt and that number may fall, never rise."
        )

    for site in sorted(baseline - found):
        path, token = site.split("\t")
        problems.append(
            f"g107_min_width_baseline.txt still lists `{token}` in {path} and it is no longer "
            f"there. Delete that line — the baseline ratchets DOWN, and a line that matches "
            f"nothing is history pretending to be a measurement."
        )

    return problems


def self_test() -> list[tuple[str, bool, str]]:
    """Each case is the shape of a real defect. Proved by breaking, not by reading."""
    results: list[tuple[str, bool, str]] = []

    portal = "07-frontend/src/portal/components/primitives.tsx"
    staff = "07-frontend/src/features/tenancy/Foo.tsx"

    good = [(portal, 'const a = "grid grid-cols-2 gap-4 max-md:grid-cols-1";')]
    results.append(("clean world is silent", check(good, set()) == [], str(check(good, set()))))

    bad = [(portal, 'const a = "grid grid-cols-1 gap-4 md:grid-cols-2";')]
    got = check(bad, set())
    results.append(
        ("a min-width variant in the portal bites", len(got) == 1 and "md:grid-cols-2" in got[0], str(got))
    )

    # DEF-CWP-4004's own mechanism: the theme's docstring QUOTES the wrong form
    # to forbid it. A gate that fires on the sentence explaining a rule teaches
    # the next lane to delete the explanation.
    prose = [(portal, '/* authoring reads `max-lg:grid-cols-1` — NEVER `lg:grid-cols-2` */\nconst a = 1;')]
    results.append(("a variant named only in a comment is not a use", check(prose, set()) == [], str(check(prose, set()))))

    baselined = [(staff, 'const a = "grid gap-4 md:grid-cols-2";')]
    key = f"{staff}\tmd:grid-cols-2"
    results.append(("a recorded staff site is tolerated", check(baselined, {key}) == [], str(check(baselined, {key}))))

    got = check(baselined, set())
    results.append(("an UNrecorded staff site bites", len(got) == 1 and "NEW min-width" in got[0], str(got)))

    got = check([(staff, "const a = 1;")], {key})
    results.append(("a baseline line matching nothing bites", len(got) == 1 and "ratchets DOWN" in got[0], str(got)))

    # `max-md:` must never be mistaken for `md:` — the whole point of the gate.
    maxform = [(portal, 'const a = "max-md:col-span-1 max-2xl:hidden";')]
    results.append(("the max- form is never a hit", check(maxform, set()) == [], str(check(maxform, set()))))

    return results


def run() -> tuple[str, str]:
    failures = [name for name, ok, detail in self_test() if not ok]
    if failures:
        return "FAIL", (
            "the gate's own self-test does not hold (" + ", ".join(failures) + ") — a check whose "
            "output cannot distinguish pass from fail is worse than no check (DEF-182)"
        )

    files = [
        (common.rel(p), common.read_text(p))
        for p in common.frontend_code_files()
        if ".test." not in p.name
    ]
    if not files:
        return "SKIP", "no front-end sources present"

    problems = check(files, read_baseline())
    if problems:
        return "FAIL", common.summarize(problems, limit=8)

    recorded = len(read_baseline())
    return "PASS", (
        f"the customer portal writes ZERO min-width variants; {recorded} recorded elsewhere, "
        f"a number that may only fall"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
