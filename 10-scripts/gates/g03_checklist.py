"""G3 - completion-checklist validator (B12 §5).

Every `── Lifecycle ──` trailer must carry a `checklist:` line marking each of
A-H as ✔, ✖, or =deferred(<who/when>). Any ✖ = the story is admitted
incomplete = FAIL. A missing letter or unreadable mark also FAILs — an
unverifiable checklist is not a checklist.

NOT done here: recomputing the machine-checkable rows (that arrives with the
verifier tool per B12 r2 G3 — this gate validates the recorded marks only).
"""
import sys
import re

import common

LETTERS = "ABCDEFGH"
MARK_RE = re.compile(r"([A-H])(✔|✖|=deferred\([^)]*\))")


def run() -> tuple[str, str]:
    stamped = [(p, t) for p, t in common.files_with_trace_header()
               if common.lifecycle_block(t) is not None]
    if not stamped:
        return "SKIP", "no Lifecycle trailers in the codebase yet — nothing to validate"

    problems = []
    for path, text in stamped:
        block = common.lifecycle_block(text)
        line_match = re.search(r"checklist:(.*)", block)
        if not line_match:
            problems.append(f"{common.rel(path)}: Lifecycle trailer has no checklist: line")
            continue
        marks = dict(MARK_RE.findall(line_match.group(1)))
        missing = [ch for ch in LETTERS if ch not in marks]
        crossed = [ch for ch in LETTERS if marks.get(ch) == "✖"]
        if missing:
            problems.append(f"{common.rel(path)}: checklist missing letters {','.join(missing)}")
        if crossed:
            problems.append(f"{common.rel(path)}: checklist has ✖ at {','.join(crossed)} — story incomplete")
    if problems:
        return "FAIL", common.summarize(problems)
    return "PASS", f"{len(stamped)} checklist line(s) valid, no ✖ marks"


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
