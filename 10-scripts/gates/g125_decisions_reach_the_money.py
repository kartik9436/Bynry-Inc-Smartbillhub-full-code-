#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-5271 — a decision on the bill run's Check screen recorded a
#          choice and never re-priced anything, and sign-off gated only on
#          UNRESOLVED BREAKS, so a bulk decision over 44 accounts left 44
#          drafts at their pre-decision figures and walked through the
#          BR-BIL-053 gate.
#          DEF-BIL-5270 — a cycle run never checked that an account's
#          consumption starts where its last ISSUED bill ended.
# Rules:   BR-BIL-053 (*"the run cannot enter phase 4 with an unresolved break
#          row"*, extended to decisions) · BR-BIL-015 (a missing input is a
#          CHOICE a human takes) · BR-CUS-103 (`cut_bill`'s anchor) ·
#          CLAUDE.md hard-won law 2 (BUILT IS NOT WIRED) · law 7 (proved RED
#          first, in the harness that will run it)
# Tests:   selftest() below · 06-backend/tests/
#          test_def_bil_5270_5271_continuity_and_reprice.py
# Impacts: 06-backend/apps/billing/runs.py · release.py · api.py
# ───────────────────────────────────────────────────────
"""Three money-path checks a bill run must not quietly lose its wiring to.

WHY A GATE AND NOT ONLY THE TESTS
---------------------------------
The suite proves each check WORKS. This asks the different question that has
cost this repository more: **is anything still calling it?** Both defects this
gate was written for were silent — no exception, no log, no screen — and the
repair for each is ONE CALL in a file five lanes edit:

  * `release.authorise_release` → `runs.refuse_stale_drafts` — the phase-4 gate;
  * `runs._decisions_for` → `_continuity_decisions` — the billed-through anchor;
  * `api.run_exception_resolve` → `runs.reprice_accounts` — the scoped re-price.

Delete any one of them and the product goes back to exactly the behaviour that
was filed, with every unit test still green in its own file, because the tests
call the engine functions directly. That is `decisions.apply_decisions`'s own
history in this module: built, tested, correct, and with **no production
caller for five days** while a clerk's recorded answers reached no bill.

⚠ **AND THE THIRD ONE IS THE LOAD-BEARING ONE.** Without the phase-4 gate, the
re-price is a button — and an optional re-price is the same defect wearing a
button. So the gate FAILS on a missing call rather than warning about it.

WHAT WOULD MAKE THIS PASS WRONGLY — asked before trusting it (law 7)
--------------------------------------------------------------------
  1. **A file that moved or was renamed.** The scan would then find nothing and
     report a clean PASS over three files it never read. **Refused:** a missing
     file is a FAIL naming the path, never a SKIP, because all three are core
     billing modules that exist in every checkout.
  2. **The call appearing only in a COMMENT or a DOCSTRING.** Every paragraph
     in these files quotes its own defect ids, so a prose mention of
     `refuse_stale_drafts` is near-certain and would satisfy a bare substring
     search for ever. **Refused:** the scan strips comments and string literals
     before looking, so only real code counts.
  3. **The self-test passing on a clean tree and proving nothing.** A scanner
     proved against the very tree it scans proves only that the tree is clean
     today. **Refused:** `selftest()` plants each removal in a COPY of the real
     text and requires the scanner to name it, and plants the call back and
     requires it not to.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BILLING = ROOT / "06-backend" / "apps" / "billing"

#: (file, the function that must contain the call, the call, why it matters).
#: A LIST rather than three `if`s so a fourth wiring can be added in one line,
#: and so the PASS sentence can count what it checked.
WIRINGS: tuple[tuple[Path, str, str, str], ...] = (
    (
        BILLING / "release.py",
        "authorise_release",
        "refuse_stale_drafts",
        "the phase-4 gate — without it a run whose drafts predate their own "
        "decisions is authorised and the re-price becomes optional (DEF-BIL-5271b)",
    ),
    (
        BILLING / "runs.py",
        "_decisions_for",
        "_continuity_decisions",
        "the billed-through anchor — without it a gap bills nobody and an "
        "overlap bills a customer twice, silently (DEF-BIL-5270)",
    ),
    (
        BILLING / "api.py",
        "run_exception_resolve",
        "reprice_accounts",
        "the scoped re-price — without it a decision records a choice and every "
        "draft keeps its pre-decision figure (DEF-BIL-5271a)",
    ),
)


def identifiers_in(text: str, function: str) -> set[str] | None:
    """Every NAME actually referenced inside `def <function>`, or None.

    Hazard 2, closed by construction rather than by a pattern. These files
    carry long prose blocks that quote the very symbols this gate looks for —
    `refuse_stale_drafts` appears in three comments in `release.py` alone — so
    a substring search over raw text would go on passing for ever after the
    call itself was deleted.

    **THE ABSTRACT SYNTAX TREE CANNOT SEE A COMMENT OR A DOCSTRING**, so
    walking it is not a filter over the text but a different question asked of
    a different object: *what does this function refer to when it runs?* A
    regex or a tokenizer would each need its own reasoning about quoting; this
    needs none.

    Scoped to the FUNCTION rather than the file, because the question is *does
    this particular entry point still call it* — a call left behind in a dead
    helper elsewhere in the same file would answer the wrong question.

    `None` means the function is not there at all, which is a different finding
    from *there and no longer calling* and gets its own sentence.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function
        ):
            names: set[str] = set()
            for inner in ast.walk(node):
                if isinstance(inner, ast.Name):
                    names.add(inner.id)
                elif isinstance(inner, ast.Attribute):
                    names.add(inner.attr)
            return names
    return None


