#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-022 (EP-INT-06) · CR-069 wave F — one utility's dead mail
#           server stays one utility's problem.
# Rules:    BR-INT-022 (a hard timeout, a per-connection cap and a breaker on
#           EVERY provider call) · BR-INT-041 (P5 — one tenant's outage is one
#           tenant's outage) · CLAUDE.md hard-won law 2 (built is not wired) ·
#           law 7 (proven RED first — see the docstring)
# Tests:    selftest() below · 06-backend/tests/test_us_int_022_isolation.py
# Impacts:  every module under 06-backend/apps/integrations that dials out
# ───────────────────────────────────────────────────────
"""G108 — every adapter call goes through the guard, and the guard has a caller.

WHY THIS GATE EXISTS, AND IT IS A DEFECT THAT ALREADY HAPPENED
---------------------------------------------------------------
On 2026-09-04 `apps/integrations/runtime.py` landed: 427 lines implementing a
hard timeout, a per-connection concurrency cap and a circuit breaker, with 297
lines of tests, all green. **Nothing imported it** (`DEF-INT-4015`). Every one
of the four places that actually dials a provider — the two runners, the *Test
it now* job and the notifications seam — called the adapter directly, so the
ninety-second hang the module exists to contain was exactly as uncontained
after that commit as before it.

⚠ **NOTHING IN THIS REPOSITORY COULD SEE IT.** `G13` is the built-is-not-wired
gate and it reads React props; no check asks whether a Python module has a
caller. The tests could not see it either, and that is the part worth
understanding rather than the bug: **they all called `guarded_call` themselves**,
so they proved the policy and said nothing about the product. A test that
constructs the thing it is testing cannot tell you the product constructs it too.

WHAT IT READS
-------------
The AST of every non-test module under `06-backend/apps/integrations`.

1. **No unguarded dial.** A call to `.execute(...)` or `.test(...)` on anything
   whose name mentions an adapter is a dial. It is legal only inside a
   `call=` keyword argument (the callable handed to the guard) — anywhere else
   it is a provider call with no deadline. `adapters/` and `conformance.py` are
   exempt: an adapter IS the transport, and the conformance kit drives adapters
   directly on purpose.
2. **The guard has a caller.** `runtime.guarded_call` must be reached from
   outside `runtime.py` and outside `tests/`. This is the clause that fails on
   the state the branch was actually in.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not check that the guard is *correct* — `tests/test_us_int_022_*.py`
does that, on a thread pool with a stopwatch. This gate answers the one question
those tests cannot ask about themselves: **is the product wired to it.**

PROVEN RED FIRST (law 7, 2026-09-05), AND THROUGH `run_gates.py`
-----------------------------------------------------------------
The RED proof is the tip of 2026-09-04 itself: with `runners/deliver.py` calling
`adapter.execute(view_of(connection), secrets, work)` directly the gate reports

    FAIL: apps/integrations/runners/deliver.py:82 dials a provider outside the
    guard — .execute( with no timeout, cap or breaker (BR-INT-022)

and with `guarded_call` deleted from every caller it reports

    FAIL: runtime.guarded_call has no caller outside runtime.py and tests/ —
    the guard exists and the product does not use it (DEF-INT-4015, law 2)

`selftest()` replays both on in-memory bodies and `run()` refuses to report
anything until it has (the `G42` contract). ⚠ It was proved through
`run_gates.py` and not `python3 g108_….py` — `DEF-GOV-3733` records two gates
announced green while the suite reported they had no callable `run`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
MODULE = REPO / "06-backend" / "apps" / "integrations"

#: The two adapter methods that reach a third party. `validate` and `describe`
#: are local and touch nothing.
DIALS = frozenset({"execute", "test"})

#: An adapter IS the transport, so it dials by definition; the conformance kit
#: drives adapters directly and that is its whole job.
EXEMPT_PARTS = frozenset({"adapters", "tests", "migrations"})
EXEMPT_NAMES = frozenset({"conformance.py", "runtime.py"})

GUARD = "guarded_call"


def _is_adapterish(node: ast.expr) -> bool:
    """Does this expression look like an adapter instance?

    Deliberately broad — `adapter`, `adapter_cls()`, `self.adapter` — because a
    gate that only recognises one spelling is a gate the next lane walks past
    by naming a variable differently.
    """
    while isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Name):
        return "adapter" in node.id.lower()
    if isinstance(node, ast.Attribute):
        return "adapter" in node.attr.lower() or _is_adapterish(node.value)
    return False


def _guarded_calls(tree: ast.AST) -> set[int]:
    """Every `Call` node that sits INSIDE a `call=<expr>` keyword — the callable
    handed to the guard.

    ⚠ **BY AST ANCESTRY, NOT BY LINE SPAN, AND THE FIRST DRAFT USED LINE SPANS
    AND WAS DEFEATED BY ITS OWN RED PROOF (2026-09-05).** A dial written on the
    SAME LINE as a `call=` keyword — `call=None); result = adapter.execute(...)`
    — falls inside that keyword's line range and was read as guarded, so the
    gate reported PASS over a sabotage written specifically to break it. A
    check whose output cannot distinguish pass from fail is worse than no check,
    because it is trusted (CLAUDE.md law 11, DEF-182's lesson). Ancestry cannot
    be fooled by layout.
    """
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg != "call":
                continue
            for inner in ast.walk(kw.value):
                if isinstance(inner, ast.Call):
                    guarded.add(id(inner))
    return guarded


def findings_in(source: str, *, where: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    guarded = _guarded_calls(tree)
    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in DIALS or not _is_adapterish(node.func.value):
            continue
        if id(node) in guarded:
            continue
        line = node.lineno
        problems.append(
            f"{where}:{line} dials a provider outside the guard — .{node.func.attr}( "
            f"with no timeout, cap or breaker (BR-INT-022); hand it to "
            f"services.guarded_adapter_call as `call=`"
        )
    return problems


def _sources() -> list[Path]:
    found: list[Path] = []
    for path in sorted(MODULE.rglob("*.py")):
        if EXEMPT_PARTS & set(path.parts) or path.name in EXEMPT_NAMES:
            continue
        found.append(path)
    return found


_CLEAN = (
    "outcome = services.guarded_adapter_call(\n"
    "    connection=connection,\n"
    "    operation=operation,\n"
    "    call=lambda _s=secrets: adapter.execute(view_of(connection), _s, work),\n"
    ")\n"
)
_RED = "result = adapter.execute(view_of(connection), secrets, work)\n"
#: The sabotage that defeated the line-span draft: a dial sharing its line with
#: a `call=` keyword. Kept in the self-test permanently — this gate has been
#: wrong once and the shape it was wrong about is cheap to keep testing.
_RED_SAME_LINE = (
    "outcome = services.guarded_adapter_call(\n"
    "    call=None); result = adapter.execute(view_of(connection), secrets, work); _=(\n"
    ")\n"
)


def selftest() -> bool:
    if findings_in(_CLEAN, where="selftest"):
        return False
    red = findings_in(_RED, where="selftest")
    if len(red) != 1 or ".execute(" not in red[0]:
        return False
    same_line = findings_in(_RED_SAME_LINE, where="selftest")
    return len(same_line) == 1 and ".execute(" in same_line[0]


def run() -> tuple[str, str]:
    if not selftest():
        return "FAIL", "the gate's own self-test does not hold — it cannot see an unguarded dial (DEF-182)"
    if not MODULE.is_dir():
        return "FAIL", f"{MODULE} is not a directory — nothing to guard"

    problems: list[str] = []
    dials = 0
    callers: list[str] = []
    for path in _sources():
        source = path.read_text(encoding="utf-8")
        where = str(path.relative_to(REPO))
        problems.extend(findings_in(source, where=where))
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in DIALS and _is_adapterish(node.func.value):
                    dials += 1
        if GUARD in source:
            callers.append(where)

    # Clause 2 — the one that fails on the state the branch was actually in.
    if not callers:
        problems.append(
            f"runtime.{GUARD} has no caller outside runtime.py and tests/ — the "
            f"guard exists and the product does not use it (DEF-INT-4015, "
            f"hard-won law 2: built is not wired)"
        )
    if problems:
        return "FAIL", " | ".join(problems)
    return "PASS", (
        f"{dials} provider dial(s) across {len(_sources())} module(s), every one inside a "
        f"guarded `call=`; {GUARD} reached from {len(callers)} file(s); "
        "self-test: the unguarded-dial sabotage bites"
    )


def main() -> int:
    status, note = run()
    print(f"G108 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
