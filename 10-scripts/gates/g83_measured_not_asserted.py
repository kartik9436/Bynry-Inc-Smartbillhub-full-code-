#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    CR-071 — the response-time specification, made measurable.
# Rules:    `04-docs/05-modules/15-portal/11-response-times.md` §5, verbatim:
#           *"Every portal endpoint's walkthrough records the measured time and
#           prints it, rather than asserting that a target was met. A number a
#           person can read beats a claim."* and *"A failure here is reported,
#           never rounded. If p95 for the balance screen is 900 ms, the report
#           says 900 ms against a 600 ms target — it does not say 'meets
#           target'."* · CLAUDE.md hard-won law 7 (proven RED first — see below)
#           · DEF-182 (a check whose output cannot distinguish pass from fail is
#           worse than no check, because it is trusted)
# Tests:    selftest() below · 10-scripts/tests/test_cr071_timings.mjs covers the
#           instrument this gate points lanes at
# Impacts:  10-scripts/render-checks/*.mjs
# ───────────────────────────────────────────────────────
"""G83 — a portal walkthrough MEASURES, and no walkthrough prints a verdict
instead of a number.

WHY THIS GATE EXISTS
--------------------
`CR-071` wrote response-time targets that nobody had. A target nobody measures
is a wish, and §5 says exactly how it is not to become one: the walkthrough
*prints the measured time*, and a miss *is reported, never rounded*. Both halves
are easy to lose, and they are lost in opposite directions:

  * the walkthrough that never measures at all — the obligation quietly not
    done, with every test still green;
  * the walkthrough that measures and then helpfully turns the number into
    `check(p95 < 600, "the balance screen meets target")` — which is the more
    dangerous one, because it LOOKS like proof. A reviewer reads "meets target",
    the figure never appears, and a 900 ms screen has been signed off.

THREE CLAUSES
-------------
**0 · The instrument exists and exports what a walkthrough imports.** Clause 1
below lets a file satisfy itself by importing `lib/timings.mjs`. If that file is
deleted or renamed, every walkthrough that imports it breaks at run time and
clause 1 would go on passing the ones that never imported it — `DEF-524`'s
shape, where `G14`'s hardcoded path outlived the file it named and reported PASS
through six UI defects. So the instrument is checked first.

**1 · Every portal / response-time walkthrough measures something.** That is
`cr068-<wave>-<slug>.mjs` (the portal's own waves) and `cr071-*.mjs` (this CR's
proof). Each must either import the shared instrument — which prints the table
and says what its own percentiles are worth — or print a percentile of its own.
`cr068-a-switch-it-on.mjs` predates the instrument and does the second: its step
11 loops thirty requests and prints min / median / p95. It passes honestly, and
no lane has to touch another lane's file for this gate to go green.

⚠ **CLAUSE 1 IS DORMANT UNTIL A `cr068-*` WALKTHROUGH LANDS, AND THE GATE SAYS
SO OUT LOUD.** When this was written, `cr068-a-switch-it-on.mjs` existed only as
an untracked file in a sibling lane's checkout. A gate reporting `PASS` over an
empty set is a check that cannot fail, which `DEF-182` says is worse than no
check because it is trusted — so the note names the dormancy in words rather
than reporting "0 walkthroughs all print a measured time", which reads like
proof and is not.

**2 · No walkthrough turns a measurement into a verdict.** A line of CODE (not a
comment) that says `meets target`, `within target`, `under target`, `within
budget` or `target met` must carry an interpolated value — `${…}` — on the same
line. A sentence with a number in it is a report; the same sentence without one
is the claim §5 forbids. Comments are stripped before this runs, deliberately:
this file's own docstring quotes the forbidden phrase, and so does the module's.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not read a number, compare it to a target, or fail a build on latency.
It cannot: no gate in this repository runs a browser. And §5 would not want it
to — an instrument that can fail a build on a response time is the assertion it
replaces. This gate guards the SHAPE of the proof, and a human reads the number.

PROVEN RED FIRST (law 7, 2026-09-04) — THREE SABOTAGES, ONE OF WHICH FOUND A BUG
--------------------------------------------------------------------------------
Clause 1, with the import and every percentile deleted from
`cr071-response-times-instrument.mjs`::

    G83 FAIL — 10-scripts/render-checks/cr071-response-times-instrument.mjs measures
    nothing: it neither imports lib/timings.mjs nor prints a percentile
    (11-response-times.md §5)

⚠ **THAT SABOTAGE PASSED THE FIRST DRAFT OF THIS GATE, AND THAT IS THE WHOLE
ARGUMENT FOR LAW 7.** The draft tested `"lib/timings.mjs" in code`. The
walkthrough prints the module's NAME in its opening banner, so a file with its
import and all three percentiles removed still satisfied the check. The gate now
looks for an actual `import { … } from "…/lib/timings.mjs"`, and `selftest()`
carries the near-miss as a case of its own.

Clause 2, with `check(true, "the balance screen meets target")` added::

    G83 FAIL — 10-scripts/render-checks/cr071-response-times-instrument.mjs:174 claims
    'meets target' with no measured value on the line — §5: reported, never rounded

Clause 0, with the instrument moved out of the way::

    G83 FAIL — 10-scripts/render-checks/lib/timings.mjs is missing — every walkthrough
    that imports it is broken, and clause 1 would pass the ones that do not (DEF-524)

`selftest()` replays all three on in-memory bodies — the near-miss included — and
`run()` refuses to report anything until it has.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
RENDER_CHECKS = REPO / "10-scripts" / "render-checks"
INSTRUMENT = "lib/timings.mjs"

#: An actual ES import of the instrument — NOT a mention of its name.
#: ⚠ The first draft of this gate tested `"lib/timings.mjs" in code`, and the
#: RED proof caught it: this repo's own walkthrough prints the module's NAME in
#: its opening banner (`console.log(`… proving lib/timings.mjs on the STAFF
#: app`)`), so a file that had had its import and every percentile deleted still
#: passed. A substring of prose is not evidence of a call, and law 7 exists for
#: exactly the ten minutes that found this.
IMPORTS_INSTRUMENT = re.compile(
    r"""import\s*\{[^}]*\}\s*from\s*['"][^'"]*lib/timings\.mjs['"]"""
)

#: Phrases that convert a measurement into a claim. Lower-cased before matching.
VERDICT_PHRASES = (
    "meets target",
    "meets the target",
    "target met",
    "within target",
    "within the target",
    "under target",
    "within budget",
    "within the budget",
    "meets its target",
)


def strip_comments(source: str) -> list[str]:
    """The source with every comment blanked, one entry per original line.

    Line numbers are preserved so a finding can name one. Strings are walked
    rather than skipped so a `//` inside a URL literal is not read as a comment
    — which matters here, because every walkthrough is full of
    `http://127.0.0.1:4290`.

    ⚠ Known and accepted limit: a regex literal containing `//` or `/*` would
    confuse the scanner. No walkthrough has one, and the alternative is a
    JavaScript parser for a check about five phrases.
    """
    out: list[list[str]] = [[] for _ in source.splitlines() or [""]]
    line = 0
    i = 0
    mode = "code"
    n = len(source)
    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if ch == "\n":
            line += 1
            if line >= len(out):
                out.append([])
            if mode == "line_comment":
                mode = "code"
            i += 1
            continue
        if mode == "code":
            if ch == "/" and nxt == "/":
                mode, i = "line_comment", i + 2
                continue
            if ch == "/" and nxt == "*":
                mode, i = "block_comment", i + 2
                continue
            if ch in "\"'`":
                mode = {'"': "dq", "'": "sq", "`": "bt"}[ch]
                out[line].append(ch)
                i += 1
                continue
            out[line].append(ch)
            i += 1
            continue
        if mode == "block_comment":
            if ch == "*" and nxt == "/":
                mode, i = "code", i + 2
                continue
            i += 1
            continue
        if mode == "line_comment":
            i += 1
            continue
        # inside a string literal
        if ch == "\\":
            out[line].append(source[i : i + 2])
            i += 2
            continue
        closer = {"dq": '"', "sq": "'", "bt": "`"}[mode]
        out[line].append(ch)
        if ch == closer:
            mode = "code"
        i += 1
    return ["".join(parts) for parts in out]


def measures(source: str) -> bool:
    """True when the walkthrough prints a measured response time.

    Either it imports the shared instrument, or it computes a percentile of its
    own. Comments do not count: a file that only TALKS about measuring has not.
    """
    code = "\n".join(strip_comments(source))
    if IMPORTS_INSTRUMENT.search(code):
        return True
    return "p95" in code or "p99" in code


def verdicts_without_a_number(source: str, *, where: str) -> list[str]:
    """Lines of code that claim a target was met without showing the figure."""
    problems: list[str] = []
    for number, line in enumerate(strip_comments(source), start=1):
        low = line.lower()
        for phrase in VERDICT_PHRASES:
            if phrase not in low:
                continue
            if "${" in line:
                continue  # the measured value is right there
            problems.append(
                f"{where}:{number} claims {phrase!r} with no measured value on the "
                "line — §5: reported, never rounded"
            )
            break
    return problems


def _portal_walkthroughs() -> list[Path]:
    """The walkthroughs §5 obliges: the portal's own waves, and this CR's proof."""
    return sorted({*RENDER_CHECKS.glob("cr068-*.mjs"), *RENDER_CHECKS.glob("cr071-*.mjs")})


def _all_walkthroughs() -> list[Path]:
    return sorted(p for p in RENDER_CHECKS.glob("*.mjs"))


# ── the two sabotages, kept beside the code they guard ──────────────────────
_MEASURES = 'console.log(`p95 ${pct(95)} ms`);\n'
_MEASURES_VIA_MODULE = 'import { attachTimings } from "./lib/timings.mjs";\n'
#: The near-miss the RED proof found: the module NAMED but never imported.
_MENTIONS_ONLY = 'console.log(`proving lib/timings.mjs on the staff app`);\n'
_MEASURES_NOT = '// step 11 prints a p95 one day\nconsole.log("the front page loaded");\n'
_VERDICT_BARE = 'check(p95 < 600, "the balance screen meets target");\n'
_VERDICT_WITH_FIGURE = 'console.log(`p95 ${got} ms against ${want} ms — within target`);\n'
_VERDICT_IN_A_COMMENT = '// it must not say "meets target"\nconsole.log("hello");\n'
_URL_NOT_A_COMMENT = 'const BASE = "http://127.0.0.1:4290"; // meets target\nconsole.log(`p95 ${x}`);\n'


def selftest() -> bool:
    # clause 1 — both honest shapes pass, and the empty one bites
    if not measures(_MEASURES) or not measures(_MEASURES_VIA_MODULE):
        return False
    if measures(_MEASURES_NOT):
        return False
    if measures(_MENTIONS_ONLY):
        return False  # naming the module is not importing it
    # clause 2 — a bare verdict bites; the same sentence with its figure does not
    if len(verdicts_without_a_number(_VERDICT_BARE, where="x")) != 1:
        return False
    if verdicts_without_a_number(_VERDICT_WITH_FIGURE, where="x"):
        return False
    # …and a comment quoting the forbidden phrase is not a verdict
    if verdicts_without_a_number(_VERDICT_IN_A_COMMENT, where="x"):
        return False
    # …while a `//` inside a URL is not the start of one (DEF-974's shape: a
    # scanner that is wrong in a way nothing visible depends on)
    stripped = "\n".join(strip_comments(_URL_NOT_A_COMMENT))
    if "127.0.0.1:4290" not in stripped or "meets target" in stripped:
        return False
    return True


def run() -> tuple[str, str]:
    if not selftest():
        return "FAIL", "the gate's own self-test does not hold — it cannot see a bare verdict (DEF-182)"
    if not RENDER_CHECKS.is_dir():
        return "FAIL", f"{RENDER_CHECKS} is missing — nothing to guard"

    problems: list[str] = []

    # clause 0 — the instrument clause 1 points at must actually be there
    instrument = RENDER_CHECKS / INSTRUMENT
    if not instrument.is_file():
        problems.append(
            f"{instrument.relative_to(REPO)} is missing — every walkthrough that "
            "imports it is broken, and clause 1 would pass the ones that do not (DEF-524)"
        )
    elif "export function attachTimings" not in instrument.read_text(encoding="utf-8"):
        problems.append(
            f"{instrument.relative_to(REPO)} no longer exports attachTimings — the "
            "import in every walkthrough resolves to nothing"
        )

    portal = _portal_walkthroughs()
    for path in portal:
        source = path.read_text(encoding="utf-8")
        if not measures(source):
            problems.append(
                f"{path.relative_to(REPO)} measures nothing: it neither imports "
                f"{INSTRUMENT} nor prints a percentile (11-response-times.md §5)"
            )

    every = _all_walkthroughs()
    for path in every:
        problems.extend(
            verdicts_without_a_number(
                path.read_text(encoding="utf-8"), where=str(path.relative_to(REPO))
            )
        )

    if problems:
        return "FAIL", " | ".join(problems)

    using = sum(
        1
        for p in portal
        if IMPORTS_INSTRUMENT.search("\n".join(strip_comments(p.read_text(encoding="utf-8"))))
    )
    if not portal:
        clause1 = (
            "clause 1 is DORMANT — no cr068-*/cr071-* walkthrough exists to check, so "
            "it has proved nothing; it starts biting the moment one lands"
        )
    else:
        clause1 = (
            f"{len(portal)} portal/response-time walkthrough(s) each print a measured "
            f"response time ({using} through {INSTRUMENT})"
        )
    return "PASS", (
        f"the instrument is present and exports attachTimings; {clause1}; "
        f"{len(every)} walkthrough(s) carry no target verdict without its figure; "
        "self-test: all three sabotages bite"
    )


def main() -> int:
    status, note = run()
    print(f"G83 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
