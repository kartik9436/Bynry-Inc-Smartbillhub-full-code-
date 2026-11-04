"""G57 — a test fixture may not stand in front of the tenant kernel on PostgreSQL.

Added 2026-08-31 from DEF-2761, and it exists because the thing it checks is
invisible to every other check in this repo, including the entire test suite.

THE DEFECT, IN ITS OWN NUMBERS
------------------------------
`06-backend/tests/test_us_ten_helpers.py` carried

    @pytest.fixture(autouse=True)
    def sqlite_guc(monkeypatch):
        fake = FakeGucConnection()
        monkeypatch.setattr(core_tenancy, "connection", fake)

with no vendor guard. `autouse=True`, re-exported by `from … import *`, and
through the chain

    test_us_ten_helpers
      -> test_us_met_helpers
           -> test_us_met_reads_helpers
           -> test_us_rat_helpers

it reached **447 collected test modules — 6,575 test cases**. In every one of
them `set_config('app.tenant_id', …)` was written to a Python list and never
reached PostgreSQL. Measured on live PostgreSQL 16.13, same connection, same
transaction: the kernel was asked for `1111…1111`, the ContextVar mirror said
`1111…1111`, and `current_setting('app.tenant_id', true)` returned the nil
sentinel on the very next statement.

WHY NOTHING CAUGHT IT — AND WHY A GATE IS THE ONLY THING THAT CAN
------------------------------------------------------------------
While the app role was `SUPERUSER`, row-level security was bypassed
unconditionally, so the missing marker had NO OBSERVABLE CONSEQUENCE: no policy
was consulted, every query returned its rows, and the suite was green. That is
this repo's recurring shape — **a check that cannot fail** — one layer below
where DEF-2717 found it.

Three things that look like they would catch it, and do not:
  * **the suite itself**: `config/settings/test.py` hardcodes in-memory sqlite
    (CLAUDE.md law 14), and sqlite has no `set_config` and no RLS, so the whole
    question is meaningless there and every case passes;
  * **G5**: it is honest, and that is precisely why it is blind here —
    `isolation_helpers.live_tenant_context` swaps the REAL connection BACK
    before asserting, so G5 proves the policies while saying nothing about the
    447 modules beside it;
  * **G56**: it proves the RUNNING APPLICATION is not on a bypassing role. It
    reads shipped code, not test fixtures.

So the gate. It needs no database, runs beside the others, and asks the one
question none of them asks: *is anything standing between the tests and the
kernel that sets `app.tenant_id`?*

WHAT IT CHECKS
--------------
Every `06-backend/tests/**/*.py`, for two ways to replace the kernel's
connection:

    monkeypatch.setattr(<mod>, "connection", <anything>)   # the fixture form
    <mod>.connection = <anything>                          # direct assignment

where `<mod>` is the tenancy kernel under any of its import aliases. Each such
statement must sit inside a function that ALSO carries a vendor guard —
`connection.vendor != "postgresql"`, `== "postgresql"`, or `is_postgres()`.

…but only where the substitution is IMPLICIT — `autouse=True` fixtures and
`setUp` methods. That line is not a convenience, it is the mechanism of the
defect: what made `sqlite_guc` cost 447 modules was that no module ever asked
for it and no line in any of them mentions it, so nothing at any call site says
the kernel has been replaced.

WHAT IT DELIBERATELY ALLOWS, because each is the correct thing to do
--------------------------------------------------------------------
  * **A recorder a test asks for BY NAME.** `test_be01_tenancy.py`'s `db`
    fixture is requested per-test, and the cases that take it assert the
    STATEMENT TEXT — that the tenant id travels as a bind parameter and is
    never interpolated into SQL, and that a malformed id emits no SQL at all:

        assert db.executed == [(tenancy._SET_TENANT_SQL, [str(TENANT_A)])]
        assert str(TENANT_A) not in db.executed[0][0]

    Those are claims about the kernel's own code, they hold on every vendor,
    and they CANNOT be made against a real connection — there would be nothing
    to inspect. The opt-in is visible in the test's signature, which is exactly
    what the autouse form destroyed.
  * **Swapping the REAL connection back in.** `live_tenant_context` and
    `clear_live_guc` in `isolation_helpers.py` assign
    `core_tenancy.connection = real_connection`. That is the opposite of the
    defect — it REMOVES a fake — so an assignment whose value names the real
    connection is not a finding.
  * **Restoring a saved original** (`core_tenancy.connection = saved`), for the
    same reason.

PROVING IT RED (hard-won law 7 — done before this was trusted green)
---------------------------------------------------------------------
Delete the `if connection.vendor != "postgresql":` line from `sqlite_guc` and
re-run: the gate names the file, the line and the fixture. The self-test below
does exactly that on synthetic sources on every invocation, so the gate cannot
quietly become a formality — if any sabotage stops biting, the gate FAILS
rather than passing.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
TESTS = REPO / "06-backend" / "tests"

# ── CLAUSE 2: THE PARKED MODULES MAY ONLY EVER SHRINK ────────────────────────
#
# Removing the fake turned 416 of the 447 affected modules red on real
# PostgreSQL. Repairing the shared fixture helpers recovered most of them; the
# rest are listed, by name, in the file below, and this constant is the ceiling.
#
# ⚠ BE HONEST ABOUT WHAT THIS RATCHET IS. The i18n and refusal-copy baselines
# RE-DERIVE their offenders from source on every run and compare, so a lane
# cannot grow one by editing it. THIS ONE CANNOT: deciding whether a module
# passes with tenant scoping enforced needs a real PostgreSQL under a
# non-bypassing role, which no gate can open. So the list is bookkeeping, and
# the ceiling lives HERE — in a second file — so that growing it takes two
# deliberate edits and this gate names the number in both directions. It is the
# strongest static form available, and calling it more than that would be the
# very thing this gate exists to stop.
#
# To re-measure (about forty minutes on four cores, three workers):
#   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
#     python -m pytest <module> -x -q --reuse-db      # per module
PARKED = TESTS / "tenant-scoping-unproven.txt"
PARKED_CEILING = 127  # measured 2026-08-31; may fall, never rise

#: Import aliases the tenancy kernel travels under in this suite.
KERNEL_ALIASES = {"core_tenancy", "tenancy", "core.tenancy"}

#: Any of these inside the enclosing function means the author thought about
#: the vendor. The gate checks that the QUESTION was asked, not how.
VENDOR_MARKERS = (
    'vendor != "postgresql"',
    "vendor != 'postgresql'",
    'vendor == "postgresql"',
    "vendor == 'postgresql'",
    "is_postgres",
    "requires_postgres",
)

#: A value that puts the REAL connection back is the cure, never the disease.
RESTORING_VALUES = ("real_connection", "saved", "previous", "_real", "original")


def _is_kernel(node: ast.expr) -> bool:
    """Does this expression name the tenancy kernel module?"""
    if isinstance(node, ast.Name):
        return node.id in KERNEL_ALIASES
    if isinstance(node, ast.Attribute):
        return ast.unparse(node) in KERNEL_ALIASES
    return False


def _is_implicit(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Does this function apply to tests that never asked for it?

    Two forms, and between them they are the whole of the DEF-2761 mechanism:
    an `autouse=True` fixture, and a `setUp`/`setup_method` that runs before
    every case in its class. In both, no call site mentions the substitution,
    so nothing a reader of the test can see says the kernel was replaced.

    A fixture requested BY NAME is not implicit: it appears in the signature of
    every test that takes it, which is an opt-in a reviewer can actually read.
    """
    if func.name in {"setUp", "setup_method", "setup_class", "setUpClass"}:
        return True
    for deco in func.decorator_list:
        if not isinstance(deco, ast.Call):
            continue
        if not any(
            kw.arg == "autouse" and isinstance(kw.value, ast.Constant) and kw.value.value is True
            for kw in deco.keywords
        ):
            continue
        target = deco.func
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
        if name == "fixture":
            return True
    return False


