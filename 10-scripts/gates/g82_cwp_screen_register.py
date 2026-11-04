#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-068 §9 (PO 2026-09-03: *"You can assign number CWP-nnn - Assig
#           all unqie numbers"*) · §13 (the gate the plan called G78; G78–G80
#           were taken by CR-070 and CR-069 wave B, so it is G82) · PO 2026-09-03:
#           *"We need unique screen ID - on every screen"*
# Rules:    CR-068 §11d (`CWP-###` is mirrored into the portal's own
#           `screenIds.ts`, never the staff map) · §13 G78's rule ("every portal
#           route carries a CWP number from §9's register, and no route invents
#           one; the staff app's g29 cannot be pointed here without a ruling")
#           · CLAUDE.md hard-won law 7 (proven RED first — see the docstring)
# Tests:    selftest() below · 07-frontend/src/portal/routing/screenIds.test.ts
# Impacts:  07-frontend/src/portal/routing/screenIds.ts · portalRoutes.tsx ·
#           10-scripts/gates/g29_allocated_badges.txt (its CWP rows)
# ───────────────────────────────────────────────────────
"""G82 — every portal screen carries a `CWP` id CR-068 §9 allocates, and no route invents one.

THREE FILES, ONE REGISTER
-------------------------
  * **CR-068 §9's table** (`12-governance/change-requests/CR-068-customer-portal.md`)
    is the authority: `| CWP-001 | G1 | The public front page |`. Seventy-five
    rows, the PO's to allocate (R13).
  * **`07-frontend/src/portal/routing/screenIds.ts`** mirrors it, one row per
    ROUTED portal screen: `{ path, id, blueprint, title }`.
  * **`portalRoutes.tsx`** is the route table those rows describe.
  * **`g29_allocated_badges.txt`** carries the STAFF screens the blueprint
    numbered in the portal's series (CWP-069–075) — those are checked against
    §9 too, so the staff map cannot mint a `CWP` id of its own.

WHAT IT ASSERTS
---------------
  1. every `id` in the portal register is a `CWP-###` §9 allocates, and its
     `blueprint` label is the one §9 pairs it with;
  2. no id and no path appears twice in the register;
  3. every `path:` in `portalRoutes.tsx` has a register row, and every register
     row has a route — the tag can never show an id for a screen that is not
     there, nor draw nothing on a screen that is;
  4. every `CWP-` badge `g29_allocated_badges.txt` allocates is one §9 allocates.

PROVEN RED FIRST (law 7, 2026-09-03)
------------------------------------
With `{ path: "/nowhere", id: "CWP-999", blueprint: "Z9", title: "x" }` added
to the register the gate reported
    FAIL: src/portal/routing/screenIds.ts claims "CWP-999" — CR-068 §9 allocates
    no such id (an id no authority defines is an id nobody can look up) |
    /nowhere is in the register and portalRoutes.tsx serves no such route
and green again with the row removed. `selftest()` replays that and the
mirror case (a route with no row) on in-memory sources.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
CR = REPO / "12-governance" / "change-requests" / "CR-068-customer-portal.md"
REGISTER = REPO / "07-frontend" / "src" / "portal" / "routing" / "screenIds.ts"
ROUTES = REPO / "07-frontend" / "src" / "portal" / "routing" / "portalRoutes.tsx"
ALLOCATED = Path(__file__).resolve().parent / "g29_allocated_badges.txt"

#: `| **CWP-069** | `B1` | Overview |` — bold and backticks are the table's own dress.
#: ⚠ **`[a-z]?` AFTER THE DIGITS — ADDED 2026-09-30 (gate triage T6, DEF-GOV-8532).** `CWP-078`
#: is labelled `R24c` (a Reports Build Brief plate) and the class stopped at
#: `R24`, so §9's own row did not parse and the gate reported an id §9 DOES
#: allocate as invented. Red from 639bffa2a (2026-09-27) on its own blind spot.
#: The self-test now carries a suffixed label, so the narrow class goes red.
CR_ROW = re.compile(r"^\|\s*\**(CWP-\d{3,5}(?!\d))\**\s*\|\s*`?([A-Z]{1,2}\d{1,3}[a-z]?)`?\s*\|", re.M)
REGISTER_ROW = re.compile(
    r'\{\s*path:\s*"([^"]*)",\s*id:\s*"([^"]*)",\s*blueprint:\s*"([^"]*)"', re.S
)
ROUTE_PATH = re.compile(r'\bpath:\s*"([^"]*)"')
BADGE_ROW = re.compile(r"^(CWP-\d{3,5}(?!\d))\s", re.M)


def section_nine(cr_text: str) -> dict[str, str]:
    """`{CWP id: blueprint label}` from §9's table."""
    start = cr_text.find("### CR-068 · 9 ·")
    end = cr_text.find("### CR-068 · 10 ·", start + 1)
    body = cr_text[start:end] if start >= 0 else ""
    return {m.group(1): m.group(2) for m in CR_ROW.finditer(body)}


