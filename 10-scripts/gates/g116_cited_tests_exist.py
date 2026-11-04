#!/usr/bin/env python3
"""G116 — a file's `Tests:` line must name a file that EXISTS.

THE DEFECT, THREE TIMES IN ONE DAY
----------------------------------
`DEF-RBS-4335`. `07-frontend/src/features/runbooks/RunResultPage.tsx` named
`RunResultPage.dom.test.tsx` under `Tests:` and promised, in a comment in its
own body, that *"`RunResultPage.dom.test.tsx` asserts the boundary by ADDRESS:
the day a volume runbook lands, that test names this file."* **The file had
never been written.** The page therefore had no test of any kind while two
files described a specific one.

It was not an isolated slip. On the same day `RunbookSetupPage.tsx` cited a
`RunbookSetupPage.dom.test.tsx` that did not exist — which is how two of its
holds rotted unseen — and `setupWire.ts` cited `setupModel.test.ts` twice, in
its `Tests:` header and again in its lifecycle `gates:` trailer, in the very
commit that fixed a hard-won-law-1 defect.

**Three occurrences of one shape in one day is when this repo writes a gate**,
and the prevention was already recorded in `DEF-RBS-4335`'s own row: *"a gate
that resolves every path named on a Trace header's `Tests:` line and fails when
one does not exist would catch the whole class in one pass — it is a filesystem
check over text already in a fixed position."* This is that gate.

WHY NOTHING CAUGHT IT
---------------------
This is hard-won law 1 — *a comment claiming a guarantee is not the guarantee* —
in the one place the repo treats as structured rather than as prose. Every check
that reads a Trace header reads its SHAPE: `trace_lint` requires the fields to be
present and well formed and has never asked whether the paths in them resolve.
The test suites report on the files they FIND, so a named-but-absent file is
**silence**, not a failure — law 7's *reporting zero over a scope it silently
excludes*, where the excluded scope is "the test that was promised". And `tsc`,
eslint and every gate pass over a comment naming any path whatsoever.

The damage is specific and it is not "less coverage". A `Tests:` line is how the
next lane decides whether a change is already guarded. Pointed at nothing, it
says *this is covered* — so the lane does not write the case, and the file ends
up with less coverage than an honestly blank header would have produced.

WHAT IT CHECKS
--------------
Every path ending `.ts` / `.tsx` / `.py` named on a `Tests:` line of a Trace
header in source code must resolve to a file that exists.

⚠ **RESOLVED BY BASENAME, NOT BY THE STRING AS WRITTEN, AND THAT IS DELIBERATE
RATHER THAN LAX.** The repo spells these paths four ways in live headers —
repo-relative (`06-backend/tests/test_x.py`), package-relative
(`src/components/Chip.test.tsx`), bare (`RunResultPage.dom.test.tsx`) and
occasionally a fragment. A gate that demanded one spelling would fail hundreds of
correct citations, and **a gate that is mostly wrong gets a `# noqa` instead of a
fix**. The question worth asking mechanically is the one that actually bit three
times: *does a file by this name exist anywhere in the repository?* A wrong-but-
existing path is a weaker fault and this gate does not claim to catch it.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7 — a check you cannot describe a
false pass for is one you do not understand):

  * **A basename that exists somewhere unrelated.** `SignIn.test.tsx` cited from
    the portal resolves against any `SignIn.test.tsx` in the tree. Accepted, and
    stated here rather than hidden: this gate answers *does this name exist*, and
    the three defects it was written for were all names that existed NOWHERE.
  * **A file listed by git but deleted on disk**, or the reverse. It reads
    `git ls-files` AND the working tree, so a test that exists only as an
    uncommitted new file still counts — a lane writing the test and the citation
    in one commit must not be failed on the way past.
  * **A header this parser cannot see.** `common.files_with_trace_header()`
    decides that, and the number of files scanned is PRINTED beside the number of
    citations checked, because a declared blind spot with no number attached is
    indistinguishable from an empty one.

THE BASELINE, AND WHY IT MAY ONLY FALL
--------------------------------------
**65 of 913 cited test paths did not resolve against `git ls-files` when this
gate was written — one in fourteen — and 59 of those did not resolve against the
working tree either**, across nine modules: the whole of Work's mobile app cites
nine front-end tests that do not exist, Work's backend cites five, and the portal
cites three. **The six-file gap between those two numbers is the point of reading
both**: they are tests a lane had written on disk and not yet committed, and a
gate that read only the index would have failed the lane doing exactly the right
thing. The baseline therefore holds 59, not 65. Failing on all of them would make the gate red from birth, which is
how a guard gets switched off instead of obeyed. They are listed in
`g116_missing_test_citations.txt` with the file that cites each one, so they can
be worked off one at a time — **either by writing the test or by correcting the
line, and correcting the line is a real fix**: a header that names nothing is
worse than one that names nothing at all.

**A citation NOT on that list fails the merge**, and the list may only ever
shrink — the same ratchet `G26`, `G40` and `G106` use.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

BASELINE = Path(__file__).resolve().parent / "g116_missing_test_citations.txt"

#: The `Tests:` row of a Trace header, in either comment syntax.
TESTS_LINE = re.compile(r"^\s*(?://|#)\s*Tests?\s*:\s*(.+)$")

#: A path-shaped token ending in a source extension. Deliberately greedy about
#: separators and strict about the extension: prose on a `Tests:` line ("see
#: also", "none yet") names no file and must not be read as one.
PATH_TOKEN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:tsx?|py)\b")


def repo_basenames() -> set[str]:
    """Every filename in the repo, from git AND from disk.

    Both, because the two disagree in exactly the case that matters: a lane that
    writes a test and its citation in one commit has the file on disk and not yet
    in the index, and failing that lane would punish the correct behaviour.
    """
    names: set[str] = set()
    listed = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, cwd=common.REPO_ROOT, check=False
    )
    for line in listed.stdout.splitlines():
        names.add(line.rsplit("/", 1)[-1])
    for root in ("06-backend", "07-frontend/src", "10-scripts"):
        base = common.REPO_ROOT / root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in (".ts", ".tsx", ".py"):
                names.add(path.name)
    return names


def paths_on_lines(lines: list[str]) -> list[str]:
    """Every path named on a `Tests:` line, from header lines already extracted.

    ⚠ **SPLIT OUT FROM `citations` BECAUSE THE SELF-TEST COULD NOT REACH IT.**
    The first draft's self-test handed `citations` a bare `// Tests: …` line and
    three of its six cases reported PASS — not because the rule held, but because
    `common.trace_header_lines` correctly returned NOTHING for a string with no
    `── Trace ──` marker, so the rule was never exercised at all. A self-test that
    exercises no code is law 7's *structurally incapable of failing*, in the very
    place this gate keeps its proof. It failed loudly here only because two other
    cases DID bite; had all six been written that way the gate would have shipped
    green and empty.
    """
    found: list[str] = []
    for line in lines:
        matched = TESTS_LINE.match(line)
        if matched is None:
            continue
        found.extend(PATH_TOKEN.findall(matched.group(1)))
    return found


def citations(sources: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """[(cited path, "citing file")] for every path on a `Tests:` line."""
    found: list[tuple[str, str]] = []
    for path, text in sources:
        for token in paths_on_lines(common.trace_header_lines(text)):
            found.append((token, path))
    return found


def baseline_pairs() -> set[tuple[str, str]]:
    """`{(cited, citing)}` — keyed on BOTH, so moving a bad citation to a new
    file does not inherit the old file's excuse."""
    if not BASELINE.is_file():
        return set()
    out: set[tuple[str, str]] = set()
    for line in common.read_text(BASELINE).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            out.add((parts[0], parts[1].strip()))
    return out