class _StripDocstrings(ast.NodeTransformer):
    """Drop every bare string expression — docstrings and their kin.

    ⚠ THIS CLASS EXISTS BECAUSE THE GATE WAS BLIND WITHOUT IT, and it was found
    by pointing the gate at the REAL DEF-2761 file with its guard removed rather
    than only at the synthetic sabotages (hard-won law 7, which says to do
    exactly that). `sqlite_guc`'s docstring NARRATES the guard —
    *"⚠ VENDOR-GUARDED SINCE DEF-2761 … narrowed to `connection.vendor !=
    'postgresql'`"* — so an unguarded version of that function still contained
    every marker string this gate looks for, and the gate passed it.

    That is the failure this whole gate exists to prevent, one level up: a check
    that cannot fail. And it is hard-won law 1 in miniature — **a comment
    claiming a guarantee is not the guarantee** — so the gate must read CODE,
    never prose. Removing the narration would have been the wrong fix: the
    narration is the point (law 10).
    """

    def visit_Expr(self, node: ast.Expr):  # noqa: N802 — ast API
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        return node


def _code_only(func: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """The function's executable source, with all docstrings removed."""
    clone = _StripDocstrings().visit(ast.parse(ast.unparse(func)))
    ast.fix_missing_locations(clone)
    return ast.unparse(clone)


def _offences_in(tree: ast.AST, source: str) -> list[tuple[int, str]]:
    """(line, description) for every unguarded IMPLICIT replacement of the kernel connection."""
    out: list[tuple[int, str]] = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _is_implicit(func):
            continue
        try:
            body_src = _code_only(func)
        except Exception:  # pragma: no cover - unparse is total on parsed trees
            body_src = source
        guarded = any(marker in body_src for marker in VENDOR_MARKERS)
        if guarded:
            continue
        for node in ast.walk(func):
            # monkeypatch.setattr(<kernel>, "connection", <fake>)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "setattr"
                and len(node.args) >= 3
                and _is_kernel(node.args[0])
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "connection"
            ):
                value = ast.unparse(node.args[2])
                if any(token in value for token in RESTORING_VALUES):
                    continue
                out.append((node.lineno, f"{func.name}(): monkeypatch of the kernel connection"))
            # <kernel>.connection = <fake>
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and target.attr == "connection"
                        and _is_kernel(target.value)
                    ):
                        value = ast.unparse(node.value)
                        if any(token in value for token in RESTORING_VALUES):
                            continue
                        out.append(
                            (node.lineno, f"{func.name}(): assignment to the kernel connection")
                        )
    return out


