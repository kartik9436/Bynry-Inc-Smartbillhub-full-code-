"""G21 - BR-BIL-038, the refactor contract (US-BIL-030).

The rule, from EP-BIL-02: **however the billing engine is restructured inside,
GT-1..61 come out identical.** That guarantee is worth nothing as a sentence —
hard-won law 1 is exactly about sentences like it — so the story names two
clauses and this gate is both of them, mechanised.

CLAUSE (a) - A COMMIT MAY NOT BOTH MOVE A STAGE BOUNDARY AND CHANGE A GOLDEN
             EXPECTED VALUE.
A B5 change needs a finance re-sign via HUMAN-GUIDE §6, never an inline edit.
The failure this prevents would look exactly like success: a refactor shifts a
figure, and the same patch adjusts the fixture so the suite still passes. Nobody
lies; the signed number simply moves. So the two kinds of change are made
un-combinable, and a legitimate B5 change is still perfectly possible — it just
cannot ride along with a boundary move.

    stage-boundary files : apps/billing/pipeline.py (SEQUENCE), the stage
                           modules under apps/billing/stages/, and the seam
                           apps/billing/rating_seam.py
    golden-value files   : 04-docs/02-decisions/05-golden-tests.md,
                           10-scripts/03-golden-verify.py and
                           06-backend/tests/golden/

CLAUSE (b) - THE GOLDEN SUITE RUNS THE PUBLIC ENTRY POINT, NEVER A STAGE'S
             INTERNALS.
Otherwise a refactor can retarget the tests at the thing it just changed and
pass by testing itself. The permitted doors are `pipeline.PUBLIC_ENTRY_POINTS`
and the forbidden ones are `pipeline.STAGE_INTERNALS` — read from that module so
the gate and the code cannot drift apart (a second copy of the list here is how
they would).

HOW CLAUSE (a) IS EVALUATED WITHOUT RUNNING GIT. This gate never shells out to
git: the lane that owns commits is not this process, and a gate that depended on
a working tree's VCS state would pass or fail for reasons unrelated to the
patch. Instead it reads the STAGED-CHANGE MANIFEST when one is present
(`10-scripts/gates/changed_files.txt`, one repo-relative path per line, written
by CI from `git diff --name-only`). With no manifest the clause reports as
NOT-EVALUATED and says so — an unevaluated clause is never counted as a pass.

PROVED RED BEFORE TRUSTED GREEN (hard-won law 7). Both clauses were shown to
fail on the shapes they exist for — a manifest naming a stage file and a golden
file together, and a golden test importing `apps.billing.stages.
assemble_document` — before either was believed. `self_test()` below reproduces
both on demand, so the proof is re-runnable rather than a claim in a report.
"""

import sys
import re
from pathlib import Path

import common

MANIFEST = Path(__file__).resolve().parent / "changed_files.txt"

#: Files whose change MOVES A STAGE BOUNDARY (clause (a), left half).
BOUNDARY_PATTERNS = (
    "06-backend/apps/billing/pipeline.py",
    "06-backend/apps/billing/stages/",
    "06-backend/apps/billing/rating_seam.py",
)

#: Files that carry a SIGNED GOLDEN VALUE (clause (a), right half).
GOLDEN_PATTERNS = (
    "04-docs/02-decisions/05-golden-tests.md",
    "10-scripts/03-golden-verify.py",
    "06-backend/tests/golden/",
)

FINANCE_RESIGN_ROUTE = "HUMAN-GUIDE §6 (finance re-sign)"

#: Parsed out of apps/billing/pipeline.py rather than copied — see the module
#: docstring on why a second copy is the drift.
_TUPLE_RE = re.compile(r"^(PUBLIC_ENTRY_POINTS|STAGE_INTERNALS)[^=]*=\s*\((.*?)\)", re.S | re.M)


def _pipeline_lists() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """`(public_entry_points, stage_internals)` read from the shipping module."""
    path = common.BACKEND_DIR / "apps" / "billing" / "pipeline.py"
    if not path.exists():
        return (), ()
    text = common.read_text(path)
    found = {name: body for name, body in _TUPLE_RE.findall(text)}

    def parse(body: str) -> tuple[str, ...]:
        return tuple(re.findall(r'"([^"]+)"', body))

    return parse(found.get("PUBLIC_ENTRY_POINTS", "")), parse(found.get("STAGE_INTERNALS", ""))


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(path.startswith(p) or path == p for p in patterns)


