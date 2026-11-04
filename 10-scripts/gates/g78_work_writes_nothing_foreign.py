#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-005 (EP-WRK-01) TC-2..TC-4 — the Work module's boundary
#           gate. `CR-070` §12 gate 1: *"no file under apps/work/** names
#           another module's model in a write position"*.
# Rules:    BR-WRK-002 (Work writes no other module's tables; one read-only
#           seam file per module; a direct write to another module's table
#           fails a gate) · B2 §2 / DB-16 (cross-module writes forbidden) ·
#           CLAUDE.md hard rule 5 (only the ledger posting service writes
#           journal lines) · hard-won law 7 (proven RED first — see the
#           docstring and `selftest()`)
# Tests:    selftest() below · 06-backend/tests/test_us_wrk_005_module.py
#           (TC-2 the tree is clean, TC-3/TC-4 a sabotaged copy is named)
# Impacts:  every .py under 06-backend/apps/work
# ───────────────────────────────────────────────────────
"""G78 — nothing under `apps/work/` writes another module's table.

WHY THIS GATE EXISTS
--------------------
The Work module was ruled its own module on 2026-09-03 (*"it will become the
module itself"*) with the boundary rule applied FROM THE FIRST COMMIT: Work
READS assets, connections, accounts, meters, areas and users through one
read-only seam file per module and writes none of them. The blueprint prices
getting this wrong in one line — *"Moving it later is a migration across nine
modules"* — and a boundary that is a sentence in a rules file is broken the
first time a lane reaches for `Asset.objects.filter(...).update(...)` because
it is three lines shorter than asking assets to do it. This gate makes that
line fail the merge instead of shipping.

WHAT IT READS
-------------
Every `.py` under `06-backend/apps/work`, EXCEPT `migrations/` (Django's own
operations name models by string) and `tests.py`. Three findings:

  1. **A FOREIGN MODELS IMPORT OUTSIDE `seams/`** — `from apps.<other>.models
     import X`, `from apps.<other> import models`, `import apps.<other>.models`,
     and `apps.metering.connections` (metering's second models module; the
     six Work tables were declared there until T-43 moved them to
     `apps/work/connection_models.py`, and it still holds the New Connect
     services and binds the model names). Allowed ONLY under `apps/work/seams/`,
     which is the whole point of having seams (US-WRK-005 TC-4).
  2. **AN ORM WRITE ON A FOREIGN MODEL, ANYWHERE** — `<X>.objects.create(…)`,
     `.update(…)`, `.delete(…)`, `.bulk_create(…)`, `.bulk_update(…)`,
     `.get_or_create(…)`, `.update_or_create(…)`, and `.save()` / `.delete()`
     on an instance built from a foreign model, where `<X>` is a name bound by
     an import of the kind in (1). Seams included: a seam READS. The one thing
     that causes a write in this module — `metering_seam.raise_work_order` —
     calls metering's own SERVICE by name (`w6.create_work_order`), which is
     not an ORM write and is exactly the door BR-WRK-002 sanctions.
  3. **RAW SQL THAT WRITES** — a string literal carrying `INSERT INTO`,
     `UPDATE … SET`, `DELETE FROM` or `TRUNCATE`. Work owns no table in phase
     0, so any such literal is foreign; when `apps/work/models.py` gains
     models, a literal naming one of THEIR `db_table`s is exempt (the same
     ownership read that exempts the ORM form below).

A model declared in `apps/work/models.py` (a `ClassDef` whose bases mention
`Model`) is Work's own and may be written anywhere in the package; the gate
reads that file rather than carrying a list, so wave C's first table exempts
itself. `dict.update(...)` and `list.append` are never findings: only a chain
rooted in a foreign-model binding, or one that passes through `.objects`, is
read as an ORM write — the first draft flagged `payload.update(...)` and a
gate with a false positive is a gate that gets switched off (DEF-323).

Comments and docstrings are read through `ast`, not grep, so a sentence
explaining the rule cannot trip it (the DEF-741 shape).

PROVED RED FIRST (law 7)
------------------------
On 2026-09-03, before this gate was trusted, one line was added to
`apps/work/services.py` — `Asset.objects.filter(pk=order_id).update(status=
"retired")` with its import — and the gate reported, verbatim:

    FAIL: 06-backend/apps/work/services.py:40 imports apps.assets.models
    outside seams/ (BR-WRK-002) | 06-backend/apps/work/services.py:45 writes
    a foreign model — Asset.objects.update (BR-WRK-002)

then the line was removed and the gate passed. `selftest()` repeats that
shape on synthetic files in a temp directory every run, plus a journal-line
write (hard rule 5) and a raw `UPDATE`, so the sabotage bites without
touching the repo.
"""