_SABOTAGES = {
    "bare monkeypatch in a fixture": (
        "import pytest\n"
        "from core import tenancy as core_tenancy\n"
        "@pytest.fixture(autouse=True)\n"
        "def sqlite_guc(monkeypatch):\n"
        "    monkeypatch.setattr(core_tenancy, 'connection', FakeGucConnection())\n"
        "    yield\n"
    ),
    "direct assignment in setUp with no guard": (
        "from core import tenancy as core_tenancy\n"
        "class T:\n"
        "    def setUp(self):\n"
        "        core_tenancy.connection = FakeGucConnection()\n"
    ),
    # ⚠ THE ONE THAT WAS ACTUALLY MISSED. The gate's first draft read the
    # unparsed function INCLUDING its docstring, and `sqlite_guc`'s docstring
    # narrates the very guard the fix added — so the unguarded form still
    # contained the marker string and sailed through. Found by running the gate
    # against the real file with its guard removed (law 7), not against these
    # synthetic cases, which is why this one is here now.
    "guard named ONLY in the docstring": (
        "import pytest\n"
        "from core import tenancy as core_tenancy\n"
        "@pytest.fixture(autouse=True)\n"
        "def sqlite_guc(monkeypatch):\n"
        '    """Narrowed to connection.vendor != "postgresql" since DEF-2761."""\n'
        "    monkeypatch.setattr(core_tenancy, 'connection', FakeGucConnection())\n"
        "    yield\n"
    ),
    "autouse fixture assigning directly": (
        "import pytest\n"
        "from core import tenancy as core_tenancy\n"
        "@pytest.fixture(autouse=True)\n"
        "def shim():\n"
        "    core_tenancy.connection = FakeGucConnection()\n"
        "    yield\n"
    ),
}

