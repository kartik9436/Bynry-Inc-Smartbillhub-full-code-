#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-6980 (2026-09-27) — 28 tests in the rating base-resolution
#          neighbourhood were RED for four days and nothing read them. Every
#          one had been proved red at birth exactly as hard-won law 7 requires;
#          nothing ever read the output again. 20 of the 160 defects filed on
#          2026-09-05 were checks that do not check — one in eight — and this
#          is that shape at a scale of 28.
# Rules:   CLAUDE.md hard-won law 7 — *"PROVED RED, THEN NEVER READ … a guard
#          is a claim only while somebody reads its output"*, and its fifth
#          shape, *"a check that cannot cover its whole subject must print what
#          it skipped beside what it checked"* · law 1 (a comment claiming a
#          guarantee is not the guarantee) · G95's ratchet shape, and G5's
#          receipt shape (10-scripts/prove_isolation.py).
# Tests:   selftest() below, exercised through run()
# Impacts: 10-scripts/prove_backend_suite.py ·
#          12-governance/backend-suite-receipt.json ·
#          10-scripts/gates/backend_suite_scope.txt ·
#          10-scripts/gates/backend_suite_known_reds.txt
# ───────────────────────────────────────────────────────
"""G135 — a DECLARED slice of the backend suite has been run, and its reds are read.

WHY THIS GATE EXISTS
--------------------
On 2026-09-27, `test_br_rat_088_base_migration.py` had been failing **17 of 17**
for four days, beside `test_br_rat_088_base_charge_gate.py` passing **7 of 7**.
A lane running one file saw green. Every workflow in `.github/workflows/` is
`.disabled`, so nothing gated a merge on either. The failures were a money
neighbourhood — base resolution — and one of them was a `$30.00` disagreement
about what a sample utility charges.

**Nothing in this repository was reading a suite result.** That is the gap.

WHAT IT CHECKS, AND WHAT IT COSTS
----------------------------------
It reads ONE JSON file. It runs no tests, so it costs a lane milliseconds.
`10-scripts/prove_backend_suite.py` is what runs them, as an explicit act —
that split is `prove_isolation.py`'s, with its reasoning: **a gate that costs a
quarter of an hour is a gate lanes stop running**, and a check nobody runs is
worth what a check that cannot fail is worth.

It FAILS when:

  1. **there is no receipt** — nobody has ever run the scope;
  2. **a red is NOT in the baseline** — a new one, which is what this exists
     to stop;
  3. **a baseline row is no longer red** — the debt was paid and the line must
     go in the same diff, so the file can only SHRINK (G95's ratchet, exactly);
  4. **a baseline row carries no `DEF-` id** — a parked red with no defect row
     is a red nobody can count, which is the failure being closed here;
  5. **the receipt predates a change to what it proved** — the scoped test
     files or `06-backend/apps/rating/`. A receipt that has outlived its
     subject is a claim about a tree that no longer exists.

⚠ **STALENESS IS CONTENT-ADDRESSED, NOT A CLOCK, AND THAT IS DELIBERATE.**
`G5` keys its isolation receipt on the migration digest for the same reason: a
proof cannot outlive the schema it proved. A gate that goes red on a calendar
teaches lanes to ignore it (G78 was red for days and three lanes ran past it);
one that goes red exactly when the thing it proved moved is a gate with
something to say. `DEF-RAT-6980`'s own cause — `870b4c21f` changing
`rate_plans.account_type_id` — would have tripped clause 5 the same day.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
* **It does not run the suite**, and cannot tell you the receipt is honest. A
  receipt is a RECORD, not an attestation — `prove_isolation.py`'s wording, and
  the same caveat applies. What it removes is the SILENCE.
* **It does not cover 06-backend/tests.** The scope is six files of ~1,295.
  The PASS message prints both numbers, every time, because a declared blind
  spot with no number beside it is indistinguishable from an empty one.

PROVED RED FIRST (law 7, BOTH halves — every failure below is produced by
`selftest()`, which exercises `run()`, the path `run_gates` itself calls):

    G135 backend-suite-receipt FAIL  1 red(s) in the receipt are not in the
    baseline: tests/test_x.py::test_y
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
BACKEND = REPO / "06-backend"
RECEIPT = REPO / "12-governance" / "backend-suite-receipt.json"
SCOPE = HERE / "backend_suite_scope.txt"
BASELINE = HERE / "backend_suite_known_reds.txt"

#: What a receipt's proof is ABOUT. A change under any of these makes it stale.
#: `apps/rating` is here because `DEF-RAT-6980`'s 18 failures came from a field
#: rename in `apps/rating/services.py`, not from a test edit.
SUBJECT = ("06-backend/apps/rating",)

DEFECT_ID = re.compile(r"DEF-(?:[A-Z]{3}-)?\d{3,5}(?!\d)")


def _rows(path: pathlib.Path) -> list[str]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        stripped = line.split("#", 1)[0].strip() if path is SCOPE else line.strip()
        if stripped and not stripped.startswith("#"):
            out.append(stripped)
    return out


def _baseline() -> dict[str, str]:
    """`<node id>  <DEF-id and why>` per line. The id is required."""
    rows: dict[str, str] = {}
    for line in _rows(BASELINE):
        node, _, note = line.partition(" ")
        rows[node.strip()] = note.strip()
    return rows


def _receipt() -> dict | None:
    if not RECEIPT.exists():
        return None
    try:
        return json.loads(RECEIPT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _moved_since(commit: str) -> list[str]:
    """Scoped test files and `apps/rating` changed since the receipt's commit.

    ⚠ An empty answer because git could not resolve the commit is NOT the same
    as an empty answer because nothing moved, so the two are separated: an
    unresolvable commit is reported as such rather than read as *nothing
    changed* (law 7's fifth shape, one command down).
    """
    if not commit:
        return ["<receipt names no commit>"]
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        return [f"<receipt commit {commit[:9]} is not in this checkout>"]
    paths = [f"06-backend/{name}" for name in _rows(SCOPE)] + list(SUBJECT)
    diff = subprocess.run(
        ["git", "diff", "--name-only", commit, "HEAD", "--", *paths],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    return sorted(name for name in diff.stdout.split("\n") if name.strip())


def run() -> tuple[str, str]:
    scope = _rows(SCOPE)
    in_tests = len(list((BACKEND / "tests").glob("*.py"))) if (BACKEND / "tests").exists() else 0
    out_of_scope = max(in_tests - len(scope), 0)
    baseline = _baseline()

    receipt = _receipt()
    if receipt is None:
        return "FAIL", (
            f"no readable receipt at {RECEIPT.relative_to(REPO)} — nobody has run the "
            f"{len(scope)} scoped file(s). Run "
            "`python3 10-scripts/prove_backend_suite.py` and commit the receipt; a suite "
            "nobody runs is a check that cannot fail (law 7)"
        )

    problems: list[str] = []

    unnumbered = sorted(node for node, note in baseline.items() if not DEFECT_ID.search(note))
    if unnumbered:
        problems.append(
            f"{len(unnumbered)} parked red(s) carry no DEF- id: {'; '.join(unnumbered[:3])}"
            + " — file the defect; a red nobody can count is the thing this gate exists for"
        )

    red = sorted(receipt.get("failing", []))
    new = [node for node in red if node not in baseline]
    if new:
        problems.append(
            f"{len(new)} red(s) in the receipt are not in the baseline: {'; '.join(new[:5])}"
            + (f" (+{len(new) - 5} more)" if len(new) > 5 else "")
            + " — fix it, or park it in backend_suite_known_reds.txt WITH a DEF- id"
        )

    paid = [node for node in baseline if node not in red]
    if paid:
        problems.append(
            f"{len(paid)} baseline row(s) are no longer red and must be deleted in this same "
            f"diff: {'; '.join(paid[:5])} — backend_suite_known_reds.txt can only shrink"
        )

    moved = _moved_since(str(receipt.get("commit", "")))
    if moved:
        problems.append(
            f"the receipt predates {len(moved)} change(s) to what it proved: "
            f"{'; '.join(moved[:4])}"
            + (f" (+{len(moved) - 4} more)" if len(moved) > 4 else "")
            + " — re-run `python3 10-scripts/prove_backend_suite.py`"
        )

    if problems:
        return "FAIL", "; ".join(problems)

    counts = receipt.get("counts", {})
    return "PASS", (
        f"receipt {receipt.get('taken_at', '?')} at {str(receipt.get('commit', ''))[:9]}: "
        f"{counts.get('passed', 0)} passed, {len(red)} red ({len(baseline)} parked, each with "
        f"a DEF- id) over {len(scope)} scoped file(s) — "
        f"⚠ {out_of_scope} file(s) in 06-backend/tests are NOT in scope and this gate says "
        "nothing about them"
    )


def selftest() -> int:
    """Five directions, each through `run()` — the path `run_gates` calls."""
    ok = True
    kept_receipt = RECEIPT.read_text(encoding="utf-8") if RECEIPT.exists() else None
    kept_baseline = BASELINE.read_text(encoding="utf-8") if BASELINE.exists() else None
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True
    ).stdout.strip()

    def _write(failing, baseline_text, commit=head):
        RECEIPT.write_text(
            json.dumps(
                {
                    "taken_at": "2026-09-27T00:00:00+00:00",
                    "commit": commit,
                    "counts": {"passed": 1},
                    "failing": failing,
                    "scope": _rows(SCOPE),
                }
            ),
            encoding="utf-8",
        )
        BASELINE.write_text(baseline_text, encoding="utf-8")

    try:
        RECEIPT.unlink(missing_ok=True)
        BASELINE.write_text("", encoding="utf-8")
        status, message = run()
        if status != "FAIL" or "no readable receipt" not in message:
            print(f"SELFTEST FAIL 1/5: a missing receipt did not bite ({status}: {message})")
            ok = False
        else:
            print(f"selftest 1/5 — missing receipt bites: {message[:90]}")

        _write(["tests/test_x.py::test_y"], "")
        status, message = run()
        if status != "FAIL" or "not in the baseline" not in message:
            print(f"SELFTEST FAIL 2/5: a new red did not bite ({status}: {message})")
            ok = False
        else:
            print(f"selftest 2/5 — a new red bites: {message[:90]}")

        _write([], "tests/test_x.py::test_y  DEF-RAT-6980 parked\n")
        status, message = run()
        if status != "FAIL" or "can only shrink" not in message:
            print(f"SELFTEST FAIL 3/5: a paid-off row did not bite ({status}: {message})")
            ok = False
        else:
            print(f"selftest 3/5 — a paid-off row bites: {message[:90]}")

        _write(["tests/test_x.py::test_y"], "tests/test_x.py::test_y  parked, no id\n")
        status, message = run()
        if status != "FAIL" or "no DEF- id" not in message:
            print(f"SELFTEST FAIL 4/5: an un-numbered park did not bite ({status}: {message})")
            ok = False
        else:
            print(f"selftest 4/5 — a park with no DEF- id bites: {message[:90]}")

        _write([], "", commit="0" * 40)
        status, message = run()
        if status != "FAIL" or "predates" not in message:
            print(f"SELFTEST FAIL 5/5: a stale receipt did not bite ({status}: {message})")
            ok = False
        else:
            print(f"selftest 5/5 — a receipt that outlived its subject bites: {message[:90]}")
    finally:
        if kept_receipt is None:
            RECEIPT.unlink(missing_ok=True)
        else:
            RECEIPT.write_text(kept_receipt, encoding="utf-8")
        if kept_baseline is None:
            BASELINE.unlink(missing_ok=True)
        else:
            BASELINE.write_text(kept_baseline, encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    status, message = run()
    print(f"G135 backend-suite-receipt {status}  {message}")
    raise SystemExit(selftest())
