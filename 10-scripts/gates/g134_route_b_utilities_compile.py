"""G134 — THE ROUTE B COMPILER CHECK IS IN THE MERGE SET, OR ITS ABSENCE IS A NUMBER.

WHY THIS EXISTS (DEF-GOV-6778, 2026-09-25)
-----------------------------------------------
`G31` refuses a component naming a class no stylesheet declares. For a file on
`07-frontend/src/styles/route-b-migrated.txt` that rule is FALSE — a Tailwind
utility is declared by the COMPILER — so `G31` skips those files BY DESIGN and
hands them to `07-frontend/src/styles/routeBUtilities.test.ts`, the one check in
this repo that can ask the real compiler whether a class token emits a rule.

⚠ **NOTHING RAN THAT CHECK.** `run_gates` is Python and runs no vitest.
`.github/workflows/ci-frontend.yml`, which used to run `npm test`, has been
`.disabled` since 2026-09-04 (Actions minutes exhausted), and every other
workflow with it. `g31_declared_classes.route_b_migrated()`'s own docstring
says *"Run it by hand"* — which is hard-won law 1 exactly: a comment claiming a
guarantee is not the guarantee. Measured on 2026-09-25, the handover covered
**559 files** and the check behind it had not been in any merge verdict for
three weeks.

WHAT IT COST, AND IT IS THE PROOF THIS GATE WAS BORN RED ON
-----------------------------------------------------------
`features/customers/moveOutTables.tsx` has asked for `border-danger` and
`bg-danger-50` since 2026-09-24. Neither compiles and no stylesheet declares
either, so that panel draws with **no border and no background** on a live
screen. `tsc` passes, eslint passes, `toHaveClass()` passes, `G31` skips the
file, and the full 134-gate suite was green over it. The vitest file was red the
whole time and was in nobody's merge set.

WHAT THIS GATE DOES
-------------------
It shells that one vitest file — nothing else — and reports its orphan list.
It adds no rule: `routeBUtilities.test.ts` remains the only definition of the
rule, and this is the thing that makes a merge read its answer.

⚠ **AND WHEN IT CANNOT RUN, IT SAYS SO WITH THE NUMBER** (hard-won law 7, the
fifth shape: *a declared blind spot with no NUMBER attached is indistinguishable
from an empty one* — `G32` reported `0 unresolved` over 21 live refusals the
same way). A bare worktree has no `07-frontend/node_modules`, so this SKIPs —
and the SKIP detail names how many Route B files went unchecked and the one
command that fixes it. A silent skip here would rebuild the blind spot this gate
was written to close.

WHAT WOULD MAKE IT PASS WRONGLY, asked before it was trusted (law 7, habit 2)
-----------------------------------------------------------------------------
* **vitest matching no file and exiting 0.** It does not — it exits non-zero on
  "No test files found" — but the check does not rest on that: the output must
  name the test file AND report at least one passed test, or this FAILs as
  *the check did not run*. That is `--stat`'s lesson (DEF-182): an exit code
  that cannot distinguish "green" from "never looked" is not an answer.
* **the ledger emptied.** Then `handed` is 0 and the PASS detail says 0, which
  is a number a reader can act on rather than a silence.
* **a crash inside `g31`'s ledger reader** (it `SystemExit`s on an entry naming
  a missing file). Caught here and reported as a FAIL of this gate rather than
  as a killed runner.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND = ROOT / "07-frontend"
TEST_FILE = "src/styles/routeBUtilities.test.ts"
VITEST = FRONTEND / "node_modules" / ".bin" / "vitest"

#: A generous ceiling. The file itself runs in ~2s; the margin is for a machine
#: several lanes are sharing, which is the normal case here.
TIMEOUT_SECONDS = 600

#: vitest prints every orphan as `"<token> (asked for by <file>)"` inside the
#: received array of the failing `toEqual([])`. One per line, quoted.
_ORPHAN = re.compile(r'^\s*\+?\s*"([^"]+\(asked for by [^"]+\))",?\s*$', re.M)


def handed_over() -> tuple[int, str | None]:
    """How many files G31 skips and hands to the vitest check.

    ONE LIST, TWO READERS (hard-won law 5): this asks `g31` for its own
    expansion of `route-b-migrated.txt` rather than re-parsing the ledger, so
    the number printed here cannot drift from the number G31 skips.
    """
    try:
        import g31_declared_classes

        return len(g31_declared_classes.route_b_migrated()), None
    except SystemExit as exc:  # the ledger names a file that does not exist
        return 0, str(exc)
    except Exception as exc:  # pragma: no cover - reported, never swallowed
        return 0, f"{type(exc).__name__}: {exc}"


def run() -> tuple[str, str]:
    handed, ledger_problem = handed_over()
    if ledger_problem:
        return "FAIL", (
            f"the Route B ledger cannot be read, so the count of files this gate "
            f"covers is unknown: {ledger_problem}"
        )

    # ⚠ BORROW THE MAIN WORKTREE'S INSTALL THROUGH A TEMPORARY SYMLINK
    # (`DEF-GOV-9126`) — `common.LinkedFrontendInstall`, which says why a link
    # and not `NODE_PATH` (vitest loads its config as ESM). `node_modules/` is
    # gitignored, so every lane worktree lacks it and this gate SKIPPED there
    # over 631 Route B files.
    with common.LinkedFrontendInstall("vitest") as link:
        if not link.ok or not VITEST.exists():
            return "SKIP", (
                f"vitest is not installed, so the compiler check did NOT run and "
                f"{handed} Route B file(s) — the ones G31 skips by design — were "
                f"checked by NOBODY this run. This is a stated blind spot with its "
                f"number, not a pass. {link.problem}. Looked in: {'; '.join(link.tried)}. "
                f"Fix: `cd 07-frontend && npm ci` (here or in the main checkout), then re-run."
            )
        borrowed_note = link.note
        try:
            proc = subprocess.run(
                [str(VITEST), "run", TEST_FILE, "--reporter=basic"],
                cwd=str(FRONTEND),
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return "FAIL", (
                f"the Route B compiler check did not finish in {TIMEOUT_SECONDS}s, so "
                f"{handed} file(s) are unchecked. A check that hangs is not a green."
            )

    out = f"{proc.stdout}\n{proc.stderr}"

    # ── DID IT ACTUALLY LOOK? ────────────────────────────────────────────
    # An exit code alone cannot tell "green" from "never ran"; both of these
    # must hold before a 0 is read as an answer.
    # ⚠ THE `Tests` LINE, NOT THE FIRST `N passed` IN THE STREAM. vitest's
    # basic reporter prints `Test Files  1 passed (1)` BEFORE
    # `Tests  11 passed (11)`, so a loose `\d+ passed` reports the number of
    # FILES as though it were the number of cases — a detail line that reads
    # like an answer and is about something else (DEF-182's shape).
    ran = TEST_FILE.rsplit("/", 1)[-1] in out
    passed = re.search(r"^\s*Tests\s+(?:\d+\s+\w+\s*\|\s*)*(\d+)\s+passed\b", out, re.M)
    if not ran or not passed or int(passed.group(1)) == 0:
        tail = " | ".join(line.strip() for line in out.splitlines() if line.strip())[-300:]
        return "FAIL", (
            f"the Route B compiler check did not run: vitest never reported a "
            f"passing case for {TEST_FILE}, so {handed} file(s) are unchecked. "
            f"Output tail: {tail}"
        )

    if proc.returncode == 0:
        return "PASS", (
            f"every class token in {handed} Route B file(s) compiles as a utility "
            f"or is declared by a stylesheet ({TEST_FILE}, {passed.group(1)} case(s))"
            f"{borrowed_note}"
        )

    orphans = sorted(set(_ORPHAN.findall(out)))
    if orphans:
        return "FAIL", (
            f"{len(orphans)} class token(s) in Route B file(s) render NOTHING — no "
            f"stylesheet declares them and Tailwind generates no rule for them. "
            f"tsc, eslint and toHaveClass() all pass on these: "
            + "; ".join(orphans[:5])
            + (f" (+{len(orphans) - 5} more)" if len(orphans) > 5 else "")
        )

    tail = " | ".join(line.strip() for line in out.splitlines() if line.strip())[-400:]
    return "FAIL", (
        f"{TEST_FILE} failed for a reason this gate could not parse as an orphan "
        f"list, over {handed} Route B file(s). Run it by hand and read it: "
        f"`cd 07-frontend && ./node_modules/.bin/vitest run {TEST_FILE}`. "
        f"Output tail: {tail}"
    )


def main() -> int:
    status, message = run()
    print(f"{status}: {message}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