_MUST_PASS = {
    "vendor-guarded monkeypatch": (
        "import pytest\n"
        "from django.db import connection\n"
        "from core import tenancy as core_tenancy\n"
        "@pytest.fixture(autouse=True)\n"
        "def sqlite_guc(monkeypatch):\n"
        '    if connection.vendor != "postgresql":\n'
        "        monkeypatch.setattr(core_tenancy, 'connection', FakeGucConnection())\n"
        "    yield\n"
    ),
    "a recorder a test asks for by name": (
        "import pytest\n"
        "from core import tenancy as core_tenancy\n"
        "@pytest.fixture()\n"
        "def db(monkeypatch):\n"
        "    fake = FakeConnection()\n"
        "    monkeypatch.setattr(core_tenancy, 'connection', fake)\n"
        "    return fake\n"
    ),
    "swapping the real connection back": (
        "from core import tenancy as core_tenancy\n"
        "def live_tenant_context(tenant_id):\n"
        "    from django.db import connection as real_connection\n"
        "    saved = core_tenancy.connection\n"
        "    core_tenancy.connection = real_connection\n"
        "    try:\n"
        "        yield\n"
        "    finally:\n"
        "        core_tenancy.connection = saved\n"
    ),
}


def _self_test() -> list[str]:
    """Every sabotage must bite and every lawful form must not. Returns failures."""
    broken = []
    for name, src in _SABOTAGES.items():
        if not _offences_in(ast.parse(src), src):
            broken.append(f"sabotage not detected: {name}")
    for name, src in _MUST_PASS.items():
        if _offences_in(ast.parse(src), src):
            broken.append(f"false positive on lawful code: {name}")
    return broken


def run():
    blind = _self_test()
    if blind:
        return "FAIL", (
            f"SELF-TEST FAILED: {'; '.join(blind)}. A check that cannot fail is worse "
            "than no check, because it is trusted (hard-won law 7)"
        )

    if not TESTS.is_dir():
        return "FAIL", f"{TESTS.relative_to(REPO)} does not exist — nothing was scanned"

    findings: list[str] = []
    scanned = 0
    for path in sorted(TESTS.rglob("*.py")):
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except SyntaxError:
            continue
        scanned += 1
        for line, what in _offences_in(tree, source):
            findings.append(f"{path.relative_to(REPO)}:{line} — {what}")

    if findings:
        head = findings[0]
        more = f" (+{len(findings) - 1} more)" if len(findings) > 1 else ""
        return "FAIL", (
            f"{head}{more}. A fixture that replaces core.tenancy.connection on "
            "PostgreSQL means set_config('app.tenant_id', …) never reaches the "
            "database, so every tenant-scoping claim in that module is vacuous "
            "(DEF-2761). Guard it with connection.vendor != 'postgresql' — sqlite "
            "still needs the recorder, PostgreSQL must use the shipping kernel"
        )

    # ── clause 2: the parked list may only shrink ────────────────────────
    parked = _parked_modules()
    if parked is None:
        return "FAIL", (
            f"{PARKED.relative_to(REPO)} is missing — the modules not yet proved "
            "under enforced tenant scoping are recorded there by name, and a "
            "count nobody can read is not a record (DEF-2761)"
        )
    if len(parked) > PARKED_CEILING:
        return "FAIL", (
            f"{PARKED.relative_to(REPO)} lists {len(parked)} modules, above the "
            f"ceiling of {PARKED_CEILING}. This list may only ever SHRINK: a module "
            "is added to it only by a lane that has measured it red on real "
            "PostgreSQL under a non-bypassing role, and adding one is a deliberate "
            "act that also lowers nothing (DEF-2761)"
        )
    missing = [m for m in parked if not (REPO / "06-backend" / m).exists()]
    if missing:
        return "FAIL", (
            f"{PARKED.relative_to(REPO)} names {len(missing)} module(s) that no "
            f"longer exist ({missing[0]}) — a parked list that outlives its "
            "entries is the hardcoded-path failure of DEF-524 again"
        )

    slack = PARKED_CEILING - len(parked)
    note = (
        f"; {len(parked)} modules parked against a ceiling of {PARKED_CEILING}"
        + (f" — {slack} have been repaired, LOWER THE CEILING" if slack else "")
    )
    return "PASS", (
        f"{scanned} test modules scanned; no fixture replaces the tenant kernel's "
        f"connection on PostgreSQL; self-test: all {len(_SABOTAGES)} sabotages bite "
        f"and all {len(_MUST_PASS)} lawful forms pass{note}"
    )


def _parked_modules() -> list[str] | None:
    """The module paths listed in the parked file, or None if it is absent."""
    if not PARKED.is_file():
        return None
    return [
        line.strip()
        for line in PARKED.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


if __name__ == "__main__":
    status, detail = run()
    print(f"{status}: {detail}")
    raise SystemExit(0 if status != "FAIL" else 1)
