#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-013 (EP-CWP-04) — the applicant's draft is written by
#           `apps/portal/applications.py`, which needed a write allowance that
#           G81 does not otherwise bound.
# Rules:    BR-CWP-001 (the portal may create rows of exactly FOUR kinds) ·
#           BR-CWP-003 (the boundary is declared AS DATA so a gate can read it)
#           · CR-068 §13, verbatim: *"It erodes one reasonable-looking commit
#           at a time. Nobody ever decides to allow a fifth; a lane just needs
#           one more field."* · CLAUDE.md hard-won law 7 (proven RED first —
#           the failures are quoted below)
# Tests:    selftest() below · 06-backend/apps/portal/write_points.py (the data)
# Impacts:  06-backend/apps/portal/** — every file with a write allowance
# ───────────────────────────────────────────────────────
"""G84 — a portal module with a write allowance writes ONLY the models it names.

WHY THIS GATE EXISTS, AND IT IS A HOLE THIS WAVE OPENED
--------------------------------------------------------
`G81` is the portal's write boundary: it reads `write_points.py`, checks the
four kinds are the four, and refuses an ORM write in any file except
`services.py` and the ones named in `STAFF_WRITE_MODULES`. That last clause is
**all-or-nothing**: a file listed there may write ANY model at all.

Wave A had two entries and could live with that. Wave C added a third —
`applications.py`, for the applicant's unsent draft — and at three the
all-or-nothing shape is exactly the erosion `CR-068` §13 describes: nobody
decides to let the portal write an invoice, but a file that may already write
*something* is one plausible line away from writing anything.

So the allowance became DATA as well: `MODULE_WRITE_TABLES` maps each file to
the model class names it may write, and this gate refuses every other one. The
prose entry says WHY a file may write; this says WHAT.

WHAT IT READS, AND WHAT IT REFUSES
----------------------------------
`apps/portal/write_points.py` is parsed with `ast` (never imported — the gate
suite is stdlib-only) for `MODULE_WRITE_TABLES` and `STAFF_WRITE_MODULES`.
Then, over every allowed file:

  1. **Every declared writer is listed.** A file in `STAFF_WRITE_MODULES` with
     no `MODULE_WRITE_TABLES` row is an allowance nobody bounded, and it fails
     — an unlisted file would otherwise read as *"checked"* when it is not,
     which `DEF-182` says is worse than no check.
  2. **Every ORM write in it names a model the row allows.** `X.objects.create`
     / `update` / `delete` / `bulk_create` / `bulk_update` / `get_or_create` /
     `update_or_create`, and `Model(...)` construction, are read for their
     receiver: `models.PortalConsent.objects.create(...)` is `PortalConsent`.
  3. **A row may not name a model this module does not define.** Naming
     `Invoice` here would be a declaration with nothing behind it, which is the
     shape hard-won law 1 warns about.

⚠ **WHAT IT DELIBERATELY DOES NOT CATCH.** A write reached through a variable
(`table.objects.create(...)`) or through another module's service is invisible
to it — the second is `G81` clause 4's job, and the first is the reason this
gate is a *floor* and not a proof. It reads SOURCE, like every other gate here.

PROVEN RED FIRST (law 7, 2026-09-04)
------------------------------------
With `models.PortalSettings.objects.create(tenant_id=1)` added to
`applications.py`, whose row names only `PortalApplicationDraft`:
    FAIL: 06-backend/apps/portal/applications.py:… writes PortalSettings, which
    its write_points.py allowance does not name (BR-CWP-003)
and with the `applications.py` row deleted from `MODULE_WRITE_TABLES` while the
file stayed in `STAFF_WRITE_MODULES`:
    FAIL: applications.py may write (STAFF_WRITE_MODULES) and MODULE_WRITE_TABLES
    does not say what — an allowance nobody bounded (CR-068 §13)
Both reverted; `selftest()` replays both on in-memory sources and `run()`
refuses to report anything until it has.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
PORTAL = REPO / "06-backend" / "apps" / "portal"
WRITE_POINTS = PORTAL / "write_points.py"
MODELS = PORTAL / "models.py"

MANAGER_WRITES = frozenset(
    {"create", "update", "delete", "bulk_create", "bulk_update", "get_or_create", "update_or_create"}
)


def _dict_of_names(node: ast.AST) -> dict[str, tuple[str, ...]]:
    out: dict[str, tuple[str, ...]] = {}
    if not isinstance(node, ast.Dict):
        return out
    for key, value in zip(node.keys, node.values):
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            continue
        names: list[str] = []
        if isinstance(value, (ast.Tuple, ast.List)):
            for item in value.elts:
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    names.append(item.value)
        out[key.value] = tuple(names)
    return out


def read_declarations(source: str) -> tuple[dict[str, tuple[str, ...]], set[str], list[str]]:
    """(MODULE_WRITE_TABLES, STAFF_WRITE_MODULES keys, problems)."""
    tables: dict[str, tuple[str, ...]] = {}
    staff: set[str] = set()
    problems: list[str] = []
    for node in ast.parse(source).body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        if "MODULE_WRITE_TABLES" in names:
            tables = _dict_of_names(node.value)
            if not tables:
                problems.append("MODULE_WRITE_TABLES is missing or is not a dict of name tuples")
        if "STAFF_WRITE_MODULES" in names and isinstance(node.value, ast.Dict):
            staff = {
                key.value
                for key in node.value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
    return tables, staff, problems


def _receiver(node: ast.AST) -> str | None:
    """`models.PortalConsent.objects.create` → `PortalConsent`."""
    while isinstance(node, ast.Attribute):
        if node.attr == "objects":
            owner = node.value
            if isinstance(owner, ast.Attribute):
                return owner.attr
            if isinstance(owner, ast.Name):
                return owner.id
            return None
        node = node.value
    return None


def models_written(source: str) -> list[tuple[int, str]]:
    """Every `<Model>.objects.<write>(…)` in `source`, with its line."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in MANAGER_WRITES:
            continue
        owner = node.func.value
        if not (isinstance(owner, ast.Attribute) and owner.attr == "objects"):
            continue
        name = _receiver(node.func)
        found.append((node.lineno, name or "<unreadable receiver>"))
    return found


