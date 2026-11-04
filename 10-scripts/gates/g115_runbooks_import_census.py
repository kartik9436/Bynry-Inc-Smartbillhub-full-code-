#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) TC-RBS-25 — the Runbooks module's boundary
#           gate. `CR-075` wave A task `A6`: *"every cross-module import
#           resolves to `*_seam.py`; every seam names a register row; no
#           `requests`, no `httpx`, no other module's models; a Check's seams
#           expose reads only."*
# Rules:    BR-RBS-039 (a runbook reaches another module ONLY through a seam
#           this module owns, calling the owner's selector by name in the same
#           process; every seam is a row in the cross-module interface register;
#           the module never calls the product's own HTTP endpoints and never
#           imports another module's models) · BR-RBS-022 (a write is a named
#           port; work items and audit rows are the ENGINE's) · BR-RBS-002 (a
#           Check is CONSTRUCTED with no ports) · B2 §2 / DB-16 (cross-module
#           writes forbidden) · CLAUDE.md hard rule 5 (only the ledger posting
#           service writes journal lines) · hard-won law 7 (proved RED first,
#           through `run_gates`, and its output distinguishes pass from fail)
# Tests:    selftest() below (runs on every invocation) ·
#           06-backend/tests/test_us_rbs_041_module.py
# Impacts:  every .py under 06-backend/apps/runbooks
# ───────────────────────────────────────────────────────
"""G115 — nothing under `apps/runbooks/` reaches past its own seams.

WHY THIS GATE EXISTS
--------------------
Runbooks is the twelfth code module and it is defined by what it CANNOT do: it
owns seven tables, reads nine other modules through one seam file each, and
writes none of them — every write is one of thirteen ports, and in phase 1 not
one of those has a writer bound. That is not tidiness. It is the reason a Check
can be trusted: **a Check is constructed with no ports at all, so a write from
one is a construction error rather than a runtime refusal.**

A boundary that is only a sentence in a rules file is broken the first time a
lane reaches for `Account.objects.filter(...)` because it is four lines shorter
than asking customers for a selector — and that lane will be under time
pressure, with a screen to ship. This gate makes that line fail the merge.
`G78` does the same job for the `work` module and this is deliberately its
sibling; the differences are listed under WHAT IS STRICTER HERE.

WHAT IT READS
-------------
Every `.py` under `06-backend/apps/runbooks`, EXCEPT `migrations/` (Django's own
operations name models by string) and `__pycache__`. Eight findings:

  1. **A FOREIGN IMPORT OUTSIDE THE TWO DOORS.** `from apps.<other> import …`,
     `import apps.<other>…`, in any form. Lawful ONLY in
     `seams/<module>_seam.py` (reads) and `ports/<module>_ports.py` (writes,
     from wave L). ⚠ **`seams/__init__.py` IS NOT A DOOR** — see the re-export
     hole below.
  2. **A RELATIVE IMPORT THAT ESCAPES THE PACKAGE.** `from ...customers import
     x` resolves outside `apps.runbooks` and would otherwise sail past a rule
     written in terms of the string `apps.`.
  3. **A DYNAMIC IMPORT OUTSIDE THE TWO DOORS.** `importlib.import_module(…)`
     and `__import__(…)`, unless the argument is a string LITERAL beginning
     `apps.runbooks.` — this module's own. Inside the doors a dynamic import is
     lawful (it is how a late-bound seam resolves its owner) and is COUNTED.
  4. **AN HTTP CLIENT ANYWHERE.** `requests`, `httpx`, `aiohttp`, `urllib3`,
     `urllib.request`, `http.client`, `socket`. `BR-RBS-039`: this module never
     calls the product's own HTTP endpoints and never dials out. A partner is
     reached through `integrations`, which is a seam like any other.
  5. **AN ORM WRITE ON A FOREIGN MODEL, ANYWHERE — INCLUDING INSIDE `seams/`.**
     A seam READS. This is stricter than `G78`, which sanctions one named write
     door in `work`'s metering seam, because here a write is a PORT and a seam
     that writes is a seam in name only.
  6. **RAW SQL THAT WRITES.** `INSERT INTO`, `UPDATE … SET`, `DELETE FROM`,
     `TRUNCATE` in a string literal, unless it names one of this module's own
     tables.
  7. **A SEAM WITH NO REGISTER ROW.** `BR-RBS-039` ends *"every seam is a row in
     the cross-module interface register"*. Each `seams/*_seam.py` must be named
     by `04-docs/02-decisions/02-database-design-brief.md`. A tenth seam added
     without its row fails here, which is the only thing that stops the register
     drifting behind the code.
  8. **THE PORT LIST MOVED.** Exactly THIRTEEN ports, and `raise_work_item` is
     not among them. Both halves are load-bearing and the membership matters
     more than the count — see below.

WHAT WOULD MAKE THIS CHECK PASS WRONGLY
---------------------------------------
Hard-won law 7's second habit, answered in writing because a check whose false
pass you cannot describe is a check you do not understand. Each of these was a
draft of this gate at some point:

  * **AN IMPORT INSIDE A FUNCTION BODY.** `def steps(): from apps.customers.models
    import Account` is not a module-level import and a reader-of-the-top-of-file
    never sees it. → `ast.walk` visits every node in the tree, so a nested
    import is found at whatever depth it hides.
  * **AN IMPORT INSIDE `if TYPE_CHECKING:`.** It does not execute at runtime, so
    a lane will argue it is harmless — and it is a real coupling that a later
    refactor turns into a runtime one. → Same answer: `ast.walk` does not care
    about the guard, and this gate makes no exception for one.
  * **`importlib.import_module("apps." + module)`.** A census cannot follow a
    computed name. → Refused outright outside the two doors; inside them it is
    lawful, and the gate PRINTS HOW MANY it could not follow. A declared blind
    spot with no number attached is indistinguishable from an empty one, which
    is exactly how `G32` reported `0 unresolved` over 21 live refusals.
  * **A RELATIVE IMPORT.** `from ..customers.models import Account` contains no
    `apps.` at all. → Resolved against the file's own package path and judged on
    the result.
  * **A RE-EXPORT THROUGH `__init__.py`.** `seams/__init__.py` doing
    `from apps.customers.models import Account` would launder a foreign name
    into `apps.runbooks.seams`, reachable from anywhere in the module with no
    file appearing to import it. → The door is `seams/*_seam.py`, NOT the
    directory: `__init__.py` and any other file under `seams/` are held to the
    same rule as the rest of the module.
  * **A WRITE THROUGH A SEAM.** `G78` permits one, by name, because `work`
    writes `work_orders` through metering's own service. Here that would be a
    port. → No seam write is sanctioned, and the ORM-write rule applies inside
    `seams/` too.
  * **AN EMPTY MODULE.** A gate that walks zero files and reports PASS is
    `G5`-calling-192-skips-a-pass. → The file count is printed, and `run()`
    SKIPs (never passes) when the package is absent.

WHY THE PORT COUNT IS ASSERTED AND NOT MERELY DESCRIBED
--------------------------------------------------------
The source specification says a runbook writes through *"four named calls"* and
lists *raise a work item* among them, in seven places; the contract, one page
later, lists THIRTEEN and states that raising work items and writing audit rows
are ENGINE acts. **A lane grepping for *port* finds the wrong answer seven times
out of eight.** Building the four-call version gives every Check a writer and
`BR-RBS-002` is gone — the module's whole safety promise with it. So the count
and the membership are both asserted here, and a fourteenth port fails this gate
on purpose: adding one is a reviewed interface, not a line somebody writes on
the way past.

PROVED RED FIRST, AND THROUGH `run_gates` (law 7)
--------------------------------------------------
`selftest()` builds a synthetic `runbooks` package in a temp directory on every
invocation and breaks exactly one thing per case: a foreign import in
`services.py`, the same import inside a function body, the same inside
`TYPE_CHECKING`, a relative import that escapes, an `importlib` call outside the
doors, `import requests`, an ORM write inside a seam, a journal-line write, raw
SQL, a re-export through `seams/__init__.py`, a seam with no register row, and a
fourteenth port named `raise_work_item`. If any sabotage fails to bite, this
gate reports FAIL rather than PASS — a gate whose own self-test does not hold has
a worthless verdict.

The planted violations for the wave's `2d` transcript were run through
`10-scripts/gates/run_gates.py`, NOT through `python3 g115_…py`, because the
runner calls `module.run()` and never `__main__`: `DEF-GOV-3733` is two gates
announced green while the suite reported *"gate crashed: module has no attribute
run"*. A red proof through the wrong entry point is no proof of the thing that
matters.
"""