def check(
    cited: list[tuple[str, str]], present: set[str], excused: set[tuple[str, str]]
) -> list[str]:
    """The whole rule, as a pure function so the self-test can drive it."""
    problems: list[str] = []
    for target, citing in cited:
        if target.rsplit("/", 1)[-1] in present:
            continue
        if (target, citing) in excused:
            continue
        problems.append(f"{citing} cites {target}, which does not exist")
    return problems


def self_test() -> list[tuple[str, bool, str]]:
    """Each case is one way this gate could fail to bite. Law 7: a guard is
    proved RED on the defect it was written for before it is trusted green.

    ⚠ Every case drives `paths_on_lines`, the PURE half, precisely so that no
    case can pass by exercising nothing — see that function's own docstring.
    """
    results: list[tuple[str, bool, str]] = []

    # A1 — the real DEF-RBS-4335, in its own words.
    named = paths_on_lines(["// Tests:   RunResultPage.dom.test.tsx"])
    cited = [(target, "RunResultPage.tsx") for target in named]
    problems = check(cited, {"Other.test.tsx"}, set())
    results.append(
        (
            "A1 the real defect",
            named == ["RunResultPage.dom.test.tsx"] and len(problems) == 1,
            "an absent cited test is reported",
        )
    )

    # A2 — and it goes quiet when the file is there.
    results.append(
        (
            "A2 no false positive",
            check(cited, {"RunResultPage.dom.test.tsx"}, set()) == [],
            "a present cited test passes",
        )
    )

    # A3 — prose on a `Tests:` line names no file and must not be read as one.
    results.append(
        (
            "A3 prose is not a path",
            paths_on_lines(["// Tests: none yet — see the epic's section 3"]) == [],
            "no path token, no claim",
        )
    )

    # A4 — the baseline excuses a PAIR, not a name: the same bad citation moved
    # into a new file is a NEW fault and must fail.
    moved = [(target, "moved.ts") for target in paths_on_lines(["// Tests: setupModel.test.ts"])]
    results.append(
        (
            "A4 baseline is keyed on both",
            len(check(moved, set(), {("setupModel.test.ts", "setupWire.ts")})) == 1,
            "a baselined citation does not travel to another file",
        )
    )

    # A5 — a `Tests:` line carrying several paths is several claims.
    results.append(
        (
            "A5 several paths",
            len(paths_on_lines(["// Tests:   a.test.tsx · b.dom.test.tsx"])) == 2,
            "each path on the line is checked",
        )
    )

    # A6 — the resolution is by BASENAME, which is the documented compromise.
    repo_rel = [(t, "z.py") for t in paths_on_lines(["# Tests: 06-backend/tests/test_thing.py"])]
    results.append(
        (
            "A6 basename resolution",
            len(repo_rel) == 1 and check(repo_rel, {"test_thing.py"}, set()) == [],
            "a repo-relative citation resolves against the bare name",
        )
    )

    # A7 — a line that is NOT a `Tests:` row contributes nothing, so a path in a
    # `Rules:` or `Defects:` row is never read as a coverage claim.
    results.append(
        (
            "A7 only the Tests row",
            paths_on_lines(["// Defects: DEF-RBS-4335 (RunResultPage.dom.test.tsx)"]) == [],
            "only a Tests: line makes a claim about coverage",
        )
    )
    return results