def source_of(text: str, function: str) -> str:
    """The literal lines of `def <function>` — what `selftest` edits.

    Separate from `identifiers_in` on purpose: one answers what the function
    REFERS to and the other hands back its TEXT, and conflating them is how a
    scanner ends up reasoning about quoting again.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ""
    lines = text.splitlines(keepends=True)
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function
        ):
            return "".join(lines[node.lineno - 1 : node.end_lineno])
    return ""


def unwired(sources: dict[Path, str]) -> list[str]:
    """Every wiring whose call is not REFERRED TO by its function."""
    findings: list[str] = []
    for path, function, call, why in WIRINGS:
        text = sources.get(path)
        if text is None:
            findings.append(
                f"{path.name}: the file is not present, so {call} cannot be wired"
            )
            continue
        names = identifiers_in(text, function)
        if names is None:
            findings.append(f"{path.name}: {function}() was not found — {why}")
        elif call not in names:
            findings.append(
                f"{path.name}: {function}() no longer calls {call}() — {why}"
            )
    return findings


def _read() -> dict[Path, str]:
    return {
        path: path.read_text(encoding="utf-8")
        for path, _f, _c, _w in WIRINGS
        if path.is_file()
    }


#: The scanner's own fixture. **SYNTHETIC ON PURPOSE, and the first draft of
#: this gate got it wrong in a way worth recording.** That draft proved the
#: scanner by planting removals into the REAL files — which meant that on a
#: tree where the wiring was genuinely absent (the tree this gate was written
#: FOR) the self-test failed first and the gate reported *"my self-test does
#: not hold"* instead of *"three money-path checks are not called"*. Both are
#: a FAIL, so the exit code was right and **the sentence a reader acts on was
#: wrong** — law 7's *a check's output must distinguish pass from fail to a
#: READER*, failing on the gate written to enforce it.
#:
#: Every hazard this scanner claims to close is present here: a call made for
#: real, the same name in a DOCSTRING, the same name in a COMMENT, and a
#: function that does not exist.
SELFTEST_SOURCE = '''
def wired(run):
    """A docstring naming sentinel_call, which must not count."""
    # sentinel_call() in a comment, which must not count either
    helper.sentinel_call(run)


def unwired(run):
    """A docstring naming sentinel_call, which must not count."""
    # sentinel_call() in a comment, which must not count either
    return None
'''


def selftest() -> bool:
    """Prove the scanner in BOTH directions, against a source of its own.

    Four claims, and the gate refuses to report anything if any of them fails:

      1. a real call IS seen;
      2. the same name in a docstring and a comment is NOT seen — which is the
         whole reason this walks a syntax tree instead of searching text;
      3. a function that is not there answers `None`, which is a different
         finding from *there and no longer calling*;
      4. `source_of` hands back real lines for a function that exists.
    """
    wired_names = identifiers_in(SELFTEST_SOURCE, "wired")
    unwired_names = identifiers_in(SELFTEST_SOURCE, "unwired")
    if wired_names is None or unwired_names is None:
        return False
    if "sentinel_call" not in wired_names:
        return False
    if "sentinel_call" in unwired_names:
        return False
    if identifiers_in(SELFTEST_SOURCE, "never_defined") is not None:
        return False
    return "def wired(run):" in source_of(SELFTEST_SOURCE, "wired")


def run() -> tuple[str, str]:
    missing = [path for path, _f, _c, _w in WIRINGS if not path.is_file()]
    if missing:
        # Hazard 1 — a FAIL and never a SKIP. These are core billing modules.
        return "FAIL", (
            "cannot read "
            + ", ".join(str(path.relative_to(ROOT)) for path in missing)
            + " — a scan over a file that is not there reports a clean zero"
        )
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it could not tell a planted removal "
            "from a live call, so its verdict is worthless (hard-won law 7)"
        )
    findings = unwired(_read())
    if findings:
        return "FAIL", (
            f"{len(findings)} money-path check(s) built and no longer called — "
            + " · ".join(findings)
        )
    return "PASS", (
        f"all {len(WIRINGS)} money-path checks are referenced by real code (the syntax tree "
        "is walked, so a comment or a docstring naming one does not count): "
        + ", ".join(
            f"{path.name}:{function}()→{call}()" for path, function, call, _w in WIRINGS
        )
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
