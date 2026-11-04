#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-039 (EP-WRK-05) — the five flows raise their jobs.
#           `CR-070` §12, `10-execution-plan.md` wave P task P6.
# Rules:    BR-WRK-055 (*"the move-out does not wait for the visit and the visit
#           does not close the account"*; Customers writes nothing to
#           `work_orders`) · BR-WRK-002 / A7 (the Work boundary, from the
#           Customers side) · CLAUDE.md hard rule 7 (a money act writes audit) ·
#           hard-won law 7 (proved RED first, through `run_gates`' own path)
# Tests:    selftest() below · 06-backend/tests/test_us_wrk_039_from_flows.py
#           (TC-2 and TC-5 are this gate's two clauses as unit cases)
# Impacts:  06-backend/apps/customers/**
# ───────────────────────────────────────────────────────
"""G102 — no flow raises a job silently, and no flow can be blocked by one.

WHY THIS GATE EXISTS
--------------------
Wave P puts a field job inside five Customers flows: an approved service
request being routed, a move-out, a move-in, a transfer, a reconnect. Both
things that can go wrong are invisible to every other check in this repo.

**CLAUSE (a) — A RAISE THAT FAILS MUST NOT FAIL THE FLOW.** `BR-WRK-055` and
judgment 7 of the 2026-09-04 plan: a field module able to block a customer's
move-out is the failure the whole design exists to prevent. The way that breaks
is not dramatic — somebody deletes a `try` while tidying, or adds a sixth caller
and forgets one. Nothing notices: the suite runs on SQLite with Work published
and every template valid, so the failure path is never taken and every test
stays green until a real template is deactivated in production.

**CLAUSE (b) — `apps/customers/**` WRITES NO `work_orders` ROW.** `A7`'s
boundary from the Customers side, the mirror of what `G78` enforces from Work's.
It breaks because reaching for `WorkOrder.objects.create(...)` is three lines
shorter than asking Work to do it, and because the model is importable from
`apps.metering.connections` with nothing in the way.

WHAT IT READS
-------------
Every `.py` under `06-backend/apps/customers`, except `tests.py` and
`migrations/`. Two findings:

  1. **A CALL TO `raise_flow_work_orders` NOT INSIDE A `try`** whose handler
     returns rather than re-raising. The check is on the AST: a call node is
     located, and its enclosing `Try` is required to exist and to have a handler
     that does not `raise`. A handler that re-raises is a `try` that changes
     nothing, which is the shape a tidy-up produces.
  2. **A WRITE TO `work_orders`** — `WorkOrder.objects.create/update/delete/
     bulk_*/get_or_create/update_or_create`, `.save()` on an instance built from
     it, or a string literal carrying `INSERT INTO work_orders`, `UPDATE
     work_orders` or `DELETE FROM work_orders`.

⚠ **THE SEAM FILE IS NOT AN EXEMPTION AND DOES NOT NEED ONE.**
`apps/customers/seams.py` resolves `apps.work.from_flows.raise_for` by name and
calls it; it touches no model, so clause (b) has nothing to say about it. That
is the whole point of the seam — the one lawful door is a function call, not an
ORM write, so the gate can be absolute rather than carrying a list of blessed
files that the next lane appends to.

⚠ **CLAUSE (a) DELIBERATELY DOES NOT READ `apps/work`.** `from_flows.raise_for`
RAISES on failure, on purpose: returning an empty list would look identical to
*nothing was ticked* and a caller cannot tell those apart (`DEF-708`'s shape).
The catch belongs to the caller, because only the caller knows what completing
means for its own flow — so the caller is where this gate looks.

PROVED RED FIRST (law 7), AND THROUGH `run_gates` (DEF-GOV-3733)
----------------------------------------------------------------
On 2026-09-05, before this gate was trusted, each clause was broken in the real
tree and the SUITE was run — `python3 run_gates.py`, not `python3
g102_….py` — because a gate proved through `__main__` alone is no proof of the
path the suite uses. `G85` and `G87` were both announced green on 2026-09-04
while `run_gates` reported `gate crashed: AttributeError: module has no
attribute 'run'`.

  * clause (a): the `try` was removed from `services._raise_flow_work` →
    `FAIL: 06-backend/apps/customers/services.py:NNNN calls
    raise_flow_work_orders outside a try that completes the flow (BR-WRK-055)`
  * clause (b): `WorkOrder.objects.create(tenant_id=…)` was added to
    `close_out.py` → `FAIL: 06-backend/apps/customers/close_out.py:NNN writes
    work_orders — WorkOrder.objects.create (A7 / BR-WRK-002)`

`selftest()` repeats both shapes on synthetic files in a temp directory every
run, so the sabotage bites without touching the repo — the `G53` posture: a
proof that sabotages real content is worthless the day that content is already
broken.
"""

