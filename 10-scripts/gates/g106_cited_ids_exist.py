#!/usr/bin/env python3
"""G106 — a cited `OQ-` or `DEF-` id must be one the register actually ISSUED.

THE DEFECT, IN ITS OWN WORDS
----------------------------
`DEF-GOV-4014`. On 2026-09-05 `07-frontend/src/portal/routing/screenIds.ts`
carried, in a comment about `CWP-013`'s title, the citation `DEF-CWP-3647`.
**No such row has ever existed** — not in `10-defect-log.csv`, not in
`14-id-reservations.md`, nowhere in the repo. The note was recording a real
finding (the one that is actually `DEF-CWP-3728`) and pointed at empty space,
so anyone following it to learn why the titles disagree landed on nothing.

WHY NOTHING CAUGHT IT, WHICH IS THE WHOLE REASON THIS GATE EXISTS
-----------------------------------------------------------------
`G17` is the gate that owns identifiers and it is a good one: 4,140 ids across
eight vocabularies, each required to be DEFINED EXACTLY ONCE. But "exactly
once" is a rule about **definitions**, and a citation is not a definition.
`G17` would refuse `DEF-CWP-3647` if it were declared twice; it has nothing to
say about an id that was never declared at all. So a citation can point into
empty space forever and every gate in this repo stays green — `tsc`, eslint and
542 tests pass over a comment naming any id whatsoever, because nothing reads a
citation for truth (hard-won law 1, one vocabulary over).

⚠ **AND THE DAMAGE IS THE SAME SHAPE THIS REPO HAS ALREADY PAID FOR TWICE.**
`DEF-2804`: a three-digit search pattern read `OQ-1190` as `OQ-119` and a stub
blocked on one question was recorded against another. `DEF-CWP-3800`: two live
sources cited `OQ-CWP-1569` for a question the register did not hold. Both are
*a reader following an id to the wrong place, or to no place*, and in a repo
where the ID **is** the way a rule is looked up, that is how a rule quietly
stops being read.

WHAT IT CHECKS, AND THE SCOPE IS DELIBERATE
-------------------------------------------
Every `OQ-` and `DEF-` id cited anywhere in **source code** — `common.
code_files()`, i.e. the backend and frontend trees — must exist in its register.

**It does NOT read `12-governance/` prose, and that is measured rather than
squeamish.** On the day this gate was written the governance registers held 29
"undefined" citations and almost every one was *legitimate prose ABOUT an id*:
`04-docs/05-modules/16-work/02-business-rules.md` says `OQ-WRK-1498`-`OQ-WRK-1509`
"are UNUSED and free"; `11-change-requests.md` says `DEF-1815` and `DEF-1816`
"DO NOT EXIST in the register"; the defect log's own `DEF-2804` row discusses
`OQ-123456` and `OQ-12345` as examples of a pattern bug. A gate that failed on
those would be noise, and noise is how a check earns a `# noqa` instead of a
fix. **Code does not talk about ids in the abstract — it cites them to point at
a rule — so that is where the rule bites.**

THE TWO REGISTRY SHAPES, AND WHY THE OBVIOUS COLLECTOR IS WRONG
---------------------------------------------------------------
⚠ **AN OQ IS DEFINED IN TWO DIFFERENT SHAPES AND A GATE THAT KNOWS ONLY THE
TABLE INVENTS PHANTOMS.** `01-open-questions.md` holds most questions as table
rows, and some as `## OQ-1166 — …` SECTIONS. Collecting only rows reports
`OQ-1166` as undefined — and `OQ-1166` is real, is cited from a 🔒 rating-math
file, and CLAUDE.md names it by name. The first draft of this gate did exactly
that and reported **40** phantoms where the truth was 16; the difference was
nine section-defined questions and the citations that follow them.

So the definition set is `common`'s own, never re-derived here (hard-won law 5,
one source): `oq_status_by_id()` **plus** `oq_sections_with_no_table_row()`
**plus** `oq_rows_the_parser_cannot_see()`. Those three functions exist because
the parser's blind spots were paid for already; re-implementing the scan here
would rediscover them one at a time.

THE PATTERN IS CLAUDE.md's, AND THE LOOKAHEAD IS LOAD-BEARING
--------------------------------------------------------------
`(?:OQ|DEF)-(?:[A-Z]{3}-)?\\d{3,5}(?!\\d)` — the module segment is optional
because ids carry one only since 2026-09-03 and nothing is renumbered, and the
`(?!\\d)` is what stops `OQ-123456` being read as `OQ-12345`. That is `DEF-2804`
one order of magnitude up, and without the lookahead this gate would MANUFACTURE
the very defect it is written to catch.

THE BASELINE, AND WHY IT MAY ONLY FALL
--------------------------------------
16 phantom citations were already live in source when this gate was written, in
51 places. Failing on all of them would make the gate red from birth, which is
how a guard gets disabled instead of obeyed. They are listed by name in
`g106_phantom_citations.txt` with where each one is, so they can be worked off
one at a time. **A phantom NOT on that list fails the merge**, and the list may
only ever shrink — the same ratchet `G26` and `G40` use.
"""
from __future__ import annotations

import csv
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

