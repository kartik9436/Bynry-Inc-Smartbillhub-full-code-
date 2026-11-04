#!/usr/bin/env python3
"""Bulk bill run: is every agreed change mapped to a task and proved by a test?

Asked by the PO on 2026-09-30: "how you will ensure they are implemented". Three
documents must agree, and before this script nothing checked that they did —
on the day it was written, rows 43-54 of the changes list (four rulings of the
afternoon plus the eight next-bill rulings) had no build task at all.

  14-bulk-bill-run-changes.md   what was agreed (one numbered row each)
  15-bulk-bill-run-build-plan.md the tasks
  17-bulk-bill-run-tracker.md    row -> tasks -> state -> proving test

Fails (exit 1) when:
  * a changes row has no tracker row, or the tracker names a row that does not exist;
  * a tracker row names a task the plan does not have, or no task at all;
  * a row is Merged or Walked with no proving test, or a named test file is
    missing or does not carry the marker BULK-CHG-<n>.
With --close it also fails unless EVERY row is Walked (plan C1-C4).

What would make it pass wrongly: a test that carries the marker without
asserting the change. The marker is a pointer for the reviewer, not proof of
the assertion — reading the tagged test at merge is still the coordinator's job.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "04-docs/05-modules/07-billing"
STATES = ("To build", "In progress", "Merged", "Walked")


def rows(path):
    out = {}
    for line in path.read_text().splitlines():
        m = re.match(r"\| (\d+) \|", line)
        if m:
            out[int(m.group(1))] = [c.strip() for c in line.strip().strip("|").split("|")]
    return out


def main(close=False):
    changes = rows(DOCS / "14-bulk-bill-run-changes.md")
    tracker = rows(DOCS / "17-bulk-bill-run-tracker.md")
    plan = set(re.findall(r"^\| ([A-Z]{1,2}\d+) \|",
                          (DOCS / "15-bulk-bill-run-build-plan.md").read_text(), re.M))
    errors, counts, unproved = [], {s: 0 for s in STATES}, []
    for n in sorted(set(changes) - set(tracker)):
        errors.append(f"change {n} has no tracker row")
    for n in sorted(set(tracker) - set(changes)):
        errors.append(f"tracker row {n} is not in the changes list")
    for n, cells in sorted(tracker.items()):
        if len(cells) < 5:
            errors.append(f"row {n}: expected 5 cells"); continue
        _, _, tasks, state, proof = cells[:5]
        if state not in STATES:
            errors.append(f"row {n}: unknown state {state!r}"); continue
        counts[state] += 1
        ids = [t.strip() for t in tasks.split(",") if t.strip()]
        if not ids:
            errors.append(f"row {n}: no task")
        for t in ids:
            if t != "pre-plan" and t not in plan:
                errors.append(f"row {n}: task {t} is not in the build plan")
        files = [p.strip(" `") for p in proof.split(";") if p.strip(" `—-")]
        marker = re.compile(rf"BULK-CHG-{n}(?!\d)")
        for f in files:
            fp = ROOT / f.split("::")[0]
            if not fp.is_file():
                errors.append(f"row {n}: proving test {f} does not exist")
            elif not marker.search(fp.read_text(errors="replace")):
                errors.append(f"row {n}: {f} does not carry BULK-CHG-{n}")
        if state in ("Merged", "Walked") and not files:
            unproved.append(n)
        if close and state != "Walked":
            errors.append(f"row {n}: {state}, not Walked")
    total = len(tracker)
    print(f"{total} agreed changes: " + " · ".join(f"{counts[s]} {s}" for s in STATES))
    if unproved:
        print(f"{len(unproved)} claimed Merged/Walked with NO proving test: {unproved}")
        errors.append(f"{len(unproved)} rows claim Merged/Walked with no proving test")
    for e in errors:
        print("FAIL:", e)
    print("PASS" if not errors else f"FAIL ({len(errors)})")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(close="--close" in sys.argv))
