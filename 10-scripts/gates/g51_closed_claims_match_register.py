#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-1930 — seven of the nine high-severity `customers` defects that
#           step 4 triaged as OPEN on 2026-08-27 were already fixed in the
#           shipped product, and three module headers said so in their own
#           words: `apps/customers/service_request_service.py:12` reads
#           `# Defects: DEF-634 ✅ · DEF-635 ✅ · DEF-637 ✅ · DEF-638 12.a ✅
#           — all closed`, over register rows that all read `status: open`.
#           A whole lane was aimed at work already shipped.
# Rules:    CLAUDE.md "Defect register" — the register is where a defect's state
#           lives · r11 step 0 (check the packet is current) · law 1 (a comment
#           claiming a guarantee is not the guarantee — pointed at a claim about
#           the REGISTER, which is the one kind a machine can check)
# Ruling:   decision log 2026-08-27, "STEP 4, FIRST MODULE BLOCK".
# ───────────────────────────────────────────────────────
"""G51 — code that claims a defect is CLOSED may not point at an OPEN row.

WHY THIS AND NOT "EVERY OPEN ROW IS REALLY OPEN"
------------------------------------------------
The check anybody would ask for first — *does the product still have this
defect* — cannot be written. No source-reading gate can know whether a screen is
right, and one that pretended to would be worse than none (DEF-182, twice on the
same law: *"a check whose output cannot distinguish pass from fail is worse than
no check, because it is trusted"*).

So this asks the narrow question the actual defect was about. When a lane closes
a defect it very often writes the closure into the file it touched — `DEF-634 ✅`
in a module header, `DEF-637 ✅ closed → BR-CUS-090` beside a service. **That is
a checkable promise about the register**, in exactly the way `G50`'s *"Filed as
DEF-1790"* is. This gate is `G50` pointed the other way:

    G50: prose claims a defect was FILED  → the row must EXIST.
    G51: code  claims a defect is CLOSED  → the row must not read `open`.

Nothing else in the repo asks it, and every other signal was green on the day:
the code compiled, 83 CR-031 cases passed, the gate suite sat at its baseline,
and `G26` — the register's own gate — checks that a row marked `fixed` carries a
`fixed_commit` and has no way to ask the reverse.

⚠ **G26's DOCSTRING ALREADY RECORDS THE SECOND OCCURRENCE** — *"the CR-010 lane
found FOUR rows fixed a day earlier still reading open — its own triage list was
wrong because of it"*. It was written as an argument for a different clause and
no check followed it. DEF-1930 is the third occurrence and the largest.

WHAT COUNTS AS A CLAIM, AND WHAT DELIBERATELY DOES NOT
------------------------------------------------------
A claim is a defect id followed by a **tick** — `DEF-634 ✅`, `DEF-637 ✅ closed`.
That is the form this repo actually uses and it is unambiguous.

NOT claims, and each is ordinary, correct prose that must never fail a build:

  * `DEF-628's shape` / `see DEF-127` — a mention, not a status;
  * `Defect:  DEF-1930 —` in a Trace header — naming what a file is FOR;
  * `# Defects: DEF-632 · DEF-638 12.b` with no tick — an OPEN defect a file
    tracks, which is precisely what a stated absence is supposed to do (G38);
  * a tick anywhere else on the line without an id in front of it;
  * **`DEF-638 12.a ✅` over a row marked `fixed-in-part`** — a SUB-CLAUSE claim
    is a narrower claim and `fixed-in-part` is the register agreeing with it.
    The first run of this gate reported exactly that, on three files, and it was
    wrong: `12.a` is closed by BR-CUS-091 and `12.b` is not.

BASELINE: HARD ZERO, AND IT IS EARNED RATHER THAN ASPIRATIONAL
---------------------------------------------------------------
Measured at the tip before this gate landed: **3 distinct ids claimed closed in
code (DEF-634, DEF-635, DEF-637) and all 3 stale.** All three are corrected in
the commit that adds this file, so the baseline is a true zero on the day it
lands — the condition `G50`'s own docstring names as the reason a gate stays
read: *"a gate whose baseline equalled reality on the day it landed stays green
and stays read; a gate given an aspirational number over an existing pile is
never green, so nobody reads it, and it drifts out of true."*

RED PROOF (hard-won law 7)
---------------------------
Run at the tip, before the three rows were closed:

    G51 FAIL — 3 closure claim(s) point at a row that is not closed, baseline 0:
      06-backend/apps/customers/service_request_service.py claims DEF-634 is
      closed and the register row reads 'open'. …

and with the rows corrected it reports PASS over the same 3 claims. The
self-test below proves each clause bites on text built here, so the proof does
not expire the moment the tree moves (G46 learned that the expensive way).
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "12-governance" / "10-defect-log.csv"

#: Where code lives. Governance prose is G50's, not this gate's.
SOURCE_ROOTS = ("06-backend", "07-frontend/src", "10-scripts")
SOURCE_SUFFIXES = (".py", ".ts", ".tsx")

#: A defect id followed by a TICK. Group 3 is a SUB-CLAUSE where one is given
#: (`DEF-638 12.a ✅`), and that distinction is load-bearing — see below.
CLOSED_CLAIM = re.compile(r"(DEF-((?:[A-Z]{3}-)?\d{3,6}(?!\d)))(\s+\d+\.[a-z])?\s*(?:✅|✓)")

#: Statuses that mean "this row is done with".
CLOSED_STATUSES = frozenset({"fixed", "closed", "wontfix", "invalid", "duplicate"})

#: ⚠ **A SUB-CLAUSE CLAIM IS A NARROWER CLAIM, AND THE FIRST RUN OF THIS GATE
#: IS WHAT TAUGHT IT.** Written without this distinction, G51 reported three
#: files for `DEF-638 12.a ✅` over a row correctly marked `fixed-in-part` —
#: which is not a disagreement at all: `12.a` IS closed (BR-CUS-091) and `12.b`
#: is not, and `fixed-in-part` is the register saying exactly that. A gate that
#: fired there would push a lane to either close a row that still holds work or
#: delete a true sentence, and both are worse than the drift it was written for.
PART_STATUSES = CLOSED_STATUSES | {"fixed-in-part", "partially-fixed"}

CLAIMS_BASELINE = 0


def _statuses() -> dict[str, str]:
    if not REGISTER.exists():
        return {}
    with REGISTER.open(encoding="utf-8", newline="") as fh:
        return {
            r["id"]: (r.get("status") or "").strip()
            for r in csv.DictReader(fh)
            if r.get("id", "").startswith("DEF-")
        }


def problems_in(text: str, name: str, statuses: dict[str, str]) -> list[str]:
    """Every closure claim in `text` whose row is not closed, as a sentence.

    An id with NO row is left to `G50` and to `G26`'s gap note: this gate is
    about disagreement between two records that both exist, and reporting a
    missing row here would duplicate a check that already words it better.
    """
    out: list[str] = []
    for match in CLOSED_CLAIM.finditer(text):
        row_id = match.group(1)
        status = statuses.get(row_id)
        allowed = PART_STATUSES if match.group(3) else CLOSED_STATUSES
        if status is None or status in allowed:
            continue
        out.append(
            f"  {name} claims {row_id} is closed and the register row reads "
            f"'{status}'. One of the two is wrong: close the row with its "
            "fixed_commit, or take the tick off the claim."
        )
    return out


def selftest() -> list[str]:
    """Prove every clause bites, on text built here rather than on the repo."""
    statuses = {"DEF-001": "fixed", "DEF-002": "open", "DEF-003": "fixed-in-part"}
    broken: list[str] = []
    if problems_in("DEF-001 ✅ closed → BR-X", "t", statuses):
        broken.append("a claim over a FIXED row was reported")
    if not problems_in("# Defects: DEF-002 ✅ — all closed", "t", statuses):
        broken.append("a claim over an OPEN row was not reported")
    if problems_in("DEF-003 12.a ✅", "t", statuses):
        broken.append("a SUB-CLAUSE claim over a part-fixed row was reported")
    if not problems_in("DEF-003 ✅ — all closed", "t", statuses):
        broken.append("a WHOLE-ROW claim over a part-fixed row was not reported")
    if problems_in("see DEF-002, and DEF-002's shape recurs here", "t", statuses):
        broken.append("a mere mention was reported as a claim")
    if problems_in("# Defects:  DEF-002 · DEF-003 (both tracked)", "t", statuses):
        broken.append("an untickd tracking list was reported as a claim")
    if problems_in("DEF-999 ✅", "t", statuses):
        broken.append("an id with no row was reported (that is G50's question)")
    return broken


def run() -> tuple[str, str]:
    broken = selftest()
    if broken:
        return "FAIL", "the gate's own self-test did not bite: " + "; ".join(broken)

    statuses = _statuses()
    if not statuses:
        return "FAIL", f"no register at {REGISTER} — this gate has nothing to check"

    found: list[str] = []
    claims: set[str] = set()
    files = 0
    for root in SOURCE_ROOTS:
        base = ROOT / root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in SOURCE_SUFFIXES or "node_modules" in path.parts:
                continue
            files += 1
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "✅" not in text and "✓" not in text:
                continue
            claims.update(m.group(1) for m in CLOSED_CLAIM.finditer(text))
            found += problems_in(text, str(path.relative_to(ROOT)), statuses)

    if len(found) > CLAIMS_BASELINE:
        return "FAIL", (
            f"{len(found)} closure claim(s) point at a row that is not closed, "
            f"baseline {CLAIMS_BASELINE}: " + "; ".join(s.strip() for s in found)
        )
    return "PASS", (
        f"{len(claims)} defect(s) claimed closed in code across {files} source "
        f"file(s), every one closed in the register; self-test: 7/7 clauses bite"
    )


def main() -> int:
    status, note = run()
    print(f"G51 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
