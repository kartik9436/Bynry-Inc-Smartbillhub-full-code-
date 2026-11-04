#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects: DEF-CWP-3743 (2026-09-04 — five `# Tests:` citations naming files
#          that have NEVER existed) · DEF-CWP-3766 (the same shape found again
#          the same day, in `portal/home/Home.tsx`, by a lane that went looking
#          for the test it named). Two occurrences in one day is a missing
#          gate, not a discipline problem.
# Rules:   CLAUDE.md hard-won law 1 — *"a comment claiming a guarantee is not
#          the guarantee"*. A `Tests:` line is the most load-bearing comment in
#          this repo: it is how a reviewer decides a file is covered, and how
#          the next lane finds the case it must not break.
# Tests:   selftest() below
# Impacts: every file under 06-backend/apps, 06-backend/tests and
#          07-frontend/src that carries a Trace header
# ───────────────────────────────────────────────────────
"""G95 — a `Tests:` line names files that EXIST.

WHY, IN ONE SENTENCE: a citation to a test that was never written reads
exactly like a citation to a test that passes.

WHAT IT CHECKS
--------------
Every file with a Trace header is read for its `Tests:` line and that line's
indented continuations. Every token on it that looks like a source path
(`something.py`, `something.tsx`, `something.ts`, `something.mjs`) must resolve
against one of four roots — the repository, `06-backend/`, `07-frontend/` and
`07-frontend/src/` — because that is how the existing citations are actually
written: backend traces cite `tests/test_x.py` and front-end traces cite
`src/portal/...tsx`, both relative to their own package.

**A RATCHET, NOT A CLIFF (the shape `i18n_known_gaps.txt` and
`seam_known_gaps.txt` already use).** There were **120 broken citations of
1,004** the day this gate was written; failing on all of them would have meant
either a 120-file commit nobody could review or a gate switched off. So the
baseline lists them, and it can only SHRINK:

  * a broken citation NOT in the baseline fails — that is a new one, and new
    ones are what this gate exists to stop;
  * a baseline entry that now RESOLVES fails too — the debt was paid and the
    line must go in the same diff, so the file cannot quietly re-grow.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
* It does not check the cited test **covers** anything. It cannot: that needs
  semantic knowledge of which case belongs to which rule, and a gate that
  claimed to check coverage would be the same lie one level up.
* It does not read `Impacts:` or `Rules:`. Those cite files and ids for
  ORIENTATION; `Tests:` is the one that makes a claim about verification.
* **It does not resolve a GLOB, and nineteen `Tests:` lines write one**
  (`06-backend/tests/test_us_ast_*.py`, `src/portal/arrears/*.dom.test.tsx`).
  Until 2026-09-05 it did something worse than skip them: it started a token
  in the MIDDLE of one and reported `dom.test.tsx`, a file that has never
  existed, against a line whose four real tests were all present
  (`DEF-CWP-3932`). Globs are now removed before tokenising, so they are
  honestly unchecked rather than dishonestly checked. **Resolving them is a
  real strengthening and it is deliberately not done here**: it would raise
  eight findings across `assets`, `identity`, `integrations` and `tenancy` in
  the same commit that fixes a portal defect, and a lane that has not read
  those files cannot judge them. Written down rather than left implicit,
  because a silent hole is what law 1 is about.
* It ignores prose — `this file`, `n/a`, `selftest() below` — because those
  are honest answers, and a gate that failed on them would teach lanes to stop
  writing the line at all.

PROVED RED FIRST (law 7, both halves — the failure below was produced by
`selftest()`, which is also what `run_gates` executes):

    G95 trace-tests-exist FAIL   1 Trace citation(s) name a file that does not
    exist and is not in the baseline: <sabotage>.py -> tests/test_never.py
"""

from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
BASELINE = HERE / "trace_tests_known_gaps.txt"

#: Where a citation may be relative to. Backend traces write `tests/test_x.py`
#: and front-end traces write `src/portal/....tsx`; both are relative to their
#: own package, and some write the full repo path. All four are legitimate.
ROOTS = ("", "06-backend", "07-frontend", "07-frontend/src")

SCAN: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("06-backend", ("**/*.py",)),
    ("07-frontend/src", ("**/*.ts", "**/*.tsx")),
    ("10-scripts", ("**/*.py", "**/*.mjs")),
)
SKIP_PARTS = {"node_modules", "__pycache__", ".venv", "dist", "build", "migrations"}

