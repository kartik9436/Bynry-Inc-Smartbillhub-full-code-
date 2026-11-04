#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2722 (2026-08-31) — `apps/customers/sample_data.py` swallowed a
#           row's refusal and carried on inside ONE PostgreSQL transaction, so
#           eight of the fourteen sample blocks failed, seven of them only as a
#           cascade off the first. Fixed with 25 savepoints and a same-file
#           test.
#           DEF-2795 (2026-08-31) — THE SAME SHAPE IN SIX MORE SEEDERS, 20
#           sites, which the same-file test could not see. This gate is that
#           defect's own stated prevention.
# Rules:    CLAUDE.md hard-won law 14 (a failed statement poisons the whole
#           PostgreSQL transaction; a SAVEPOINT is the ONLY option, and the
#           default suite is in-memory SQLite so the broken version passes
#           green) · law 7 (prove a guard RED first) · BR-TEN-063 (the sample
#           plant is atomic per module)
# ───────────────────────────────────────────────────────
"""G66 — every catch-and-continue in a sample seeder opens a SAVEPOINT.

WHY THIS IS A GATE AND NOT A TEST
---------------------------------
DEF-2722's guard is `06-backend/tests/test_def2722_sample_plant_survives.py
::test_def2722_tc6__every_catch_and_continue_in_the_seeder_opens_a_savepoint`.
It walks ONE FILE — `apps/customers/sample_data.py` — and it went red naming
all 25 sites there by line, which is exactly what a fixing lane needs.

**It looks at one file, and nothing looked at the other seven.** DEF-2795
measured the rest on 2026-08-31: billing 8 sites, metering 5, payments 3,
identity 2, assets 1, rating 1 — **20 more**, every one of them running inside
`apps.tenancy.sample_data.seed_sample_data`'s per-module `with
transaction.atomic()` (BR-TEN-063), which is the whole precondition of law 14.

A per-file test can never give a fixing lane the list. A directory gate can, so
this is a gate.

WHAT IT CHECKS
--------------
For every `06-backend/apps/*/sample_data.py`: find each `except`, walk back to
the matching `try:` at the same indent, skip the handlers that re-raise, and
FAIL when the `try` body opens no `transaction.atomic()`.

THE ONE EXEMPTION, AND WHY IT IS SAFE TO STATE STATICALLY
---------------------------------------------------------
A `try` whose body does nothing but IMPORT is exempt. An import touches no
database and therefore cannot poison a transaction, and the three sites this
covers are all of the form

    try:
        metering_services = import_module("apps.metering.services")
    except ImportError:
        return None

The rule is deliberately narrow so it cannot be stretched: every statement in
the body must be an `import` / `from … import`, or an assignment whose value is
exactly a call to `import_module(...)`. A body that imports **and then calls
something** is NOT exempt — `apps/billing/sample_data.py`'s
`customers_sample.sample_account_ids()` is an import followed by a query, and
it is guarded.

`apps/tenancy/sample_data.py` IS EXCLUDED, EXPLICITLY AND WITH A REASON
-----------------------------------------------------------------------
That file is the ORCHESTRATOR: its own `except` clauses sit partly OUTSIDE the
per-module `atomic()` it opens, so law 14's argument does not carry there
without reading each of its 5 sites one at a time. DEF-2795 says so in those
words and excludes them from its count of 20.

**A gate that quietly skipped the orchestrator would be a green check that
cannot fail on the file most likely to need it**, so the exclusion is named
here, printed in the PASS line, and its site count is pinned: if the number of
unguarded sites in that file MOVES, this gate fails and asks for a decision.
Pinned at 5, measured 2026-08-31 (lines 841, 929, 1668, 1685, 1762).

PROVED RED (law 7)
------------------
Run over the pre-fix blobs read straight out of `HEAD` — the gate's own walk,
the real pre-fix content, nothing written — it reported, verbatim:

    G66 over HEAD (pre-fix): FAIL — 17 catch-and-continue site(s) with no SAVEPOINT
        apps/assets/sample_data.py:711
        apps/billing/sample_data.py:166,307,457,459,675
        apps/identity/sample_data.py:166,206
        apps/metering/sample_data.py:1019,2544,2617,3155,3276
        apps/payments/sample_data.py:127,206,500
        apps/rating/sample_data.py:909

**17 AND NOT DEF-2795's 20, AND THE DIFFERENCE IS THE EXEMPTION ABOVE, NOT A
MISS.** That defect counted with DEF-2722's `tc6` walk, which has no exemption,
so its 20 include `apps/billing/sample_data.py:271, 734, 766` — three bodies
that do nothing but import a module. An import issues no statement to the
database and cannot abort a transaction, so wrapping those three in a savepoint
would be cargo cult rather than law 14. **All 17 that CAN poison a transaction
are guarded; the 3 that cannot are named here rather than left as a silent
difference between a defect's figure and a gate's.**

The self-sabotage below re-proves the walk on every run, so a change that made
it unable to find anything would FAIL rather than report a clean tree.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEEDERS = sorted((ROOT / "06-backend" / "apps").glob("*/sample_data.py"))

#: The orchestrator — excluded with a reason, and its site count PINNED so the
#: exclusion cannot quietly grow. See the docstring.
ORCHESTRATOR = "apps/tenancy/sample_data.py"
ORCHESTRATOR_SITES = 5

_EXCEPT = re.compile(r"^\s*except\b")
_IMPORT_ONLY = re.compile(
    r"^\s*(?:import\s+\S.*"
    r"|from\s+[.\w]+\s+import\s+\S.*"
    r"|[A-Za-z_]\w*\s*=\s*import_module\([^()]*\))\s*$"
)


def _rel(path: pathlib.Path) -> str:
    return str(path.relative_to(ROOT / "06-backend"))


def unguarded(source: str) -> list[int]:
    """Every catch-and-continue line number (1-based) with no SAVEPOINT."""
    lines = source.split("\n")
    found: list[int] = []
    for index, line in enumerate(lines):
        if not _EXCEPT.match(line):
            continue
        indent = len(line) - len(line.lstrip())
        back = index - 1
        while back >= 0:
            candidate = lines[back]
            if candidate.strip() == "try:" and (len(candidate) - len(candidate.lstrip())) == indent:
                break
            back -= 1
        if back < 0:
            continue
        body = lines[back + 1 : index]
        # A handler that re-raises is not a catch-and-continue: the transaction
        # dies either way and nothing after it runs.
        if any(one.strip() == "raise" for one in lines[index + 1 : index + 4]):
            continue
        if any("transaction.atomic()" in one for one in body):
            continue
        # The narrow exemption — an import cannot poison a transaction.
        statements = [one for one in body if one.strip() and not one.strip().startswith("#")]
        if statements and all(_IMPORT_ONLY.match(one) for one in statements):
            continue
        found.append(index + 1)
    return found


def findings() -> tuple[list[str], int]:
    """`(violations, orchestrator_site_count)`."""
    violations: list[str] = []
    orchestrator = 0
    for path in SEEDERS:
        rel = _rel(path)
        sites = unguarded(path.read_text(encoding="utf-8"))
        if rel == ORCHESTRATOR:
            orchestrator = len(sites)
            continue
        if sites:
            violations.append(f"{rel}:{','.join(str(one) for one in sites)}")
    return violations, orchestrator


#: The self-sabotage — a body that catches and continues with no savepoint. If
#: the walk above ever stops finding this, it has stopped working and a clean
#: tree means nothing (DEF-182: a check that cannot fail is worse than none).
_SABOTAGE = """
def seed():
    for row in rows:
        try:
            models.Thing.objects.create(**row)
        except Exception:
            continue
