#!/usr/bin/env python3
"""Screens per module — declared and OWNED. It does NOT count "done".

    python3 10-scripts/screen_report.py

Answers the question the other two tables could not: **how many screens does
each module need, and how many are done?**

`r2_status.py` counts COMPONENT FILES, which is a proxy and a poor one — a
module whose screens live in fewer, larger files scores low for no reason, and
platform-shell scored a dash for 17 components because they live outside a
feature directory. This counts SCREENS, from the inventory that declares them.

HOW A SCREEN IS ATTRIBUTED TO A MODULE. The inventory (A1) has no module
column, and screens carry no module marker in code. What it does have is
stories: every screen is cited by the story that owns it, and a story's id
carries its module (`US-BIL-…` is billing). So a screen belongs to the module
of the story that claims it. A screen NO story claims is an orphan and is
counted separately — that state is real and has bitten three times: the landing
page, the tenant dashboard and the signup review step each reached a user
unbuilt because nobody owned them.

WHY THERE IS NO "DONE" COLUMN, after three attempts to build one.

A screen cannot be scored complete from the data this repository holds, and
shipping a number anyway would have been worse than shipping none:

  1. **Screens carry no id in the code** (DEF-137). Nothing can look at a built
     screen and say which inventory row it is.
  2. **The inventory has no module column.** Attribution is inferred from which
     module's docs discuss a screen — a heuristic, not a fact. The first attempt
     handed platform-shell all 77 screens, because a navigation map names every
     screen in the product.
  3. **Screen-to-story is many-to-many.** Scoring a screen done when ANY owning
     story is complete marked 73 of 77 done, on a tree where 47 stories are
     unreachable and billing alone holds 17 of them. Scoring it done only when
     ALL are complete is equally arbitrary in the other direction.

So this prints what IS knowable — how many screens each module owns, and which
screens no story owns at all. **For completion, read stories, not screens:**
`module_report.py` for built-vs-touched, and `10-scripts/gates/surface_debt.txt`
for what remains unreachable, which lanes maintain and a merge-blocking gate
enforces.

The orphan list is the part worth acting on. A screen no story owns is nobody's
to build and nobody's to notice — the landing page, the tenant dashboard and the
signup review step each reached a user unbuilt for exactly that reason.

Python 3.12 stdlib only.
"""

from __future__ import annotations

import collections
import glob
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "04-docs" / "01-spec" / "01-screen-inventory.md"

PREFIX_TO_MODULE = {
    "SHL": "platform-shell", "TEN": "tenancy", "IDN": "identity", "AUD": "audit",
    "RAT": "rating", "MET": "metering", "AST": "assets", "CUS": "customers",
    "BIL": "billing", "PAY": "payments", "LED": "ledger", "NOT": "notifications",
    "REP": "reports", "INT": "integrations",
               "CWP": "portal",  # CR-068 (2026-09-03)
}
#: build order — B12 addendum line 176, PO-corrected. Never sorted by size.
BUILD_ORDER = ["platform-shell", "tenancy", "identity", "audit", "rating",
               "metering", "assets", "customers", "billing", "payments",
               "ledger", "notifications", "reports", "integrations", "portal"]

SCREEN_RE = re.compile(r"\bS(\d{1,3})\b")
STORY_RE = re.compile(r"\bUS-([A-Z]{3})-(\d{3,6})\b")
PACKET_RE = re.compile(r"^\s*(?:#|//)\s*packet:\s*(.+)$", re.M)
CHECKLIST_RE = re.compile(r"^\s*(?:#|//)\s*checklist:(.*)$", re.M)
MARK_RE = re.compile(r"([A-H])(✔|✖|=deferred\([^)]*\))")


def read(p: pathlib.Path) -> str:
    try:
        return p.read_text(errors="replace")
    except OSError:
        return ""


def declared_screens() -> set[str]:
    """Screen ids the inventory declares, read from its TABLE ROWS only.

    Row-anchored deliberately: prose elsewhere in the file mentions screen ids
    in passing, and counting those inflates the denominator.
    """
    out = set()
    for line in read(INVENTORY).split("\n"):
        m = re.match(r"\|\s*(S\d{1,3})\s*\|", line)
        if m:
            out.add(m.group(1))
    return out