def declared_models(models_source: str) -> set[str]:
    return {
        node.name
        for node in ast.parse(models_source).body
        if isinstance(node, ast.ClassDef)
    }


def check(
    write_points_src: str, models_src: str, files: dict[str, str]
) -> list[str]:
    tables, staff, problems = read_declarations(write_points_src)
    known = declared_models(models_src)
    for name in sorted(staff - set(tables)):
        problems.append(
            f"{name} may write (STAFF_WRITE_MODULES) and MODULE_WRITE_TABLES does not say "
            "what — an allowance nobody bounded (CR-068 §13)"
        )
    for name, allowed in sorted(tables.items()):
        for model in allowed:
            if known and model not in known:
                problems.append(
                    f"MODULE_WRITE_TABLES lets {name} write {model}, which apps/portal/models.py "
                    "does not define — a declaration with nothing behind it (law 1)"
                )
    for rel, src in sorted(files.items()):
        base = rel.rsplit("/", 1)[-1]
        if base not in tables:
            continue
        allowed = set(tables[base])
        for lineno, model in models_written(src):
            if model not in allowed:
                problems.append(
                    f"{rel}:{lineno} writes {model}, which its write_points.py allowance "
                    "does not name (BR-CWP-003)"
                )
    return problems


CLEAN_POINTS = '''
STAFF_WRITE_MODULES = {"applications.py": "the draft", "settings_service.py": "the settings row"}
MODULE_WRITE_TABLES = {
    "services.py": ("PortalConsent",),
    "settings_service.py": ("PortalSettings",),
    "applications.py": ("PortalApplicationDraft",),
}
'''
UNBOUNDED_POINTS = CLEAN_POINTS.replace('    "applications.py": ("PortalApplicationDraft",),\n', "")
GHOST_POINTS = CLEAN_POINTS.replace('("PortalApplicationDraft",)', '("Invoice",)')
MODELS_SRC = "class PortalSettings:\n    pass\nclass PortalApplicationDraft:\n    pass\nclass PortalConsent:\n    pass\n"
CLEAN_APP = "def save(t):\n    return models.PortalApplicationDraft.objects.create(tenant_id=t)\n"
RED_APP = CLEAN_APP + "def sneak(t):\n    return models.PortalSettings.objects.create(tenant_id=t)\n"


def selftest() -> bool:
    clean = check(CLEAN_POINTS, MODELS_SRC, {"applications.py": CLEAN_APP})
    if clean:
        return False
    foreign = check(CLEAN_POINTS, MODELS_SRC, {"applications.py": RED_APP})
    unbounded = check(UNBOUNDED_POINTS, MODELS_SRC, {"applications.py": CLEAN_APP})
    ghost = check(GHOST_POINTS, MODELS_SRC, {"applications.py": CLEAN_APP})
    return (
        any("writes PortalSettings" in p for p in foreign)
        and any("allowance nobody bounded" in p for p in unbounded)
        and any("nothing behind it" in p for p in ghost)
    )


def run() -> tuple[str, str]:
    if not PORTAL.is_dir():
        return "SKIP", f"{PORTAL.relative_to(REPO)} is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell an allowed write from a "
            "foreign one, so its verdict is worthless (DEF-182)"
        )
    if not WRITE_POINTS.is_file() or not MODELS.is_file():
        return "FAIL", "apps/portal/write_points.py or models.py is missing"
    files = {
        str(path.relative_to(REPO)): path.read_text(encoding="utf-8")
        for path in sorted(PORTAL.glob("*.py"))
    }
    problems = check(
        WRITE_POINTS.read_text(encoding="utf-8"), MODELS.read_text(encoding="utf-8"), files
    )
    if problems:
        return "FAIL", " | ".join(problems[:6]) + (
            f" (+{len(problems) - 6} more)" if len(problems) > 6 else ""
        )
    tables, _staff, _ = read_declarations(WRITE_POINTS.read_text(encoding="utf-8"))
    bounded = sum(1 for names in tables.values() if names)
    return "PASS", (
        f"{len(tables)} portal file(s) carry a declared write allowance, {bounded} of them naming "
        f"model(s); every ORM write in them is one the allowance names; self-test: a foreign "
        "model, an unbounded allowance and a model that does not exist all bite"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
