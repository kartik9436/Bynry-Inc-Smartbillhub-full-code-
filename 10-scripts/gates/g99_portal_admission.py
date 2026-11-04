#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-3931 — NFR-39's connection budget and per-tenant rate
#           covered guest_api.py 15/15 and api.py 8/62, and all eight of those
#           eight are AllowAny. Not one of the fifty-four AUTHENTICATED portal
#           endpoints carried either — the traffic NFR-38 counts and the
#           traffic guards.py's own docstring was written about.
# Rules:    NFR-38 (500 concurrent portal users, "guests and signed-in
#           customers together") · NFR-39 (three isolations, "each a build
#           task, not an aspiration": its own queue and worker, its own
#           connection budget, its own rate limits per tenant as well as per
#           address) · NFR-41 (the guest surface is the cheapest thing) ·
#           CLAUDE.md hard-won law 7 (proven RED first, in the harness that
#           will run it — DEF-GOV-3733)
# Tests:    selftest() below
# Impacts:  06-backend/apps/portal/api.py · guest_api.py — every new endpoint
# ───────────────────────────────────────────────────────
"""G99 — every portal endpoint carries the connection budget.

WHY THIS GATE EXISTS
--------------------
`portal_admission` is a per-view DECORATOR, and `apps/portal/api.py`'s own
convention — stated twice in its comments, for good shared-tree reasons — is
that a new wave APPENDS `urlpatterns += [...]` at the END of the file. A lane
adding an endpoint copies the block above it. For fifty-four of sixty-two
endpoints that block carried no guard, so **forgetting was the default
outcome, not an accident**, and an endpoint shipped without the budget is
indistinguishable from one that has it: nothing fails, nothing logs, and the
protection is simply absent under the load it was written for.

That is the same absence hard rule 8's `DEF-CUS-3653` clause records one
module over — *an absence is invisible to every check this repo has* — and the
answer is the same: make the absence FAIL.

WHAT IT READS, AND WHY WITH `ast`
---------------------------------
The decorator list of every function that carries `@api_view`, parsed rather
than grepped. A grep for `portal_admission` would pass on the four docstrings
and comments in these files that EXPLAIN the guard — the false positive G78's
own header warns about (`DEF-741`'s shape: a sentence explaining a rule must
not trip the check that enforces it).

WHAT IT DOES NOT CHECK, STATED SO NOBODY ASSUMES OTHERWISE
----------------------------------------------------------
It does not check the RATE. `PortalSignedInThrottle`'s `3000/min` is a
deliberately loose ceiling on abuse, derived and not measured, and the figure
that would actually bound it is `NFR-42`'s load case — 500 concurrent portal
users with the back office working — which nothing yet runs. A gate asserting
an unmeasured number would be a check that cannot fail usefully.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EDGES = (
    "06-backend/apps/portal/api.py",
    "06-backend/apps/portal/guest_api.py",
    # CR-189-BRC10 — the locked-out email change's five anonymous routes.
    "06-backend/apps/portal/email_update_api.py",
)


def _decorator_names(fn: ast.FunctionDef) -> list[str]:
    names = []
    for dec in fn.decorator_list:
        node = dec.func if isinstance(dec, ast.Call) else dec
        names.append(node.attr if isinstance(node, ast.Attribute) else getattr(node, "id", ""))
    return names


def unguarded(source: str) -> list[str]:
    """Endpoint function names that carry `@api_view` and not `@portal_admission`."""
    missing = []
    for node in ast.parse(source).body:
        if not isinstance(node, ast.FunctionDef):
            continue
        names = _decorator_names(node)
        if "api_view" in names and "portal_admission" not in names:
            missing.append(f"{node.name}:{node.lineno}")
    return missing


def endpoint_count(source: str) -> int:
    return sum(
        1
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and "api_view" in _decorator_names(node)
    )


def selftest() -> bool:
    """It must bite on the defect it was written for, and not on prose.

    ⚠ Proved RED before it was trusted green (law 7): the real `api.py` at
    `b02c68f1` returns fifty-four names from `unguarded()`, which is the
    defect, and zero after the fix.
    """
    guarded = (
        "@api_view(['GET'])\n"
        "@permission_classes([IsPortalCustomer])\n"
        "@throttle_classes([PortalSignedInThrottle])\n"
        "@portal_admission\n"
        "def home(request):\n    return None\n"
    )
    bare = (
        "@api_view(['GET'])\n"
        "@permission_classes([IsPortalCustomer])\n"
        "def bills(request):\n    return None\n"
    )
    # A docstring and a comment that NAME the guard must not satisfy it — the
    # whole reason this reads `ast` and not the file's text.
    prose = (
        '"""Everything here is behind portal_admission."""\n'
        "# portal_admission bounds this module.\n" + bare
    )
    not_an_endpoint = "@portal_admission\ndef helper(request):\n    return None\n"
    return (
        unguarded(guarded) == []
        and [n.split(":")[0] for n in unguarded(bare)] == ["bills"]
        and [n.split(":")[0] for n in unguarded(prose)] == ["bills"]
        and unguarded(not_an_endpoint) == []
        and endpoint_count(guarded + bare) == 2
    )


def run() -> tuple[str, str]:
    present = [p for p in EDGES if (REPO / p).is_file()]
    if not present:
        return "SKIP", "the portal's edge files are not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a guarded endpoint from a bare one, "
            "so its verdict is worthless (DEF-182)"
        )
    problems: list[str] = []
    total = 0
    for rel in present:
        source = (REPO / rel).read_text(encoding="utf-8")
        total += endpoint_count(source)
        for name in unguarded(source):
            problems.append(f"{rel}:{name} has no @portal_admission")
    if problems:
        return "FAIL", (
            f"{len(problems)} portal endpoint(s) carry no connection budget (NFR-39) — "
            + " | ".join(problems[:5])
            + (f" (+{len(problems) - 5} more)" if len(problems) > 5 else "")
        )
    return "PASS", (
        f"{total} portal endpoint(s) across {len(present)} edge file(s), every one behind the "
        "connection budget; self-test: a bare endpoint bites and a docstring naming the guard does not satisfy it"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