def _clause_a() -> tuple[bool, str]:
    """`(ok, detail)` — the two-change rule, over the staged-change manifest."""
    if not MANIFEST.exists():
        return True, (
            "clause (a) NOT EVALUATED: no staged-change manifest at "
            f"{common.rel(MANIFEST)}. CI writes one with `git diff --name-only > "
            "10-scripts/gates/changed_files.txt` before running the gates. Reported "
            "rather than counted as a pass — an unevaluated clause proves nothing"
        )
    changed = [
        line.strip()
        for line in common.read_text(MANIFEST).splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    boundary = [p for p in changed if _matches(p, BOUNDARY_PATTERNS)]
    golden = [p for p in changed if _matches(p, GOLDEN_PATTERNS)]
    if boundary and golden:
        return False, (
            f"BR-BIL-038: this change moves a stage boundary ({', '.join(boundary[:3])}) AND "
            f"edits a signed golden value ({', '.join(golden[:3])}) in one commit. Those two "
            "may never travel together: a refactor that shifts a figure and adjusts the "
            "fixture in the same patch is indistinguishable from one that did not shift it. "
            f"A B5 figure changes ONLY by {FINANCE_RESIGN_ROUTE} — never by an inline edit, "
            "and never alongside a refactor. Split the commit."
        )
    return True, (
        f"clause (a): {len(changed)} changed file(s) — "
        f"{len(boundary)} boundary, {len(golden)} golden; never both"
    )


def _clause_b() -> tuple[bool, str]:
    """`(ok, detail)` — the golden suite enters through the public door only."""
    public, internals = _pipeline_lists()
    if not public:
        return True, (
            "clause (b) NOT EVALUATED: apps/billing/pipeline.py declares no "
            "PUBLIC_ENTRY_POINTS. Reported rather than counted as a pass"
        )
    golden_dir = common.BACKEND_DIR / "tests" / "golden"
    if not golden_dir.exists():
        return True, "clause (b): no backend golden suite yet"
    offenders = []
    for path in sorted(golden_dir.glob("test_*.py")):
        text = common.read_text(path)
        for internal in internals:
            module, _, attr = internal.rpartition(".")
            # `from apps.billing.stages.assemble_document import …` or
            # `apps.billing.stages.assemble_document(...)` — either is a reach
            # past the door.
            if re.search(rf"\b{re.escape(internal)}\b", text) or re.search(
                rf"from\s+{re.escape(module)}\s+import\s+[^\n]*\b{re.escape(attr)}\b", text
            ):
                offenders.append(f"{common.rel(path)} reaches {internal}")
    if offenders:
        return False, (
            f"BR-BIL-038 clause (b): {common.summarize(offenders)}. The golden suite must "
            "exercise the same door the bill run uses — "
            f"{', '.join(public[:3])} and the rest of pipeline.PUBLIC_ENTRY_POINTS — or a "
            "refactor can retarget the tests at the thing it just changed and pass by "
            "testing itself."
        )
    return True, (
        f"clause (b): {len(list(golden_dir.glob('test_*.py')))} golden file(s) enter through "
        f"{len(public)} declared public entry point(s); none reaches a stage internal"
    )


def self_test() -> tuple[int, int]:
    """Both clauses, shown to BITE. Returns `(bit, total)` — hard-won law 7."""
    bit = 0
    total = 2
    # (a) a manifest naming a boundary file and a golden file together.
    saved = common.read_text(MANIFEST) if MANIFEST.exists() else None
    try:
        MANIFEST.write_text(
            "06-backend/apps/billing/pipeline.py\n04-docs/02-decisions/05-golden-tests.md\n",
            encoding="utf-8",
        )
        ok, _ = _clause_a()
        if not ok:
            bit += 1
    finally:
        if saved is None:
            MANIFEST.unlink(missing_ok=True)
        else:
            MANIFEST.write_text(saved, encoding="utf-8")
    # (b) a golden file that reaches a stage internal.
    probe = common.BACKEND_DIR / "tests" / "golden" / "test_zz_g21_selftest.py"
    try:
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text(
            "from apps.billing.stages.assemble_document import assemble_document  # probe\n",
            encoding="utf-8",
        )
        ok, _ = _clause_b()
        if not ok:
            bit += 1
    finally:
        probe.unlink(missing_ok=True)
    return bit, total


def run() -> tuple[str, str]:
    a_ok, a_detail = _clause_a()
    b_ok, b_detail = _clause_b()
    bit, total = self_test()
    detail = f"{a_detail}; {b_detail}; self-test: {bit}/{total} clauses bite"
    if not a_ok or not b_ok:
        return "FAIL", "; ".join(
            part for part, ok in ((a_detail, a_ok), (b_detail, b_ok)) if not ok
        )
    if bit != total:
        return "FAIL", (
            f"the gate's own self-test did not bite ({bit}/{total}): a guard that cannot be "
            "shown to fail on the thing it guards is not a guard (hard-won law 7). " + detail
        )
    return "PASS", detail


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