def screen_owners() -> dict[str, tuple[str, set[str]]]:
    """screen id -> (owning module, the story ids that claim it).

    **ATTRIBUTED BY THE DOCS DIRECTORY, not by the story prefix, and the first
    attempt got this badly wrong.** Keying on the story prefix and breaking ties
    by build order handed platform-shell all 77 screens, because the shell's own
    epics list every screen id in the product — that is what a navigation map
    IS. A passing mention in a nav table is not ownership.

    So a screen belongs to the module whose OWN docs directory describes it, and
    where several describe it, to the one that mentions it MOST — the module
    writing about a screen repeatedly is the module that owns it. platform-shell
    is excluded from that contest unless it is the ONLY claimant, for the same
    reason: it names every screen by design.
    """
    hits: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    stories: dict[str, set[str]] = collections.defaultdict(set)
    for pattern in ("04-docs/05-modules/*/06-epics/*.md",
                    "04-docs/05-modules/*/05-user-stories.md"):
        for f in glob.glob(str(ROOT / pattern)):
            path = pathlib.Path(f)
            m = re.search(r"/05-modules/\d+-([a-z-]+)/", f)
            module = m.group(1) if m else None
            if module not in PREFIX_TO_MODULE.values():
                continue
            text = read(path)
            found = SCREEN_RE.findall(text)
            if not found:
                continue
            cited = {f"US-{a}-{b}" for a, b in STORY_RE.findall(text)}
            for num in found:
                sid = f"S{num}"
                hits[sid][module] += 1
                stories[sid] |= cited

    owners: dict[str, tuple[str, set[str]]] = {}
    for sid, counter in hits.items():
        ranked = [m for m in counter if m != "platform-shell"] or list(counter)
        winner = max(ranked, key=lambda m: (counter[m], -BUILD_ORDER.index(m)))
        owners[sid] = (winner, stories[sid])
    return owners


def built_stories() -> set[str]:
    """Stories whose API half AND screen half are both marked complete."""
    halves: dict[str, set[str]] = collections.defaultdict(set)
    for pattern in ("06-backend/**/*.py", "07-frontend/src/**/*.ts",
                    "07-frontend/src/**/*.tsx"):
        for f in ROOT.glob(pattern):
            if "node_modules" in f.parts or "__pycache__" in f.parts:
                continue
            text = read(f)
            if "packet:" not in text:
                continue
            cited = {f"US-{m.group(1)}-{m.group(2)}"
                     for line in PACKET_RE.findall(text)
                     for m in STORY_RE.finditer(line)}
            cl = CHECKLIST_RE.search(text)
            marks = dict(MARK_RE.findall(cl.group(1))) if cl else {}
            for sid in cited:
                if marks.get("D") == "✔":
                    halves[sid].add("D")
                if marks.get("E") == "✔":
                    halves[sid].add("E")
    return {s for s, seen in halves.items() if {"D", "E"} <= seen}


def main() -> int:
    declared, owners, built = declared_screens(), screen_owners(), built_stories()

    per: dict[str, int] = {m: 0 for m in BUILD_ORDER}
    orphans: list[str] = []
    for s in sorted(declared, key=lambda x: int(x[1:])):
        if s not in owners:
            orphans.append(s)
            continue
        per[owners[s][0]] += 1

    print(f"{'module':<16}{'screens owned':>15}")
    print("-" * 32)
    for m in BUILD_ORDER:
        print(f"{m:<16}{per[m]:>15}")
    print("-" * 32)
    print(f"{'TOTAL':<16}{sum(per.values()):>15}")

    if orphans:
        print(f"\nOWNED BY NO STORY ({len(orphans)}): {', '.join(orphans)}")
        print("  Nobody's to build and nobody's to notice. Three screens reached")
        print("  users unbuilt for exactly this reason.")

    print("\nTHERE IS DELIBERATELY NO 'done' COLUMN — see the module docstring.")
    print("Screens carry no id, the inventory has no module column, and one screen")
    print("is claimed by many stories, so any completion score is arbitrary.")
    print("For completion read STORIES: 10-scripts/module_report.py and")
    print("10-scripts/gates/surface_debt.txt (merge-blocking, lane-maintained).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
