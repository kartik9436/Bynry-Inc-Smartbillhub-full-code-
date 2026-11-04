#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-6980 (2026-09-27) — 28 tests in the rating base-resolution
#          neighbourhood were RED on the branch for four days and no lane read
#          them. Every one had been proved red at birth exactly as hard-won
#          law 7 requires; what was missing is anything that READS a suite
#          again afterwards. A lane running ONE file saw green:
#          `test_br_rat_088_base_charge_gate.py` passes 7/7 beside
#          `test_br_rat_088_base_migration.py` failing 17/17, and neither
#          gates a merge — every workflow in `.github/workflows/` is
#          `.disabled`.
# Rules:   CLAUDE.md hard-won law 7 — *"PROVED RED, THEN NEVER READ"*, and its
#          fifth shape, *"a declared blind spot with no NUMBER attached is
#          indistinguishable from an empty one"* · law 1 (a comment claiming a
#          guarantee is not the guarantee) · NFR-3 is untouched by this file.
# Tests:   10-scripts/gates/g135_backend_suite_receipt.py selftest()
# Impacts: 12-governance/backend-suite-receipt.json ·
#          10-scripts/gates/backend_suite_scope.txt ·
#          10-scripts/gates/backend_suite_known_reds.txt
# ───────────────────────────────────────────────────────
"""Run a DECLARED slice of the backend suite and record what happened.

WHY THIS IS A SCRIPT AND NOT PART OF THE GATE
----------------------------------------------
This is `prove_isolation.py`'s shape, deliberately and for its reasons. That
file's own docstring settles the trade already: `run_gates.py` is what a lane
runs before every merge, several times an hour, and **a gate that costs a
quarter of an hour is a gate lanes stop running**. The five files in scope
today took **11m48s** on real PostgreSQL with `--reuse-db` warm (measured
2026-09-27). Putting that inside `run_gates` would buy a check nobody runs,
which is exactly what `DEF-RAT-6980` already is.

So the RUN is an explicit act — here — and its RESULT is a receipt. `G135`
reads the receipt and costs a file read.

WHY A SCOPE FILE AND NOT `06-backend/tests`
--------------------------------------------
`06-backend/tests` holds **1,295 files**. Nobody in this repo has ever run them
all in one go and this script does not pretend otherwise. `backend_suite_scope.txt`
names what IS proved, and `G135` prints how many files are NOT — because the
honest failure this whole defect is about is a blind spot nobody had a number
for. The scope is meant to GROW; adding a file to it is a one-line change and a
fresh receipt.

WHAT THE RECEIPT IS WORTH, AND WHAT IT IS NOT
----------------------------------------------
A receipt is a RECORD, not an attestation — `prove_isolation.py`'s wording, and
the same caveat applies. It is written by whoever ran the thing. What it CAN do
is make *"nobody has run this since rating changed"* a red line with a date on
it instead of a silence, and make a NEW red fail a merge instead of joining a
crowd.

⚠ **IT CANNOT TELL A RED FROM A BROKEN ENVIRONMENT.** A run that errors at
collection is recorded as errors, not as passes — `--strict` refuses to write a
receipt at all when nothing was selected, because a receipt saying `0 failed`
over `0 selected` is law 7's *reporting zero over a scope it silently excludes*
in its purest form.

HOW TO USE IT
-------------
    python3 10-scripts/prove_backend_suite.py            # run the declared scope
    python3 10-scripts/prove_backend_suite.py --dry-run  # print what it would run

Then commit `12-governance/backend-suite-receipt.json` with your work.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
BACKEND = REPO / "06-backend"
SCOPE = HERE / "gates" / "backend_suite_scope.txt"
RECEIPT = REPO / "12-governance" / "backend-suite-receipt.json"

#: pytest's own short summary. `FAILED`/`ERROR` then the node id, up to the
#: first space (the ` - AssertionError: ...` tail is a message, not an id).
#:
#: ⚠ **THE NODE ID MUST LOOK LIKE ONE, AND THE FIRST RECEIPT THIS SCRIPT EVER
#: TOOK PROVES WHY.** A captured LOG line reads
#: `ERROR    smartbillhub.jobs:tasks.py:126 ...`, and the pattern above matched
#: it: the receipt recorded **11 reds where pytest reported 10**, and
#: `smartbillhub.jobs:tasks.py:126` went into the list as a failing test. That
#: is this gate's own law-7 shape — a check reporting something that is not
#: there — caught on its first run by counting what it found against what
#: pytest said. A node id is `<path>.py` or `<path>.py::<something>`, and a
#: captured log line is neither.
SUMMARY = re.compile(r"^(FAILED|ERROR)\s+(\S+\.py(?:::\S+)?)\s*(?:-|$)")
#: `1 failed, 16 passed, 10 warnings in 708.83s`
COUNTS = re.compile(r"(\d+) (passed|failed|error|errors|skipped|xfailed|xpassed)")


def scope_files() -> list[str]:
    """The declared slice, as paths relative to `06-backend/`."""
    if not SCOPE.exists():
        return []
    out: list[str] = []
    for line in SCOPE.read_text(encoding="utf-8").split("\n"):
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, timeout=60
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - environment
        return ""


def run_suite(files: list[str], timeout: int) -> tuple[int, str]:
    env = dict(os.environ)
    #: `JOBS_EAGER` defaults to true under the local settings and seeds a whole
    #: sample utility per fixture — DEF-567 measured a twelve-file run at an
    #: hour that took four minutes with it off.
    env["JOBS_EAGER"] = "false"
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *files,
        "-q",
        "-p",
        "no:randomly",
        "--reuse-db",
    ]
    proc = subprocess.run(
        cmd, cwd=BACKEND, capture_output=True, text=True, timeout=timeout, env=env
    )
    return proc.returncode, proc.stdout + proc.stderr


def parse(output: str) -> dict:
    failing = sorted({match.group(2) for match in map(SUMMARY.match, output.split("\n")) if match})
    counts: dict[str, int] = {}
    tail = output.strip().split("\n")[-1] if output.strip() else ""
    for number, word in COUNTS.findall(tail):
        counts[word.rstrip("s") if word != "passed" else "passed"] = int(number)
    return {"failing": failing, "counts": counts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=int, default=7200)
    args = parser.parse_args()

    files = scope_files()
    if not files:
        print(f"REFUSED: {SCOPE.relative_to(REPO)} names no files. A receipt over an empty")
        print("scope would report zero failures truthfully and mean nothing (law 7).")
        return 2
    missing = [f for f in files if not (BACKEND / f).exists()]
    if missing:
        print(f"REFUSED: {len(missing)} scoped file(s) do not exist: {', '.join(missing[:5])}")
        return 2

    print(f"scope: {len(files)} file(s) of {len(list((BACKEND / 'tests').glob('*.py')))} in tests/")
    if args.dry_run:
        for name in files:
            print(f"  {name}")
        return 0

    started = dt.datetime.now(dt.timezone.utc)
    code, output = run_suite(files, args.timeout)
    finished = dt.datetime.now(dt.timezone.utc)
    parsed = parse(output)

    selected = sum(parsed["counts"].get(k, 0) for k in ("passed", "failed", "error", "skipped"))
    if selected == 0:
        print("REFUSED: pytest selected nothing. No receipt written — see this file's docstring.")
        print(output[-2000:])
        return 2

    receipt = {
        "taken_at": started.isoformat(timespec="seconds"),
        "duration_s": round((finished - started).total_seconds(), 2),
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "scope": files,
        "scope_files": len(files),
        "tests_dir_files": len(list((BACKEND / "tests").glob("*.py"))),
        "exit_code": code,
        "counts": parsed["counts"],
        "failing": parsed["failing"],
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"receipt: {RECEIPT.relative_to(REPO)}")
    print(
        f"  {parsed['counts'].get('passed', 0)} passed, "
        f"{len(parsed['failing'])} red, over {len(files)} file(s), "
        f"in {receipt['duration_s']}s"
    )
    for node in parsed["failing"]:
        print(f"  RED {node}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