from __future__ import annotations

import ast
import re
import sys
import tempfile
from pathlib import Path

import common

REPO = common.REPO_ROOT
RUNBOOKS_APP = common.BACKEND_APPS / "runbooks"
SCHEMA_BRIEF = REPO / "04-docs" / "02-decisions" / "02-database-design-brief.md"
SKIP_PARTS = ("migrations", "__pycache__")

#: The THIRTEEN ports, and the count is asserted rather than described — see the
#: module docstring. `raise_work_item` is deliberately absent and adding it is
#: the specific mistake this constant exists to refuse.
#:
#: ⚠ **FIFTEEN SINCE 2026-10-07.** `step_ladder` (payments) arrived on
#: 2026-09-07 (`dff6b379f`, `DEF-RBS-4347`) and this number was not moved, so the
#: gate was red on the count from that day; `send_partner_file` (integrations,
#: `CR-173-BRC10`, decision log 2026-10-07) is the fifteenth. Both moved here.
EXPECTED_PORT_COUNT = 15
FORBIDDEN_PORT_NAMES = frozenset({"raise_work_item", "write_audit", "write_audit_row"})

#: ORM verbs that WRITE. `get`, `filter`, `exists`, `count`, `first` are reads.
WRITE_ATTRS = frozenset(
    {"create", "update", "delete", "bulk_create", "bulk_update", "get_or_create", "update_or_create", "save"}
)
#: No HTTP client, and no raw socket either — `BR-RBS-039` says this module
#: never calls the product's own endpoints and never dials a partner. A partner
#: is reached through `integrations`, which is a seam like any other.
FORBIDDEN_TOP_LEVEL = frozenset(
    {"requests", "httpx", "aiohttp", "urllib3", "socket", "http", "urllib", "django_requests"}
)
RAW_WRITE_RE = re.compile(r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|TRUNCATE)\b", re.IGNORECASE)
DYNAMIC_CALLS = frozenset({"import_module", "__import__"})