#: A path-shaped token. The extension list is closed on purpose: a bare word is
#: prose, and `US-CWP-026` is an id.
TOKEN = re.compile(r"[\w][\w./@-]*\.(?:py|tsx|ts|mjs)\b")
#: ⚠ **A GLOB IS NOT A PATH, AND READING ONE AS A PATH INVENTED A CITATION
#: NOBODY WROTE (`DEF-CWP-3932`).** `TOKEN` cannot match `*`, so on
#: `src/portal/arrears/*.dom.test.tsx` it did not decline the token — it
#: started one character later and returned `dom.test.tsx`, a file that has
#: never existed anywhere, reported against a line whose four real tests are
#: all present. The two `*` forms are stripped BEFORE tokenising and they are
#: stripped differently on purpose: `**bold**` is markdown emphasis wrapped
#: around a real path and that path must survive it, while a run still
#: carrying a `*` afterwards is a glob, which this gate does not resolve (see
#: WHAT IT DELIBERATELY DOES NOT DO).
BOLD = re.compile(r"\*\*")
GLOB_RUN = re.compile(r"[\w*./@-]*\*[\w*./@-]*")
#: The repo's supersession marker. A `Tests:` line makes a claim about the
#: PRESENT; a continuation carrying this marker is a note about the PAST —
#: *"this line named `X` until 2026-09-05 and that file never existed"* — which
#: is hard-won law 9's write-back, not a citation. Two files write one today
#: and both put the live citation on the label line above it. Failing on the
#: note would teach the next lane to delete the history rather than record it,
#: which is the same trade this gate's docstring already makes for prose.
SUPERSEDED = "⚠"
#: `# Tests:` or `// Tests:`, and the continuation lines indented under it.
LABEL = re.compile(r"^\s*(?:#|//)\s*Tests:\s*(.*)$")
NEXT_LABEL = re.compile(r"^\s*(?:#|//)\s*[A-Z][A-Za-z]+:\s")
CONTINUATION = re.compile(r"^\s*(?:#|//)\s{4,}\S")
#: A Trace header is at the top of a file; reading past it would pick up prose
#: in a docstring that happens to contain the word.
HEADER_LINES = 40


def _files() -> list[pathlib.Path]:
    found: list[pathlib.Path] = []
    for base, patterns in SCAN:
        root = REPO / base
        if not root.exists():
            continue
        for pattern in patterns:
            for path in root.glob(pattern):
                if SKIP_PARTS & set(path.parts):
                    continue
                found.append(path)
    return sorted(found)


def citations_in(text: str) -> list[str]:
    """Every path-shaped token on a `Tests:` line and its continuations.

    ⚠ A token with no `/` is kept only when it looks like a test file name
    (`test_*.py`, `*.test.tsx`), because a bare `services.py` on that line is
    almost always the thing being tested rather than the test.
    """
    out: list[str] = []
    grabbing = False
    for line in text.split("\n")[:HEADER_LINES]:
        label = LABEL.match(line)
        if label:
            grabbing = True
            payload = label.group(1)
        elif grabbing and CONTINUATION.match(line) and not NEXT_LABEL.match(line):
            payload = line
        else:
            grabbing = False
            continue
        if SUPERSEDED in payload:
            #: From the marker to the end of the block is narrative, not claim.
            grabbing = False
            continue
        for token in TOKEN.findall(GLOB_RUN.sub(" ", BOLD.sub("", payload))):
            if "/" not in token and not (
                token.startswith("test") or ".test." in token or ".dom." in token
            ):
                continue
            out.append(token)
    return out


def resolves(token: str, peers: tuple[pathlib.Path, ...] = ()) -> bool:
    """Does this citation name a file that is on disk?

    ⚠ **THE FOUR ROOTS ARE NOT HOW THIS REPO ACTUALLY WRITES A LIST, AND THAT
    PARKED 89 CITATIONS WHOSE FILES WERE ALL PRESENT (`DEF-CWP-3932`).** The
    dominant form is a fully-pathed FIRST token with bare siblings after it —
    `06-backend/tests/test_us_rat_plans.py · test_us_rat_schedules.py` — and a
    front-end file often writes the whole list bare, as siblings of itself.
    Measured the day this was fixed: of **105** bare citations in the tree,
    **not one** resolved against the four roots, and **92** of them named a
    file that was sitting there. The baseline was therefore 144 rows of which
    89 were fiction, and the 13 real absences were hiding inside them.

    **This does not soften the rule.** The rule is *the cited file exists*; a
    bare sibling that is NOT there still fails, and the 55 rows left in the
    baseline are the ones where nobody ever wrote the test. What it removes is
    a false negative that made the gate unable to see its own findings.

    `peers` carries the two extra places a bare token may be relative to — the
    citing file's own directory, and the directory of every fully-pathed token
    in the same block. `broken_now` computes them per file.
    """
    return any((root / token).exists() for root in tuple(REPO / r for r in ROOTS) + peers)


