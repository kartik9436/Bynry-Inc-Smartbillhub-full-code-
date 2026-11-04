#!/usr/bin/env python3
"""How many wave tasks exist, and how many are done — derived, never typed.

    python3 10-scripts/wave_report.py

WHY (DEF-1932). The PO asked *"how many are there and how many completed"*. The
bugs half was one command; the waves half could not be produced at all, because
tasks live as sentences in `11-change-requests.md`. Three extraction attempts
gave three answers and the first was silently wrong — an unscoped search matched
one change request's counts against all nine and printed them nine times, which
looked like a clean table.

**This reports what is RECORDED and names what is not.** A change request with no
task rows is printed as a gap, not omitted — an absent row and a finished wave
must never read the same way, which is the same rule
`apps/tenancy/service_size_classes.py` keeps between *ruled to have none* and
*nobody has said*.

Output is NEVER committed. The TSV is the single source; every view is derived.
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

GOV = Path(__file__).resolve().parents[1] / "12-governance"
TASKS = GOV / "20-wave-tasks.tsv"
REGISTER = GOV / "11-change-requests.md"

#: One vocabulary, refused rather than remapped — G46's lesson, which cost
#: 270 rows and made every count taken from `severity` wrong for seventeen days.
STATES = ("done", "verify", "open", "blocked")
DONE = ("done",)


def rows() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not TASKS.exists():
        return out
    for n, line in enumerate(TASKS.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#") or line.startswith("cr\t"):
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            sys.exit(f"{TASKS.name}:{n}: expected 5 tab-separated fields, got {len(parts)}")
        cr, wave, task, state, desc = (p.strip() for p in parts[:5])
        if state not in STATES:
            sys.exit(
                f"{TASKS.name}:{n}: state {state!r} is not one of {list(STATES)}. "
                "Add the row's real state; do not invent a sixth word — a column "
                "holding two vocabularies makes every count taken from it wrong (G46)."
            )
        out.append(dict(cr=cr, wave=wave, task=task, state=state, description=desc))
    return out


def known_crs() -> list[str]:
    """Every change request that has a top-level heading, so a gap can be named."""
    if not REGISTER.exists():
        return []
    return sorted(set(re.findall(r"^## (CR-\d+)", REGISTER.read_text(encoding="utf-8"), re.M)))


def main() -> int:
    rs = rows()
    by_cr: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for r in rs:
        by_cr[r["cr"]].append(r)

    print(f"{'change request':16} {'tasks':>6} {'done':>6} {'verify':>7} {'open':>6} {'blocked':>8}")
    for cr in sorted(by_cr):
        c = collections.Counter(r["state"] for r in by_cr[cr])
        print(f"{cr:16} {len(by_cr[cr]):>6} {c['done']:>6} {c['verify']:>7} {c['open']:>6} {c['blocked']:>8}")

    total = len(rs)
    done = sum(1 for r in rs if r["state"] in DONE)
    print(f"\n{total} task(s) recorded · {done} done · {total - done} not done")
    print("  'verify' is NOT done — built and unproved is the state that hides a gap")

    gaps = [cr for cr in known_crs() if cr not in by_cr and int(cr.split("-")[1]) >= 38]
    if gaps:
        print(f"\n⚠ {len(gaps)} change request(s) record NO tasks here, so nothing above counts them:")
        print("   " + ", ".join(gaps))
        print("   Their tasks are prose in 11-change-requests.md and are NOT included in the")
        print("   totals. A lane owning one of those waves adds its rows to")
        print(f"   {TASKS.relative_to(GOV.parent)} when it starts (DEF-1932).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
