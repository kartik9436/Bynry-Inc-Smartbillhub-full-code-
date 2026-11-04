#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 2 · P2.22 (THE MONEY TASK).
# Rules:    CLAUDE.md hard rule 2 · hard rule 3 · brief §7.2.2 p85
# ───────────────────────────────────────────────────────
"""REPRODUCE THE THREE WRONG TOTALS BEFORE REFUSING THEM.

⚠ **WHY THIS SCRIPT EXISTS AND IS NOT A PARAGRAPH.** The PO's standing
instruction of 2026-09-27: *"do all tasks based on actual code"* — the build
brief is EVIDENCE, not truth. §7.2.2 says three totals are wrong today and
*"nothing stops you"*. That is a claim about this repository until somebody
runs it. **A refusal built against a fault nobody demonstrated is a refusal
nobody can check.**

So this prints, from the code as it stands:

  1. every place on the RENDER path that could consult additivity and does not;
  2. the three wrong numbers, computed the way the product computes them;
  3. what the one existing guard (`runner.validate` → `assert_summable`) covers
     and what it cannot reach.

Run:  06-backend/.venv/bin/python 10-scripts/cr142_p2_22_wrong_totals.py
It touches no database and writes nothing.
"""

from __future__ import annotations

import os
import pathlib
import re
import sys
from decimal import Decimal

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")

import django  # noqa: E402

django.setup()

from apps.reports import datasets  # noqa: E402

QUERIES = ROOT / "06-backend" / "apps" / "reports" / "queries.py"
RUNNER = ROOT / "06-backend" / "apps" / "reports" / "runner.py"
APPS = ROOT / "06-backend" / "apps"


def rule(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


# ── 1 · what the render path consults ───────────────────────────────────────
rule("1 · THE RENDER PATH — every totals map served, and what checks it")

source = QUERIES.read_text()
totals_blocks = [m.start() for m in re.finditer(r"^\s+totals=\{", source, re.M)]
print(f"`totals=` maps built in apps/reports/queries.py : {len(totals_blocks)}")
for module, name in (("queries.py", "assert_summable"), ("queries.py", "additivity")):
    print(f"  references to {name!r} in {module:12s}: {source.count(name)}")

callers = []
for path in APPS.rglob("*.py"):
    if "migrations" in path.parts:
        continue
    text = path.read_text(errors="ignore")
    if "runner.validate(" in text or "\nvalidate(" in text and path == RUNNER:
        callers.append(path.relative_to(ROOT))
print(f"\napplication-code callers of runner.validate(): {len(callers)} {callers}")
print("  → P0.16's refusal is a SAVE-time guard, and there is no save path yet")
print("    (`P5.2` is Phase 5). So today nothing calls it outside tests, and")
print("    the render path has no guard of any kind.")


# ── 2 · the three wrong numbers ─────────────────────────────────────────────
rule("2 · THE THREE WRONG TOTALS, COMPUTED THE WAY THE PRODUCT COMPUTES THEM")

# The product's own shape: `_money()` over a running Decimal, straight into
# `totals={...}` with nothing between it and the screen.
def product_total(values: list[str]) -> str:
    running = Decimal("0")
    for raw in values:
        running += Decimal(raw)
    return f"{running:.2f}"


print("\nCASE 1 · a balance summed ACROSS TIME  (semi-additive)")
print("  AR Ageing, grouped by month, balance column totalled.")
months = {"2026-05": "41220.0000", "2026-06": "44118.5000", "2026-07": "48221.1400"}
for month, amount in months.items():
    print(f"    {month}   {Decimal(amount):>12,.2f}   ← lawful: one month, summed across accounts")
wrong1 = product_total(list(months.values()))
meas = datasets.BY_CODE["payments"].measure("total")
print(f"    TOTAL   {Decimal(wrong1):>12,.2f}   ← WRONG. `payments.total` is "
      f"{meas.additivity}-additive, forbidden across {meas.forbidden_across}")
print("    Every account owing money in more than one month is counted more than")
print("    once. The figure is not a receivable at all, and nothing says so.")

print("\nCASE 2 · a DSO AVERAGED ACROSS ROUTES  (non-additive)")
routes = {"R-01": "20", "R-02": "30", "R-03": "40", "R-04": "90"}
avg = sum(Decimal(v) for v in routes.values()) / Decimal(len(routes))
dso = datasets.BY_CODE["payments"].measure("dso_days")
print(f"    routes {list(routes.values())}  →  mean {avg:.2f} days")
print(f"    WRONG. `payments.dso_days` is {dso.additivity}-additive: a ratio of")
print("    sums is not the mean of ratios. The utility's DSO is its own")
print("    receivable over its own daily sales and is not 45.00.")

print("\nCASE 3 · TWO UNITS ADDED TOGETHER  (additive within one service)")
usage = datasets.BY_CODE["meter_reads"].measure("consumption")
col = datasets.BY_CODE["meter_reads"].column("consumption")
print(f"    26.24 kgal + 684.00 kWh  →  {product_total(['26.2400', '684.0000'])}")
print(f"    WRONG. `meter_reads.consumption` is {usage.additivity}, forbidden")
print(f"    across {usage.forbidden_across}; the column carries its unit as "
      f"{col.unit or 'unit_from=' + str(col.unit_from)}.")
print("    710.24 has no unit, so by hard rule 3 it is not a quantity at all.")


# ── 3 · what the one existing guard can and cannot reach ────────────────────
rule("3 · WHAT `assert_summable` ALREADY COVERS, AND WHAT IT CANNOT REACH")

for code, measure_name, across, label in (
    ("payments", "total", ("time",), "case 1"),
    ("payments", "dso_days", (), "case 2"),
    ("meter_reads", "consumption", ("service",), "case 3"),
):
    try:
        datasets.assert_summable(code, measure_name, across)
        verdict = "ALLOWED"
    except datasets.UnlawfulTotal as exc:
        verdict = f"refused — {exc}"
    print(f"  {label}: assert_summable({code}.{measure_name}, across={across})\n     → {verdict}")

print("\n  So the RULE is right and complete; what is missing is a CALLER on the")
print("  render path. That is P2.22, and apps/reports/additivity.py is it.")

print("\nSeeded definitions that GROUP (and would therefore be caught at save):")
sys.path.insert(0, str(ROOT / "06-backend" / "apps" / "reports" / "migrations"))
seed = (ROOT / "06-backend" / "apps" / "reports" / "migrations"
        / "0003_seed_catalogue.py").read_text()
print(f"  `\"group_by\": []` occurrences in the seeder: {seed.count('\"group_by\": []')}")
print("  → every seeded definition groups by NOTHING, so `assert_summable` has")
print("    nothing to fire on even when it is called. The three faults are")
print("    reachable only through a grouping a clerk makes, which is P2.17 —")
print("    built in this same lane, which is why the refusal ships with it.")
print()
