"""G7 - 🔒 sensitive-path guard (CLAUDE.md list, as amended by PO ruling 2026-08-09).

Original law: the listed paths stay NotImplementedError stubs until a human
writes them. PO ruling 2026-08-09 ("AI will do it; we will review it later as
human") converts the guard: AI MAY author these files, but every such file must
(a) keep HUMAN-OWNED in its module docstring,
(b) carry HUMAN-REVIEW-PENDING in the docstring the moment it holds real logic,
(c) have a row in 12-governance/09-human-review-ledger.md (matched by its
    repo-relative path) so the deferred human review is a standing, findable
    ledger — never a memory.
A guarded file with real logic missing any of the three = FAIL. Stub-only files
need only (a). Non-Python files (e.g. RLS SQL) are checked for the markers and
ledger row textually. These files may never reach lifecycle status RATIFIED
without a human sign-off recorded in the ledger (checked at ratification time).

The guard list lives in human_owned.txt next to this file (path glob + reason).

WHAT THE MARKER MEANS, AND WHAT THE LEDGER MEANS — clarified 2026-08-11, when
the PO ratified every open row at once and this gate began printing a sentence
that was no longer true.

`HUMAN-REVIEW-PENDING` in a docstring is an ENROLMENT marker: it says "this file
was AI-authored under the PO's 2026-08-09 protocol and is therefore subject to
human review". That remains true for the life of the file, and the gate still
REQUIRES it — a guarded file that drops it has left the protocol, which is the
condition this gate exists to prevent.

The LEDGER row carries the current review STATE. It is the single authoritative
answer to "has a human signed this off?", because a status kept in 115 docstrings
is 115 places to go stale, and the ledger is one. So the summary below counts
ratified-versus-pending BY READING THE LEDGER, not by counting markers. Before
this change it counted markers and reported all 115 as "pending human review"
minutes after the PO had ratified them — a gate stating a falsehood about its own
subject, which is hard-won law 1 with the guard as the culprit.
"""
import sys
import ast
from pathlib import Path

import common

GUARD_FILE = Path(__file__).resolve().parent / "human_owned.txt"
LEDGER = common.REPO_ROOT / "12-governance" / "09-human-review-ledger.md"


def _load_guard_list() -> list[tuple[str, str]]:
    entries = []
    for line in common.read_text(GUARD_FILE).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        glob_pattern, _, reason = line.partition(" ")
        entries.append((glob_pattern, reason.strip()))
    return entries


def _stmt_is_stub(stmt: ast.stmt) -> bool:
    """A statement allowed inside a stub function body."""
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return True  # docstring or `...`
    if isinstance(stmt, ast.Raise):
        exc = stmt.exc
        if isinstance(exc, ast.Call):
            exc = exc.func
        return isinstance(exc, ast.Name) and exc.id == "NotImplementedError"
    return False


def _has_real_logic(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not all(_stmt_is_stub(s) for s in node.body):
                return True
            continue
        if isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(member, (ast.Assign, ast.AnnAssign, ast.Pass)):
                    continue
                if isinstance(member, ast.Expr) and isinstance(member.value, ast.Constant):
                    continue
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and all(
                        _stmt_is_stub(s) for s in member.body):
                    continue
                return True
            continue
        return True  # any other executable statement
    return False


def _violations(path: Path, ledger_text: str) -> list[str]:
    text = common.read_text(path)
    problems = []
    if path.suffix == ".py":
        tree = ast.parse(text)
        docstring = ast.get_docstring(tree) or ""
        implemented = _has_real_logic(tree)
    else:
        docstring = text
        implemented = "HUMAN-REVIEW-PENDING" in text or len(text.strip()) > 0 and not text.lstrip().startswith(("--", "#", "/*", '"""'))
        # non-Python heuristic: content beyond leading comments counts as implemented
    if "HUMAN-OWNED" not in docstring:
        problems.append("lacks HUMAN-OWNED marker")
    if implemented:
        if "HUMAN-REVIEW-PENDING" not in docstring:
            problems.append("holds real logic without HUMAN-REVIEW-PENDING marker (PO 2026-08-09 protocol)")
        if common.rel(path) not in ledger_text:
            problems.append("holds real logic but has no row in the human-review ledger")
    return problems


def run() -> tuple[str, str]:
    if not GUARD_FILE.is_file():
        return "FAIL", "human_owned.txt is missing — the 🔒 guard list must exist"
    ledger_text = common.read_text(LEDGER) if LEDGER.is_file() else ""
    entries = _load_guard_list()
    checked = 0
    implemented = 0
    unmatched = 0
    problems = []
    for glob_pattern, _reason in entries:
        matches = sorted(p for p in common.REPO_ROOT.glob(glob_pattern) if p.is_file())
        if not matches:
            unmatched += 1
            continue
        for path in matches:
            checked += 1
            file_problems = _violations(path, ledger_text)
            if not file_problems and "HUMAN-REVIEW-PENDING" in common.read_text(path):
                implemented += 1
            for problem in file_problems:
                problems.append(f"{common.rel(path)}: {problem}")
    if problems:
        return "FAIL", common.summarize(problems)
    # Review STATE comes from the ledger, never from the markers — see the
    # module docstring. A row is pending only while it still says so.
    pending_rows = ledger_text.count("HUMAN-REVIEW-PENDING |")
    ratified_rows = ledger_text.count("RATIFIED (blanket, PO 2026-08-11)")
    state = (
        f"ledger: {pending_rows} row(s) awaiting sign-off, {ratified_rows} ratified"
        if (pending_rows or ratified_rows)
        else "ledger carries no review rows yet"
    )
    return "PASS", (f"{checked} guarded file(s) conform ({implemented} enrolled in the "
                    f"2026-08-09 AI-authoring protocol, rest stubs); {state}; "
                    f"{unmatched} of {len(entries)} pattern(s) match nothing yet")


def main() -> int:
    """Run this gate from the command line.

    ⚠ ADDED 2026-08-25 (DEF-672). Sixteen gate modules defined `run()` and NO
    main block, so `python3 10-scripts/gates/<gate>.py` imported the module,
    defined a function and exited **0 with no output** — indistinguishable from
    a gate that ran and passed, to the eye and to `$?`. Two commit messages on
    this branch claim a G7 PASS obtained exactly that way.

    `run_gates.py` was never affected: it imports `run()` directly, which is why
    the real stack stayed honest while every direct invocation lied.
    """
    status, message = run()
    print(f"{status}: {message}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