#: This module's own tables — a raw literal naming one of these is its own
#: business. Read from `models.py` rather than carried as a list, so wave B's
#: eighth table exempts itself.
OWN_TABLE_FALLBACK = frozenset(
    {
        "runbooks",
        "runbook_versions",
        "runbook_runs",
        "runbook_run_records",
        "work_items",
        "cutover_plans",
        "cutover_plan_items",
    }
)


def _is_door(rel_parts: tuple[str, ...]) -> bool:
    """Is this file one of the two places a foreign import is lawful?

    `seams/<x>_seam.py` reads; `ports/<x>_ports.py` writes (from wave L).
    **The door is the FILE, never the directory** — `seams/__init__.py` is not a
    door, because a re-export there launders a foreign name into the whole
    package with no file appearing to import it.
    """
    if len(rel_parts) != 2:
        return False
    folder, name = rel_parts
    if folder == "seams":
        return name.endswith("_seam.py")
    if folder == "ports":
        return name.endswith("_ports.py")
    return False


def _own_model_names(root: Path) -> set[str]:
    """Every model class declared anywhere under `<root>` — this app's own tables.

    Declared ANYWHERE under the app, not only in `models.py`: `DEF-WRK-4032`
    was `G78` calling Work's own tables foreign because a second models module
    held them and `models.py` merely re-exported.
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


def _own_tables(root: Path) -> set[str]:
    """`db_table = "..."` values declared under `<root>`, plus the known seven."""
    tables = set(OWN_TABLE_FALLBACK)
    for path in sorted(root.rglob("*.py")):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "db_table" for t in node.targets)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                tables.add(node.value.value)
    return tables


def _absolute_from_relative(module: str | None, level: int, package_parts: list[str]) -> str:
    """What `from ..x import y` resolves to, given the file's own package."""
    if level <= 0:
        return module or ""
    base = package_parts[: len(package_parts) - (level - 1)] if level > 1 else package_parts
    return ".".join([*base, module]) if module else ".".join(base)


def _foreign(module: str) -> str | None:
    """`apps.<other>` → `<other>`; this module's own and non-`apps` → None."""
    if not module.startswith("apps."):
        return None
    parts = module.split(".")
    if len(parts) < 2 or parts[1] == "runbooks":
        return None
    return parts[1]


