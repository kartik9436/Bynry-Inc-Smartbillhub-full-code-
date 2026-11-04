#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-001 (EP-CWP-01) — the guard in front of the guest surface.
#           CR-068 §13 (the gate the plan called G75; G75–G80 were taken by the
#           time it landed — CR-069 waves A and B, CR-070 — so it is G81; the
#           number is the register's, never the plan's).
# Rules:    BR-CWP-001 (the portal may write rows of exactly SIX kinds — FOUR
#           until 2026-09-04) · BR-CWP-002 (a write outside them is refused at
#           the edge) · BR-CWP-003 (the six are declared AS DATA in
#           write_points.py; one more in code without a row there fails the
#           build) · BR-CWP-103 (the portal's security lives at the door) ·
#           CR-068 R12 (PO 2026-09-03: *"Inlcude all these features - A gate on
#           the four write points."*) · CLAUDE.md hard-won law 7 (proven RED
#           first — see the docstring)
# Tests:    selftest() below · 06-backend/apps/portal/write_points.py (the data)
# Impacts:  06-backend/apps/portal/** — every file, every commit
# ───────────────────────────────────────────────────────
"""G81 — the portal's surface reaches exactly the declared writes, and they are data.

WHY THIS GATE EXISTS
--------------------
The blueprint's rule, verbatim: *"THE PORTAL MAY WRITE IN FOUR PLACES ONLY: a
payment, a service request, a meter reading, its own preferences."* CR-068 §13
says why a person cannot hold it: *"It erodes one reasonable-looking commit at
a time. Nobody ever decides to allow a fifth; a lane just needs one more
field."* And it forbids the cheap version in as many words: *"Must not be a
grep for four table names — that passes on a write reached through a service
that writes something else. Read what the portal's surface can reach, from
`write_points.py`."*

WHAT IT READS, AND WHAT IT REFUSES
----------------------------------
`apps/portal/write_points.py` is parsed with `ast` (never imported — the gate
suite is stdlib-only) for the `WRITE_POINTS` tuple's `kind=` and `function=`
values and the `STAFF_WRITE_MODULES` keys. Then, over every Python file under
`apps/portal/` except migrations, tests and the management command:

  1. **Exactly the six kinds are declared** — `payment`, `service_request`,
     `meter_reading`, `preference`, `contact_detail`, `account_link` — no
     fewer, no more, none twice.
  2. **Every public function in `services.py` is the `function` of one row**,
     and every non-null `function` exists in `services.py`. One more `def`
     there is one more write, and it fails by name.
  3. **No file outside `services.py` and `STAFF_WRITE_MODULES` performs an ORM
     write** — `.objects.create/update/delete/bulk_create/bulk_update/
     get_or_create/update_or_create(...)`, or `.save(...)` / `.delete(...)` on
     anything but `cache`. The guest edge, the portal edge, the selectors and
     the seams are READ-ONLY by construction (BR-CWP-012).
  4. **No file outside those may import another app's `services`** — a write
     reached through somebody else's service is still a write.

THE LIST MOVED ONCE, AND THAT IS THE POINT OF THE GATE
------------------------------------------------------
`REQUIRED_KINDS` said four until 2026-09-04. Two rows were added that day and
they came by DIFFERENT ROUTES, which is what the gate is for — it made both of
them visible as a red build rather than as a diff nobody read:

  * `contact_detail` — a **Product Owner ruling** (`OQ-CWP-1562`): a signed-in
    customer may fix their own email, mobile and postal address, and it updates
    the utility's master records. The first kind here that CHANGES rather than
    creates.
  * `account_link` — a **defect in our own extraction** (`DEF-CWP-3768`).
    `BR-CWP-009` has said *"the set grows only from a customer-to-account link
    or a delegate grant"* since the blueprint, and the same blueprint drew
    `CWP-020`; `BR-CWP-001`'s *"four"* simply never counted it.

**Neither was a lane needing one more field, and that is the distinction this
gate exists to force.** Moving `REQUIRED_KINDS` is a one-line edit; what makes
it a ruling is that the edit cannot be quiet — the build is red until somebody
writes down which of the two routes above the new kind came by.

`settings_service.py` is the back office's write to the portal's OWN settings
row, by a signed-in System Admin and never by the portal surface; it is named
in `STAFF_WRITE_MODULES` with what it may write, and clause 3 lets it through
for that reason and no other.

PROVEN RED FIRST (law 7, 2026-09-03)
------------------------------------
With `def refund_guest_payment(actor, amount): ...` added to `services.py` and
no row for it, the gate reported
    FAIL: 06-backend/apps/portal/services.py defines refund_guest_payment,
    which no row of write_points.py declares — a fifth write point (BR-CWP-003)
and with `models.PortalSettings.objects.create(tenant_id=tenant_id)` written
into `guest_api.py`
    FAIL: 06-backend/apps/portal/guest_api.py:… performs an ORM write
    (.objects.create) — the guest edge is read-only (BR-CWP-001, BR-CWP-012)
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
SERVICES = PORTAL / "services.py"

#: ⚠ **FOUR UNTIL 2026-09-04, SIX SINCE — see the docstring for which of the
#: two arrived by a ruling and which by a defect.** Adding to this set without
#: a decision-log row and a `rule=` on the new WritePoint is the erosion
#: `CR-068` §13 describes; the gate cannot stop that, it can only make it loud.
REQUIRED_KINDS = frozenset(
    {
        "payment",
        "service_request",
        "meter_reading",
        "preference",
        # `OQ-CWP-1562` — the PO's ruling of 2026-09-04.
        "contact_detail",
        # `DEF-CWP-3768` — our own miscount of the blueprint.
        "account_link",
        # ⚠ **SEVENTH, 2026-09-05 — CR-068 phase 5, US-CWP-046.** A customer's
        # saved card. It is NOT `payment` (that row is money moving; a card is
        # saved without paying anything) and NOT a companion (a companion has
        # no independent door, and `CWP-039` is one).
        #
        # ⚠ The gate was GREEN over this write before the row existed, by its
        # own letter: it refuses ORM writes in `apps/portal/` and imports of
        # another module's `…services`, and the owner is `apps.payments.
        # instruments`. The lane reported that rather than banking the pass.
        "stored_instrument",
    }
)
MANAGER_WRITES = frozenset(
    {"create", "update", "delete", "bulk_create", "bulk_update", "get_or_create", "update_or_create"}
)
INSTANCE_WRITES = frozenset({"save", "delete"})
#: Receivers whose `.save`/`.delete` are not database rows.
NOT_A_ROW = frozenset({"cache", "session", "request", "response"})
SKIP_DIRS = frozenset({"migrations", "management", "__pycache__"})


def read_write_points(source: str) -> tuple[list[str], list[str | None], set[str], list[str]]:
    """(kinds, functions, staff modules, problems) from write_points.py's source."""
    kinds: list[str] = []
    functions: list[str | None] = []
    staff: set[str] = set()
    problems: list[str] = []
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        value = node.value
        if "WRITE_POINTS" in names and isinstance(value, (ast.Tuple, ast.List)):
            for call in value.elts:
                if not (isinstance(call, ast.Call) and getattr(call.func, "id", "") == "WritePoint"):
                    problems.append("WRITE_POINTS holds something that is not a WritePoint(...) call")
                    continue
                kw = {k.arg: k.value for k in call.keywords}
                kind = kw.get("kind")
                function = kw.get("function")
                if not isinstance(kind, ast.Constant) or not isinstance(kind.value, str):
                    problems.append("a WritePoint has no literal kind=")
                    continue
                kinds.append(kind.value)
                if isinstance(function, ast.Constant) and (function.value is None or isinstance(function.value, str)):
                    functions.append(function.value)
                else:
                    problems.append(f"WritePoint {kind.value!r}: function= must be a literal name or None")
        if "STAFF_WRITE_MODULES" in names and isinstance(value, ast.Dict):
            for key in value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    staff.add(key.value)
    return kinds, functions, staff, problems