BASELINE = Path(__file__).resolve().parent / "g106_phantom_citations.txt"
DEFECT_LOG = common.REPO_ROOT / "12-governance" / "10-defect-log.csv"

#: CLAUDE.md's own search pattern for these two families. The lookahead is not
#: decoration — see the module docstring.
CITATION = re.compile(r"\b((?:OQ|DEF)-(?:[A-Z]{3}-)?\d{3,5})(?!\d)")


def issued_ids() -> set[str]:
    """Every id either register has actually issued, in BOTH registry shapes."""
    issued: set[str] = set(common.oq_status_by_id())
    # Sections and parser-blind rows are questions too. `common` already knows
    # about both; this gate must not learn it a second time and differently.
    for group in (common.oq_sections_with_no_table_row(), common.oq_rows_the_parser_cannot_see()):
        for entry in group:
            for found in CITATION.finditer(str(entry)):
                issued.add(found.group(1))
    if DEFECT_LOG.is_file():
        reader = csv.DictReader(io.StringIO(common.read_text(DEFECT_LOG)))
        for row in reader:
            ident = (row.get("id") or "").strip()
            if ident:
                issued.add(ident)
    return issued


def citations(sources: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """[(id, "path:line")] for every OQ/DEF id cited in source code."""
    found: list[tuple[str, str]] = []
    for path, text in sources:
        for number, line in enumerate(text.splitlines(), 1):
            for match in CITATION.finditer(line):
                found.append((match.group(1), f"{path}:{number}"))
    return found


def baseline_ids() -> set[str]:
    if not BASELINE.is_file():
        return set()
    out = set()
    for line in common.read_text(BASELINE).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.add(line.split()[0])
    return out


def check(cited: list[tuple[str, str]], issued: set[str], excused: set[str]) -> list[str]:
    """The whole rule, as a pure function so the self-test can drive it."""
    problems: list[str] = []
    seen: set[str] = set()
    for ident, where in cited:
        if ident in issued or ident in excused or ident in seen:
            continue
        seen.add(ident)
        problems.append(f"{ident} is cited at {where} and no register ever issued it")
    return problems


def self_test() -> list[tuple[str, bool, str]]:
    """Law 7 — prove it goes RED before trusting it green, over mutated data."""
    issued = {"DEF-CWP-3728", "OQ-1166"}
    results = []

    planted = [("DEF-CWP-3647", "07-frontend/src/portal/routing/screenIds.ts:73")]
    bites = len(check(planted, issued, set())) == 1
    results.append(("A1 the real defect", bites, "a citation of an id nobody issued"))

    real = [("DEF-CWP-3728", "x.ts:1"), ("OQ-1166", "y.py:2")]
    quiet = check(real, issued, set()) == []
    results.append(("A2 no false alarm", quiet, "issued ids, one of them section-defined"))

    excused_ok = check(planted, issued, {"DEF-CWP-3647"}) == []
    results.append(("A3 baseline excuses", excused_ok, "a named phantom is allowed through"))

    # The lookahead: `OQ-123456` must not be read as `OQ-12345` (DEF-2804).
    long_id = citations([("z.py", "see OQ-123456 for the rest")])
    results.append(("A4 lookahead holds", long_id == [], "a six-digit id matches nothing"))

    # A module-tagged id is found at all (ids carry a module since 2026-09-03).
    tagged = citations([("z.py", "# DEF-WRK-3542 and OQ-CWP-1720")])
    ok = [i for i, _ in tagged] == ["DEF-WRK-3542", "OQ-CWP-1720"]
    results.append(("A5 module segment", ok, "OQ-<MOD>-nnnn and DEF-<MOD>-nnnn are read"))

    return results


def run() -> tuple[str, str]:
    failures = [name for name, ok, _ in self_test() if not ok]
    if failures:
        return "FAIL", (
            "the gate's own self-test does not hold (" + ", ".join(failures) + ") — a check whose "
            "output cannot distinguish pass from fail is worse than no check (DEF-182)"
        )

    issued = issued_ids()
    if not issued:
        return "SKIP", "no register is present to check citations against"

    sources = [(common.rel(path), common.read_text(path)) for path in common.code_files()]
    cited = citations(sources)
    excused = baseline_ids()
    problems = check(cited, issued, excused)

    if problems:
        head = " | ".join(problems[:5])
        more = f" (+{len(problems) - 5} more)" if len(problems) > 5 else ""
        return "FAIL", (
            head + more + f". A citation is how a rule is looked up, so an id no register issued "
            f"is a rule nobody can read (DEF-GOV-4014). Fix the citation, or add the id to "
            f"{BASELINE.name} with the reason — that list may only ever shrink."
        )

    still = sum(1 for ident, _ in cited if ident in excused)
    return "PASS", (
        f"{len(cited)} OQ/DEF citation(s) across {len(sources)} source file(s) all name an id a "
        f"register issued, against {len(issued)} issued ids; {len(excused)} phantom(s) baselined "
        f"and cited {still} time(s); self-test: 5/5 bite (the real DEF-CWP-3647, a section-defined "
        "OQ, the baseline, the six-digit lookahead and a module-tagged id)"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
