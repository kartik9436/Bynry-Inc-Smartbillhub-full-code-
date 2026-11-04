#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-010 (EP-CWP-02) — track anything. CR-068 §13 (the gate the
#           plan called G77; G77–G91 were taken by the time it landed, so it is
#           G92 — the number is the REGISTER's at push time, never the plan's,
#           DEF-CWP-3734)
# Rules:    BR-CWP-021 (a guest sees an amount and a status, NEVER a person) ·
#           BR-CWP-024 (a public reference lookup returns PROGRESS AND NEVER
#           DATA) · BR-CWP-019/020 (the one masked exception) ·
#           CLAUDE.md hard-won law 7 (proven RED first, in the harness that
#           runs it)
# Tests:    selftest() below · 06-backend/apps/portal/guest_fields.py (the data)
# Impacts:  06-backend/apps/portal/selectors.py · seams/customers_seam.py
# ───────────────────────────────────────────────────────
"""G92 — a stranger is told only what somebody decided a stranger may be told.

WHY THIS GATE EXISTS
--------------------
`BR-CWP-024` is *"progress and never data"*, and the thing that breaks it is
never a decision. It is a serialiser gaining a field for a signed-in screen,
five files away, on a function the guest edge also calls. `request_progress_view`
already says so in its own docstring — *"a field that is served and merely not
drawn is still served"* — and a docstring is a note, not the guarantee (law 1).

WHAT IT READS, AND THE THREE THINGS IT REFUSES
-----------------------------------------------
`apps/portal/guest_fields.py` is parsed with `ast` (never imported — the gate
suite is stdlib-only) for `GUEST_RESPONSES` and `NEVER_ON_A_GUEST_RESPONSE`.
Then, for each declared `<file>::<function>`:

  1. **The function must exist.** A declaration naming a function nobody wrote,
     or a function that was renamed out from under the declaration, is a rule
     guarding nothing — `DEF-524`'s exact shape, where a hardcoded path
     outlived the file it named and reported PASS through six UI defects.
  2. **Every key of every dict the function RETURNS is in its allow-list.** Not
     every dict in the file: the ones that leave it. A key nobody listed is a
     field nobody decided a stranger may see.
  3. **No key anywhere in the function is a person-shaped name**, whatever the
     allow-list says. Belt and braces: clause 2 is the rule and this is what
     still bites when somebody widens the allow-list without thinking.

⚠ **A ROW DECLARED `None` IS NOT YET BUILT AND IS SKIPPED BY CLAUSES 2 AND 3,
BUT NOT BY CLAUSE 1** — if the function exists, it must have an allow-list. That
is what stops the wave that builds quick pay from also writing the list that
permits its own leak.

⚠ **WHAT THIS GATE DOES NOT DO.** It does not read INPUT. A guest form
legitimately receives a name, an email and a phone — somebody typing their own
details into `CWP-047` — so `applications.py` is not declared and must not be.
The rule is about what the product TELLS a stranger.

PROVEN RED FIRST (law 7, 2026-09-04) — AND THROUGH `run_gates`, NOT `__main__`
------------------------------------------------------------------------------
`DEF-GOV-3733`: a guard shown red through `python3 <gate>.py` exercises
`__main__`, which is a path the suite never uses. So this gate was driven red on
the REAL tree by adding `"email": row.applicant_email` to
`customers_seam.request_progress_view` — the actual body `POST /public/track`
returns — and then called the way `run_gates` calls it, by importing the
registry and invoking `module.run()`. Verbatim, and it is worth reading that it
fired TWICE for one field:

    FAIL: G92 guest-leaks-nothing :: seams/customers_seam.py::
    request_progress_view returns 'email', which its allow-list does not name —
    a guest is told progress and never data, and a field that is served and
    merely not drawn is still served (BR-CWP-024) | seams/customers_seam.py::
    request_progress_view names 'email', which may never appear on a guest
    response — a guest sees an amount and a status, never a person (BR-CWP-021)

The field was reverted and the same dispatch reported PASS. The other clauses
are driven red on in-memory sources by `selftest()`, which `run()` calls before
it reports anything; their verbatim failures are in its docstring.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
PORTAL = REPO / "06-backend" / "apps" / "portal"
DECLARATION = PORTAL / "guest_fields.py"


def read_declaration(source: str) -> tuple[dict[str, tuple[str, ...] | None], set[str], list[str]]:
    """(responses, never-names, problems) from `guest_fields.py`'s source."""
    responses: dict[str, tuple[str, ...] | None] = {}
    never: set[str] = set()
    problems: list[str] = []
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        value = node.value
        if "GUEST_RESPONSES" in names and isinstance(value, ast.Dict):
            for key, allowed in zip(value.keys, value.values):
                if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                    problems.append("GUEST_RESPONSES holds a key that is not a literal string")
                    continue
                if isinstance(allowed, ast.Constant) and allowed.value is None:
                    responses[key.value] = None
                elif isinstance(allowed, (ast.Tuple, ast.List)):
                    fields = tuple(
                        element.value
                        for element in allowed.elts
                        if isinstance(element, ast.Constant) and isinstance(element.value, str)
                    )
                    if len(fields) != len(allowed.elts):
                        problems.append(f"{key.value}: its allow-list holds something that is not a string")
                    responses[key.value] = fields
                else:
                    problems.append(f"{key.value}: allow-list must be a tuple of strings or None")
        if "NEVER_ON_A_GUEST_RESPONSE" in names and isinstance(value, (ast.Tuple, ast.List)):
            never = {
                element.value
                for element in value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            }
    return responses, never, problems


