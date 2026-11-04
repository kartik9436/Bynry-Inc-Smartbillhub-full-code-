#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-004 (EP-INT-01) · CR-069 wave B task B6 — the gate the
#           module overview promises: no `POST /integrations/{key}/send`
#           anywhere in a URLconf.
# Rules:    BR-INT-008 (integrations SENDS / IMPORTS / EXPORTS nothing itself
#           — connections are config READ by the owning flows: the
#           dispatcher sends mail, payments imports files, ledger exports) ·
#           ⚠ BR-INT-008 AMENDED 2026-10-02 (PO, *"B · Keep it and change the
#           rule, because it only passes the job on."*): the module may HAND an
#           export job to the runner, carrying no figure and no file — the ONE
#           route that does so is named in RULED_EXCEPTIONS below ·
#           CLAUDE.md hard-won law 7 (proven RED first — see the docstring)
# Tests:    selftest() below
# Impacts:  every `urlpatterns` under 06-backend
# ───────────────────────────────────────────────────────
"""G79 — no URLconf mounts a `send` (or `import`, `export`) route under `/integrations`.

WHY THIS GATE EXISTS
--------------------
BR-INT-008 draws the line the module lives by: *"Integrations sends/imports/
exports NOTHING itself — connections are config READ by the owning flows."*
The dispatcher sends a bill through the mailbox connection; payments imports
the bank file through the lockbox connection; ledger hands the export to the
accounting target. A `POST /integrations/{key}/send` is the first step of
the module becoming a second dispatcher, and the overview says a gate stops
it. `test` (one real message, BR-INT-019) and `run` (one manual attempt at
an operation the manifest declares) are the module's own and are allowed.

WHAT IT READS
-------------
Every `path(...)` / `re_path(...)` string literal in every `.py` under
`06-backend` whose module carries `urlpatterns`. A route is refused when it
starts with `integrations/` (or `/integrations/`) and its last segment is
one of the forbidden verbs. Comments and docstrings are not routes and are
not read: only the first string argument of a `path()` call is.

A RULED EXCEPTION IS NAMED HERE, BY FILE AND BY ROUTE — NEVER BY VERB
-----------------------------------------------------------------------
⚠ **ADDED 2026-10-02, AND IT IS THE ONLY WAY THIS GATE GOES GREEN OVER A
FORBIDDEN VERB.** `POST /integrations/{key}/export` (`CR-069` wave J) was red
here from the day it landed. The PO was shown a clerk sending July's journal to
QuickBooks from that door and ruled, verbatim: *"B · Keep it and change the
rule, because it only passes the job on."* `BR-INT-008` is amended to match:
integrations may hand an export job to the runner; the door carries no figure
and no file itself (what is IN the file is Runbooks', `BR-INT-054`).

So the exception is that ONE route string in that ONE file, with the ruling
quoted beside it in `RULED_EXCEPTIONS`. `export` stays in `FORBIDDEN_VERBS`:
the same route mounted from any other URLconf is still red, `send` is still red
everywhere, and the self-test proves both. Removing `export` from the verb list
would have been the weakening this gate exists to refuse. And the exception
expires loudly — if the route stops being mounted, the entry is STALE and the
gate fails until it is removed, so a ruling cannot outlive the thing it ruled
on. **A future exception is a new PO ruling and a new entry here, never a
shorter verb list.**

PROVEN RED FIRST (law 7, 2026-09-03)
------------------------------------
With `path("integrations/<str:key>/send", send)` written into
`apps/integrations/api.py` the gate reported
    FAIL: 06-backend/apps/integrations/api.py mounts 'integrations/<str:key>/send' — the
    module sends nothing itself (BR-INT-008)
and with the line removed it went green. `selftest()` replays that on an
in-memory body and `run()` refuses to report anything until it has.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
BACKEND = REPO / "06-backend"
FORBIDDEN_VERBS = frozenset({"send", "import", "export", "dispatch", "deliver"})

#: `(URLconf relative to the repo, exact route string)` → the ruling that
#: permits it. See the docstring; exact match only, and a stale entry FAILS.
RULED_EXCEPTIONS: dict[tuple[str, str], str] = {
    ("06-backend/apps/integrations/api.py", "integrations/<str:key>/export"): (
        "BR-INT-008 amended 2026-10-02, PO: \"B · Keep it and change the rule, because it "
        "only passes the job on.\" — the door hands an export job to the runner; no figure, no file"
    ),
}


def _routes_in(source: str) -> list[str]:
    """Every first-argument string of a `path()` / `re_path()` call."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        name = callee.id if isinstance(callee, ast.Name) else callee.attr if isinstance(callee, ast.Attribute) else None
        if name not in ("path", "re_path") or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            found.append(first.value)
    return found