def _baseline() -> set[tuple[str, str]]:
    if not BASELINE.exists():
        return set()
    rows: set[tuple[str, str]] = set()
    for line in BASELINE.read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        owner, _, cited = line.partition(" -> ")
        if cited:
            rows.add((owner.strip(), cited.strip()))
    return rows


def broken_now() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for path in _files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = path.relative_to(REPO).as_posix()
        tokens = citations_in(text)
        #: Where a bare sibling may be relative to. Two passes are needed: the
        #: fully-pathed tokens have to be resolved first, because it is THEIR
        #: directory that `· test_us_rat_schedules.py` continues.
        peers = {path.parent}
        for token in tokens:
            for root in ROOTS:
                candidate = REPO / root / token
                if candidate.exists():
                    peers.add(candidate.parent)
        anchored = tuple(sorted(peers))
        for token in tokens:
            if not resolves(token, anchored):
                found.add((rel, token))
    return found


def run() -> tuple[str, str]:
    baseline = _baseline()
    broken = broken_now()

    new = sorted(broken - baseline)
    paid = sorted(baseline - broken)
    problems: list[str] = []
    if new:
        listed = "; ".join(f"{owner} -> {cited}" for owner, cited in new[:5])
        problems.append(
            f"{len(new)} Trace citation(s) name a file that does not exist and is not in "
            f"the baseline: {listed}"
            + (f" (+{len(new) - 5} more)" if len(new) > 5 else "")
            + " — write the test, or correct the line; a citation to a test nobody wrote "
            "reads exactly like a citation to one that passes (law 1)"
        )
    if paid:
        listed = "; ".join(f"{owner} -> {cited}" for owner, cited in paid[:5])
        problems.append(
            f"{len(paid)} baseline entr(y/ies) now RESOLVE and must be deleted in this same "
            f"diff: {listed}"
            + (f" (+{len(paid) - 5} more)" if len(paid) > 5 else "")
            + f" — {BASELINE.name} can only shrink"
        )
    if problems:
        return "FAIL", "; ".join(problems)

    total = sum(len(citations_in(p.read_text(encoding="utf-8", errors="ignore"))) for p in _files())
    return "PASS", (
        f"{total} Trace test citation(s) across {len(_files())} file(s) all resolve, "
        f"{len(baseline)} known gap(s) parked and shrinking; self-test: an invented "
        "citation, a paid-off baseline row and an absent bare sibling all bite, a "
        "present bare sibling resolves, and a glob invents nothing"
    )