def _function(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node  # type: ignore[return-value]
    return None


def _returned_keys(function: ast.AST) -> set[str]:
    """Every string key of every dict literal this function RETURNS.

    Nested dicts inside a returned dict are walked too — `{"customer": {"email":
    …}}` is exactly the shape a leak arrives in, and a check that read only the
    top level would pass over it.
    """
    keys: set[str] = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Return) and node.value is not None:
            for inner in ast.walk(node.value):
                if isinstance(inner, ast.Dict):
                    for key in inner.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            keys.add(key.value)
    return keys


def _all_keys(function: ast.AST) -> set[str]:
    keys: set[str] = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
    return keys


def check(declaration: str, sources: dict[str, str]) -> list[str]:
    """(guest_fields source, relative-path → source) → the problems."""
    responses, never, problems = read_declaration(declaration)
    if not responses:
        problems.append(
            "guest_fields.py declares no guest response at all — an empty allow-list permits "
            "everything, which is the opposite of what BR-CWP-024 asks for"
        )
    if not never:
        problems.append("guest_fields.py declares no NEVER_ON_A_GUEST_RESPONSE names")
    for declared, allowed in sorted(responses.items()):
        if "::" not in declared:
            problems.append(f"{declared!r} is not <file>::<function>")
            continue
        rel, _, function_name = declared.partition("::")
        source = sources.get(rel)
        if source is None:
            problems.append(f"{declared}: {rel} is not a file under apps/portal — a rule guarding nothing (DEF-524)")
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:  # pragma: no cover
            problems.append(f"{rel}: does not parse ({exc.msg})")
            continue
        function = _function(tree, function_name)
        if function is None:
            if allowed is None:
                continue  # declared ahead of the wave that builds it — the point of the row
            problems.append(
                f"{declared}: no such function. A declaration naming a function nobody wrote, or one "
                "that was renamed out from under it, guards nothing (DEF-524)"
            )
            continue
        if allowed is None:
            problems.append(
                f"{declared}: the function EXISTS and its allow-list is still None — the wave that "
                "builds a guest response may not also be the wave that decides what it may disclose "
                "(BR-CWP-024)"
            )
            continue
        for key in sorted(_returned_keys(function) - set(allowed)):
            problems.append(
                f"{declared} returns {key!r}, which its allow-list does not name — a guest is told "
                "progress and never data, and a field that is served and merely not drawn is still "
                "served (BR-CWP-024)"
            )
        for key in sorted(_all_keys(function) & never):
            problems.append(
                f"{declared} names {key!r}, which may never appear on a guest response — a guest sees "
                "an amount and a status, never a person (BR-CWP-021)"
            )
    return problems


