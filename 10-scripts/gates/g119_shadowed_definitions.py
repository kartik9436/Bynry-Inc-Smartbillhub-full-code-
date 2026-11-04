#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects: DEF-RBS-4365 — a second `def _person()` 1,250 lines below the first
#          in `apps/runbooks/selectors.py`. Python took the last one, silently,
#          and `GET /runbooks/{key}` answered **500** for every runbook the code
#          had added rather than a person edited.
# Rules:   CLAUDE.md hard-won law 1 (a comment claiming a guarantee is not the
#          guarantee — and a NAME claiming to be one function is not one) ·
#          law 7 (proved RED first, in the harness that will run it, and its
#          output distinguishes pass from fail to a reader)
# Tests:   self_test() below, which runs on every invocation
# ───────────────────────────────────────────────────────
"""G119 — one module-scope name, one definition. The last one silently wins.

WHAT HAPPENED, AND WHY NOTHING CAUGHT IT
-----------------------------------------
`apps/runbooks/selectors.py` grew a second `def _person(user)` in a later wave,
1,250 lines below the first. Both are private, both are called, and **each reads
perfectly correctly at its own call site** — the first returns `{"name": …}` or
`None` for a NULLABLE actor, the second returns a bare string for a REQUIRED
owner. Python binds the last definition, so three call sites written against the
first silently began calling the second, and `runbook_activity` raised

    AttributeError: 'NoneType' object has no attribute 'first_name'

which reaches a clerk as a **500 on `RBS-004`** for every runbook whose bootstrap
version has no `changed_by` — which is every runbook the code added.

**Nothing in this repository looks.** `ruff`'s default set does not carry `F811`
for this shape at module scope in the configuration here, `tsc` has no
equivalent on the Python side, the trace-header gates read a header's SHAPE, and
both suites pass because each asserts its own layer. The only way to see it is
to grep a file for its own function names, which nobody does.

WHAT IT READS
-------------
Every backend `.py` file (`common.backend_code_files()`), parsed with `ast`. It
reports a name **defined more than once at MODULE SCOPE** as a `FunctionDef`,
`AsyncFunctionDef` or `ClassDef`.

WHAT WOULD MAKE THIS CHECK PASS WRONGLY — answered in writing, because a check
whose false pass you cannot describe is a check you do not understand:

  * **A REDEFINITION INSIDE A CLASS OR A FUNCTION.** Two methods of the same
    name in one class is the same bug one scope down. → Not covered, and SAID SO
    rather than implied: this walks `tree.body` only, and the count of what it
    did NOT look at is printed beside what it did. A declared blind spot with no
    number attached is indistinguishable from an empty one (`G32` reported
    `0 unresolved` truthfully over 21 live refusals).
  * **A DELIBERATE REDEFINITION UNDER `if TYPE_CHECKING:` OR A VERSION BRANCH.**
    Two `def`s under opposite arms of an `if` are one name with two bodies and
    exactly one runs. → Only `tree.body` top-level statements are counted, so a
    definition inside any `if`/`try` block is not counted at all. That is the
    conservative direction: it can miss, it cannot cry wolf.
  * **A `@overload` STACK OR A `@singledispatch` REGISTRATION.** Both legitimately
    repeat a name. → Any definition carrying a decorator whose name ends
    `overload`, or any `.register` decorator, is skipped by name.
  * **A NAME RE-BOUND BY AN ASSIGNMENT** (`ALL = PARAM_ALL` after a `def ALL`).
    → Not covered. Assignments are a different and much noisier class, and this
    gate is aimed at the one that shipped a 500.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402

#: Decorators that make a repeated name legitimate. Matched on the LAST dotted
#: part, so `typing.overload`, `t.overload` and a bare `overload` all hit.
EXEMPT_DECORATOR_TAILS = ("overload", "register", "setter", "getter", "deleter")


def _decorator_tails(node: ast.AST) -> list[str]:
    tails: list[str] = []
    for decorator in getattr(node, "decorator_list", ()):  # type: ignore[arg-type]
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        while isinstance(target, ast.Attribute):
            tails.append(target.attr)
            target = target.value
        if isinstance(target, ast.Name):
            tails.append(target.id)
    return tails


def shadowed(text: str) -> list[tuple[str, int, int]]:
    """`[(name, first line, second line)]` for every name defined twice up top."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    seen: dict[str, int] = {}
    found: list[tuple[str, int, int]] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if any(tail in EXEMPT_DECORATOR_TAILS for tail in _decorator_tails(node)):
            continue
        if node.name in seen:
            found.append((node.name, seen[node.name], node.lineno))
        else:
            seen[node.name] = node.lineno
    return found


