# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 0 tasks `P0.13` and
#          `P0.14`.
#          `P0.13` outcome, verbatim: *"No import of another module's `models`
#          anywhere in `apps/reports/`"*.
#          `P0.14` outcome, verbatim: *"Both resolve by name at call time and
#          degrade to a named gap"*.
# Rules:   B1 / BR-TEN-013 (a module never touches a neighbour's ORM) ·
#          BR-REP-024 (render the owner's figure, or report BY NAME that you
#          cannot answer — never 0, never an ImportError) · CLAUDE.md
#          hard-won law 1 (a comment claiming a guarantee is not the guarantee)
# Tests:   this file
# Impacts: apps/reports/report_seams.py · apps/reports/queries.py ·
#          apps/reports/api.py
# ───────────────────────────────────────────────────────
"""The reports module's boundary, asserted rather than described.

⚠ **THE FAULT `P0.14` NAMES IS NOT A WRONG NUMBER — IT IS A DEAD MODULE.**
`apps/reports/api.py` carried `from apps.ledger import reporting, wire` at its
own top level, so a deployment where `apps.ledger.reporting` does not import
lost `GET /reports/{key}` **entirely**, the four reports this module owns
included, plus `GET /dashboard/summary`. Every other read in the module goes
through `report_seams.resolve`, whose whole job is to turn a missing owner into
a sentence. The module's two most important reports bypassed its own refusal
machinery.

⚠ **AND `P0.13`'s FAULT IS SMALLER AND WORTH THE SAME TEST.** `queries.py`
read `apps.payments.models.PAYMENT_PURPOSES` with `import_module`. It read a
constant and touched no ORM, so no figure was ever wrong — what was wrong is
that the one file whose job is to list what this module reads from its
neighbours did not mention it, and a boundary crossing nobody has written down
is one nobody can audit.

**THE SOURCE SCAN BELOW STATES WHAT IT SKIPS** (hard-won law 7's fifth shape —
a check reporting zero over a scope it silently excludes). It counts the files
it read and asserts that count is non-zero, so a scan that walks the wrong
directory fails instead of passing on an empty set.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from apps.reports import api as reports_api
from apps.reports import report_seams as seams
from core import errors

REPORTS_DIR = pathlib.Path(seams.__file__).resolve().parent

#: `P0.14` — the four reads that used to be module-level imports.
LEDGER_SEAMS = (
    ("account_ledger", "reporting"),
    ("by_premises_summary", "reporting"),
    ("account_ledger_dict", "wire"),
    ("by_premises_dict", "wire"),
)


def _python_files() -> list[pathlib.Path]:
    return sorted(
        path
        for path in REPORTS_DIR.rglob("*.py")
        if "migrations" not in path.parts and "__pycache__" not in path.parts
    )


def _imported_modules(tree: ast.AST) -> list[str]:
    """Every dotted module name this file imports, however it spells it.

    Three spellings, because one of them is how `P0.13` hid: `import x.y`,
    `from x.y import z`, and `import_module("x.y")` — the last of which no
    import-graph tool sees at all.
    """
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append(node.module)
        elif isinstance(node, ast.Call):
            callee = node.func
            name = getattr(callee, "id", None) or getattr(callee, "attr", None)
            if name == "import_module" and node.args and isinstance(node.args[0], ast.Constant):
                value = node.args[0].value
                if isinstance(value, str):
                    found.append(value)
    return found


def test_p0_13_no_file_in_reports_imports_another_modules_models():
    """`P0.13`'s outcome, checked against the tree rather than asserted.

    `apps.reports.models` is this module's OWN and is not a crossing.
    """
    offenders: list[str] = []
    scanned = 0
    for path in _python_files():
        scanned += 1
        tree = ast.parse(path.read_text(), filename=str(path))
        for module in _imported_modules(tree):
            parts = module.split(".")
            if parts[:1] == ["apps"] and parts[-1] == "models" and parts[1:2] != ["reports"]:
                offenders.append(f"{path.name}: {module}")
    assert scanned > 5, f"the scan read {scanned} files — it is looking in the wrong place"
    assert offenders == [], (
        "CR-142 `P0.13` / B1: a neighbour's `models` is reached through "
        f"`report_seams.py` and nowhere else. Found: {offenders}"
    )


def test_p0_14_the_reports_api_does_not_import_ledger_at_module_load():
    """The import that made a missing owner an `ImportError` rather than a gap."""
    tree = ast.parse(pathlib.Path(reports_api.__file__).read_text())
    ledger_imports = [
        module
        for module in _imported_modules(tree)
        if module.split(".")[:2] == ["apps", "ledger"]
    ]
    assert ledger_imports == [], (
        "CR-142 `P0.14`: `apps/reports/api.py` imports "
        f"{ledger_imports} at module scope. A missing owner must be a NAMED GAP "
        "on one report, not an ImportError that takes the whole module with it."
    )


@pytest.mark.parametrize("function,kind", LEDGER_SEAMS)
def test_p0_14_each_ledger_read_resolves_by_name_at_call_time(function, kind):
    """All four are WIRED on this deployment — `resolve` finds a callable."""
    assert seams.resolve("ledger", function, kind=kind) is not None, (
        f"`apps.ledger.{kind}.{function}` does not resolve. The seam is correct; "
        "the owner moved."
    )


@pytest.mark.parametrize("function,kind", LEDGER_SEAMS)
def test_p0_14_an_unpublished_ledger_read_is_none_and_never_raises(function, kind, monkeypatch):
    """Degrading to a named gap, proved by taking the owner away.

    ⚠ The seam must answer **None**, which `api.py` turns into a sentence. A
    seam that raised here would be the ImportError back again one layer down.
    """
    import importlib

    real = importlib.import_module(f"apps.ledger.{kind}")
    monkeypatch.delattr(real, function)
    assert seams.resolve("ledger", function, kind=kind) is None
    # The seam itself short-circuits BEFORE it calls anything, so the argument
    # list never matters on this path — which is the whole point.
    assert getattr(seams, function)() is None


def test_p0_14_the_named_gap_carries_a_sentence_a_clerk_can_read():
    """`reports.ledger_read_model_is_not_published` resolves in all eleven.

    An unresolved `message_key` renders as NOTHING, not as an ugly key
    (PO 2026-08-19), so this is the difference between a refusal and silence.
    `ApiError.__init__` raises if the key resolves to nothing, which is what
    makes the construction below the assertion.
    """
    gap = reports_api._ledger_gap("account_ledger", "apps.ledger.reporting.account_ledger")
    assert isinstance(gap, errors.SysError)
    assert gap.code == errors.SYS_INTERNAL
    assert gap.message_key == "reports.ledger_read_model_is_not_published"
    assert gap.params["wanted_read"] == "apps.ledger.reporting.account_ledger"


def test_p0_13_both_vocabularies_come_through_the_seam():
    """Payments' purposes and billing's bill types, read from their owners."""
    assert seams.payment_purposes() == ("bill", "deposit", "plan_down", "prepay")
    assert "cycle" in seams.bill_types()


def test_p0_13_an_unpublished_vocabulary_is_empty_and_never_a_hardcoded_trio():
    """BR-REP-006 as an ABSENCE: no owner ⇒ no options, never a guessed list."""
    assert seams.resolve_constant("payments", "NO_SUCH_CONSTANT", kind="models") is None
    assert seams.resolve_constant("no_such_module", "ANY", kind="models") is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P0.13 + P0.14 (05-prototype/09 Reports Build Brief.pdf p8, read as images per B14 rule 42)
# screens: S44 · S46 · S59 · S60
# generated: 2026-09-26 by lane REP-P0B
# checklist: A✔ B=n/a(test file) C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — both boundary tests were run against the tree BEFORE the seam change and both failed by name (queries.py: apps.payments.models · api.py: ['apps.ledger']). ruff✔ black✔
# exceptions: (1) the source scan asserts its own file COUNT, so a scan pointed at an empty directory fails rather than passing over nothing (law 7)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