def public_functions(source: str) -> list[str]:
    tree = ast.parse(source)
    return [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_")
    ]


def _receiver_name(node: ast.AST) -> str | None:
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def writes_in(source: str, *, where: str) -> list[str]:
    """Every ORM write and every foreign-service import in `source`."""
    problems: list[str] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            method = node.func.attr
            owner = node.func.value
            if method in MANAGER_WRITES and isinstance(owner, ast.Attribute) and owner.attr == "objects":
                problems.append(
                    f"{where}:{node.lineno} performs an ORM write (.objects.{method}) — "
                    "the portal surface is read-only (BR-CWP-001, BR-CWP-012)"
                )
            elif method in INSTANCE_WRITES and _receiver_name(owner) not in NOT_A_ROW:
                if isinstance(owner, ast.Attribute) and owner.attr == "objects":
                    continue  # counted above
                problems.append(
                    f"{where}:{node.lineno} calls .{method}() on a row — "
                    "the portal surface is read-only (BR-CWP-001, BR-CWP-012)"
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if parts[:1] == ["apps"] and len(parts) >= 2 and parts[1] != "portal":
                if (len(parts) >= 3 and parts[2].endswith("services")) or any(
                    alias.name.endswith("services") for alias in node.names
                ):
                    problems.append(
                        f"{where}:{node.lineno} imports another module's services ({node.module}) — "
                        "a write reached through a service is still a write (BR-CWP-001)"
                    )
    return problems


def check(
    write_points_src: str, services_src: str, files: dict[str, str]
) -> list[str]:
    """`files` maps a repo-relative path to its source, services.py included."""
    kinds, functions, staff, problems = read_write_points(write_points_src)
    declared = set(kinds)
    if len(kinds) != len(declared):
        problems.append("write_points.py declares a kind twice")
    missing = REQUIRED_KINDS - declared
    extra = declared - REQUIRED_KINDS
    if missing:
        problems.append(
            f"write_points.py is missing the kind(s) {sorted(missing)} — "
            f"the {len(REQUIRED_KINDS)} declared kinds are the whole list (BR-CWP-001)"
        )
    if extra:
        problems.append(
            f"write_points.py declares {sorted(extra)} — one more kind is a ruling, not an edit (BR-CWP-001)"
        )
    named = {f for f in functions if f is not None}
    defined = public_functions(services_src)
    for name in defined:
        if name not in named:
            problems.append(
                f"06-backend/apps/portal/services.py defines {name}, which no row of write_points.py "
                "declares — a fifth write point (BR-CWP-003)"
            )
    for name in sorted(named):
        if name not in defined:
            problems.append(f"write_points.py names {name} and services.py does not define it (BR-CWP-003)")
    allowed = {"services.py", *staff}
    for rel, src in sorted(files.items()):
        base = rel.rsplit("/", 1)[-1]
        if base in allowed:
            continue
        problems.extend(writes_in(src, where=rel))
    return problems


CLEAN_POINTS = '''
WRITE_POINTS = (
    WritePoint(kind="payment", lands_in="x", owner="x", function=None, built_in="x", rule="x"),
    WritePoint(kind="service_request", lands_in="x", owner="x", function="raise_request", built_in="x", rule="x"),
    WritePoint(kind="meter_reading", lands_in="x", owner="x", function=None, built_in="x", rule="x"),
    WritePoint(kind="preference", lands_in="x", owner="x", function=None, built_in="x", rule="x"),
    WritePoint(kind="contact_detail", lands_in="x", owner="x", function=None, built_in="x", rule="x"),
    WritePoint(kind="account_link", lands_in="x", owner="x", function=None, built_in="x", rule="x"),
    WritePoint(kind="stored_instrument", lands_in="x", owner="x", function=None, built_in="x", rule="x"),
)
STAFF_WRITE_MODULES = {"settings_service.py": "the portal's own settings row"}
'''
CLEAN_SERVICES = "def raise_request(actor, tenant_id):\n    return None\n"
RED_SERVICES = CLEAN_SERVICES + "def refund_guest_payment(actor, amount):\n    return None\n"
CLEAN_EDGE = "def front(request):\n    return selectors.front(require_tenant(request))\n"
RED_EDGE = "def front(request):\n    models.PortalSettings.objects.create(tenant_id=1)\n    return None\n"
RED_IMPORT = "from apps.customers import services as customer_services\n"
STAFF_OK = "def save_settings(actor, tenant_id, changes):\n    row, _ = models.PortalSettings.objects.get_or_create(tenant_id=tenant_id)\n    row.save()\n"


def selftest() -> bool:
    clean = check(CLEAN_POINTS, CLEAN_SERVICES, {"services.py": CLEAN_SERVICES, "guest_api.py": CLEAN_EDGE, "settings_service.py": STAFF_OK})
    if clean:
        return False
    fifth = check(CLEAN_POINTS, RED_SERVICES, {"services.py": RED_SERVICES, "guest_api.py": CLEAN_EDGE})
    edge = check(CLEAN_POINTS, CLEAN_SERVICES, {"services.py": CLEAN_SERVICES, "guest_api.py": RED_EDGE})
    imported = check(CLEAN_POINTS, CLEAN_SERVICES, {"services.py": CLEAN_SERVICES, "selectors.py": RED_IMPORT})
    # ⚠ **RENAMING A DECLARED KIND HAS TO BITE IN BOTH DIRECTIONS**: `refund`
    # is a kind nobody ruled on, and `preference` has silently gone missing.
    # A gate that noticed only the addition would pass on a lane that quietly
    # REPLACED a write point with a different one.
    one_more_kind = check(CLEAN_POINTS.replace('kind="preference"', 'kind="refund"'), CLEAN_SERVICES, {"services.py": CLEAN_SERVICES})
    return (
        any("refund_guest_payment" in p for p in fifth)
        and any(".objects.create" in p for p in edge)
        and any("another module's services" in p for p in imported)
        and any("missing the kind" in p for p in one_more_kind)
        and any("one more kind is a ruling" in p for p in one_more_kind)
    )


def run() -> tuple[str, str]:
    if not PORTAL.is_dir():
        return "SKIP", f"{PORTAL.relative_to(REPO)} is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell an undeclared write point from a declared one, "
            "so its verdict is worthless (DEF-182)"
        )
    if not WRITE_POINTS.is_file() or not SERVICES.is_file():
        return "FAIL", "apps/portal/write_points.py or services.py is missing — the kinds are declared as data (BR-CWP-003)"
    files: dict[str, str] = {}
    for path in sorted(PORTAL.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts) or path.name in {"tests.py", "__init__.py"}:
            continue
        files[str(path.relative_to(REPO))] = path.read_text(encoding="utf-8")
    problems = check(WRITE_POINTS.read_text(encoding="utf-8"), SERVICES.read_text(encoding="utf-8"), files)
    if problems:
        return "FAIL", " | ".join(problems[:6]) + (f" (+{len(problems) - 6} more)" if len(problems) > 6 else "")
    kinds, functions, staff, _ = read_write_points(WRITE_POINTS.read_text(encoding="utf-8"))
    built = sum(1 for f in functions if f is not None)
    return "PASS", (
        f"{len(kinds)} write points declared as data, {built} built so far; {len(files)} portal file(s) read — "
        f"only services.py and {sorted(staff)} write; self-test: an undeclared function, a write in the guest edge, "
        "a foreign services import and a renamed kind all bite"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
