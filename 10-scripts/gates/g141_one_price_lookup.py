#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-156-BRC10 (PO 2026-10-01 — the GO for the charge-code build):
#          *"19 read places must return exactly one price row … guaranteed by
#          three locks — a database rule refusing overlapping live rows, ONE
#          shared lookup price on date (code, size, class, date) that all 19
#          call, and a repo gate failing any direct query of the price table"*.
#          This is the third lock.
# Rules:   BR-RAT-1050 (one lookup) · BR-RAT-1048 (`charges.amount` retired)
# Tests:   selftest() below runs as part 0 of every run
# ───────────────────────────────────────────────────────
"""G141 — a charge code's price is read and written in ONE place.

WHAT IT FAILS
-------------
Outside `06-backend/apps/rating/charge_prices.py` (the lookup and its writer),
`06-backend/apps/rating/models.py` (where the model is declared) and every
`migrations/` directory, any of:

  1. `<anything>.ChargeCodeAmount.objects` — a direct query of the price table;
  2. `apps.get_model("rating", "ChargeCodeAmount")` — the same, by name;
  3. `<charge>.amounts.<manager method>(…)` — the same, through `Charge`'s
     related manager (`related_name="amounts"`). `resolution.ChargeCode.amounts`
     is a plain dict and is never followed by a manager method, so it does not
     match;
  4. `legacy_amount` — the retired `charges.amount` column under its Python
     name; nothing but the move and the lookup may read it;
  5. a SQL string reading or writing the table (`FROM`/`JOIN`/`UPDATE`/`INTO
     charge_code_amounts`) — raw SQL is a query too. Prose that merely names
     the table is not SQL and does not match.

Tests are not scanned: a test may build its own world.

⚠ **WHAT IT CANNOT SEE, WITH A NUMBER BESIDE IT (law 7, fifth shape).** A read
of `charge.amount` is not static — it is refused at RUN time instead
(`models.Charge.amount` raises `RetiredChargeAmount`), and `.values("amount")`
on a `Charge` queryset raises `FieldError` because the field is now
`legacy_amount`. A query built through `getattr` or a variable model is
invisible here. The gate prints how many files it read and how many it skipped
as allowed, every run, so a sudden drop reads as a blind spot, not as a pass.

PROVEN RED FIRST (law 7), THROUGH THE REGISTRY ENTRY THE SUITE CALLS
--------------------------------------------------------------------
On the tip before CR-156-BRC10 (`98b74e815`, its `06-backend/apps` extracted
with `git archive` and named by `SBH_G141_APPS`), `run()` reached through
`run_gates.GATES` answered FAIL with the eight direct queries the PO was shown
(selectors ×4, resolution_catalogue ×2, services ×2) plus the delete in
`services._write_size_amounts` — see the CR file §6 for the printed output.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
APPS = Path(os.environ.get("SBH_G141_APPS") or (REPO / "06-backend" / "apps"))

ALLOWED = {
    ("rating", "charge_prices.py"),
    ("rating", "models.py"),
}
MANAGER_METHODS = {
    "all",
    "filter",
    "exclude",
    "get",
    "create",
    "update",
    "delete",
    "exists",
    "count",
    "order_by",
    "values",
    "values_list",
    "first",
    "last",
    "bulk_create",
    "get_or_create",
    "update_or_create",
    "aggregate",
    "annotate",
    "select_for_update",
}
SQL = re.compile(r"\b(FROM|JOIN|UPDATE|INTO)\s+charge_code_amounts\b", re.I)


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def findings_in(source: str, label: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"{label}: cannot parse ({exc.msg}) — a file the gate cannot read is not a pass"]
    docstrings = _docstring_nodes(tree)
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr == "objects" and isinstance(node.value, (ast.Attribute, ast.Name)):
                owner = node.value.attr if isinstance(node.value, ast.Attribute) else node.value.id
                if owner == "ChargeCodeAmount":
                    out.append(f"{label}:{node.lineno}: ChargeCodeAmount.objects")
            if node.attr == "legacy_amount":
                out.append(f"{label}:{node.lineno}: legacy_amount (the retired charges.amount)")
            if (
                node.attr in MANAGER_METHODS
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "amounts"
            ):
                out.append(f"{label}:{node.lineno}: .amounts.{node.attr}() (Charge's price rows)")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "get_model":
                names = [a.value for a in node.args if isinstance(a, ast.Constant)]
                if "ChargeCodeAmount" in names:
                    out.append(f"{label}:{node.lineno}: get_model('rating', 'ChargeCodeAmount')")
        elif isinstance(node, ast.keyword) and node.arg == "legacy_amount":
            out.append(f"{label}: legacy_amount= (writes the retired charges.amount)")
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and SQL.search(node.value)
        ):
            out.append(f"{label}:{node.lineno}: raw SQL on charge_code_amounts")
    return out


def check(apps: Path = APPS) -> tuple[list[str], dict[str, int]]:
    findings: list[str] = []
    counts = {"read": 0, "allowed": 0, "tests_or_migrations": 0}
    for path in sorted(apps.rglob("*.py")):
        rel = path.relative_to(apps)
        parts = rel.parts
        if "migrations" in parts or "tests" in parts or parts[-1].startswith("test"):
            counts["tests_or_migrations"] += 1
            continue
        if len(parts) == 2 and (parts[0], parts[1]) in ALLOWED:
            counts["allowed"] += 1
            continue
        counts["read"] += 1
        findings.extend(findings_in(path.read_text(encoding="utf-8"), f"apps/{rel}"))
    return findings, counts


def selftest() -> list[str]:
    """Part 0 of every run: each shape the gate claims to catch, caught."""
    cases = {
        "direct": "x = models.ChargeCodeAmount.objects.filter(charge=c)\n",
        "by name": "M = apps.get_model('rating', 'ChargeCodeAmount')\n",
        "related": "rows = charge.amounts.all()\n",
        "retired column": "a = charge.legacy_amount\n",
        "retired write": "Charge.objects.create(legacy_amount=1)\n",
        "raw sql": "cursor.execute('SELECT amount FROM charge_code_amounts')\n",
    }
    prose = "x = ('a dataset over tariff_versions x {rate_tiers, charge_code_amounts}, from rating')\n"
    missed = [name for name, src in cases.items() if not findings_in(src, name)]
    clean = "if code.amounts and size in code.amounts:\n    x = code.amounts[size]\n"
    if findings_in(clean, "clean"):
        missed.append("a plain dict named `amounts` was flagged (false positive)")
    if findings_in(prose, "prose"):
        missed.append("prose naming the table was read as SQL (false positive)")
    return missed


def run() -> tuple[str, str]:
    """Runner contract: ('PASS'|'FAIL'|'SKIP', detail)."""
    missed = selftest()
    if missed:
        return "FAIL", f"G141's own detector is blind to: {', '.join(missed)}"
    if not APPS.is_dir():
        return "FAIL", f"no apps directory at {APPS} — a gate that read nothing is not a pass"
    findings, counts = check()
    seen = (
        f"read {counts['read']} file(s); skipped {counts['allowed']} allowed "
        f"(charge_prices.py, rating/models.py) and {counts['tests_or_migrations']} "
        "test/migration file(s); `charge.amount` reads are refused at run time, not here"
    )
    if findings:
        return "FAIL", f"{len(findings)} price read(s) outside the one lookup: {findings[0]} — {seen}"
    return "PASS", f"every charge-code price goes through apps/rating/charge_prices.py — {seen}"


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    if status == "FAIL" and "--list" in sys.argv:
        for line in check()[0]:
            print("  " + line)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
