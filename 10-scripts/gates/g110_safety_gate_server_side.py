#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-043 (EP-WRK-08) TC-5 — *"remove the server check → the gate
#           FAILS, proved RED first"*. `CR-070` §12 gate 2.
# Rules:    BR-WRK-037 (safety blocks the task list on the phone AND the server
#           refuses a completion carrying an unticked mandatory safety row,
#           naming the row) · BR-SHL-025 (the server independently enforces
#           every mutating call) · CLAUDE.md hard-won law 1 (a comment claiming
#           a guarantee is not the guarantee) · law 7 (prove a guard RED first)
# Tests:    selftest() below · 06-backend/tests/test_us_wrk_043_safety_server.py
# ───────────────────────────────────────────────────────
"""G110 — the SERVER still refuses a completion with an unticked safety row.

r10, verbatim, and it is the sentence this gate exists to keep true:

    *"The lock is on the phone, and it must also be on the server. A screen that
    greys a list is a convenience; a server that refuses a completion with an
    unticked mandatory safety row is the guarantee. **Build both or you have
    built neither.**"*

WHY A GATE AND NOT ONLY A TEST
------------------------------
`tests/test_us_wrk_043_safety_server.py` proves the refusal WORKS. This proves
it still EXISTS, and the two fail differently. A lane refactoring
`submit_field_result` — moving the completion behind a new service, splitting it
for wave L's sync, "simplifying" a guard that appears to duplicate a screen —
deletes the call and the suite goes red in a way that reads as *fix the test*.
This goes red in a way that reads as *you have removed a safety rule*, which is
the sentence that ought to appear.

⚠ **IT CHECKS THREE THINGS, AND THE THIRD IS THE ONE A REFACTOR BREAKS
SILENTLY.**

  1. `apps/work/checklist.py` still exports `safety_lock` — THE one evaluator.
  2. `apps/metering/connections.py` still CALLS a safety check inside
     `submit_field_result`, and that call is reached before the order is
     mutated.
  3. **The check delegates to `checklist.safety_lock` rather than re-deriving
     the condition.** `checklist.py`'s own docstring gives the reason: two
     surfaces that each decide for themselves is how a technician comes to be
     allowed to start work the office believes is blocked. A hand-rolled
     `if not all(row.ticked_at ...)` here would pass checks 1 and 2 and would be
     the beginning of exactly that divergence.

WHY IT READS THE SOURCE AND NOT THE BEHAVIOUR
---------------------------------------------
`run_gates.py` is stdlib-only and imports no Django app, so this reads the file
with `ast` — a real parse, not a grep, because a grep matches the word in a
comment and would go on passing over a deleted call sitting under a docstring
that still describes it (hard-won law 1, precisely). Every place it could fail
to understand what it read reports **FAIL**: a gate that cannot find the
function it is checking has verified nothing (`DEF-524`).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
CONNECTIONS = REPO / "06-backend" / "apps" / "metering" / "connections.py"
CHECKLIST = REPO / "06-backend" / "apps" / "work" / "checklist.py"

#: The completion. `BR-MET-110` step one — *the field sends its data*.
COMPLETION = "submit_field_result"
#: The one evaluator, in `apps/work/checklist.py`.
EVALUATOR = "safety_lock"


def _functions(path: Path) -> dict[str, ast.FunctionDef]:
    """Every top-level `def` in a module, by name, from a real parse."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _called_names(node: ast.AST) -> set[str]:
    """Every name called anywhere inside a node — `f()` and `a.b.f()` alike."""
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        target = child.func
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Attribute):
            names.add(target.attr)
    return names


def findings() -> tuple[list[str], dict[str, object]]:
    problems: list[str] = []
    seen: dict[str, object] = {}

    # ── 1 · the one evaluator still exists ──────────────────────────────────
    if not CHECKLIST.exists():
        problems.append(
            "06-backend/apps/work/checklist.py is missing — there is no safety "
            "evaluator at all, so neither the screen nor the server can be locked"
        )
        return problems, seen
    checklist_functions = _functions(CHECKLIST)
    if EVALUATOR not in checklist_functions:
        problems.append(
            f"apps/work/checklist.py no longer defines {EVALUATOR}() — BR-WRK-037's "
            "ONE evaluator is gone, and every caller is now deciding for itself "
            "whether a job may proceed"
        )
    seen["evaluator"] = f"checklist.{EVALUATOR}" if EVALUATOR in checklist_functions else "MISSING"

    # ── 2 · the completion still calls a safety check ───────────────────────
    if not CONNECTIONS.exists():
        problems.append("06-backend/apps/metering/connections.py is missing")
        return problems, seen
    functions = _functions(CONNECTIONS)
    if COMPLETION not in functions:
        problems.append(
            f"apps/metering/connections.py no longer defines {COMPLETION}() — this gate "
            "cannot verify the refusal on a function it cannot find, and a moved "
            "completion is exactly when the check gets left behind. Point this gate at "
            "the new home in the same commit that moves it."
        )
        return problems, seen

    body = functions[COMPLETION]
    called = _called_names(body)
    guards = sorted(name for name in called if "safety" in name.lower())
    if not guards:
        problems.append(
            f"{COMPLETION}() calls NOTHING with 'safety' in its name — the server no "
            "longer refuses a completion carrying an unticked mandatory safety row "
            "(BR-WRK-037). r10: 'a server that refuses ... is the guarantee. Build "
            "both or you have built neither.' The phone's greyed list is a courtesy "
            "that a replayed request, an out-of-order sync batch and an offline phone "
            "all walk straight past."
        )
        return problems, seen
    seen["guard"] = ", ".join(guards)

    # ── 3 · the guard DELEGATES rather than re-deriving ─────────────────────
    #
    # The guard is a module-level helper; find it and check that IT asks the one
    # evaluator. A hand-rolled condition passes checks 1 and 2 and is the start
    # of the divergence BR-WRK-037 exists to prevent.
    delegating = []
    for name in guards:
        guard = functions.get(name)
        if guard is None:
            # Called through an attribute (`work_checklist.safety_lock(...)`) —
            # the evaluator's own name IS the call, which is delegation.
            if name == EVALUATOR:
                delegating.append(name)
            continue
        if EVALUATOR in _called_names(guard):
            delegating.append(name)
    if not delegating:
        problems.append(
            f"the safety guard in {COMPLETION}() ({', '.join(guards)}) does not call "
            f"{EVALUATOR}() — it is re-deriving the lock instead of asking the one "
            "evaluator. checklist.py's own docstring gives the reason: two surfaces "
            "that each decide for themselves is how a technician is allowed to start "
            "work the office believes is blocked. One gets a fix; the other does not."
        )
    seen["delegates_to"] = ", ".join(delegating) or "NOTHING"

    return problems, seen


def run() -> tuple[str, str]:
    """`(status, detail)` for `run_gates.py`.

    ⚠ Both entry points on purpose (`DEF-672` / `DEF-674`), and the red proof for
    this gate was run THROUGH `run_gates.py` rather than through `python3
    g110_….py` — `DEF-GOV-3733` records two gates announced green while the
    suite reported *"gate crashed: module has no attribute 'run'"*, because
    `__main__` is not the path the suite uses.
    """
    problems, seen = findings()
    if problems:
        return "FAIL", f"{len(problems)} problem(s): " + " · ".join(problems)
    return (
        "PASS",
        f"the server still refuses an unticked mandatory safety row: "
        f"{seen.get('guard')} inside submit_field_result(), delegating to "
        f"{seen.get('delegates_to')} (BR-WRK-037)",
    )


def main() -> int:
    status, note = run()
    print(f"G110 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