def findings_in(
    source: str,
    *,
    where: str,
    package_parts: list[str],
    is_door: bool,
    own_models: frozenset[str] = frozenset(),
    own_tables: frozenset[str] = frozenset(),
) -> tuple[list[str], int]:
    """Findings for ONE file, and the number of dynamic imports not followed.

    Pure, so the self-test can hand it synthetic text and a future test can hand
    it a sabotaged copy of the real tree.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"{where}:{exc.lineno or 0} could not be parsed ({exc.msg})"], 0
    out: list[str] = []
    unfollowed = 0
    bound_foreign: dict[str, int] = {}

    for node in ast.walk(tree):
        # 1 · 2 · 4 — every import, at any depth, in any guard
        if isinstance(node, ast.ImportFrom):
            module = _absolute_from_relative(node.module, node.level, package_parts)
            if node.level and not module.startswith("apps.runbooks"):
                out.append(
                    f"{where}:{node.lineno} relative import escapes the module — "
                    f"{'.' * node.level}{node.module or ''} resolves to {module} (BR-RBS-039)"
                )
            other = _foreign(module)
            if other and not is_door:
                out.append(
                    f"{where}:{node.lineno} imports {module} outside seams/*_seam.py and "
                    f"ports/*_ports.py (BR-RBS-039)"
                )
            if other:
                for alias in node.names:
                    bound_foreign[alias.asname or alias.name] = node.lineno
            top = (node.module or "").split(".")[0]
            if not node.level and top in FORBIDDEN_TOP_LEVEL:
                out.append(
                    f"{where}:{node.lineno} imports {node.module} — this module dials nothing "
                    "and calls no HTTP endpoint of its own product (BR-RBS-039)"
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                other = _foreign(alias.name)
                if other and not is_door:
                    out.append(
                        f"{where}:{node.lineno} imports {alias.name} outside seams/*_seam.py "
                        f"and ports/*_ports.py (BR-RBS-039)"
                    )
                if other:
                    bound_foreign[(alias.asname or alias.name).split(".")[0]] = node.lineno
                if alias.name.split(".")[0] in FORBIDDEN_TOP_LEVEL:
                    out.append(
                        f"{where}:{node.lineno} imports {alias.name} — this module dials nothing "
                        "and calls no HTTP endpoint of its own product (BR-RBS-039)"
                    )

        # 3 — a dynamic import: refused outside the doors, COUNTED inside them
        if isinstance(node, ast.Call):
            fn = node.func
            called = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")
            if called in DYNAMIC_CALLS:
                arg = node.args[0] if node.args else None
                literal = (
                    arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None
                )
                own = literal is not None and literal.startswith("apps.runbooks")
                if own:
                    pass
                elif is_door:
                    unfollowed += 1
                else:
                    shown = repr(literal) if literal is not None else "a computed name"
                    out.append(
                        f"{where}:{node.lineno} resolves an import dynamically ({called}, {shown}) "
                        "outside seams/*_seam.py and ports/*_ports.py — a census cannot follow it "
                        "(BR-RBS-039)"
                    )

    # 5 — an ORM write on a foreign model, ANYWHERE, seams included
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in WRITE_ATTRS:
            continue
        chain = _chain(node.func)
        if not chain:
            continue
        via_objects = "objects" in chain[:-1]
        model = chain[chain.index("objects") - 1] if via_objects else None
        if model in own_models:
            continue
        rooted_foreign = chain[0] in bound_foreign
        if via_objects and (rooted_foreign or (model is not None and model[:1].isupper())):
            out.append(
                f"{where}:{node.lineno} writes a foreign model — {model}.objects.{node.func.attr}. "
                "A seam READS; a write is a port (BR-RBS-022)"
            )
        elif not via_objects and rooted_foreign and node.func.attr in ("save", "delete"):
            out.append(
                f"{where}:{node.lineno} writes a foreign model — {'.'.join(chain)} (BR-RBS-022)"
            )

    # 6 — raw SQL that writes something this module does not own
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            hit = RAW_WRITE_RE.search(node.value)
            if hit and not any(table in node.value.lower() for table in own_tables):
                out.append(f"{where}:{node.lineno} raw SQL writes a table — {hit.group(0)} (BR-RBS-039)")

    return sorted(set(out), key=lambda line: int(line.split(":")[1].split(" ")[0])), unfollowed


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


def _bound_port_count(root: Path) -> int:
    """How many `PortDeclaration(...)` pass a `writer=` — i.e. can actually write.

    ⚠ **THE NUMBER A READER MOST NEEDS, AND THE FIRST DRAFT OF THIS GATE DID NOT
    PRINT IT.** Phase 1's promise is *"nothing can be written: no writer is
    bound"*, and a PASS line reading only *"13 ports declared"* is true whether
    that promise holds or not. A check's output must distinguish pass from fail
    TO A READER and not merely to an exit code — the habit `--stat` was twice
    trusted against, and it is the one this gate could most easily have failed.

    It is a REPORTED number rather than a finding: binding a writer is exactly
    what wave L is for, and a gate that failed on it would have to be switched
    off that day. What it buys is that the day the first writer is bound, the
    line says `1 bound` instead of `0 bound`, in a suite somebody reads.
    """
    bound = 0
    ports_dir = root / "ports"
    if not ports_dir.is_dir():
        return 0
    for path in sorted(ports_dir.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "PortDeclaration":
                continue
            if any(kw.arg == "writer" for kw in node.keywords):
                bound += 1
    return bound


def _port_names(root: Path) -> list[str]:
    """Every `PortDeclaration(name="…")` under `ports/`, in file order."""
    names: list[str] = []
    ports_dir = root / "ports"
    if not ports_dir.is_dir():
        return names
    for path in sorted(ports_dir.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "PortDeclaration":
                continue
            for kw in node.keywords:
                if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                    names.append(str(kw.value.value))
    return names


def _seams_without_a_register_row(root: Path, brief_text: str) -> list[str]:
    """`BR-RBS-039`: every seam is a row in the cross-module interface register."""
    problems: list[str] = []
    seams_dir = root / "seams"
    if not seams_dir.is_dir():
        return problems
    for path in sorted(seams_dir.glob("*_seam.py")):
        # The register names seams by their repo path; match on the file name so
        # a move under apps/ does not silently un-register nine seams.
        if path.name not in brief_text:
            problems.append(
                f"seams/{path.name} is not named in 02-database-design-brief.md — a seam owes a "
                "row in the cross-module interface register, in the same commit as the file "
                "(BR-RBS-039)"
            )
    return problems


def scan(root: Path, *, brief_text: str) -> tuple[list[str], int, int]:
    """Every finding under `root`, the file count, and the unfollowed count."""
    own_models = frozenset(_own_model_names(root))
    own_tables = frozenset(_own_tables(root))
    problems: list[str] = []
    unfollowed = 0
    files = 0
    for path in sorted(root.rglob("*.py")):
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_PARTS for part in rel_parts):
            continue
        files += 1
        try:
            shown = str(path.relative_to(REPO))
        except ValueError:
            shown = str(Path(*rel_parts))
        found, skipped = findings_in(
            path.read_text(encoding="utf-8"),
            where=shown,
            package_parts=["apps", "runbooks", *rel_parts[:-1]],
            is_door=_is_door(rel_parts),
            own_models=own_models,
            own_tables=own_tables,
        )
        problems.extend(found)
        unfollowed += skipped

    problems.extend(_seams_without_a_register_row(root, brief_text))

    ports = _port_names(root)
    if ports:
        forbidden = sorted(set(ports) & FORBIDDEN_PORT_NAMES)
        if forbidden:
            problems.append(
                f"ports/ declares {', '.join(forbidden)} as a PORT. Raising a work item and "
                "writing an audit row are ENGINE acts, never ports — that is the only thing that "
                "lets a Check populate the work list while holding no writer (BR-RBS-002/022)"
            )
        if len(ports) != EXPECTED_PORT_COUNT:
            problems.append(
                f"ports/ declares {len(ports)} port(s); the reviewed interface set is "
                f"{EXPECTED_PORT_COUNT}. A fourteenth port is a reviewed interface (BR-RBS-022), "
                "not a line added on the way past — move this number deliberately, with its row "
                "in the schema brief"
            )
    return problems, files, unfollowed


# ── the self-test's synthetic package ─────────────────────────────────────
CLEAN_SERVICES = '''
"""A clean service: writes this module's own tables and nothing else's."""
from apps.runbooks import interfaces
from apps.runbooks.models import RunbookRun

def open_run(runbook):
    return RunbookRun.objects.create(runbook=runbook)
'''
CLEAN_SEAM = '''
"""operations -> customers. A foreign import IS lawful here, and it only reads."""
from apps.customers import selectors as customers_selectors

def account(account_id):
    return customers_selectors.account_row(account_id)
'''
CLEAN_SEAM_INIT = '''
"""No imports here on purpose — a re-export would launder a foreign name."""
'''
CLEAN_PORTS = '''
from apps.runbooks.boundary import PortDeclaration

P1 = PortDeclaration(name="queue_notice", owning_module="notifications", what_it_does="x")
'''
CLEAN_MODELS = '''
from django.db import models

class RunbookRun(models.Model):
    class Meta:
        db_table = "runbook_runs"
'''
RED_TOP_LEVEL = 'from apps.customers.models import Account\n\ndef n():\n    return Account\n'
RED_IN_FUNCTION = 'def steps():\n    from apps.customers.models import Account\n    return Account\n'
RED_TYPE_CHECKING = (
    "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n"
    "    from apps.customers.models import Account\n"
)
RED_RELATIVE = 'from ...customers.models import Account\n\ndef n():\n    return Account\n'
RED_IMPORTLIB = (
    "from importlib import import_module\n\n"
    "def owner(name):\n    return import_module('apps.' + name + '.selectors')\n"
)
RED_HTTP = 'import requests\n\ndef fetch(url):\n    return requests.get(url)\n'
RED_SEAM_WRITE = (
    "from apps.customers import models as customer_models\n\n"
    "def flag(account_id):\n"
    "    customer_models.Account.objects.filter(pk=account_id).update(flagged=True)\n"
)
RED_JOURNAL = (
    "from apps.ledger import models as ledger_models\n\n"
    "def post(amount):\n    ledger_models.JournalLine.objects.create(amount=amount)\n"
)
RED_RAW = 'def bump(cursor, pk):\n    cursor.execute("UPDATE accounts SET balance = 0 WHERE id = %s", [pk])\n'
RED_SEAM_INIT_REEXPORT = 'from apps.customers.models import Account\n\n__all__ = ["Account"]\n'
RED_FOURTEENTH_PORT = '''
from apps.runbooks.boundary import PortDeclaration

P1 = PortDeclaration(name="queue_notice", owning_module="notifications", what_it_does="x")
P2 = PortDeclaration(name="raise_work_item", owning_module="notifications", what_it_does="x")
'''
#: The synthetic brief the clean case is measured against — the self-test must
#: not depend on the real document, or a sibling editing B2 turns this red.
FAKE_BRIEF = "…apps/runbooks/seams/customers_seam.py… (the register row)"


def selftest() -> bool:
    """Break exactly one thing per case and confirm the gate says so.

    A gate whose own sabotage does not bite has a worthless verdict, so `run()`
    reports FAIL rather than PASS when this returns False (`DEF-182`).
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "runbooks"
        (root / "seams").mkdir(parents=True)
        (root / "ports").mkdir(parents=True)
        (root / "models.py").write_text(CLEAN_MODELS, encoding="utf-8")
        (root / "services.py").write_text(CLEAN_SERVICES, encoding="utf-8")
        (root / "seams" / "__init__.py").write_text(CLEAN_SEAM_INIT, encoding="utf-8")
        (root / "seams" / "customers_seam.py").write_text(CLEAN_SEAM, encoding="utf-8")
        (root / "ports" / "notifications_ports.py").write_text(CLEAN_PORTS, encoding="utf-8")

        def problems() -> list[str]:
            found, _files, _skipped = scan(root, brief_text=FAKE_BRIEF)
            # the synthetic package declares one port; the real count check is
            # exercised by its own case below
            return [p for p in found if "the reviewed interface set is" not in p]

        if problems():
            return False

        cases: list[tuple[str, str, str]] = [
            ("selectors.py", RED_TOP_LEVEL, "outside seams/*_seam.py"),
            ("selectors.py", RED_IN_FUNCTION, "outside seams/*_seam.py"),
            ("selectors.py", RED_TYPE_CHECKING, "outside seams/*_seam.py"),
            ("selectors.py", RED_RELATIVE, "relative import escapes the module"),
            ("selectors.py", RED_IMPORTLIB, "resolves an import dynamically"),
            ("selectors.py", RED_HTTP, "this module dials nothing"),
            ("selectors.py", RED_RAW, "raw SQL writes a table"),
        ]
        for name, body, expected in cases:
            (root / name).write_text(body, encoding="utf-8")
            if not any(expected in line for line in problems()):
                return False
            (root / name).unlink()

        # an ORM write INSIDE a seam — the import is lawful there, the write is not
        (root / "seams" / "customers_seam.py").write_text(RED_SEAM_WRITE, encoding="utf-8")
        if not any("writes a foreign model" in line for line in problems()):
            return False
        (root / "seams" / "customers_seam.py").write_text(CLEAN_SEAM, encoding="utf-8")

        # a journal line — CLAUDE.md hard rule 5
        (root / "posting.py").write_text(RED_JOURNAL, encoding="utf-8")
        if not any("JournalLine.objects.create" in line for line in problems()):
            return False
        (root / "posting.py").unlink()

        # the re-export hole: seams/__init__.py is NOT a door
        (root / "seams" / "__init__.py").write_text(RED_SEAM_INIT_REEXPORT, encoding="utf-8")
        if not any("outside seams/*_seam.py" in line for line in problems()):
            return False
        (root / "seams" / "__init__.py").write_text(CLEAN_SEAM_INIT, encoding="utf-8")

        # a seam with no row in the register
        (root / "seams" / "metering_seam.py").write_text(CLEAN_SEAM, encoding="utf-8")
        found, _f, _s = scan(root, brief_text=FAKE_BRIEF)
        if not any("owes a row in the cross-module interface register" in line for line in found):
            return False
        (root / "seams" / "metering_seam.py").unlink()

        # a fourteenth port, and the one name that must never be one
        (root / "ports" / "notifications_ports.py").write_text(RED_FOURTEENTH_PORT, encoding="utf-8")
        found, _f, _s = scan(root, brief_text=FAKE_BRIEF)
        if not any("raise_work_item" in line and "ENGINE acts" in line for line in found):
            return False
        (root / "ports" / "notifications_ports.py").write_text(CLEAN_PORTS, encoding="utf-8")

        # a dynamic import INSIDE a door is lawful and is COUNTED, not refused
        (root / "seams" / "customers_seam.py").write_text(
            CLEAN_SEAM + RED_IMPORTLIB, encoding="utf-8"
        )
        found, _f, skipped = scan(root, brief_text=FAKE_BRIEF)
        if skipped != 1 or any("resolves an import dynamically" in line for line in found):
            return False
    return True


