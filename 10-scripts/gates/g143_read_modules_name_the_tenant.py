#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-RAT-9791 — production plan edit (ottumwa-water-works, 2.526.0)
#           listed BASE-SOL x20 and AFTER-HRS x13: `rating/plan_reads.py` read
#           `charges` with no tenant filter in ~28 chains and relied on RLS
#           alone, and in production RLS was not holding.
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id`; no cross-tenant queryset) · hard-won law 14 (the
#           suite runs on SQLite, which has no RLS, so a leak passes every
#           test) · law 7 (proved RED first through run_gates; fifth shape:
#           print what was skipped beside what was checked)
# Sibling:  G96 (`g96_portal_reads_name_the_tenant.py`) — the same question for
#           the customer portal's reads of other modules' tables.
# Tests:    selftest() below · ratchet `g143_tenantless_reads_baseline.txt`
# ───────────────────────────────────────────────────────
"""G143 — a READ MODULE names the tenant in every queryset over a tenant table.

WHY
---
`plan_reads.py` was written as a read module that trusted row-level security
to scope every query. On a production database where RLS was not in force for
the app's connection, the Edit plan screen of one utility listed twenty other
utilities' `BASE-SOL` codes as "Several base codes" and the Charges step listed
`AFTER-HRS` thirteen times. `selectors.py` beside it filters `tenant_id`
explicitly ~137 times; the read module beside it did not, and nothing asked.

RLS stays the guarantee. This gate is the second strand: a read names the
tenant IN THE QUERY, so one bypassing role, one table without its policy, or
one `.using()` does not turn a screen into a cross-tenant listing.

WHAT IT READS
-------------
Every READ MODULE under `06-backend/apps/`: files named `*_reads.py`,
`*_read.py` and `selectors.py` (migrations, tests, management excluded). It
walks each queryset CHAIN with `ast` (the chain, not the call — G96's lesson)
whose ROOT is `<Model>.objects` or `<Model>.all_versions`, and asks: does any
link name a `tenant…` keyword?

A model is tenant-scoped when its class body assigns a `tenant…` attribute,
read from EVERY non-test `.py` under apps/ (not only `models.py` —
`rating/discounts.py` holds five tenant tables, and a scan of `models.py` alone
reports zero over them: law 7, fifth shape).

WHAT IT SKIPS, AND SAYS SO
--------------------------
* chains over a model with no tenant column (nothing to add) — counted;
* chains rooted anywhere else — a related manager (`plan.services.filter`) is
  scoped by its already-scoped parent; a variable holding a queryset cannot be
  typed by an AST — counted as "not rooted at a manager";
* modules not named as read modules (`services.py`, `plan_writes.py`, jobs) —
  counted as files out of scope.
All three numbers are printed on every PASS.

THE RATCHET
-----------
`g143_tenantless_reads_baseline.txt` holds the chains OUTSIDE rating that were
already tenant-less when this landed (`path:line  Model`). It may only SHRINK:
a new chain fails; a fixed chain left on the list fails as stale. **No rating
row may sit on it** — rating was swept in the same commit as the gate.

PROVED RED FIRST (law 7) through `run_gates`' registry entry on the
pre-fix `plan_reads.py` (28 chains), then green after the sweep.

Python 3.12 stdlib only.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
APPS = REPO / "06-backend" / "apps"
RATCHET = Path(__file__).resolve().parent / "g143_tenantless_reads_baseline.txt"

MANAGERS = frozenset({"objects", "all_versions"})
SKIP_DIRS = frozenset({"migrations", "management", "__pycache__", "tests"})
#: Rating was swept with this gate; it may never be pardoned.
NO_PARDON_PREFIX = "apps/rating/"


def is_read_module(path: Path) -> bool:
    name = path.name
    return name == "selectors.py" or name.endswith("_reads.py") or name.endswith("_read.py")


def tenant_scoped_models(apps: Path) -> set[str]:
    scoped: set[str] = set()
    for path in sorted(apps.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts) or path.name.startswith("test"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for stmt in node.body:
                targets = (
                    stmt.targets if isinstance(stmt, ast.Assign)
                    else [stmt.target] if isinstance(stmt, ast.AnnAssign)
                    else []
                )
                if any(isinstance(t, ast.Name) and t.id in {"tenant", "tenant_id"} for t in targets):
                    scoped.add(node.name)
                    break
    return scoped


def _chain(node: ast.AST) -> tuple[list[ast.Call], ast.AST]:
    """Calls of one chain, outermost first, and the expression they hang off."""
    out: list[ast.Call] = []
    while isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        out.append(node)
        node = node.func.value
    return out, node


def _model_of(root: ast.AST) -> str | None:
    if isinstance(root, ast.Attribute) and root.attr in MANAGERS:
        value = root.value
        if isinstance(value, ast.Attribute):
            return value.attr
        if isinstance(value, ast.Name):
            return value.id
    return None


def findings(source: str, *, where: str, scoped: set[str]) -> tuple[list[str], dict[str, int]]:
    tally = {"checked": 0, "unscoped_model": 0, "not_rooted": 0}
    out: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:  # pragma: no cover
        return [f"{where}: will not parse ({exc.msg})"], tally
    seen: set[int] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if id(node) in seen:
            continue
        calls, root = _chain(node)
        for call in calls:
            seen.add(id(call))
        model = _model_of(root)
        if model is None:
            tally["not_rooted"] += 1
            continue
        if model not in scoped:
            tally["unscoped_model"] += 1
            continue
        tally["checked"] += 1
        #: `Model.objects.none()` returns no row of any tenant — nothing to name.
        if calls[-1].func.attr == "none":
            continue
        named: set[str] = set()
        for call in calls:
            named |= {kw.arg or "" for kw in call.keywords}
        if any(name.startswith("tenant") for name in named):
            continue
        out.append(f"{where}:{calls[-1].lineno}  {model}")
    return out, tally


def _key(finding: str) -> str:
    return finding.split("  ")[0].strip()


def read_ratchet(text: str) -> set[str]:
    rows: set[str] = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            rows.add(line.split()[0])
    return rows


def check(files: dict[str, str], allowed: set[str], scoped: set[str]):
    found: list[str] = []
    tally = {"checked": 0, "unscoped_model": 0, "not_rooted": 0}
    for where, source in sorted(files.items()):
        rows, one = findings(source, where=where, scoped=scoped)
        found.extend(rows)
        for key in tally:
            tally[key] += one[key]
    keys = {_key(one) for one in found}
    new = [one for one in found if _key(one) not in allowed]
    stale = sorted(allowed - keys)
    pardoned_rating = sorted(row for row in allowed if row.startswith(NO_PARDON_PREFIX))
    return new, stale, pardoned_rating, tally


SCOPED = {"Charge", "Discount", "PlanService"}
CLEAN = "x = models.Charge.objects.filter(tenant_id=t, is_base=True).order_by('code')\n"
RED = "x = models.Charge.objects.filter(is_base=True, deleted_at__isnull=True)\n"
ALL = "for d in discount_models.Discount.objects.all().order_by('code'):\n    pass\n"
#: G96's first-draft trap: the tenant is named on an inner link only.
CHAINED = "x = models.PlanService.objects.filter(tenant_id=t).exclude(a=1).values_list('id')\n"
UNSCOPED = "x = models.Service.objects.filter(code='water')\n"
RELATED = "x = plan.services.filter(active=True)\n"
WRAPPED = "x = _window(models.Charge.objects.filter(tenant_id=t)).annotate(a=F('b'))\n"
VERSIONS = "x = models.PlanService.all_versions.filter(rate_plan=p)\n"
NONE = "x = models.Charge.objects.none()\n"


def selftest() -> bool:
    def run1(src: str, allowed: set[str] | None = None):
        return check({"apps/x/plan_reads.py": src}, allowed or set(), SCOPED)

    red, *_ = run1(RED)
    all_, *_ = run1(ALL)
    clean, *_ = run1(CLEAN)
    chained, *_ = run1(CHAINED)
    unscoped, _, _, t_un = run1(UNSCOPED)
    related, _, _, t_rel = run1(RELATED)
    wrapped, *_ = run1(WRAPPED)
    versions, *_ = run1(VERSIONS)
    none, *_ = run1(NONE)
    pardoned, *_ = run1(RED, {"apps/x/plan_reads.py:1"})
    _, stale, *_ = run1(CLEAN, {"apps/x/plan_reads.py:1"})
    _, _, no_pardon, _ = check({}, {"apps/rating/plan_reads.py:1"}, SCOPED)
    return (
        len(red) == 1
        and len(all_) == 1
        and not clean
        and not chained
        and not unscoped and t_un["unscoped_model"] == 1
        and not related and t_rel["not_rooted"] == 1
        and not wrapped
        and len(versions) == 1
        and not none
        and not pardoned
        and stale == ["apps/x/plan_reads.py:1"]
        and no_pardon == ["apps/rating/plan_reads.py:1"]
    )


def run() -> tuple[str, str]:
    if not APPS.is_dir():
        return "SKIP", "06-backend/apps is not present"
    if not selftest():
        return "FAIL", "the gate's own self-test does not hold, so its verdict is worthless"
    scoped = tenant_scoped_models(APPS)
    if not scoped:
        return "FAIL", "no tenant-scoped model could be read from apps/"
    files: dict[str, str] = {}
    out_of_scope = 0
    for path in sorted(APPS.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts) or path.name.startswith("test"):
            continue
        if not is_read_module(path):
            out_of_scope += 1
            continue
        files[str(path.relative_to(REPO / "06-backend"))] = path.read_text(encoding="utf-8")
    allowed = read_ratchet(RATCHET.read_text(encoding="utf-8")) if RATCHET.is_file() else set()
    new, stale, pardoned_rating, tally = check(files, allowed, scoped)
    if pardoned_rating:
        return "FAIL", (
            f"{len(pardoned_rating)} rating row(s) sit on the ratchet, which rating may never use "
            f"(DEF-RAT-9791): {', '.join(pardoned_rating[:3])}"
        )
    if new:
        return "FAIL", (
            f"{new[0]} is read without naming the tenant — hard rule 1; RLS alone let "
            f"DEF-RAT-9791 list other utilities' codes"
            + (f" (+{len(new) - 1} more: {', '.join(_key(n) for n in new[1:6])})" if len(new) > 1 else "")
        )
    if stale:
        return "FAIL", (
            f"{len(stale)} ratchet row(s) now name the tenant and must leave "
            f"g143_tenantless_reads_baseline.txt — it may only shrink: {', '.join(stale[:3])}"
        )
    return "PASS", (
        f"{len(files)} read module(s) read, {tally['checked']} chain(s) over {len(scoped)} tenant "
        f"model(s) checked, every one naming the tenant except {len(allowed)} ratcheted row(s) "
        f"outside rating; SKIPPED: {tally['unscoped_model']} chain(s) over a model with no tenant "
        f"column, {tally['not_rooted']} call chain(s) not rooted at a model manager (related "
        f"managers, variables), and {out_of_scope} non-read module(s) not inspected"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 0 if status in {"PASS", "SKIP"} else 1


if __name__ == "__main__":
    sys.exit(main())