from __future__ import annotations

import ast
import re
import sys
import tempfile
from pathlib import Path

import common

REPO = common.REPO_ROOT
WORK_APP = common.BACKEND_APPS / "work"
SKIP_PARTS = ("migrations", "__pycache__")
SKIP_NAMES = ("tests.py",)

#: ORM verbs that WRITE. `get`, `filter`, `exists`, `count`, `first` are reads.
WRITE_ATTRS = frozenset(
    {"create", "update", "delete", "bulk_create", "bulk_update", "get_or_create", "update_or_create", "save"}
)
#: Modules under `apps.<other>` that hold models. `connections` is metering's
#: second models module (the six Work tables were declared there until T-43,
#: 2026-10-21, and it still binds their names beside the services that write
#: them — 03-field-map §4); the list is deliberately short and named.
MODELS_MODULES = ("models", "connections")
RAW_WRITE_RE = re.compile(r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|TRUNCATE)\b", re.IGNORECASE)


def _own_model_names(root: Path) -> set[str]:
    """Every model class DECLARED anywhere under `<root>` — the app's own tables.

    ⚠ **THIS READ `<root>/models.py` AND NOTHING ELSE UNTIL 2026-09-05, AND A
    SECOND MODELS MODULE MADE THE GATE CALL WORK'S OWN TABLES FOREIGN
    (`DEF-WRK-4032`).** `apps/work/evidence_models.py` declares
    `WorkOrderAttachment` and `WorkOrderSignature`; `models.py` only
    RE-EXPORTS them, so an `ast` walk for `ClassDef` found neither and
    `evidence.py` was reported three times for writing its own tables.

    **A false positive is the failure mode this gate can least afford** — its
    own docstring says so about `payload.update(...)` (`DEF-323`) — because a
    boundary gate that cries wolf is a boundary gate somebody switches off, and
    this one then sat FAIL for a day with a real violation
    (`selectors.py:1180`) hidden among the noise.

    The read is now *declared anywhere under the app*, which is the definition
    that cannot go stale: a model class written inside `apps/work/` is Work's
    by construction, whatever file it lives in, and a foreign model is declared
    in another app's directory and so can never be picked up here. `MODELS_MODULES`
    above already knew a module may hold models somewhere other than `models.py`
    — it names metering's `connections` for exactly that reason — and this is the
    same insight applied to the app being scanned.
    """
    names: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                "Model" in ast.unparse(base) for base in node.bases
            ):
                names.add(node.name)
    return names


def _foreign_models_module(module: str | None) -> bool:
    """`apps.<other>.models` / `apps.<other>.connections`, and never `apps.work…`."""
    if not module or not module.startswith("apps."):
        return False
    parts = module.split(".")
    if len(parts) < 2 or parts[1] == "work":
        return False
    return len(parts) >= 3 and parts[2] in MODELS_MODULES


