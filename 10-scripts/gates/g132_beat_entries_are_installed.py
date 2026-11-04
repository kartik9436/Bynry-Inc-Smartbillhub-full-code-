#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-136-BRC07 task `P2.11`, the scheduling half (`DEF-PAY-6268`).
# Defects:  DEF-PAY-6268 (a sweep and a command, both correct, and nothing on
#           any clock called either — so the PO ruling of 2026-09-23 §3.1 was
#           unmet in practice for a day) · DEF-RBS-4353 (a plan recorded a job
#           as done while no Python file named it) · DEF-320 (a queue nothing
#           consumes — the same shape one layer down)
# Rules:    CLAUDE.md hard-won law 2 (built is not wired) · law 7 (prove a
#           guard RED first, in the harness that will run it; and say what you
#           did NOT check beside what you did) · BR-TEN-043 (beat owns a
#           duration; the app owns the per-utility decision)
# Tests:    selftest() below · 06-backend/tests/test_cr136_p2_11_schedule.py
# ───────────────────────────────────────────────────────
"""G132 — every beat entry this repo DECLARES is one an `AppConfig.ready()` INSTALLS.

WHY THIS IS NOT `G117`, WHICH WAS ASKED FIRST
----------------------------------------------
`G117` asks the beat question for the `runbooks` QUEUE: routed, consumed by a
dedicated worker, and fed by an entry. It is the right gate for a module with a
queue of its own, and it cannot be pointed at payments' counter watch, because
that watch **has no queue of its own and should not have one** — it rides the
shared queue exactly as `payments.collections_ladder`, `notifications.dispatch`
and `customers.cut_date_watch` do. Pointing `G117` at payments would have
demanded a dedicated worker container this feature does not need and does not
want.

So this is the sibling guard: **`G117`'s third clause alone, asked of every
module instead of one.** It is the clause `G117`'s own docstring calls the one
that would have caught `DEF-RBS-4353`, and it is the clause `DEF-PAY-6268` was.

WHAT IT CHECKS
--------------
A module is a **beat-entry module** when it defines a top-level
`def beat_schedule(...)` and assigns a string `BEAT_ENTRY`. There are six of
them, one per recurring job this product has. For each, three things:

  1. **it publishes `install()`** — the function `ready()` is supposed to call;
  2. **its own app's `apps.py` CALLS `<module>.install()` inside `ready()`** —
     an `ast` call, never a substring, because three of the six name
     `install()` in a comment or a docstring and a text search is satisfied by
     prose;
  3. **no two modules claim the same `BEAT_ENTRY` key.** Every installer does
     `existing.update(schedule)`, so two modules sharing a key means whichever
     `ready()` runs last silently erases the other's schedule — a beat entry
     that is correct, installed, and gone.

WHAT WOULD MAKE THIS CHECK PASS WRONGLY
---------------------------------------
Law 7's second habit, answered in writing.

  * **`install()` named in a comment or a docstring.** That is how
    `notifications/apps.py` and `payments/apps.py` both read, and a substring
    check passes on either with the real call deleted. Checked — the call is
    found by walking the syntax tree, and the selftest deletes the CALL while
    leaving the prose in place, which is the mutation that matters.
  * **A call to `install()` somewhere other than `ready()`** — at module import
    time, say, which runs before the app registry is loaded. Checked: the call
    has to be inside a `ready` method.
  * **A module whose `install()` is a stub.** NOT checked, and it cannot be
    from here — what `install()` does to a real celery app is
    `tests/test_cr136_p2_11_schedule.py`'s question, and that case reads
    `config.celery.app.conf.beat_schedule` rather than any function's return
    value.
  * **THE ONE IT CANNOT SEE, STATED RATHER THAN LEFT TO BE DISCOVERED:** it
    reads SOURCE. It cannot tell whether a beat process is alive, whether the
    broker is reachable, or whether the sweep finds any utility. Those are
    `10-scripts/11-smoke-stack.sh`'s and the deployment's — `09-infra/
    01-deployment-architecture.md` §4.1 records that the deployed host runs
    none of it — and this gate's PASS line says only what it checked.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402

APPS = common.BACKEND_APPS


def _module_declares_beat_entry(tree: ast.Module) -> str | None:
    """The `BEAT_ENTRY` value when this module publishes a beat schedule, else None."""
    has_schedule = any(
        isinstance(node, ast.FunctionDef) and node.name == "beat_schedule" for node in tree.body
    )
    if not has_schedule:
        return None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "BEAT_ENTRY":
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    return node.value.value
    return ""  # declares a schedule and no key — a finding, not an absence


def _publishes_install(tree: ast.Module) -> bool:
    return any(isinstance(node, ast.FunctionDef) and node.name == "install" for node in tree.body)


def _installed_in_ready(apps_tree: ast.Module) -> set[str]:
    """The module names `ready()` calls `install()` on, as an AST fact.

    A substring search would be satisfied by `# … install() never raises …`,
    which is what three of these `apps.py` files actually say.
    """
    found: set[str] = set()
    for node in ast.walk(apps_tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "ready":
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            func = call.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "install"
                and isinstance(func.value, ast.Name)
            ):
                found.add(func.value.id)
    return found


def findings(read: object = None) -> tuple[list[str], dict[str, object]]:
    """Every problem, and what was actually seen.

    `read` is a callable `(Path) -> str` so the selftest can mutate one file's
    text without touching the tree — the shared working tree is six lanes' and
    law 11 forbids moving it.
    """
    reader = read if callable(read) else common.read_text
    problems: list[str] = []
    seen: dict[str, object] = {}

    if not APPS.is_dir():
        return (["06-backend/apps does not exist"], seen)

    declared: dict[str, tuple[str, str]] = {}  # module path -> (app label, entry key)
    for path in sorted(APPS.rglob("*.py")):
        if path.name == "apps.py" or "migrations" in path.parts:
            continue
        try:
            tree = ast.parse(reader(path))
        except SyntaxError:  # pragma: no cover — another gate owns syntax
            continue
        entry = _module_declares_beat_entry(tree)
        if entry is None:
            continue
        rel = common.rel(path)
        app_label = path.relative_to(APPS).parts[0]
        declared[rel] = (app_label, entry)
        if not entry:
            problems.append(
                f"{rel} publishes beat_schedule() and assigns no BEAT_ENTRY string — the "
                "entry has no name, so nothing can say whether it was installed and two "
                "schedules cannot be told apart"
            )
        if not _publishes_install(tree):
            problems.append(
                f"{rel} publishes beat_schedule() and no install() — the schedule is a "
                "correct dict with no way of reaching celery, which is hard-won law 2 "
                "with a clock in it"
            )

    seen["modules"] = {rel: key for rel, (_, key) in sorted(declared.items())}

    # ── 1 · is each one INSTALLED from its own app's ready()? ───────────────
    by_app: dict[str, list[str]] = {}
    for rel, (app_label, _) in declared.items():
        by_app.setdefault(app_label, []).append(rel)
    for app_label, modules in sorted(by_app.items()):
        apps_py = APPS / app_label / "apps.py"
        if not apps_py.is_file():
            problems.append(
                f"apps/{app_label}/ declares a beat entry and has no apps.py — nothing "
                "runs at startup, so the entry is a dict nobody hands to celery"
            )
            continue
        try:
            installed = _installed_in_ready(ast.parse(reader(apps_py)))
        except SyntaxError:  # pragma: no cover
            problems.append(f"apps/{app_label}/apps.py could not be parsed")
            continue
        for rel in sorted(modules):
            name = Path(rel).stem
            if name not in installed:
                problems.append(
                    f"apps/{app_label}/apps.py does not CALL {name}.install() inside "
                    f"ready() — {rel} declares the beat entry "
                    f"{declared[rel][1]!r} and nothing fires it. That is DEF-PAY-6268 "
                    "exactly: the sweep was correct, the command was correct, and the "
                    "supervisor was told only if a person typed something"
                )

    # ── 2 · two modules must not claim one key ─────────────────────────────
    keys: dict[str, list[str]] = {}
    for rel, (_, entry) in declared.items():
        if entry:
            keys.setdefault(entry, []).append(rel)
    for entry, owners in sorted(keys.items()):
        if len(owners) > 1:
            problems.append(
                f"{len(owners)} modules claim the beat entry {entry!r} "
                f"({', '.join(sorted(owners))}) — every installer does "
                "`existing.update(schedule)`, so whichever ready() runs last silently "
                "erases the other's schedule"
            )

    seen["count"] = len(declared)
    seen["keys"] = ", ".join(sorted(keys))
    return problems, seen


def selftest() -> int:
    """Prove the gate can FAIL, on the mutation that matters.

    ⚠ A selftest is not the red proof law 7 asks for — that was run through
    `run_gates.py` against the real tree with the `counter_watch_schedule.
    install()` call deleted, and the failure text is quoted in the decision-log
    row. This is the cheap repeatable half.
    """
    problems, seen = findings()
    if problems:
        print("SELFTEST FAIL — the real tree should pass:", problems)
        return 1
    if not seen["count"]:
        print("SELFTEST FAIL — no beat-entry module was found at all; the gate is blind")
        return 1

    target = APPS / "payments" / "apps.py"
    real = common.read_text(target)
    if "counter_watch_schedule.install()" not in real:
        print("SELFTEST FAIL — the mutation's anchor is gone; re-point the selftest")
        return 1

    def _mutated(path: Path) -> str:
        text = common.read_text(path)
        if path == target:
            # Delete the CALL and leave every comment that names it in place —
            # a substring check passes on this mutation and that is the point.
            return text.replace("\n        counter_watch_schedule.install()\n", "\n")
        return text

    problems, _ = findings(_mutated)
    if not any("counter_watch_schedule.install()" in one for one in problems):
        print("SELFTEST FAIL — an uninstalled beat entry was not caught:", problems)
        return 1

    print(
        f"SELFTEST PASS — the real tree passes with {seen['count']} beat entr(ies); "
        "deleting one ready() call while leaving its comments fails"
    )
    return 0


def run() -> tuple[str, str]:
    """`(status, detail)` for `run_gates.py`.

    ⚠ Both entry points on purpose — `DEF-GOV-3733` is two gates announced green
    through `__main__` while the suite reported `module has no attribute 'run'`.
    """
    problems, seen = findings()
    if problems:
        return "FAIL", f"{len(problems)} problem(s): " + " · ".join(problems)
    return (
        "PASS",
        f"{seen['count']} beat entr(ies) declared and every one INSTALLED from its own "
        f"app's ready(), keys all distinct: {seen['keys']}. It does NOT check that a "
        "beat process is alive, that the broker is reachable, or that a sweep finds a "
        "utility — that is the smoke stack's and the deployment's",
    )


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    status, note = run()
    print(f"G132 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