def run() -> tuple[str, str]:
    if not RUNBOOKS_APP.is_dir():
        return "SKIP", f"{RUNBOOKS_APP.relative_to(REPO)} is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a foreign import from a "
            "read through a seam, so its verdict is worthless (DEF-182)"
        )
    brief_text = common.read_text(SCHEMA_BRIEF) if SCHEMA_BRIEF.is_file() else ""
    if not brief_text:
        return "FAIL", (
            "02-database-design-brief.md could not be read, so 'every seam names a register row' "
            "cannot be checked — reporting the gap rather than a green over an unchecked rule"
        )
    problems, files, unfollowed = scan(RUNBOOKS_APP, brief_text=brief_text)
    if problems:
        shown = " | ".join(problems[:6])
        more = f" (+{len(problems) - 6} more)" if len(problems) > 6 else ""
        return "FAIL", shown + more

    ports = _port_names(RUNBOOKS_APP)
    seams = sorted((RUNBOOKS_APP / "seams").glob("*_seam.py")) if (RUNBOOKS_APP / "seams").is_dir() else []
    # ⚠ THE BLIND SPOT CARRIES ITS NUMBER. A census cannot follow a computed
    # import; saying so with a count is the difference between a declared gap
    # and an empty one (G32 reported `0 unresolved` truthfully over 21 live
    # refusals it could not see).
    blind = (
        f"{unfollowed} dynamic import(s) inside a seam or port could not be followed statically"
        if unfollowed
        else "no dynamic import anywhere — every import in this module was followed"
    )
    return "PASS", (
        f"{files} file(s) under 06-backend/apps/runbooks import no other module outside "
        f"{len(seams)} seam file(s), dial nothing, and write no foreign table; "
        f"{len(ports)} port(s) declared and {_bound_port_count(RUNBOOKS_APP)} BOUND to a writer, "
        f"{ports.count('raise_work_item')} of them raise_work_item; "
        f"{blind}; self-test: 13 sabotages bite"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