"""

_SABOTAGE_GUARDED = """
def seed():
    for row in rows:
        try:
            with transaction.atomic():
                models.Thing.objects.create(**row)
        except Exception:
            continue
"""


def run() -> tuple[str, str]:
    if unguarded(_SABOTAGE) != [6]:
        return (
            "FAIL",
            "the self-sabotage was NOT detected — this gate's own walk is broken, so a "
            "clean tree proves nothing (law 7, DEF-182)",
        )
    if unguarded(_SABOTAGE_GUARDED):
        return (
            "FAIL",
            "the guarded self-sabotage was reported as a violation — this gate would fire "
            "on correct code, which is a gate somebody switches off",
        )

    violations, orchestrator = findings()
    if violations:
        count = sum(len(one.split(":")[1].split(",")) for one in violations)
        return (
            "FAIL",
            f"{count} catch-and-continue site(s) with no SAVEPOINT (law 14): "
            + " · ".join(violations)
            + ". A nested `transaction.atomic()` is the ONLY thing that lets these "
            "`except` clauses continue on PostgreSQL, and the default suite is "
            "in-memory SQLite, so the broken version passes green everywhere",
        )
    if orchestrator != ORCHESTRATOR_SITES:
        return (
            "FAIL",
            f"{ORCHESTRATOR} is EXCLUDED from this gate with a stated reason (its "
            f"`except` clauses sit partly outside the per-module `atomic` it opens), and "
            f"its unguarded-site count moved {ORCHESTRATOR_SITES} -> {orchestrator}. That "
            "is a decision, not a drift: read each new site and either guard it or move "
            "the pin in the same commit",
        )
    checked = len(SEEDERS) - 1
    return (
        "PASS",
        f"every catch-and-continue in {checked} sample seeder(s) opens a SAVEPOINT "
        f"(law 14); {ORCHESTRATOR} is excluded with a stated reason and its "
        f"{orchestrator} site(s) are pinned; 2/2 self-sabotages behaved as stated",
    )


def main() -> int:
    status, detail = run()
    print(f"G66 seeder-savepoints: {status} — {detail}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