RED = (
    "def _person(user):\n"
    "    return {'name': user.full_name} if user else None\n"
    "\n\n"
    "def other():\n"
    "    return 1\n"
    "\n\n"
    "def _person(user):\n"
    "    return user.first_name\n"
)
GREEN = (
    "def _person(user):\n"
    "    return {'name': user.full_name} if user else None\n"
    "\n\n"
    "def _owner_name(user):\n"
    "    return user.first_name\n"
)
NESTED_OK = (
    "def outer():\n"
    "    def inner():\n"
    "        return 1\n"
    "\n"
    "    def inner():\n"
    "        return 2\n"
    "\n"
    "    return inner\n"
)
OVERLOAD_OK = (
    "from typing import overload\n"
    "\n\n"
    "@overload\n"
    "def f(x: int) -> int: ...\n"
    "\n\n"
    "@overload\n"
    "def f(x: str) -> str: ...\n"
    "\n\n"
    "def f(x):\n"
    "    return x\n"
)
BRANCHED_OK = (
    "import sys\n"
    "\n"
    "if sys.version_info >= (3, 12):\n"
    "    def f():\n"
    "        return 1\n"
    "else:\n"
    "    def f():\n"
    "        return 2\n"
)
CLASS_RED = "class A:\n    pass\n\n\nclass A:\n    pass\n"


def self_test() -> list[tuple[str, bool, str]]:
    """Six cases, and the first is `DEF-RBS-4365` itself, reduced."""
    return [
        ("the real DEF-RBS-4365 shape bites", len(shadowed(RED)) == 1, "two _person"),
        ("the fix is green", shadowed(GREEN) == [], "renamed"),
        ("a nested redefinition is NOT reported", shadowed(NESTED_OK) == [], "inner()"),
        ("an @overload stack is NOT reported", shadowed(OVERLOAD_OK) == [], "typing.overload"),
        ("a version-branched def is NOT reported", shadowed(BRANCHED_OK) == [], "if/else"),
        ("a duplicated class bites too", len(shadowed(CLASS_RED)) == 1, "class A"),
    ]


def run() -> tuple[str, str]:
    failures = [name for name, ok, _ in self_test() if not ok]
    if failures:
        return "FAIL", f"self-test broken: {', '.join(failures)}"

    files = common.backend_code_files()
    if not files:
        return "SKIP", "no backend python file was found to read"

    problems: list[str] = []
    nested_not_checked = 0
    for path in files:
        text = common.read_text(path)
        for name, first, second in shadowed(text):
            problems.append(f"{common.rel(path)}:{second} redefines {name}() from line {first}")
        # The declared blind spot, COUNTED (see the docstring).
        nested_not_checked += text.count("    def ")

    if problems:
        return "FAIL", (
            common.summarize(problems)
            + ". Python binds the LAST definition, silently, and each function reads correctly "
            "at its own call site — DEF-RBS-4365 was a 500 on RBS-004 for every runbook the code "
            "had added. Rename one and re-point its callers."
        )
    return "PASS", (
        f"{len(files)} backend file(s): no module-scope name is defined twice; "
        f"{nested_not_checked} indented `def` not examined (nested and method scopes are this "
        "gate's declared blind spot); self-test: 6/6 bite"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