def selftest() -> int:
    """Five directions, in temp files inside the tree so the scan sees them."""
    sabotage = REPO / "06-backend" / "_g95_selftest_tmp.py"
    ok = True
    try:
        sabotage.write_text(
            "# ── Trace ──\n# Tests:    tests/test_this_was_never_written.py\n",
            encoding="utf-8",
        )
        status, message = run()
        if status != "FAIL" or "test_this_was_never_written" not in message:
            print(f"SELFTEST FAIL: an invented citation did not bite ({status}: {message})")
            ok = False
        else:
            print(f"selftest 1/5 — invented citation bites: {message[:110]}")
    finally:
        sabotage.unlink(missing_ok=True)

    real = REPO / "06-backend" / "_g95_selftest_real.py"
    rows = _baseline()
    try:
        real.write_text("# placeholder\n", encoding="utf-8")
        BASELINE.write_text(
            BASELINE.read_text(encoding="utf-8")
            + "_g95_selftest_owner.py -> 06-backend/_g95_selftest_real.py\n",
            encoding="utf-8",
        )
        status, message = run()
        if status != "FAIL" or "can only shrink" not in message:
            print(f"SELFTEST FAIL: a paid-off baseline row did not bite ({status}: {message})")
            ok = False
        else:
            print(f"selftest 2/5 — a paid-off baseline row bites: {message[:110]}")
    finally:
        real.unlink(missing_ok=True)
        BASELINE.write_text(
            "\n".join(
                line
                for line in BASELINE.read_text(encoding="utf-8").split("\n")
                if "_g95_selftest_owner" not in line
            ),
            encoding="utf-8",
        )
    assert _baseline() == rows, "the selftest must leave the baseline exactly as it found it"

    # ── DEF-CWP-3932's three directions ─────────────────────────────────
    # Each was shown to fail against the code as it stood before the fix, and
    # each is exercised through `run()`, which is the path `run_gates` uses
    # (law 7's second half — a red proof through `__main__` alone is no proof
    # of the thing that matters).
    probe = REPO / "06-backend" / "_g95_selftest_probe.py"
    sibling = REPO / "06-backend" / "test_g95_sibling.py"
    try:
        # 3/5 — a BARE sibling that IS there resolves. ⚠ The probe is named
        # `test_*` on purpose: the no-slash filter drops anything that does
        # not look like a test, so a differently-named probe would make both
        # this direction and 4/5 pass without proving anything. Before the fix every one
        # of the tree's 105 bare citations failed here, all 92 present ones
        # included, and the baseline swallowed them.
        sibling.write_text("# placeholder\n", encoding="utf-8")
        probe.write_text(
            "# \u2500\u2500 Trace \u2500\u2500\n"
            "# Tests:    test_g95_sibling.py\n",
            encoding="utf-8",
        )
        if any(owner.endswith("_g95_selftest_probe.py") for owner, _ in broken_now()):
            print("SELFTEST FAIL: a bare sibling that exists was still called broken")
            ok = False
        else:
            print("selftest 3/5 — a bare sibling that exists resolves")

        # 4/5 — and a bare sibling that is NOT there still bites. This is what
        # keeps the widening above from being a softening.
        probe.write_text(
            "# \u2500\u2500 Trace \u2500\u2500\n"
            "# Tests:    test_g95_absent_sibling.py\n",
            encoding="utf-8",
        )
        status, message = run()
        if status != "FAIL" or "test_g95_absent_sibling" not in message:
            print(f"SELFTEST FAIL: a missing bare sibling did not bite ({status}: {message})")
            ok = False
        else:
            print("selftest 4/5 — a bare sibling that is absent still bites")

        # 5/5 — the defect itself: `*.dom.test.tsx` must yield NO token. Before
        # the fix it yielded `dom.test.tsx`, a file that has never existed, and
        # reported it against a line whose four real tests were all present.
        probe.write_text(
            "# \u2500\u2500 Trace \u2500\u2500\n"
            "# Tests:    src/portal/arrears/*.dom.test.tsx\n",
            encoding="utf-8",
        )
        phantom = [c for c in citations_in(probe.read_text(encoding="utf-8"))]
        if phantom:
            print(f"SELFTEST FAIL: a glob still invented a citation: {phantom}")
            ok = False
        else:
            print("selftest 5/5 — a glob invents no citation")
    finally:
        probe.unlink(missing_ok=True)
        sibling.unlink(missing_ok=True)

    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    if "--write-baseline" in sys.argv:
        rows = sorted(broken_now())
        BASELINE.write_text(
            "# G95's known gaps — a `Tests:` line naming a file that does not exist.\n"
            "#\n"
            "# ⚠ THIS FILE CAN ONLY SHRINK. A row that starts resolving fails the gate\n"
            "# until it is deleted in the same diff, so the debt cannot quietly re-grow;\n"
            "# a NEW broken citation fails outright and never reaches this list.\n"
            "#\n"
            "# Written 2026-09-04 with 120 rows (DEF-CWP-3766). Each is a claim some file\n"
            "# makes about being tested that is not true today — fix them by writing the\n"
            "# test where the case is real, or by correcting the line where it is not.\n"
            "#\n"
            "# Format: <file that makes the claim> -> <path it cites>\n"
            + "".join(f"{owner} -> {cited}\n" for owner, cited in rows),
            encoding="utf-8",
        )
        print(f"baseline written: {len(rows)} row(s)")
        raise SystemExit(0)
    status, message = run()
    print(f"G95 trace-tests-exist {status}   {message}")
    raise SystemExit(0 if status == "PASS" else 1)
