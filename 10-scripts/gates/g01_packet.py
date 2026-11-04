"""G1 - packet gate (B12 r2): code exists only if generated FROM a packet.

Checked here: every codebase file carrying a `── Trace ──` header must also
carry a `── Lifecycle ──` trailer whose `packet:` line has the form
US-XXX-###@<hex> (story + rules snapshot hash). Files without Trace headers
(scaffolding) are exempt.

NOT checked here: recomputing the packet hash against the CURRENT story+rules
files. That arrives with the verifier tool that stamps the trailer — until
then this gate validates presence and form only.
"""
import sys
import re

import common

PACKET_RE = re.compile(r"packet:\s*US-[A-Z]{3}-\d{3,6}@[0-9a-fA-F]+\b")


def run() -> tuple[str, str]:
    traced = common.files_with_trace_header()
    if not traced:
        n = len(common.code_files())
        return "SKIP", f"no Trace-headed code files yet ({n} codebase files scanned, all scaffolding-exempt)"

    problems = []
    for path, text in traced:
        block = common.lifecycle_block(text)
        if block is None:
            problems.append(f"{common.rel(path)}: Trace header but no {common.LIFECYCLE_MARK} trailer")
        elif not PACKET_RE.search(block):
            problems.append(f"{common.rel(path)}: Lifecycle trailer lacks a 'packet: US-XXX-###@<hex>' line")
    if problems:
        return "FAIL", common.summarize(problems)
    return "PASS", f"{len(traced)} Trace-headed file(s), all carry a packet-stamped Lifecycle trailer"


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
