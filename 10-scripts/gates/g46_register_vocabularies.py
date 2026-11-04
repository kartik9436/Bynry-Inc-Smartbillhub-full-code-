#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-1710 / DEF-1711 — the defect register cannot be filtered, and
#           every count quoted from it has been wrong. Measured 2026-08-27:
#           `severity` held NINE values across two vocabularies
#           (blocker/critical, major/high, minor/low, plus cosmetic and
#           trivial), and one row carried a severity where its module belongs.
#           173 `major` rows were being read as if they did not exist, so the
#           figure reported to the PO as "40 high open" was really 90 — open
#           meaning open+reported+fixed-in-part+partially-fixed, a definition
#           that was missing from the first two times this figure was quoted.
# Rules:    CLAUDE.md "Defect register" — the escape_reason column is what turns
#           a bug list into a process fix, and a column nobody can group by is a
#           column nobody can learn from.
# Ruling:   decision log 2026-08-27, "HOW TO PRIORITISE THIS REGISTER" — severity
#           is an INPUT to the four tests, not the ranking. That only holds if
#           the label means one thing.
# ───────────────────────────────────────────────────────
"""G46 — the defect register's controlled columns hold ONLY their vocabulary.

⚠ THE "STATED BOUNDARY" THIS DOCSTRING USED TO DECLARE WAS A DEFECT, AND IT IS
THE ONE THIS FILE'S OWN AUTHOR WROTE THE LAW ABOUT (DEF-1783). The text here
said the gate was *deliberately* left out of `run_gates.py` until the rows were
normalised, and called that a boundary rather than a law-2 gap. It was neither:
`_assert_registry_sane` counts gate MODULES against registry ROWS and refuses to
start the suite when one is unrun — so from `f5c9fb1` until the commit that
normalised the rows, **every lane on the branch got a hard refusal instead of a
gate run**, and none of them could have known why from this file. Hard-won law 1,
committed by the lane that shipped the law's own gate: *a comment claiming a
guarantee is not the guarantee.* The registry is the guarantee.

Both halves landed in ONE commit, which is what the old text should have said:
the 270 rows normalised, this gate registered, suite green to green.

RED PROOF, measured 2026-08-27 against the register at the branch tip — this gate
was never trusted green before it was seen failing:

    severity values outside the vocabulary:
      'major'    173 rows
      'minor'     82 rows
      'blocker'   12 rows
      'trivial'    2 rows
      'cosmetic'   1 row
    shifted module field: DEF-358 carries a severity where a module belongs

All 271 rows were repaired by the commit that registered this gate, and the
gate was then re-proved RED by putting one of each back — a `major` severity
and DEF-358's shifted `module` — before being trusted green.

WHY A GATE RATHER THAN A ONE-OFF CLEAN-UP
-----------------------------------------
Normalising the file once fixes today's counts and nothing else: the second
vocabulary arrived one row at a time, from lanes writing the word that felt right
at the moment they filed. **A tenth value will arrive the same way.** This gate is
the ratchet that makes the clean-up stay clean.

WHAT IT REFUSES, AND WHAT IT DELIBERATELY DOES NOT
--------------------------------------------------
It refuses an unknown value in a controlled column. It does **not** guess a
mapping and rewrite the row — `blocker` might mean `critical` and might mean
something the filer could tell you and the script cannot. A gate that silently
reassigns severities would destroy exactly the evidence the register exists for.

It also refuses a value that is a *different column's* vocabulary — a severity in
`module` is a shifted field, and the row's other cells are then suspect too.
Guessing which module it meant is how a register stops being evidence.

THE THIRD COLUMN, ADDED 2026-09-10 — AND ITS TWO HALVES ARE NOT TWO SETS
------------------------------------------------------------------------
PO ruling, verbatim: *"we cannot manage what we cannot count."* `category` had
never been given a vocabulary and had grown to **1,016 distinct strings across
2,395 rows** — 580 of the last nine days' rows sitting in 485 categories used
three times or fewer. Two independent attempts to bucket the same 1,140 rows
disagreed by twenty points on the largest bucket, because both were reading free
text. `10-scripts/register_vocabulary.py` now holds twelve values derived FROM
those 1,016 strings; 99.7% of existing rows map onto them.

**The read side of this column cannot be a set.** For `severity` and `status` the
retired spellings could be listed, so the gate accepts a wide set and the writer
refuses a narrow one. 1,016 cannot be listed, and a gate that refused them would
be red from birth over history nobody may rewrite — the thing this repo's gates
earn a `# noqa` for. So the wide half is a **DATE** (`CATEGORY_RATCHET_FROM`) and
a **COUNT**:

  * a row filed BEFORE the ratchet is lawful whatever it says, and is COUNTED;
  * a row filed AFTER it carries one of the twelve, or this gate fails it;
  * the count of uncounted rows is printed on EVERY run, pass or fail, because
    "a declared blind spot with no NUMBER attached is indistinguishable from an
    empty one" (hard-won law 7 — G32 reported 0 unresolved over 21 live
    refusals). Today it reads `99/2395 rows on the twelve; 2296 legacy rows in
    1009 spellings COUNTED AND NOT CHECKED`.

RED PROOF of the category arm, measured 2026-09-10 through `run()` — the path
`run_gates.py` takes, never `python3 g46_....py`, because DEF-GOV-3733 is two
gates announced green while the suite reported `module has no attribute 'run'`:

    a row dated 2026-09-12 with category 'silent-null'  -> FAIL, names the row
    the same row dated 2026-09-04                        -> PASS, and COUNTED
    the twelve on a post-ratchet row                     -> PASS

⚠ **AND THE LIVE REGISTER CANNOT FAIL THIS ARM TODAY**, because every row in it
predates the ratchet. That is stated rather than left to be discovered: the four
`selftest()` clauses are what actually exercise the arm on every suite run, and
they are there precisely because a gate whose only evidence is a file that cannot
break it is a gate nobody has tested.

NOTHING IS REWRITTEN. Not the 2,296 legacy rows, and not the three filed on the
ruling day itself — a mass edit of a register ten lanes append to is the damage
hard-won law 11 exists to prevent, and the ratchet date is set one day later so
that this gate never asks for one.
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

REGISTER = Path(__file__).resolve().parents[2] / "12-governance" / "10-defect-log.csv"

# The twelve live in `10-scripts/register_vocabulary.py` with `file_defect.py`'s
# copy of them, which is to say there is no copy. A gate holding its own list of
# a vocabulary somebody else writes is how `severity` ended up with two.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from register_vocabulary import (  # noqa: E402
    CATEGORY_LEGACY_BASELINE,
    CATEGORY_WRITABLE,
)

#: The four the project actually reasons in. Anything else is a second
#: vocabulary, and two vocabularies in one column means every count is wrong.
SEVERITY = {"critical", "high", "medium", "low"}

#: Statuses seen in the file and meant. `partially-fixed` and `fixed-in-part`
#: are two spellings of one state and BOTH are listed rather than one being
#: picked: renaming a status is a data change, and this gate's job is to stop
#: the vocabulary growing, not to shrink it behind the register's back.
STATUS = {
    "open", "reported", "fixed", "closed",
    "partially-fixed", "fixed-in-part",
    "duplicate", "invalid", "wontfix",
}

CONTROLLED = {"severity": SEVERITY, "status": STATUS}
def problems(rows: list[dict]) -> list[str]:
    """Every vocabulary fault in `rows`, as sentences a human can act on.

    Pulled out of `main()` so `run()`, the CLI and `selftest()` all ask the
    SAME question. A gate whose suite path and command-line path are two code
    paths is a gate that can pass in one and fail in the other — which is the
    shape of DEF-674, the defect G42 exists for and the one that caught this
    file for defining `main()` and no `run()`.
    """
    found: list[str] = []
    for column, allowed in CONTROLLED.items():
        seen = Counter((r.get(column) or "").strip().lower() for r in rows)
        for value, count in sorted(seen.items(), key=lambda kv: -kv[1]):
            if value in allowed:
                continue
            ids = [r["id"] for r in rows if (r.get(column) or "").strip().lower() == value][:6]
            found.append(
                f"  {column}: {value!r} on {count} row(s) — not one of "
                f"{sorted(allowed)}. e.g. {', '.join(ids)}"
            )

    # A severity in `module` is a shifted field: the row's other cells are then
    # suspect too, so it is reported by id rather than reassigned.
    for r in rows:
        if (r.get("module") or "").strip().lower() in SEVERITY:
            found.append(
                f"  module: {r['module']!r} on {r['id']} — that is a SEVERITY. "
                "The row's fields are shifted; fix it by hand, never by mapping."
            )
    return found


#: ⚠ THE DATE IS THE READ SIDE. `severity` and `status` keep a WIDE SET for
#: reading and a NARROW one for writing. `category` cannot: 1,016 distinct
#: strings exist and no set can list them, so the wide half is a DATE instead —
#: every row filed before the vocabulary existed is lawful, and every row filed
#: after it carries one of the twelve.
#:
#: It is the day AFTER the ruling on purpose. Three rows were filed on
#: 2026-09-10 itself, hours before the vocabulary was written, and rewriting
#: them to make a new gate green is precisely the mass edit of a shared register
#: that hard-won law 11 exists to prevent. They are counted, not corrected.
CATEGORY_RATCHET_FROM = "2026-09-11"


def category_census(rows: list[dict]) -> tuple[int, int, list[str]]:
    """(rows outside the twelve, distinct spellings, rows that FAIL the ratchet).

    ⚠ **THE FIRST TWO NUMBERS ARE THE POINT OF THIS FUNCTION, NOT ITS
    BOOKKEEPING.** Hard-won law 7: "a declared blind spot with no NUMBER attached
    is indistinguishable from an empty one" — G32 reported 0 unresolved over 21
    live refusals it could not see, truthfully, of everything it could see. A gate
    that said "category is not checked on read" and stopped would be that gate.
    This one publishes how many rows it is NOT checking every single time it runs,
    in the PASS note as well as the FAIL note, so the ratchet's progress is
    readable without running anything else.
    """
    outside = [r for r in rows if (r.get("category") or "").strip().lower() not in CATEGORY_WRITABLE]
    distinct = {(r.get("category") or "").strip().lower() for r in outside}
    failures = [
        f"  category: {(r.get('category') or '').strip()!r} on {r.get('id')} "
        f"(filed {r.get('reported_on')}) — from {CATEGORY_RATCHET_FROM} a new row "
        f"carries one of the twelve: {' · '.join(sorted(CATEGORY_WRITABLE))}"
        for r in outside
        if (r.get("reported_on") or "") >= CATEGORY_RATCHET_FROM
    ]
    return len(outside), len(distinct), failures


def selftest() -> list[str]:
    """Prove each clause BITES, on rows built here rather than on the register.

    Hard-won law 7 — and this gate needed it twice over. It was proved RED by
    hand against the real file, then registered, and G42 immediately found that
    the suite could not call it at all. A hand proof expires the moment the
    code around it moves; this one runs on every suite.
    """
    ok = lambda **kw: {"id": "DEF-000", "module": "billing",
                       "severity": "high", "status": "open", **kw}
    broken: list[str] = []
    if problems([ok()]):
        broken.append("a clean row was reported")
    if not problems([ok(severity="major")]):
        broken.append("a second-vocabulary severity was not reported")
    if not problems([ok(status="done")]):
        broken.append("an unknown status was not reported")
    if not problems([ok(module="low")]):
        broken.append("a severity sitting in `module` was not reported")

    # ── the category arm ───────────────────────────────────────────────────
    # ⚠ THESE FOUR CLAUSES ARE THE ONLY THING KEEPING THE CATEGORY RATCHET
    # HONEST TODAY, AND THAT IS SAID OUT LOUD RATHER THAN LEFT TO BE NOTICED.
    # The live register cannot fail the ratchet yet: every row in it was filed
    # before `CATEGORY_RATCHET_FROM`. A gate whose only evidence is a file that
    # cannot currently break it is hard-won law 7's `structurally-incapable`
    # shape wearing a green tick. So the clause is exercised here, on rows built
    # in this function, on every single run of the suite — which is also why it
    # is here and not in a pytest file: `run_gates.py` calls `run()`, `run()`
    # calls `selftest()`, and that is the path that actually executes.
    dated = lambda **kw: {"id": "DEF-000", "module": "billing", "severity": "high",
                          "status": "open", "reported_on": "2026-09-12", **kw}
    _, _, fails = category_census([dated(category="silent-null")])
    if not fails:
        broken.append("a free-text category on a row filed after the ratchet was not refused")
    _, _, fails = category_census([dated(category="wrong-logic")])
    if fails:
        broken.append("a category from the twelve was refused")
    _, _, fails = category_census([{"id": "DEF-001", "category": "silent-null",
                                    "reported_on": "2026-09-04"}])
    if fails:
        broken.append("a legacy row was failed — the read side must stay open (1,016 spellings)")
    outside, distinct, _ = category_census([{"id": "DEF-002", "category": "silent-null",
                                             "reported_on": "2026-09-04"}])
    if (outside, distinct) != (1, 1):
        broken.append("the census did not COUNT the legacy row it declined to fail")
    return broken


def _rows() -> list[dict]:
    with REGISTER.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def run() -> tuple[str, str]:
    broken = selftest()
    if broken:
        return "FAIL", "the gate's own self-test did not bite: " + "; ".join(broken)

    if not REGISTER.exists():
        return "FAIL", f"no register at {REGISTER} — this gate has nothing to check"

    rows = _rows()
    found = problems(rows)
    outside, distinct, category_fails = category_census(rows)

    # The blind spot, as a NUMBER, on every path out of this function — pass and
    # fail alike. See `category_census`.
    was = CATEGORY_LEGACY_BASELINE["rows_outside_vocabulary"]
    census = (
        f"category: {len(rows) - outside}/{len(rows)} rows on the twelve; "
        f"{outside} legacy rows in {distinct} spellings are COUNTED AND NOT CHECKED "
        f"(baseline {was} on {CATEGORY_LEGACY_BASELINE['measured_on']}; the read side is "
        f"open because 1,016 spellings cannot be listed, and it narrows only as rows are "
        f"touched for other reasons — never by a mass rewrite)"
    )

    if found or category_fails:
        all_found = found + category_fails
        return "FAIL", (
            f"{len(all_found)} vocabulary problem(s) in {REGISTER.name}: "
            + "; ".join(s.strip() for s in all_found)
            + ". Fix by editing the rows, not by widening this gate. A second "
            "vocabulary means every count taken from this column is wrong — "
            "'40 high open' was really 90 (DEF-1710/DEF-1711), counting open as "
            "open+reported+fixed-in-part+partially-fixed. " + census
        )
    return "PASS", (
        f"{len(rows)} rows; severity and status each hold one vocabulary; "
        f"{census}; self-test: 8/8 clauses bite"
    )


def main() -> int:
    status, note = run()
    print(f"G46 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