def findings_in(
    source: str, *, where: str, exceptions: dict[tuple[str, str], str] | None = None
) -> list[str]:
    ruled = RULED_EXCEPTIONS if exceptions is None else exceptions
    problems: list[str] = []
    for route in _routes_in(source):
        clean = route.strip("/").rstrip("$").lstrip("^")
        if not clean.startswith("integrations/"):
            continue
        if (where, route) in ruled:
            continue
        last = clean.split("/")[-1].strip("<>").split(":")[-1]
        if last in FORBIDDEN_VERBS:
            problems.append(
                f"{where} mounts {route!r} — the module sends nothing itself (BR-INT-008); "
                "the owning flow reads the connection and does the sending"
            )
    return problems


def _urlconfs() -> list[Path]:
    found: list[Path] = []
    for path in sorted(BACKEND.rglob("*.py")):
        if "tests" in path.parts or "migrations" in path.parts or ".venv" in path.parts:
            continue
        try:
            if "urlpatterns" in path.read_text(encoding="utf-8"):
                found.append(path)
        except UnicodeDecodeError:
            continue
    return found


_CLEAN = 'urlpatterns = [path("integrations", grid), path("integrations/<str:key>/test", test), path("integrations/<str:key>/run", run)]\n'
_RED = 'urlpatterns = [path("integrations", grid), path("integrations/<str:key>/send", send)]\n'


_EXPORT = 'urlpatterns = [path("integrations/<str:key>/export", departure)]\n'
_RULED_AT = ("selftest/ruled.py", "integrations/<str:key>/export")


def selftest() -> bool:
    if findings_in(_CLEAN, where="selftest"):
        return False
    red = findings_in(_RED, where="selftest")
    if not (len(red) == 1 and "'integrations/<str:key>/send'" in red[0]):
        return False
    ruled = {_RULED_AT: "selftest ruling"}
    # The ruled route in its ruled file passes …
    if findings_in(_EXPORT, where="selftest/ruled.py", exceptions=ruled):
        return False
    # … the SAME route in any other file is still red (exact file, not verb) …
    if len(findings_in(_EXPORT, where="selftest/other.py", exceptions=ruled)) != 1:
        return False
    # … and a /send in the ruled file is still red (exact route, not file).
    return len(findings_in(_RED, where="selftest/ruled.py", exceptions=ruled)) == 1


def run() -> tuple[str, str]:
    if not selftest():
        return "FAIL", "the gate's own self-test does not hold — it cannot see a /send route (DEF-182)"
    files = _urlconfs()
    if not files:
        return "FAIL", "no URLconf found under 06-backend — nothing to guard"
    problems: list[str] = []
    routes = 0
    mounted: set[tuple[str, str]] = set()
    for path in files:
        source = path.read_text(encoding="utf-8")
        where = str(path.relative_to(REPO))
        found = _routes_in(source)
        routes += sum(1 for one in found if one.strip("/").startswith("integrations"))
        mounted.update((where, one) for one in found)
        problems.extend(findings_in(source, where=where))
    problems.extend(
        f"RULED_EXCEPTIONS is STALE: {where} no longer mounts {route!r} — remove the entry; "
        "a ruling must not outlive the route it ruled on"
        for (where, route) in RULED_EXCEPTIONS
        if (where, route) not in mounted
    )
    if problems:
        return "FAIL", " | ".join(problems)
    return "PASS", (
        f"{routes} /integrations route(s) across {len(files)} URLconf(s), none of them a send, "
        f"import or export except {len(RULED_EXCEPTIONS)} ruled (the export hand-over, "
        "BR-INT-008 amended 2026-10-02 — no figure, no file); self-test: /send bites, and the "
        "ruled /export bites in any other file"
    )


def main() -> int:
    status, note = run()
    print(f"G79 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