def check(cr_text: str, register_src: str, routes_src: str, badges_text: str) -> list[str]:
    problems: list[str] = []
    nine = section_nine(cr_text)
    if len(nine) < 70:
        problems.append(f"CR-068 §9 parsed to {len(nine)} rows — expected the seventy-five; the authority is unreadable")
        return problems
    rows = REGISTER_ROW.findall(register_src)
    if not rows:
        problems.append("src/portal/routing/screenIds.ts parsed to zero rows")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for path, cwp, blueprint in rows:
        if cwp not in nine:
            problems.append(
                f'src/portal/routing/screenIds.ts claims "{cwp}" — CR-068 §9 allocates no such id '
                "(an id no authority defines is an id nobody can look up)"
            )
        elif nine[cwp] != blueprint:
            problems.append(f'{cwp} is paired with blueprint "{blueprint}" but §9 says "{nine[cwp]}"')
        if cwp in seen_ids:
            problems.append(f"{cwp} appears twice in the register")
        if path in seen_paths:
            problems.append(f"{path} appears twice in the register")
        seen_ids.add(cwp)
        seen_paths.add(path)
    routed = ROUTE_PATH.findall(routes_src)
    for path in seen_paths:
        if path not in routed:
            problems.append(f"{path} is in the register and portalRoutes.tsx serves no such route")
    for path in routed:
        if path not in seen_paths:
            problems.append(f"portalRoutes.tsx serves {path} and the register has no row for it — a screen with no id")
    for badge in BADGE_ROW.findall(badges_text):
        if badge not in nine:
            problems.append(f'g29_allocated_badges.txt allocates "{badge}" — CR-068 §9 allocates no such id')
    return problems


CLEAN_CR = (
    "### CR-068 · 9 · x\n"
    + "\n".join(f"| CWP-{n:03d} | G{n} | screen {n} |" for n in range(1, 76))
    + "\n| **CWP-078** | `R24c` | Property statement |"
    + "\n### CR-068 · 10 · y\n"
)
CLEAN_REGISTER = (
    '{ path: "/", id: "CWP-001", blueprint: "G1", title: "The public front page" },\n'
    '{ path: "/property", id: "CWP-078", blueprint: "R24c", title: "Property statement" },\n'
)
CLEAN_ROUTES = '[{ path: "/", element: <FrontPage /> }, { path: "/property", element: <P /> }]'
RED_REGISTER = CLEAN_REGISTER + '{ path: "/nowhere", id: "CWP-999", blueprint: "Z9", title: "x" },\n'
RED_ROUTES = CLEAN_ROUTES[:-1] + ', { path: "/report", element: <Report /> }]'
BADGES = "CWP-069   /x  — a\n"
RED_BADGES = BADGES + "CWP-777   /y  — b\n"


def selftest() -> bool:
    if check(CLEAN_CR, CLEAN_REGISTER, CLEAN_ROUTES, BADGES):
        return False
    invented = check(CLEAN_CR, RED_REGISTER, CLEAN_ROUTES, BADGES)
    unregistered = check(CLEAN_CR, CLEAN_REGISTER, RED_ROUTES, BADGES)
    badge = check(CLEAN_CR, CLEAN_REGISTER, CLEAN_ROUTES, RED_BADGES)
    return (
        any("CWP-999" in p for p in invented)
        and any("/nowhere" in p for p in invented)
        and any("/report" in p for p in unregistered)
        and any("CWP-777" in p for p in badge)
    )


def run() -> tuple[str, str]:
    if not REGISTER.is_file():
        return "SKIP", f"{REGISTER.relative_to(REPO)} is not present — activates with the portal's first screen"
    if not selftest():
        return "FAIL", "the gate's own self-test does not hold — it cannot tell an allocated id from an invented one (DEF-182)"
    for path in (CR, ROUTES, ALLOCATED):
        if not path.is_file():
            return "FAIL", f"{path.relative_to(REPO)} is missing"
    problems = check(
        CR.read_text(encoding="utf-8"),
        REGISTER.read_text(encoding="utf-8"),
        ROUTES.read_text(encoding="utf-8"),
        ALLOCATED.read_text(encoding="utf-8"),
    )
    if problems:
        return "FAIL", " | ".join(problems[:6]) + (f" (+{len(problems) - 6} more)" if len(problems) > 6 else "")
    nine = section_nine(CR.read_text(encoding="utf-8"))
    rows = REGISTER_ROW.findall(REGISTER.read_text(encoding="utf-8"))
    staff = BADGE_ROW.findall(ALLOCATED.read_text(encoding="utf-8"))
    return "PASS", (
        f"{len(rows)} portal screen(s) routed and registered, {len(staff)} staff screen(s) numbered in the "
        f"CWP series, all {len(rows) + len(staff)} allocated in CR-068 §9's {len(nine)}; self-test: an invented "
        "id, an unregistered route and a foreign badge all bite"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
