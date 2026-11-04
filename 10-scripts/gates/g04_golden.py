"""G4 - golden-figure gate (B12 r2): the frozen finance figures hold, always.

TWO LEGS, TWO DIFFERENT NUMBERS, AND QUOTING ONE AS THE OTHER IS DEF-2846
-------------------------------------------------------------------------
* **The harness leg** runs `10-scripts/03-golden-verify.py`, which recomputes
  B4/B5's own figures from fixtures and **imports no application code**. It
  reports **33 checks** and it is DOCUMENT self-consistency: it goes red when a
  document contradicts itself and **can never go red when the engine drifts**.
* **The pytest leg** runs `06-backend/tests/golden/`, which hands inputs to
  `apps.billing.rating_seam` and asserts B5's ❄️ FROZEN outputs. That is the
  ENGINE number — **14 of the 61 signed GTs**, recorded by name in
  `g64_engine_verified_gts.txt` — and it is the one that protects a bill.

⚠ **THE PYTEST LEG WAS NOT RUNNING AT ALL — `DEF-GOV-6781`, 2026-09-25.** Two
faults produced one red line, and both are law 7's *incapable of passing*:

1. **IT RAN `sys.executable`.** So the gate's verdict depended on which Python
   the lane happened to type. `DEF-GOV-6698` named that cause for five gates on
   2026-09-25 and left this one as its open item (b). G4 was the worst of the
   set because it does not SKIP: bare `python3` on this machine HAS pytest and
   has **no Django**, so the money gate reported **FAIL over 1,180 collection
   errors** — which reads like a billing defect — while the suite underneath it
   was green. The interpreter is now chosen by ONE shared helper,
   `common.interpreter_with("pytest", "django")`, which is `DEF-GOV-6698` item
   (c); where no interpreter can run it, this gate reports **SKIP naming what it
   looked for**, never PASS.

2. **IT NAMED NO PATH.** Every `pytest.mark.golden` in this repo lives in
   `06-backend/tests/golden` — 14 files, 24 cases — but `pytest -m golden` with
   no path collected all **16,894** backend tests to deselect 16,871 of them. So
   **any unrelated broken import anywhere in the backend turned the FROZEN-figure
   gate red**, and it cost 382s against 5.4s for the directory alone. The leg now
   names `tests/golden`, and clause 0 below FAILS if a golden marker ever appears
   outside it — scoping a check must not be able to silently shrink it.

Measured at tip 3a572853d, 2026-09-25: `23 passed, 1 xfailed`. That is the
identical figure recorded by the GT-24/GT-47 lane on **2026-08-11**, so this
suite has been green whenever anything actually ran it. The 1 xfail is **GT-6**
(credit note): billing has not published `issue_credit_note`, so GT-6 is a
written contract that does not yet execute — 13 of the 14 engine GTs assert.

PROVED RED BEFORE TRUSTED GREEN, THROUGH `run()` AND NEVER `__main__` (law 7,
`DEF-GOV-3733`)
---------------------------------------------------------------------------
* a `pytest.mark.golden` written outside `tests/golden` → **FAIL** naming the
  file;
* `common.interpreter_with` finding nothing → **SKIP** naming every candidate
  it tried;
* the pytest leg returning non-zero → **FAIL** carrying the failure line.

⚠ **AND ONE END-TO-END RED, BECAUSE THE THREE ABOVE PROVE THE GATE AND NOT THE
MONEY.** `core/money.py`'s `finalize` was flipped from `ROUND_HALF_UP` to
`ROUND_DOWN` — one line, in a private worktree, reverted and never committed —
and this gate went **4 failed, 19 passed, 1 xfailed**. The 23 green cases are
green because the engine agrees with B5, not because they assert nothing.

⚠ **IT COSTS ≈6 MINUTES (353.75s) AND THAT IS THE TEST DATABASE, NOT THIS
GATE.** Measured 2026-09-25: `JOBS_EAGER=false` gives **no** improvement
(403.77s), while `--reuse-db` takes the same 24 cases to **5.36s**. `--reuse-db`
is deliberately NOT passed: the SQLite test database is one digest-named file,
two lanes' gate runs would share it, and a FLAKY money gate is worse than a slow
one. The real fix is a per-run database name the way `G5` does it
(`SBH_TEST_DB_NAME`), which is separate work and is named here rather than
half-done.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import common

GOLDEN_DIR = common.BACKEND_DIR / "tests" / "golden"
MARKER_RE = re.compile(r"pytest\.mark\.golden")


def _run(cmd: list[str], cwd) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def _golden_markers_outside_the_golden_directory() -> list[str]:
    """Files carrying `pytest.mark.golden` that the scoped run would not collect.

    This clause is the price of naming a path. `pytest -m golden` with no path
    could not miss a marker wherever it was written; `pytest -m golden
    tests/golden` can. So the gate asks the question the scoping gave away, and
    a marker written anywhere else FAILS here rather than quietly dropping out
    of the money check (law 7: a check that reports zero over a scope it
    silently excludes).
    """
    out = []
    for folder, subdirs, files in os.walk(common.BACKEND_DIR):
        here = Path(folder)
        # Prune rather than filter: a lane's `.venv` holds tens of thousands of
        # files and walking it to throw every one away is how a cheap clause
        # becomes a reason not to run the gate.
        subdirs[:] = [
            d for d in subdirs
            if not d.startswith(".") and d not in {"__pycache__", "node_modules"}
        ]
        if here == GOLDEN_DIR:
            subdirs[:] = []
            continue
        for name in files:
            if name.startswith("test_") and name.endswith(".py"):
                path = here / name
                if MARKER_RE.search(common.read_text(path)):
                    out.append(common.rel(path))
    return sorted(out)


def run() -> tuple[str, str]:
    harness = common.REPO_ROOT / "10-scripts" / "03-golden-verify.py"
    proc = _run([sys.executable, str(harness)], common.REPO_ROOT)
    out_lines = (proc.stdout.strip() or proc.stderr.strip() or "no output").splitlines()
    summary = out_lines[0]
    if proc.returncode != 0:
        fails = [ln.strip() for ln in out_lines if ln.strip().startswith("FAIL")]
        return "FAIL", f"harness: {summary}; {common.summarize(fails)}"

    # The harness count is DOCUMENT self-consistency and is said so here, every
    # run, because this line is where the `33/33` citation is copied from.
    detail = f"harness (documents, not the engine): {summary}"

    strays = _golden_markers_outside_the_golden_directory()
    if strays:
        return "FAIL", (
            detail + f"; {len(strays)} golden-marked test file(s) live outside "
            f"06-backend/tests/golden and the scoped run would not collect them: "
            + common.summarize(strays)
        )

    golden_tests = sorted(GOLDEN_DIR.glob("test_*.py"))
    if not golden_tests:
        return "PASS", detail + "; no backend golden tests yet"

    interpreter, tried = common.interpreter_with("pytest", "django")
    if interpreter is None:
        return "SKIP", (
            detail + f"; {len(golden_tests)} engine golden test file(s) present and NOT RUN — "
            "no interpreter here can import both pytest and django. Tried: "
            + common.summarize(tried, limit=8)
            + ". Build one with 10-scripts/01-bootstrap.sh."
        )

    pt = _run(
        [interpreter, "-m", "pytest", "-m", "golden", "-q", "tests/golden"],
        common.BACKEND_DIR,
    )
    tail = pt.stdout.strip().splitlines()[-1] if pt.stdout.strip() else "no output"
    # The interpreter is printed in every outcome. A number whose provenance is
    # not on the line beside it is how DEF-GOV-6781 stayed invisible.
    where = interpreter
    if pt.returncode == 5:  # pytest: no tests collected
        return "FAIL", (
            detail + f"; {len(golden_tests)} engine golden test file(s) exist and "
            f"pytest -m golden collected NONE of them ({where}) — the marker or the "
            "path moved, and the frozen figures are unchecked"
        )
    if pt.returncode != 0:
        return "FAIL", detail + f"; engine golden suite failed ({where}): {tail}"
    return "PASS", detail + f"; engine golden suite ({where}): {tail}"


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
