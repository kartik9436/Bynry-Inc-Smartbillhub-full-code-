#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects: DEF-CWP-3923 — three portal endpoints lost their decorators in a
#          merge and answered 500 to every request, with every test green.
# Rules:   BR-CWP-011 (the portal edge is a SEPARATE file with its own
#          authentication class and its own permission class) · BR-CWP-010
#          (every read intersected with the session's account set) ·
#          CLAUDE.md hard-won law 2 (built is not wired) · law 6 (no gate
#          looks at rendered output — so this one looks at the ROUTE TABLE) ·
#          law 7 (proven RED first, through the registry run_gates uses)
# Tests:   selftest() below
# Impacts: 06-backend/apps/*/api.py — every routed view in the product
# ───────────────────────────────────────────────────────
"""G97 — a function in a URL table is a DECORATED view, not a bare function.

WHAT HAPPENED, BECAUSE THE SHAPE MATTERS MORE THAN THE RULE
-----------------------------------------------------------
Two lanes appended views to `apps/portal/api.py` in the same wave. A law-11
re-derivation rebuilt the file as *the pinned tip plus my own hunks*, and three
decorator stacks were not in anybody's hunks — they were between two functions,
which is exactly where a subtraction is invisible. What landed was:

    return _no_store(Response(selectors.plan_offer(account, today=date.today())))
    def account_readings(request: Any, account_id: str) -> Response:

`account_usage`, `account_readings` and `account_equipment` were routed in
`urlpatterns` and carried **no `@api_view`, no authentication class and no
permission class**. Django called them with a raw `WSGIRequest`, so
`_account_in_set` reached for `principal.tenant_id` on `None` and every request
answered **500**.

⚠ **AND EVERY CHECK IN THIS REPOSITORY WAS GREEN.** `ast.parse` is happy — a
bare function is valid Python. `ruff` is happy. `tsc` never sees it. The three
stories' 40 backend tests are happy, **because they call `selectors.*`
directly** rather than the endpoint, which is the normal and correct thing for
a read test to do. `G82` checks the SCREEN register, not the URL table. Law
11's own checks pass, for the reason its newest clause records: the deletion is
not in the diff at all.

**The only thing that found it was running the product and asking for the
page.** That is law 6 — *diff the running app* — and this gate exists because
that step is manual and happens once a wave, while a merge happens twenty
times a day.

WHAT IT READS
-------------
Every `apps/*/api.py` and `apps/*/*_api.py`. It finds the names routed in a
`path(...)`/`re_path(...)` call, then asserts each one that is defined as a
module-level function in that same file carries an `@api_view` decorator.

⚠ **THREE THINGS IT DELIBERATELY DOES NOT DO.** It does not check WHICH
authentication or permission classes are used — that is `BR-CWP-011`'s
business and `G91`'s. It does not follow a name imported from another module,
because the decorator lives with the definition. And it does not look at
class-based views, which carry their permissions differently; a routed name
that resolves to a class is skipped by name.

PROVEN RED FIRST (law 7, 2026-09-05)
------------------------------------
Through `run_gates`' registry, not `__main__` (DEF-GOV-3733). With the three
decorator stacks removed again — the exact state the merge left — the registry
entry reported

    FAIL: apps/portal/api.py:870 account_usage is routed but carries no
    @api_view — Django will call it with a raw request and it will answer 500
    (+2 more)

and green with them restored. `selftest()` replays both directions on
in-memory sources and `run()` refuses to report until it has.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
BACKEND = REPO / "06-backend"

#: `path("x", view)` and `re_path(r"x", view)` — the name in the second slot.
ROUTE = re.compile(r"(?:re_)?path\(\s*[a-zA-Z]?[\"'][^\"']*[\"']\s*,\s*(\w+)\s*[,)]")

#: What makes a function a DRF view. `api_view` is the only wrapper this
#: product uses; a bare Django view would need `csrf_exempt` and its own
#: parsing, and there are none.
VIEW_DECORATOR = "api_view"


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Call):
        node = node.func
    return getattr(node, "id", getattr(node, "attr", ""))


def findings(source: str, *, where: str) -> list[str]:
    """`path:line name` for every routed module-level function with no @api_view."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:  # pragma: no cover — another gate's problem
        return [f"{where}: will not parse ({exc.msg})"]
    routed = set(ROUTE.findall(source))
    if not routed:
        return []
    #: A routed name that is a CLASS carries its permissions differently and is
    #: not this gate's business.
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    out: list[str] = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in routed or node.name in classes:
            continue
        names = {_decorator_name(d) for d in node.decorator_list}
        if VIEW_DECORATOR in names:
            continue
        out.append(
            f"{where}:{node.lineno} {node.name} is routed but carries no @{VIEW_DECORATOR} — "
            "Django will call it with a raw request and it will answer 500"
        )
    return out


CLEAN = '''
@api_view(["GET"])
@permission_classes([IsPortalCustomer])
def bills(request):
    return Response({})

urlpatterns = [path("portal/bills", bills)]
'''
RED = '''
def bills(request):
    return Response({})

urlpatterns = [path("portal/bills", bills)]
'''
#: A routed CLASS is skipped — it carries its permissions as attributes.
CLASS_VIEW = '''
class Thing:
    pass

urlpatterns = [path("thing", Thing)]
'''
#: A function that is NOT routed needs no decorator.
HELPER = '''
def _helper(request):
    return None

@api_view(["GET"])
def bills(request):
    return Response({})

urlpatterns = [path("portal/bills", bills)]
'''


def selftest() -> bool:
    return (
        not findings(CLEAN, where="a.py")
        and any("carries no @api_view" in one for one in findings(RED, where="a.py"))
        and not findings(CLASS_VIEW, where="a.py")
        and not findings(HELPER, where="a.py")
    )


def run() -> tuple[str, str]:
    if not BACKEND.is_dir():
        return "SKIP", "06-backend is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a bare routed function "
            "from a decorated view, so its verdict is worthless (DEF-182)"
        )
    problems: list[str] = []
    files = 0
    for path in sorted(BACKEND.glob("apps/*/*api*.py")):
        if "__pycache__" in path.parts:
            continue
        files += 1
        problems.extend(
            findings(path.read_text(encoding="utf-8"), where=str(path.relative_to(BACKEND)))
        )
    if problems:
        return "FAIL", problems[0] + (f" (+{len(problems) - 1} more)" if len(problems) > 1 else "")
    return "PASS", (
        f"{files} url table(s) read; every routed function carries @{VIEW_DECORATOR}; "
        "self-test: a bare routed function bites, a decorated one does not, and neither a "
        "routed class nor an undecorated helper is a finding"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 0 if status in {"PASS", "SKIP"} else 1


if __name__ == "__main__":
    sys.exit(main())
