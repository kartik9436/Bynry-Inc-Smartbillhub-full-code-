#!/usr/bin/env python3
"""R2 readiness by module — backend · frontend · test cases · journeys.

    python3 10-scripts/r2_status.py

Four independent measurements per module, because "done" means four different
things and a single percentage hides which one is missing. This release spent
weeks with complete, correct, tested engines that no human could reach; a report
that collapses those four into one number would have hidden exactly that.

  backend routes   HTTP endpoints the module actually mounts. Zero routes over a
                   large engine is the signature failure of this release — one
                   module ran 7,084 lines behind a 72-byte api.py that was never
                   even included in the URL conf.

  engine lines     Python in the module, excluding tests and migrations. Only
                   meaningful NEXT TO the route count: the ratio is the tell.

  screens          Page/screen components in the frontend feature directory.
                   Counted by file, not by screen id — screens do not carry
                   their ids (DEF-137), so this counts components and is
                   labelled an estimate wherever it is quoted.

  test cases       TC-## ids declared in the module's epics, against TC-named
                   tests that exist. A declared case with no test is a promise;
                   the gate that enforces this only checks Trace-cited stories,
                   so a case can be declared and never written.

  journeys         End-to-end journeys citing this module's stories: how many
                   exist, and how many are ACTIVATED (a spec file executes
                   them). Activated is the only field in this repository that
                   asserts something runs. It does NOT assert it passed —
                   pass/fail lives in the run receipt, and this is a shape.

WHY THIS IS A COMMITTED SCRIPT. A module table was produced in an earlier
session, pasted into chat and never committed, so when it was asked for again
the numbers could not be reproduced and the definitions were gone. The artefact
is the script. See also 10-scripts/module_report.py, which measures the same
tree along the story axis rather than the surface axis.

Python 3.12 stdlib only.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND = ROOT / "06-backend" / "apps"
FRONTEND = ROOT / "07-frontend" / "src" / "features"
EPICS = ROOT / "04-docs" / "05-modules"
TESTS = ROOT / "06-backend" / "tests"

#: BUILD ORDER, from B12 addendum line 176 (PO-corrected: "you are missing
#: assets"): Shell+tokens -> Settings/lookups -> Plans&Rates -> Premises/Units ->
#: Assets (meters) -> Accounts -> Reads(+estimation) -> Billing run -> Payments
#: -> Finance -> Reports -> Public.
#:
#: The table is printed in THIS order and never sorted by size. Ordering by
#: engine lines put billing first and platform-shell seventh, which reads as a
#: ranking of importance and hides the only thing the order should show: where
#: the chain breaks. A module cannot be finished before the modules it stands
#: on, so a gap high in this list matters more than a bigger gap below it.
#:
#: backend app dir -> (frontend feature dir, docs dir prefix, story prefix)
MODULES = {
    "tenancy": ("tenancy", "01-tenancy", "TEN"),
    "identity": ("identity", "02-identity", "IDN"),
    "audit": ("audit", "11-audit", "AUD"),
    "rating": ("rating", "06-rating", "RAT"),
    "metering": ("metering", "04-metering", "MET"),
    "assets": ("assets", "05-assets", "AST"),
    "customers": ("customers", "03-customers", "CUS"),
    "billing": ("billing", "07-billing", "BIL"),
    "payments": ("payments", "08-payments", "PAY"),
    "ledger": ("ledger", "09-ledger", "LED"),
    "notifications": ("notifications", "10-notifications", "NOT"),
    "reports": ("reports", "12-reports", "REP"),
    "integrations": ("integrations", "13-integrations", "INT"),
    "portal": ("portal", "15-portal", "CWP"),  # CR-068 (2026-09-03): the customer web portal
}
SHELL = ("platform-shell", "00-platform-shell", "SHL")

ROUTE_RE = re.compile(r"\bpath\s*\(|\bre_path\s*\(")
TC_RE = re.compile(r"\bTC-(\d+)\b")


def read(p: pathlib.Path) -> str:
    try:
        return p.read_text(errors="replace")
    except OSError:
        return ""


def backend_facts(app: str) -> tuple[int, int]:
    """(routes mounted, engine lines) — engine excludes tests and migrations."""
    d = BACKEND / app
    if not d.is_dir():
        return 0, 0
    routes, lines = 0, 0
    for f in d.rglob("*.py"):
        if "migrations" in f.parts or "__pycache__" in f.parts:
            continue
        text = read(f)
        lines += text.count("\n")
        if f.name in ("api.py", "urls.py"):
            routes += len(ROUTE_RE.findall(text))
    # a module's routes only reach users if the project URL conf includes it
    conf = read(ROOT / "06-backend" / "config" / "urls.py")
    if routes and f"apps.{app}" not in conf and f"{app}." not in conf:
        routes = -routes  # negative = mounted in the app, unreachable from the project
    return routes, lines


def frontend_screens(feature: str) -> int:
    """Screen/wizard components for a module.

    **platform-shell is a deliberate special case, and getting it wrong once is
    why this docstring exists.** Its directory under `features/` holds only a
    README: the shell was built into `src/components/` — AppShell, DataTable,
    FilterBar, WizardFrame, StateFrame, MoneyCell, UnitCell and the rest — which
    is exactly right, because those are what every OTHER module draws from. A
    naive count over `features/platform-shell` returns 0 and the table printed a
    dash, which read as "not built" for the most-used code in the product. It is
    built; it simply does not live where a feature lives.
    """
    if feature == "platform-shell":
        root = ROOT / "07-frontend" / "src" / "components"
        return len([f for f in root.rglob("*.tsx") if not f.name.endswith(".test.tsx")])
    d = FRONTEND / feature
    if not d.is_dir():
        return 0
    return len([
        f for f in d.rglob("*.tsx")
        if not f.name.endswith(".test.tsx") and re.search(r"(Page|Screen|Wizard|Tab|Modal)\.tsx$", f.name)
    ])


def testcase_facts(docs: str, prefix: str) -> tuple[int, int]:
    """(TC ids declared in epics, TC ids that a test file names)."""
    declared: set[str] = set()
    for f in (EPICS / docs).rglob("*.md"):
        for m in TC_RE.finditer(read(f)):
            declared.add(m.group(1))
    written: set[str] = set()
    pat = re.compile(rf"us_{prefix.lower()}_\d+.*?tc(\d+)", re.I)
    for f in TESTS.glob("*.py"):
        body = read(f)
        for m in pat.finditer(body):
            written.add(m.group(1))
    return len(declared), len(written & declared)


def journey_facts() -> dict[str, tuple[int, int]]:
    idx = ROOT / "08-qa/01-e2e/01-journey-story-index.json"
    if not idx.exists():
        return {}
    try:
        data = json.loads(read(idx))
    except json.JSONDecodeError:
        return {}
    activated = {j["id"] for j in data.get("journeys", []) if j.get("activated")}
    per: dict[str, tuple[set[str], set[str]]] = {}
    for sid, journeys in (data.get("story_to_journeys") or {}).items():
        pref = sid[3:6]
        mod = next((m for m, v in {**MODULES, SHELL[0]: SHELL}.items()
                    if (v[2] if isinstance(v, tuple) else "") == pref), None)
        if mod is None:
            continue
        total, act = per.setdefault(mod, (set(), set()))
        total.update(journeys)
        act.update(set(journeys) & activated)
    return {m: (len(t), len(a)) for m, (t, a) in per.items()}


def main() -> int:
    jf = journey_facts()
    rows = []
    for app, (feature, docs, prefix) in {SHELL[0]: SHELL, **MODULES}.items():
        routes, lines = backend_facts(app)
        screens = frontend_screens(feature)
        declared, written = testcase_facts(docs, prefix)
        jt, ja = jf.get(app, (0, 0))
        rows.append((app, routes, lines, screens, declared, written, jt, ja))
    # printed in BUILD ORDER — deliberately not sorted. See MODULES above.

    print(f"{'module':<15}{'routes':>7}{'engine':>8}{'screens':>9}{'test cases':>13}{'journeys':>12}")
    print(f"{'':<15}{'':>7}{'lines':>8}{'':>9}{'done/declared':>13}{'run/exist':>12}")
    print("-" * 66)
    for app, routes, lines, screens, dec, wri, jt, ja in rows:
        r = "NONE" if routes == 0 else (f"{-routes}*" if routes < 0 else str(routes))
        print(f"{app:<15}{r:>7}{lines:>8}{screens:>9}"
              f"{f'{wri}/{dec}':>13}{f'{ja}/{jt}':>12}")
    print("-" * 66)
    tot_routes = sum(max(r[1], 0) for r in rows)
    print(f"{'TOTAL':<15}{tot_routes:>7}{sum(r[2] for r in rows):>8}{sum(r[3] for r in rows):>9}"
          f"{f'{sum(r[5] for r in rows)}/{sum(r[4] for r in rows)}':>13}"
          f"{f'{sum(r[7] for r in rows)}/{sum(r[6] for r in rows)}':>12}")
    print()
    print("* routes exist in the app but the project URL conf does not include it —")
    print("  mounted and unreachable, which is the failure this column exists to show.")
    print("screens counts COMPONENTS, not screen ids (DEF-137: screens carry no id) — an estimate.")
    print("journeys 'run' means a spec executes it, NOT that it passed. Pass/fail is the run receipt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