def _foreign_bindings(tree: ast.AST) -> dict[str, tuple[int, str]]:
    """Every local name bound by a foreign-models import → (lineno, module).

    `from apps.assets.models import Asset` binds `Asset`; `from apps.metering
    import connections as w6` binds `w6`; `import apps.assets.models` binds
    `apps` (the chain root a later `apps.assets.models.Asset.objects…` uses).
    """
    bound: dict[str, tuple[int, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _foreign_models_module(module):
                for alias in node.names:
                    bound[alias.asname or alias.name] = (node.lineno, module)
            elif module.startswith("apps.") and not module.startswith("apps.work"):
                # `from apps.metering import connections as w6` / `import models`
                for alias in node.names:
                    if alias.name in MODELS_MODULES:
                        bound[alias.asname or alias.name] = (node.lineno, f"{module}.{alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _foreign_models_module(alias.name):
                    bound[(alias.asname or alias.name).split(".")[0]] = (node.lineno, alias.name)
    return bound


def _chain(node: ast.AST) -> list[str]:
    """`a.b.c(...).d` → ["a", "b", "c", "d"]; the leftmost Name first."""
    parts: list[str] = []
    while True:
        if isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        elif isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, ast.Name):
            parts.append(node.id)
            break
        else:
            break
    return list(reversed(parts))


def findings_in(source: str, *, where: str, own_models: frozenset[str] = frozenset(), in_seams: bool = False) -> list[str]:
    """The gate's findings for ONE file's source. Pure, so the self-test can
    hand it synthetic text and the tests can hand it a sabotaged copy."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"{where}:{exc.lineno or 0} could not be parsed ({exc.msg})"]
    out: list[str] = []
    bound = _foreign_bindings(tree)

    # 1 · foreign models import outside seams/
    if not in_seams:
        for name, (lineno, module) in sorted(bound.items(), key=lambda item: item[1][0]):
            out.append(f"{where}:{lineno} imports {module} outside seams/ (BR-WRK-002)")

    # 2 · ORM write on a foreign model, anywhere
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in WRITE_ATTRS:
            continue
        chain = _chain(node.func)
        if not chain:
            continue
        root = chain[0]
        # The model the chain names: `X.objects.create` → X; `apps.assets.models.X.objects…` → X;
        # `w6.WorkOrder.objects.create` → WorkOrder. Read as the element before `objects`.
        model = chain[chain.index("objects") - 1] if "objects" in chain[:-1] else None
        via_objects = "objects" in chain[:-1]
        if model in own_models:
            continue
        rooted_foreign = root in bound
        if via_objects and (rooted_foreign or model not in own_models and model is not None and model[:1].isupper()):
            out.append(
                f"{where}:{node.lineno} writes a foreign model — {model}.objects.{node.func.attr} (BR-WRK-002)"
            )
        elif not via_objects and rooted_foreign and node.func.attr in ("save", "delete"):
            out.append(
                f"{where}:{node.lineno} writes a foreign model — {'.'.join(chain)} (BR-WRK-002)"
            )

    # 3 · raw SQL that writes
    own_tables = {name.lower() for name in own_models}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            hit = RAW_WRITE_RE.search(node.value)
            if hit and not any(table in node.value.lower() for table in own_tables):
                out.append(f"{where}:{node.lineno} raw SQL writes a table — {hit.group(0)} (BR-WRK-002)")
    return sorted(out, key=lambda line: int(line.split(":")[1].split(" ")[0]))


def scan(root: Path) -> list[str]:
    """Every finding under `root` (an `apps/work` folder, real or copied)."""
    own = frozenset(_own_model_names(root))
    problems: list[str] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if any(part in SKIP_PARTS for part in rel.parts) or path.name in SKIP_NAMES:
            continue
        try:
            shown = str(path.relative_to(REPO))
        except ValueError:
            shown = str(rel)
        problems.extend(
            findings_in(
                path.read_text(encoding="utf-8"),
                where=shown,
                own_models=own,
                in_seams=rel.parts[0] == "seams",
            )
        )
    return problems


# ── the self-test's synthetic package ─────────────────────────────────────
CLEAN_SERVICES = '''
"""A clean Work service: reads through the seam, writes through a named door."""
from apps.work.seams import metering_seam

def raise_work_order(actor, payload):
    data = dict(payload or {})
    data.update({"scope": "per_premise"})   # dict.update is not an ORM write
    return metering_seam.raise_work_order(actor, data)
'''
CLEAN_SEAM = '''
"""A clean seam: a foreign models import IS allowed here, and it only reads."""
from apps.metering import connections as w6

def open_work_orders_queryset():
    return w6.WorkOrder.objects.filter(state="planned")

def raise_work_order(actor, payload):
    return w6.create_work_order(actor, None, payload)   # a SERVICE, by name
'''
RED_SERVICES = '''
from apps.assets.models import Asset

def retire(order_id):
    Asset.objects.filter(pk=order_id).update(status="retired")
'''
RED_DISPATCH = '''
from apps.assets.models import Asset

def plan(asset_id):
    return Asset.objects.filter(pk=asset_id).first()
'''
RED_JOURNAL = '''
from apps.ledger import models as ledger_models

def post(order):
    ledger_models.JournalLine.objects.create(amount=order.total)
'''
RED_SEAM_WRITE = '''
from apps.metering import connections as w6

def cancel(order_id):
    w6.WorkOrder.objects.filter(pk=order_id).update(state="cancelled")
'''
RED_RAW = '''
def bump(cursor, order_id):
    cursor.execute("UPDATE work_orders SET state = %s WHERE id = %s", ["done", order_id])
'''


def selftest() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "work"
        (root / "seams").mkdir(parents=True)
        (root / "services.py").write_text(CLEAN_SERVICES, encoding="utf-8")
        (root / "seams" / "metering_seam.py").write_text(CLEAN_SEAM, encoding="utf-8")
        if scan(root):
            return False
        # a foreign write in services.py — named, with its line and its model
        (root / "services.py").write_text(RED_SERVICES, encoding="utf-8")
        red = scan(root)
        if not (len(red) == 2 and "imports apps.assets.models outside seams/" in red[0] and "Asset.objects.update" in red[1]):
            return False
        (root / "services.py").write_text(CLEAN_SERVICES, encoding="utf-8")
        # a foreign models import outside seams/, even for a READ
        (root / "dispatch.py").write_text(RED_DISPATCH, encoding="utf-8")
        red = scan(root)
        if not (len(red) == 1 and "dispatch.py:2 imports apps.assets.models outside seams/" in red[0]):
            return False
        (root / "dispatch.py").unlink()
        # a journal line — hard rule 5
        (root / "costing.py").write_text(RED_JOURNAL, encoding="utf-8")
        red = scan(root)
        if not any("JournalLine.objects.create" in line for line in red):
            return False
        (root / "costing.py").unlink()
        # a seam that WRITES through the ORM — the import is lawful there, the write is not
        (root / "seams" / "metering_seam.py").write_text(RED_SEAM_WRITE, encoding="utf-8")
        red = scan(root)
        if not (len(red) == 1 and "WorkOrder.objects.update" in red[0]):
            return False
        (root / "seams" / "metering_seam.py").write_text(CLEAN_SEAM, encoding="utf-8")
        # raw SQL
        (root / "rules.py").write_text(RED_RAW, encoding="utf-8")
        red = scan(root)
        if not (len(red) == 1 and "raw SQL writes a table" in red[0]):
            return False
        (root / "rules.py").unlink()
        # a model of Work's OWN is exempt once models.py declares it
        (root / "models.py").write_text("from django.db import models\n\nclass Crew(models.Model):\n    pass\n", encoding="utf-8")
        (root / "dispatch.py").write_text("from apps.work.models import Crew\n\ndef add():\n    Crew.objects.create()\n", encoding="utf-8")
        if scan(root):
            return False
    return True


def run() -> tuple[str, str]:
    if not WORK_APP.is_dir():
        return "SKIP", f"{WORK_APP.relative_to(REPO)} is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a foreign write from a "
            "read through a seam, so its verdict is worthless (DEF-182)"
        )
    problems = scan(WORK_APP)
    if problems:
        return "FAIL", " | ".join(problems[:6]) + (f" (+{len(problems) - 6} more)" if len(problems) > 6 else "")
    files = [
        p
        for p in WORK_APP.rglob("*.py")
        if not any(part in SKIP_PARTS for part in p.relative_to(WORK_APP).parts) and p.name not in SKIP_NAMES
    ]
    return "PASS", (
        f"{len(files)} file(s) under 06-backend/apps/work write no other module's table and import "
        "foreign models only under seams/ (BR-WRK-002); self-test: the sabotage bites (a foreign "
        "update in services.py, a journal line, a seam that writes, raw SQL)"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
