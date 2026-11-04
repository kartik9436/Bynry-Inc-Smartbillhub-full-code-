#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-AST-8102 (critical) — an asset upload over the 200-row async bar
#          wrote nothing: the load ran as a background job whose actor carries
#          no role BY DESIGN, and three calls down the create path a
#          `@require_role`-guarded helper refused row 1. DEF-2515 and DEF-1108
#          are the same class; DEF-2515's own test (TC-3) looked ONE level deep
#          at the seams and passed over this one, which was three levels deep.
# Ruling:  PO GO 2026-09-30, step 4: "a new gate … that fails when any
#          @require_role-decorated function is reachable from a background-job
#          entry point".
# Tests:   selftest() below; proved RED through run_gates on the unfixed tree
# Impacts: every `core.jobs.set_job_handler(...)` body in 06-backend/apps
# ───────────────────────────────────────────────────────
"""G140 — a background-job body reaches no `@require_role`-guarded function.

WHY IT EXISTS
-------------
`core.permissions.require_role` reads `actor.role`. A job's actor carries an id
and NO role, deliberately (`import_runs._JobActor`: *"Role was checked at
enqueue; the worker carries the actor id in the record, never a role, so it can
grant nothing"*). So a role-guarded function that a job can reach is a function
that can only ever answer a job with a FALSE REFUSAL — and because the loaders
run under one transaction, one false refusal on row 1 loses the whole file. It
happened three times: DEF-1108, DEF-2515 (9,000 accounts), DEF-AST-8102 (every
asset upload over 200 rows). Each time the guard was added by somebody with no
reason to think about workers, and each time every test passed, because every
test stayed under the async bar and so ran on the request with a real role.

WHAT IT READS
-------------
A static call graph over `06-backend/apps/**/*.py` (tests and migrations
excluded), built from the AST:

  * a call to a module-level function by name, through `from … import`, or
    through a module alias (`services.fn(...)`, `seams.fn(...)`);
  * a seam: `resolve("assets", "create_from_import")` /
    `require("metering", "fn", kind="selectors")` inside a function is an edge
    to `apps.<module>.<kind or services>.<fn>`;
  * `fn.__wrapped__(...)` is an edge into `fn`'s BODY that does NOT pass its
    guard — the documented, deliberate way a job calls a guarded service
    (`update_asset.__wrapped__`), and exactly why it is lawful.

Entry points are every handler registered with `set_job_handler(kind, handler)`.
A path from an entry to a function decorated `@require_role` through an
ordinary call is a finding, printed as the path.

⚠ **WHAT IT CANNOT SEE, WITH A NUMBER BESIDE IT (law 7, fifth shape).** A call
through a variable, a dict of callables or `getattr` is not an edge; the gate
counts the job bodies it walked and the functions it reached, and prints both,
so a sudden drop reads as a blind spot rather than as a pass. It over-reports
rather than under-reports on a CONDITIONAL call — a guarded call behind an `if`
that a job never takes is still a finding, and the fix is to keep the guarded
door off the job's path (as `_create_asset_for_import` does), not to argue the
branch.

KNOWN FINDINGS
--------------
`g140_job_role_baseline.txt` lists paths that existed when this gate was born
and are NOT DEF-AST-8102's — each is a finding to fix under its own defect, not
an exemption. A path absent from the baseline fails the gate; a baseline line
that no longer matches fails it too, so the list can only shrink.

PROVEN RED FIRST (law 7)
------------------------
On the branch base `70c3cc7de`, before `_create_asset_for_import` existed
(`--list`, 10 paths):

    apps.metering.import_runs.run_load_job → … → _load_assets_rows →
    apps.metering.seams.create_asset_from_import → apps.assets.services.
    create_from_import → _create_asset_inner → _capture_opening_read (@require_role)

Then through `run_gates`' registry (`GATES` entry `.run()`, the path the suite
uses — DEF-GOV-3733) with the assets path fixed, it was STILL red, and on a
path nobody had reported:

    FAIL: … _load_locked → apps.metering.premises_owners.
    ensure_master_account_for_premises (@require_role) (+5 more)

— a premises upload over the bar creating no owner and no master account, the
`AuthError` counted as an ordinary owner refusal (`DEF-MET-8104`, filed and
fixed with `.__wrapped__`). Green after both: 18 job bodies, 1,309 functions. `selftest()` replays both directions on in-memory
sources and `run()` refuses to report until it has.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import ast
import sys
from collections import deque
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
BACKEND = REPO / "06-backend"
BASELINE = Path(__file__).resolve().parent / "g140_job_role_baseline.txt"

SEAM_CALLS = {"resolve", "require"}
GUARD = "require_role"

Key = tuple[str, str]  # (module, function)


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Call):
        node = node.func
    return getattr(node, "id", getattr(node, "attr", ""))


class Module:
    def __init__(self, name: str, tree: ast.Module, known_modules: set[str]) -> None:
        self.name = name
        self.functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        self.guarded: set[str] = set()
        self.module_alias: dict[str, str] = {}
        self.symbol_alias: dict[str, Key] = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions[node.name] = node
                if any(_decorator_name(d) == GUARD for d in node.decorator_list):
                    self.guarded.add(node.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("apps."):
                        self.module_alias[alias.asname or alias.name] = alias.name
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    parts = name.split(".")[: -node.level]
                    base = ".".join([*parts, base]) if base else ".".join(parts)
                if not base.startswith("apps"):
                    continue
                for alias in node.names:
                    local = alias.asname or alias.name
                    candidate = f"{base}.{alias.name}"
                    if candidate in known_modules:
                        self.module_alias[local] = candidate
                    else:
                        self.symbol_alias[local] = (base, alias.name)


def _edges(module: Module, fn: ast.AST) -> list[tuple[Key, bool]]:
    """(callee, passes_guard) for every call this function makes."""
    out: list[tuple[Key, bool]] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # seam: resolve("mod", "fn", kind="k")
        if isinstance(func, ast.Name) and func.id in SEAM_CALLS or (
            isinstance(func, ast.Attribute) and func.attr in SEAM_CALLS
        ):
            args = node.args
            if len(args) >= 2 and all(
                isinstance(a, ast.Constant) and isinstance(a.value, str) for a in args[:2]
            ):
                kind = "services"
                for kw in node.keywords:
                    if kw.arg == "kind" and isinstance(kw.value, ast.Constant):
                        kind = str(kw.value.value)
                out.append(((f"apps.{args[0].value}.{kind}", str(args[1].value)), True))
            continue
        # fn.__wrapped__(...) / mod.fn.__wrapped__(...) — the body, NOT the guard
        if isinstance(func, ast.Attribute) and func.attr == "__wrapped__":
            target = _target(module, func.value)
            if target is not None:
                out.append((target, False))
            continue
        target = _target(module, func)
        if target is not None:
            out.append((target, True))
    return out


def _target(module: Module, expr: ast.expr) -> Key | None:
    if isinstance(expr, ast.Name):
        if expr.id in module.functions:
            return (module.name, expr.id)
        if expr.id in module.symbol_alias:
            return module.symbol_alias[expr.id]
        return None
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        mod = module.module_alias.get(expr.value.id)
        if mod is not None:
            return (mod, expr.attr)
    return None


def _entries(modules: dict[str, Module]) -> list[Key]:
    found: list[Key] = []
    for module in modules.values():
        tree_nodes = [n for f in module.functions.values() for n in ast.walk(f)]
        tree_nodes += module._toplevel  # type: ignore[attr-defined]
        for node in tree_nodes:
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            called = getattr(func, "attr", getattr(func, "id", ""))
            if called != "set_job_handler" or len(node.args) < 2:
                continue
            target = _target(module, node.args[1])
            if target is not None:
                found.append(target)
    return sorted(set(found))


def build(sources: dict[str, str]) -> dict[str, Module]:
    names = set(sources)
    modules: dict[str, Module] = {}
    for name, source in sources.items():
        try:
            tree = ast.parse(source)
        except SyntaxError:  # pragma: no cover — another gate's problem
            continue
        module = Module(name, tree, names)
        module._toplevel = [  # type: ignore[attr-defined]
            n
            for top in tree.body
            if not isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef))
            for n in ast.walk(top)
        ]
        modules[name] = module
    return modules


def findings(modules: dict[str, Module]) -> tuple[list[str], int, int]:
    """(paths to a guarded function, entries walked, functions reached)."""
    entries = _entries(modules)
    reached_total: set[Key] = set()
    out: list[str] = []
    for entry in entries:
        parent: dict[Key, Key | None] = {entry: None}
        queue: deque[Key] = deque([entry])
        while queue:
            key = queue.popleft()
            module = modules.get(key[0])
            if module is None or key[1] not in module.functions:
                continue
            reached_total.add(key)
            for callee, passes_guard in _edges(module, module.functions[key[1]]):
                callee_module = modules.get(callee[0])
                if callee_module is None or callee[1] not in callee_module.functions:
                    continue
                if passes_guard and callee[1] in callee_module.guarded:
                    chain = [callee]
                    cursor: Key | None = key
                    while cursor is not None:
                        chain.append(cursor)
                        cursor = parent[cursor]
                    out.append(
                        " → ".join(f"{m}.{f}" for m, f in reversed(chain)) + " (@require_role)"
                    )
                    continue
                if callee not in parent:
                    parent[callee] = key
                    queue.append(callee)
    return sorted(set(out)), len(entries), len(reached_total)


def _sources() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted((BACKEND / "apps").rglob("*.py")):
        parts = path.relative_to(BACKEND).parts
        if "migrations" in parts or "tests" in parts or "__pycache__" in parts:
            continue
        name = ".".join(parts)[: -len(".py")]
        if name.endswith(".__init__"):
            name = name[: -len(".__init__")]
        out[name] = path.read_text(encoding="utf-8")
    return out


# ── self-test ────────────────────────────────────────────────────────────────
_GUARDED = '''
from core.permissions import require_role

@require_role("system_admin")
def guarded(actor):
    return 1

def create(actor):
    return guarded(actor)

def create_safely(actor):
    return guarded.__wrapped__(actor)
'''
_JOB_RED = '''
from apps.x import services
from core import jobs as core_jobs

def run_job(record):
    return services.create(None)

def register():
    core_jobs.set_job_handler("k", run_job)
'''
_JOB_GREEN = _JOB_RED.replace("services.create(None)", "services.create_safely(None)")
_JOB_SEAM = '''
from core import jobs as core_jobs

def run_job(record):
    fn = resolve("x", "create")
    return fn(None)

def register():
    core_jobs.set_job_handler("k", run_job)
'''


def selftest() -> bool:
    red, _, _ = findings(build({"apps.x.services": _GUARDED, "apps.x.jobs": _JOB_RED}))
    green, _, _ = findings(build({"apps.x.services": _GUARDED, "apps.x.jobs": _JOB_GREEN}))
    seam, _, _ = findings(build({"apps.x.services": _GUARDED, "apps.x.jobs": _JOB_SEAM}))
    return (
        any("apps.x.services.guarded (@require_role)" in one for one in red)
        and not green
        and any("apps.x.services.guarded" in one for one in seam)
    )


def _baseline() -> set[str]:
    if not BASELINE.exists():
        return set()
    return {
        line.strip()
        for line in BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def run() -> tuple[str, str]:
    if not BACKEND.is_dir():
        return "SKIP", "06-backend is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a job that reaches a "
            "role guard from one that calls the guarded body through __wrapped__ (DEF-182)"
        )
    paths, entries, reached = findings(build(_sources()))
    known = _baseline()
    new = [p for p in paths if p not in known]
    stale = sorted(known - set(paths))
    if new:
        return "FAIL", (
            f"a background job reaches a role-guarded function — its actor has no role, "
            f"so this can only refuse: {new[0]}" + (f" (+{len(new) - 1} more)" if len(new) > 1 else "")
        )
    if stale:
        return "FAIL", (
            f"g140_job_role_baseline.txt names a path that no longer exists — remove it so the "
            f"list only shrinks: {stale[0]}"
        )
    return "PASS", (
        f"{entries} job bodies walked, {reached} functions reached; no ordinary call reaches "
        f"@require_role ({len(known)} known finding(s) in the baseline, each its own defect); "
        "blind spot: calls through variables, dicts and getattr are not followed"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    if "--list" in sys.argv:
        for path in findings(build(_sources()))[0]:
            print(path)
    return 0 if status in {"PASS", "SKIP"} else 1


if __name__ == "__main__":
    sys.exit(main())
