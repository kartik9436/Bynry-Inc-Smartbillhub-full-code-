"""G11 - lifecycle-tag stamp (B12 Addendum r1): the per-file audit certificate.

Every `── Lifecycle ──` trailer must carry all six required lines — packet:,
generated:, checklist:, gates:, exceptions:, status: — and status must be one
of GENERATED, VERIFIED-UNRATIFIED, RATIFIED, SUPERSEDED. Malformed = FAIL.

NOT done here: recomputing the stamp to detect hand-editing — that is the
verifier tool's job (it writes the tag; CI recomputes and rejects mismatches).
This gate validates format so a missing/mangled tag can never merge meanwhile.
"""
import sys
import re

import common

REQUIRED_LINES = ("packet:", "generated:", "checklist:", "gates:", "exceptions:", "status:")
VALID_STATUSES = {"GENERATED", "VERIFIED-UNRATIFIED", "RATIFIED", "SUPERSEDED"}


def run() -> tuple[str, str]:
    stamped = []
    for path, text in common.files_with_trace_header():
        block = common.lifecycle_block(text)
        if block is not None:
            stamped.append((path, block))
    if not stamped:
        return "SKIP", "no Lifecycle trailers in the codebase yet (G1 requires them once Trace headers exist)"

    problems = []
    for path, block in stamped:
        missing = [name for name in REQUIRED_LINES if name not in block]
        if missing:
            problems.append(f"{common.rel(path)}: trailer missing {', '.join(missing)}")
        status_match = re.search(r"status:\s*([A-Z-]+)", block)
        if status_match and status_match.group(1) not in VALID_STATUSES:
            problems.append(f"{common.rel(path)}: status '{status_match.group(1)}' not in "
                            f"{sorted(VALID_STATUSES)}")
    if problems:
        return "FAIL", common.summarize(problems)
    return "PASS", f"{len(stamped)} lifecycle tag(s) well-formed"


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