from __future__ import annotations

import ast
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
CUSTOMERS = REPO / "06-backend" / "apps" / "customers"

#: The seam function every flow door must go through, and the one this gate
#: follows. Named once: a second spelling is how a gate stops matching its rule.
SEAM_CALL = "raise_flow_work_orders"

WRITE_VERBS = (
    "create",
    "update",
    "delete",
    "bulk_create",
    "bulk_update",
    "get_or_create",
    "update_or_create",
)
RAW_WRITES = ("INSERT INTO work_orders", "UPDATE work_orders", "DELETE FROM work_orders")
SKIP_NAMES = {"tests.py"}
SKIP_PARTS = {"migrations", "__pycache__"}


def _files(root: Path) -> list[Path]:
    return sorted(
        p
        for p in root.rglob("*.py")
        if p.name not in SKIP_NAMES
        and not any(part in SKIP_PARTS for part in p.relative_to(root).parts)
    )


def _work_order_names(tree: ast.Module) -> set[str]:
    """Every local name bound to metering's `WorkOrder`, however it was imported."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("apps.metering"):
            for alias in node.names:
                if alias.name == "WorkOrder":
                    names.add(alias.asname or alias.name)
    return names


def _attribute_chain(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _handlers_complete(node: ast.Try) -> bool:
    """True when at least one handler swallows rather than re-raising.

    A bare `raise` inside the handler makes the `try` decorative — the flow
    still fails — which is precisely the tidy-up this clause is written for.
    """
    for handler in node.handlers:
        if not any(isinstance(inner, ast.Raise) for inner in ast.walk(handler)):
            return True
    return False


def scan(root: Path) -> list[str]:
    findings: list[str] = []
    for path in _files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - a broken file is another gate's finding
            continue
        rel = path.relative_to(REPO) if path.is_relative_to(REPO) else path

        # ── clause (a) ──────────────────────────────────────────────────────
        guarded: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Try) and _handlers_complete(node):
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Call):
                        guarded.add(id(inner))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = _attribute_chain(node.func) if isinstance(node.func, ast.Attribute) else (
                node.func.id if isinstance(node.func, ast.Name) else ""
            )
            if not called.endswith(SEAM_CALL):
                continue
            if id(node) not in guarded:
                findings.append(
                    f"{rel}:{node.lineno} calls {SEAM_CALL} outside a try that completes "
                    "the flow (BR-WRK-055)"
                )

        # ── clause (b) ──────────────────────────────────────────────────────
        bound = _work_order_names(tree)
        if bound:
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                chain = _attribute_chain(node.func)
                head = chain.split(".")[0]
                if head not in bound:
                    continue
                if node.func.attr in WRITE_VERBS and ".objects" in chain:
                    findings.append(
                        f"{rel}:{node.lineno} writes work_orders — {chain} (A7 / BR-WRK-002)"
                    )
                elif node.func.attr in ("save", "delete") and len(chain.split(".")) == 2:
                    findings.append(
                        f"{rel}:{node.lineno} writes work_orders — {chain} (A7 / BR-WRK-002)"
                    )
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for raw in RAW_WRITES:
                    if raw.lower() in node.value.lower():
                        findings.append(
                            f"{rel}:{node.lineno} raw SQL writes work_orders (A7 / BR-WRK-002)"
                        )
    return findings


CLEAN_DOOR = '''from apps.customers import seams


def move_out(actor, account_id, template_ids):
    try:
        raised = seams.raise_flow_work_orders(
            actor, flow_kind="move_out", flow_id=account_id, template_ids=template_ids
        )
    except Exception as exc:
        return {"work_orders": [], "warnings": [seams.flow_work_not_raised(str(exc))]}
    return {"work_orders": raised["raised"], "warnings": []}
'''

RED_UNGUARDED = '''from apps.customers import seams


def move_out(actor, account_id, template_ids):
    raised = seams.raise_flow_work_orders(
        actor, flow_kind="move_out", flow_id=account_id, template_ids=template_ids
    )
    return {"work_orders": raised["raised"], "warnings": []}
'''

RED_RERAISE = '''from apps.customers import seams


def move_out(actor, account_id, template_ids):
    try:
        return seams.raise_flow_work_orders(
            actor, flow_kind="move_out", flow_id=account_id, template_ids=template_ids
        )
    except Exception:
        raise
'''

RED_ORM_WRITE = '''from apps.metering.connections import WorkOrder


def close(tenant_id):
    WorkOrder.objects.create(tenant_id=tenant_id)
'''

RED_RAW_SQL = '''from django.db import connection


def close(tenant_id):
    with connection.cursor() as cur:
        cur.execute("UPDATE work_orders SET state = 'cancelled'")
'''


def selftest() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "customers"
        root.mkdir(parents=True)
        (root / "services.py").write_text(CLEAN_DOOR, encoding="utf-8")
        if scan(root):
            return False
        # (a) the catch removed
        (root / "services.py").write_text(RED_UNGUARDED, encoding="utf-8")
        red = scan(root)
        if not (len(red) == 1 and "outside a try that completes the flow" in red[0]):
            return False
        # (a) a `try` that re-raises is not a catch
        (root / "services.py").write_text(RED_RERAISE, encoding="utf-8")
        red = scan(root)
        if not (len(red) == 1 and "outside a try that completes the flow" in red[0]):
            return False
        (root / "services.py").write_text(CLEAN_DOOR, encoding="utf-8")
        # (b) an ORM write
        (root / "close_out.py").write_text(RED_ORM_WRITE, encoding="utf-8")
        red = scan(root)
        if not (len(red) == 1 and "WorkOrder.objects.create" in red[0]):
            return False
        (root / "close_out.py").unlink()
        # (b) raw SQL
        (root / "close_out.py").write_text(RED_RAW_SQL, encoding="utf-8")
        red = scan(root)
        if not (len(red) == 1 and "raw SQL writes work_orders" in red[0]):
            return False
        (root / "close_out.py").unlink()
        if scan(root):
            return False
    return True


def run() -> tuple[str, str]:
    if not CUSTOMERS.is_dir():  # pragma: no cover - defensive
        return "SKIP", f"{CUSTOMERS.relative_to(REPO)} is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell an unguarded raise from a "
            "guarded one, so its verdict is worthless (DEF-182)"
        )
    problems = scan(CUSTOMERS)
    if problems:
        return "FAIL", " | ".join(problems[:6]) + (
            f" (+{len(problems) - 6} more)" if len(problems) > 6 else ""
        )
    callers = sum(
        1
        for path in _files(CUSTOMERS)
        if SEAM_CALL in path.read_text(encoding="utf-8") and path.name != "seams.py"
    )
    return "PASS", (
        f"{len(_files(CUSTOMERS))} file(s) under 06-backend/apps/customers write no work_orders "
        f"row, and every one of the {callers} flow file(s) that raises field work does so inside "
        "a try that completes the flow (BR-WRK-055 / A7); self-test: the sabotage bites (the "
        "catch removed, a try that re-raises, an ORM write, raw SQL)"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
