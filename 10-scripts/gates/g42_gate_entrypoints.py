#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-672 (2026-08-25) — sixteen gate modules defined `run()` and NO
#           `__main__`, so running one directly exited 0 printing nothing. Two
#           commit messages on this branch claim a "G7 PASS" obtained that way.
#           DEF-674 (2026-08-25) — the exact mirror: `g41_tenant_guc_form` had
#           `main()` and NO `run()`, so `run_gates.py` crashed on it from the
#           day it was added. A tenant-isolation ratchet, dead in CI.
# Rules:    CLAUDE.md hard-won law 7 (prove a guard goes RED before trusting it
#           green) · DEF-182 (a check whose output cannot distinguish pass from
#           fail is worse than no check, because it is trusted)
# ───────────────────────────────────────────────────────
"""G42 — every gate module can be reached BOTH WAYS.

WHY THIS GATE EXISTS
--------------------
There are two ways to run a gate in this repo and they use different entry
points:

    python3 10-scripts/gates/g07_human_owned.py     needs `if __name__ == …`
    run_gates.py  →  module.run()                   needs `run()`

**A module can satisfy either one alone and be silently dead in the other**, and
both halves have now happened, on the same day, in opposite directions:

* **DEF-672** — sixteen modules had `run()` and no main block. Running one
  directly imported it, defined a function, and exited **0 with no output**.
  To the eye and to `$?` that is indistinguishable from a gate that passed. I
  reported "G7 PASS" twice from exactly that command; run properly, G7 FAILS.
* **DEF-674** — `g41_tenant_guc_form` had `main()` and no `run()`. The stack
  reported `gate crashed: AttributeError(… has no attribute 'run')` on every
  run since it was added. On a branch already showing 18 FAILs, one more red
  line is not read.

Neither failure is visible from the side you happen to be using. That is the
whole reason this check is worth three lines of logic and a long comment.

WHAT IT CHECKS
--------------
Every `10-scripts/gates/g*.py` that defines `run()` must ALSO define a
`__main__` block, and every module registered in `run_gates.py` must define
`run()`. Parsed from the source with `ast`, never imported — importing a gate
to check it would run its module-level work, and one bad module would take this
one down with it.

WHAT IT DELIBERATELY DOES NOT CHECK
-----------------------------------
Whether a gate is REGISTERED in `run_gates.py`. That is already `_assert_registry_sane()`'s
job, it does it better, and duplicating it here would mean two checks disagreeing
about the same fact the first time somebody edits one.
"""
from __future__ import annotations

import ast
import pathlib
import sys

GATES = pathlib.Path(__file__).resolve().parent

#: Not gates: the runner itself, this gate's own siblings that are libraries,
#: and the self-test. Each is listed with the reason it is not one.
NOT_A_GATE = {
    "run_gates.py",  # the runner
    "common.py",  # shared helpers
    "check_unwired_props.py",  # a library g13 imports
    "g12_selftest.py",  # proves g12 bites; has no run() by design
    "g53_selftest.py",  # proves g53 bites; has no run() by design (DEF-2790)
}


def _defs(tree: ast.Module) -> set[str]:
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _has_main_block(tree: ast.Module) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
        ):
            return True
    return False


def _run_shape_problems(path: pathlib.Path, tree: ast.Module) -> list[str]:
    """What `run()` says it returns, and what it visibly returns.

    ⚠ DEF-2849, the THIRD member of this gate's own family. DEF-672 was a
    missing `__main__`; DEF-674 was a missing `run()`; this one had BOTH and
    `run()` returned a `list[str]`. The runner does `status, detail =
    module.run()`, so an empty list — the PASS case — raised
    `ValueError('not enough values to unpack (expected 2, got 0)')` and the
    gate reported `gate crashed` from the hour it was written. Presence was
    never the whole contract; SHAPE is the other half.

    Static on purpose (the module is never imported, per this gate's docstring),
    so this reads two things and claims nothing more: the declared annotation,
    and any return whose value is a literal of the wrong kind.
    """
    problems: list[str] = []
    fn = next(
        (
            n
            for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "run"
        ),
        None,
    )
    if fn is None:
        return problems

    # (a) A DECLARED shape that is not the runner's shape. Only checked when an
    #     annotation is actually written: fifteen working gates declare nothing
    #     at all, and demanding one from them would be churn, not safety. G60
    #     DID declare — `-> list[str]` — so this alone catches the occurrence.
    if fn.returns is not None:
        declared = ast.unparse(fn.returns)
        if declared not in {"tuple[str, str]", "Tuple[str, str]"}:
            problems.append(
                f"{path.name}: `run()` is declared `-> {declared}`, but `run_gates.py` unpacks "
                "`status, detail = module.run()`. It must be `-> tuple[str, str]` (DEF-2849)"
            )

    # (b) What it VISIBLY returns, which needs no annotation to be wrong. A
    #     collection literal cannot unpack into two values whatever it is
    #     called, and neither can a local the function fills as a list — which
    #     is the exact line G60 shipped: `return failures`.
    collection = (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)
    accumulators: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if ast.unparse(node.annotation).split("[")[0] in {"list", "set", "dict"}:
                accumulators.add(node.target.id)
        elif isinstance(node, ast.Assign) and isinstance(node.value, collection):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    accumulators.add(target.id)

    for node in ast.walk(fn):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) and node is not fn:
            continue
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        value = node.value
        if isinstance(value, collection):
            problems.append(
                f"{path.name}: `run()` returns a {type(value).__name__} at line "
                f"{node.lineno}; the runner unpacks two values (DEF-2849)"
            )
        elif isinstance(value, ast.Tuple) and len(value.elts) != 2:
            problems.append(
                f"{path.name}: `run()` returns a {len(value.elts)}-tuple at line "
                f"{node.lineno}; the runner unpacks exactly two (DEF-2849)"
            )
        elif isinstance(value, ast.Name) and value.id in accumulators:
            problems.append(
                f"{path.name}: `run()` returns `{value.id}` at line {node.lineno}, which this "
                "function fills as a collection; the runner unpacks two values (DEF-2849)"
            )
    return problems


def run() -> tuple[str, str]:
    problems: list[str] = []
    checked = 0
    for path in sorted(GATES.glob("g*.py")):
        if path.name in NOT_A_GATE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names = _defs(tree)
        if "run" not in names:
            problems.append(
                f"{path.name}: defines no `run()`, so `run_gates.py` cannot call it — "
                "the stack will report `gate crashed: AttributeError` and count it as one "
                "FAIL among many (DEF-674)"
            )
            continue
        checked += 1
        problems.extend(_run_shape_problems(path, tree))
        if not _has_main_block(tree):
            problems.append(
                f"{path.name}: defines `run()` but no `if __name__ == \"__main__\"` block, so "
                "running it directly exits 0 printing NOTHING — indistinguishable from a pass "
                "(DEF-672)"
            )
    if problems:
        return "FAIL", (
            f"{len(problems)} gate entry-point problem(s) — reachable only one way, or the "
            "wrong shape for the runner: " + " · ".join(problems)
        )
    return "PASS", (
        f"{checked} gate module(s) expose both `run()` (for run_gates.py) and a `__main__` "
        f"block (for a human), and every `run()` is declared and visibly returns "
        f"`(status, detail)`; {len(NOT_A_GATE)} file(s) excluded by name, each with a reason"
    )


def main() -> int:
    status, message = run()
    print(f"{status}: {message}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
