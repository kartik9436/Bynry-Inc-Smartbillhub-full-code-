#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-1792 — "Filed as DEF-1790" appeared in 11-change-requests.md,
#           the decision log and 19-execution-sequence.md, and the register
#           carried no such row. The finding was real; only the row was missing.
#           Worse, max id was DEF-1789, so the next allocation WAS DEF-1790 and
#           it went to an unrelated tooling defect — which would have pointed
#           all three citations at a real row about a different subject.
# Rules:    CLAUDE.md "Defect register" — the escape_reason column is what turns
#           a bug list into a process fix. A claim that a defect was filed is a
#           claim about the register, and it is the one claim nothing could check.
# Ruling:   decision log 2026-08-27, step 5 of 19-execution-sequence.md — derive
#           status from the registers rather than typing it.
# ───────────────────────────────────────────────────────
"""G50 — a sentence that says a defect was FILED must be able to point at the row.

WHY THIS AND NOT "EVERY CITED ID EXISTS"
----------------------------------------
The obvious gate — *every `DEF-###` in governance prose resolves* — was written,
measured, and **thrown away**, because it fires overwhelmingly on legitimate
prose. Measured at the tip, it reported 24 dangling DEF ids and 11 OQ ids, and
almost every one was a false positive of the check rather than a fault in the
repo:

  * `14-id-reservations.md` names RANGES (`DEF-1320–1359`), and the low end of a
    range is not a citation;
  * the register pads (`DEF-005`) and prose does not (`DEF-5`);
  * `DEF-5…` is a TRUNCATED QUOTE of a German UI string, inside the row about
    removing register ids from German UI strings;
  * an ABANDONED id cited *as* abandoned is correct prose — `g26_defect_register`
    says in as many words that "an abandoned id is legitimate";
  * an id the allocator OFFERED and a lane declined (`DEF-1809`) is a true
    sentence about a number that deliberately has no row.

Shipping that version would have added a fifth entry to the list of gates in this
repo that describe their own output wrongly (DEF-1788, DEF-1861, DEF-1862,
DEF-1863 — all four in the i18n family, all found within a day of anyone reading
them). **A check whose output cannot distinguish pass from fail is worse than no
check, because it is trusted** (CLAUDE.md law 11, twice).

So this gate asks the narrow question that the actual defect was about: **not
"does every id resolve", but "does every id we CLAIMED TO HAVE FILED resolve".**
A lane writing *"Filed as DEF-1790"* is making a checkable promise about the
register. Nothing else here is.

BASELINE: HARD ZERO, AND THERE IS NO LEGACY TO GRANDFATHER
-----------------------------------------------------------
Measured at the tip before this gate landed: **31 DEF claims and 20 OQ claims,
all 51 resolving.** That is the condition `G45`'s docstring names as the reason
its own baseline is a hard zero — the one offender was fixed in the commit
before this one (DEF-1790 reconstructed from the two accounts that cite it).

The distinction matters and it is this repo's own finding: a gate whose baseline
equalled reality on the day it landed stays green and stays read; a gate given an
aspirational number over an existing pile is never green, so nobody reads it, and
it drifts out of true. Decision log 2026-08-27, "WHY SOME GATE FAMILIES BREACH".

RED PROOF (hard-won law 7) — run in a throwaway worktree at `16eecad`, the tree
as it stood before DEF-1790 was reconstructed, with this file copied in:

    G50 FAIL — 1 claim(s) name a row that does not exist, baseline 0:
    12-governance/11-change-requests.md claims DEF-1790 was filed and the
    register has no such row. Either write the row or stop claiming it was
    written — and check the id has not since been handed to something else
    (DEF-1792).
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

GOV = Path(__file__).resolve().parents[2] / "12-governance"
REGISTER = GOV / "10-defect-log.csv"
QUESTIONS = GOV / "01-open-questions.md"

#: Only verbs that assert the row EXISTS. "see DEF-123", "DEF-123's shape" and
#: "reserved DEF-1900–1929" are not claims and are deliberately not matched.
DEF_CLAIM = re.compile(r"(?:[Ff]iled as|[Ff]iled it as|[Ff]iled under|[Rr]aised as)\s*`?(DEF-(?:[A-Z]{3}-)?(\d+))`?")
OQ_CLAIM = re.compile(r"(?:[Mm]inted as|[Ff]iled as|[Rr]aised as|[Mm]inted)\s*`?(OQ-(?:[A-Z]{3}-)?(\d+))`?")

CLAIMS_BASELINE = 0


def _def_ids() -> set[int]:
    if not REGISTER.exists():
        return set()
    with REGISTER.open(encoding="utf-8", newline="") as fh:
        return {int(r["id"].rsplit("-", 1)[1]) for r in csv.DictReader(fh)
                if r.get("id", "").startswith("DEF-")}


def _oq_ids() -> set[int]:
    if not QUESTIONS.exists():
        return set()
    return {int(m.rsplit("-", 1)[1]) for m in re.findall(r"OQ-(?:[A-Z]{3}-)?\d+", QUESTIONS.read_text(encoding="utf-8"))}


def problems_in(text: str, name: str, defs: set[int], oqs: set[int]) -> list[str]:
    """Every filed-claim in `text` whose id has no row, as an actionable sentence."""
    out: list[str] = []
    for rx, pool, where in ((DEF_CLAIM, defs, "register"), (OQ_CLAIM, oqs, "open-questions registry")):
        for m in rx.finditer(text):
            if int(m.group(2)) not in pool:
                out.append(
                    f"  {name} claims {m.group(1)} was filed and the {where} has no such row. "
                    "Either write the row or stop claiming it was written — and check the id "
                    "has not since been handed to something else (DEF-1792)."
                )
    return out


def selftest() -> list[str]:
    """Prove every clause bites, on text built here rather than on the repo.

    A hand proof expires the moment the code around it moves; this one runs on
    every suite. G46 learned that the expensive way on the same day.
    """
    defs, oqs = {1}, {2}
    broken: list[str] = []
    if problems_in("Filed as DEF-001 and minted as OQ-002.", "t", defs, oqs):
        broken.append("a resolving claim was reported")
    if not problems_in("Filed as `DEF-999`.", "t", defs, oqs):
        broken.append("an unresolved DEF claim was not reported")
    if not problems_in("minted as OQ-999", "t", defs, oqs):
        broken.append("an unresolved OQ claim was not reported")
    if problems_in("see DEF-999, and DEF-900–999 is reserved; DEF-999's shape recurs", "t", defs, oqs):
        broken.append("a mere mention was reported as a claim")
    return broken


def run() -> tuple[str, str]:
    broken = selftest()
    if broken:
        return "FAIL", "the gate's own self-test did not bite: " + "; ".join(broken)

    defs, oqs = _def_ids(), _oq_ids()
    if not defs:
        return "FAIL", f"no register at {REGISTER} — this gate has nothing to check"

    found: list[str] = []
    claims = 0
    for f in sorted(GOV.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        claims += len(DEF_CLAIM.findall(text)) + len(OQ_CLAIM.findall(text))
        found += problems_in(text, f"12-governance/{f.name}", defs, oqs)

    if len(found) > CLAIMS_BASELINE:
        return "FAIL", (
            f"{len(found)} claim(s) name a row that does not exist, baseline "
            f"{CLAIMS_BASELINE}: " + "; ".join(s.strip() for s in found)
        )
    return "PASS", (
        f"{claims} filed-claim(s) across {len(list(GOV.glob('*.md')))} governance "
        f"file(s), every one resolving; self-test: 4/4 clauses bite"
    )


def main() -> int:
    status, note = run()
    print(f"G50 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
