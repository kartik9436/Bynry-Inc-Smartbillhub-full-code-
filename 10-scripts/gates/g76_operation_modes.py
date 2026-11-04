#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-013 (EP-INT-05) TC-2 — an operation missing its idempotency
#           mode or its completion mode is refused. CR-069 §13 gate 3: "every
#           declared operation names its idempotency mode and its completion
#           mode — a manifest missing either is refused at registration, not at
#           run time".
# Rules:    BR-INT-020 (the idempotency key is declared by the operation's
#           shape) · BR-INT-029 (idempotency has a mode) · BR-INT-046
#           (completion is declared) · BR-INT-037 (configuration is data) ·
#           CLAUDE.md hard-won law 7 (proven RED first — see the docstring)
# Tests:    selftest() below · 06-backend/tests/test_us_int_013_registry.py
#           TC-2 (the registry's own refusal, at load, with Django)
# Impacts:  06-backend/apps/integrations/manifests/*.py
# ───────────────────────────────────────────────────────
"""G76 — every declared operation names its idempotency mode AND its completion mode.

WHY THIS GATE EXISTS WHEN THE REGISTRY ALREADY REFUSES THE SAME THING
---------------------------------------------------------------------
`apps/integrations/registry.py` refuses a manifest missing either value at
`AppConfig.ready()`, naming the provider and the operation. That refusal is
the PRODUCT's guard and it is the one that matters at 06:02 on the first of
the month. This gate is the MERGE's guard: it reads the seventeen manifest
files as source, with `ast`, and fails the merge on the same omission —
without Django, without a database, in milliseconds, on every lane whether or
not that lane has ever started the app. A lane that edits a manifest and runs
only its own module's tests would otherwise learn about the omission from a
process that will not start, after the push.

Two checks that agree are not redundancy: the registry proves the RULE holds
in the running product, and this gate proves the SOURCE holds it before the
product is built. `CR-069` §13 names this as gate 3 and asks for exactly
that placement — *"refused at registration, not at run time"*.

WHAT IT READS
-------------
Every `Operation(...)` call in every module of `apps/integrations/manifests/`,
by keyword: `idempotency=Idempotency(mode="…")` must be present with a
non-None `mode`, and `completion="…"` must be present and not None. It reads
the call's keywords, so `Idempotency()` with no mode, `idempotency=None`, an
absent keyword and `completion=None` are all the same finding — the four ways a
lane can leave the value out. The provider is the module's `MANIFEST` key
(`key="…"`), the operation its `name="…"`; both appear in the sentence.

PROVEN RED FIRST (law 7, 2026-09-03)
------------------------------------
With `completion="immediate"` stripped from `email_smtp.py`'s send operation
the gate reported
    FAIL: manifests/email_smtp.py: email_smtp · send_message declares no completion mode
and with the line restored it went green. `selftest()` replays that on an
in-memory manifest body, plus the idempotency half, and `run()` refuses to
report anything until it has.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
MANIFESTS = REPO / "06-backend" / "apps" / "integrations" / "manifests"


def _callee(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _keyword(node: ast.Call, name: str) -> ast.AST | None:
    for kw in node.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _literal(node: ast.AST | None) -> object:
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    return "<expr>"


def _provider_key(tree: ast.AST) -> str:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _callee(node) == "Manifest":
            key = _literal(_keyword(node, "key"))
            if isinstance(key, str):
                return key
    return "?"


def findings_in(source: str, *, where: str) -> list[str]:
    """Every operation in `source` missing one of the two declared values."""
    tree = ast.parse(source)
    provider = _provider_key(tree)
    problems: list[str] = []
    operations = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _callee(node) != "Operation":
            continue
        operations += 1
        name = _literal(_keyword(node, "name"))
        label = name if isinstance(name, str) else "?"
        idem = _keyword(node, "idempotency")
        mode_ok = False
        if isinstance(idem, ast.Call) and _callee(idem) == "Idempotency":
            mode = _literal(_keyword(idem, "mode"))
            mode_ok = isinstance(mode, str) and bool(mode)
        if not mode_ok:
            problems.append(
                f"{where}: {provider} · {label} declares no idempotency mode "
                "(CR-069 §13 gate 3, BR-INT-029)"
            )
        completion = _literal(_keyword(node, "completion"))
        if not (isinstance(completion, str) and completion):
            problems.append(
                f"{where}: {provider} · {label} declares no completion mode "
                "(CR-069 §13 gate 3, BR-INT-046)"
            )
    if operations == 0 and provider != "?":
        problems.append(f"{where}: {provider} declares no operations at all (BR-INT-028)")
    return problems


CLEAN = """
MANIFEST = Manifest(
    key="example",
    operations=(
        Operation(
            name="send_message",
            idempotency=Idempotency(mode="refuse", source="queue_row_id"),
            completion="immediate",
        ),
    ),
)
"""
RED_COMPLETION = CLEAN.replace('            completion="immediate",\n', "")
RED_MODE = CLEAN.replace('Idempotency(mode="refuse", source="queue_row_id")', "Idempotency()")
RED_NONE = CLEAN.replace('completion="immediate"', "completion=None")


def selftest() -> bool:
    if findings_in(CLEAN, where="selftest"):
        return False
    a = findings_in(RED_COMPLETION, where="selftest")
    b = findings_in(RED_MODE, where="selftest")
    c = findings_in(RED_NONE, where="selftest")
    return (
        len(a) == 1
        and "example · send_message declares no completion mode" in a[0]
        and len(b) == 1
        and "declares no idempotency mode" in b[0]
        and len(c) == 1
        and "no completion mode" in c[0]
    )


def run() -> tuple[str, str]:
    if not MANIFESTS.is_dir():
        return "SKIP", f"{MANIFESTS.relative_to(REPO)} is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a declared operation "
            "from an undeclared one, so its verdict is worthless (DEF-182)"
        )
    files = sorted(p for p in MANIFESTS.glob("*.py") if p.name != "__init__.py")
    if not files:
        return "FAIL", f"{MANIFESTS.relative_to(REPO)} holds no manifest — nothing to guard"
    problems: list[str] = []
    operations = 0
    for path in files:
        where = f"manifests/{path.name}"
        try:
            source = path.read_text(encoding="utf-8")
            problems.extend(findings_in(source, where=where))
            operations += sum(
                1
                for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.Call) and _callee(node) == "Operation"
            )
        except SyntaxError as exc:  # a broken gate must block the merge
            problems.append(f"{where}: does not parse — {exc}")
    if problems:
        return "FAIL", " | ".join(problems[:6]) + (f" (+{len(problems) - 6} more)" if len(problems) > 6 else "")
    return "PASS", (
        f"{operations} operation(s) across {len(files)} manifest(s) each declare an idempotency "
        "mode and a completion mode — none can reach run time undeclared; "
        "self-test: both sabotages bite (a missing idempotency mode, a missing completion)"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