# ── the three RED proofs, replayed on in-memory sources every run ───────────
_DECL = (
    'GUEST_RESPONSES = {"seams/customers_seam.py::request_progress_view": ("series", "status")}\n'
    'NEVER_ON_A_GUEST_RESPONSE = ("email", "name")\n'
)
_CLEAN = 'def request_progress_view(row):\n    return {"series": "request", "status": row.state}\n'
_RED_EXTRA = (
    'def request_progress_view(row):\n'
    '    return {"series": "request", "status": row.state, "email": row.email}\n'
)
_RED_NESTED = (
    'def request_progress_view(row):\n'
    '    return {"series": "request", "status": row.state, "who": {"name": row.name}}\n'
)
_RED_MISSING = 'def something_else(row):\n    return {}\n'
_DECL_UNBUILT = (
    'GUEST_RESPONSES = {"selectors.py::bill_lookup": None}\n'
    'NEVER_ON_A_GUEST_RESPONSE = ("email",)\n'
)
_RED_UNDECLARED = 'def bill_lookup(tenant_id):\n    return {"amount": "1.00"}\n'


def selftest() -> bool:
    """Drive all three clauses RED, then prove the clean source is green.

    Verbatim, when each was first run with the fault put back in (law 7 — and
    then re-run through `run_gates.py`, the harness that will actually call
    `run()`; `DEF-GOV-3733`):

        FAIL: seams/customers_seam.py::request_progress_view returns 'email',
        which its allow-list does not name — a guest is told progress and never
        data, and a field that is served and merely not drawn is still served
        (BR-CWP-024)
        FAIL: seams/customers_seam.py::request_progress_view names 'name',
        which may never appear on a guest response — a guest sees an amount and
        a status, never a person (BR-CWP-021)
        FAIL: seams/customers_seam.py::request_progress_view: no such function.
        A declaration naming a function nobody wrote, or one that was renamed
        out from under it, guards nothing (DEF-524)
        FAIL: selectors.py::bill_lookup: the function EXISTS and its allow-list
        is still None — the wave that builds a guest response may not also be
        the wave that decides what it may disclose (BR-CWP-024)
    """
    extra = check(_DECL, {"seams/customers_seam.py": _RED_EXTRA})
    nested = check(_DECL, {"seams/customers_seam.py": _RED_NESTED})
    missing = check(_DECL, {"seams/customers_seam.py": _RED_MISSING})
    unbuilt = check(_DECL_UNBUILT, {"selectors.py": _RED_UNDECLARED})
    clean = check(_DECL, {"seams/customers_seam.py": _CLEAN})
    return (
        any("returns 'email'" in p for p in extra)
        and any("names 'name'" in p for p in nested)
        and any("no such function" in p for p in missing)
        and any("allow-list is still None" in p for p in unbuilt)
        and not clean
    )


def run() -> tuple[str, str]:
    if not PORTAL.is_dir():
        return "SKIP", "06-backend/apps/portal is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a leaked field from a declared "
            "one, so its verdict is worthless (DEF-182)"
        )
    if not DECLARATION.is_file():
        return "FAIL", (
            "apps/portal/guest_fields.py is missing — what a stranger may be told is declared as "
            "DATA so a gate can read it (BR-CWP-024)"
        )
    sources: dict[str, str] = {}
    for path in sorted(PORTAL.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        sources[str(path.relative_to(PORTAL)).replace("\\", "/")] = path.read_text(encoding="utf-8")
    problems = check(DECLARATION.read_text(encoding="utf-8"), sources)
    if problems:
        return "FAIL", " | ".join(problems[:6]) + (
            f" (+{len(problems) - 6} more)" if len(problems) > 6 else ""
        )
    responses, never, _ = read_declaration(DECLARATION.read_text(encoding="utf-8"))
    built = sum(1 for allowed in responses.values() if allowed is not None)
    return "PASS", (
        f"{len(responses)} guest response(s) declared as data, {built} built so far; every key each "
        f"returns is one its allow-list names, and none of {len(never)} person-shaped names appears "
        "in any of them; self-test: an extra field, a nested person, a renamed function and an "
        "undeclared build all bite"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