def run() -> tuple[str, str]:
    failures = [name for name, ok, _ in self_test() if not ok]
    if failures:
        return "FAIL", (
            "the gate's own self-test does not hold (" + ", ".join(failures) + ") — a check whose "
            "output cannot distinguish pass from fail is worse than no check (DEF-182)"
        )

    scanned = common.files_with_trace_header()
    if not scanned:
        return "SKIP", "no file with a Trace header was found to read"

    sources = [(common.rel(path), text) for path, text in scanned]
    cited = citations(sources)
    present = repo_basenames()
    excused = baseline_pairs()
    problems = check(cited, present, excused)

    if problems:
        head = " | ".join(problems[:5])
        more = f" (+{len(problems) - 5} more)" if len(problems) > 5 else ""
        # ⚠ **THE SCOPE NUMBERS GO ON THE FAIL LINE TOO — `DEF-GOV-6690`.**
        # This gate's own docstring promises that "the number of files scanned is
        # PRINTED beside the number of citations checked, because a declared blind
        # spot with no number attached is indistinguishable from an empty one" —
        # and until 2026-09-25 that sentence was honoured ONLY in the PASS branch,
        # which is the one state this gate has never been in. A reader of the red
        # line could not tell 27 bad citations out of 1,266 from 27 out of 30,
        # nor see that 58 more are baselined and excluded from the count entirely.
        # A failing check is exactly when a reader needs to know what it looked at.
        scope = (
            f" [scope: {len(problems)} bad of {len(cited)} cited path(s) across "
            f"{len(sources)} file(s) with a Trace header, resolved against "
            f"{len(present)} filename(s); {len(excused)} pair(s) baselined and "
            "EXCLUDED from this count]"
        )
        return "FAIL", (
            head + more + "." + scope + " A `Tests:` line is how the next lane decides whether a change is "
            "already guarded, so one pointing at nothing says 'this is covered' and the case "
            "never gets written (DEF-RBS-4335). Write the test, correct the line — correcting it "
            f"is a real fix — or add '<cited> <citing>' to {BASELINE.name} with the reason. That "
            "list may only ever shrink."
        )

    still = sum(1 for pair in cited if pair in excused)
    return "PASS", (
        f"{len(cited)} cited test path(s) across {len(sources)} file(s) with a Trace header all "
        f"name a file that exists, against {len(present)} filenames in the repo; "
        f"{len(excused)} citation(s) baselined and still cited {still} time(s); "
        "self-test: 7/7 bite (the real DEF-RBS-4335, the no-false-positive case, prose on a "
        "Tests: line, the baseline not travelling between files, a multi-path line, "
        "basename resolution and a non-Tests row making no claim)"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
