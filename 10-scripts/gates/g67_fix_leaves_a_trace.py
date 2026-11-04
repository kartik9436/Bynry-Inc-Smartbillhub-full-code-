#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2792 (2026-08-31) — A FIX'S OWN WRITE-UP CITED THE WRONG DEFECT
#          ID, SO THE ROW IT FIXED SAT `open` FOR TWELVE DAYS. docker-compose.yml
#          carried the corrected celery healthcheck under the heading "TWO BUGS
#          IN ONE LINE — DEF-339", and DEF-339 is an unrelated lint failure in
#          tailwindTheme.test.ts. The row the comment is about is DEF-340. A
#          lane grepping the code for DEF-340 found nothing and concluded the
#          fix was never made — which is exactly what happened.
# Rules:   CLAUDE.md hard-won law 1 · law 7 (prove a guard goes RED first) ·
#          DEF-182 (a check whose output cannot distinguish pass from fail is
#          worse than no check, because it is trusted)
# Impacts: 12-governance/10-defect-log.csv · G50 · G51 · G55
# ───────────────────────────────────────────────────────
"""G67 — A FIX THE REGISTER LOCATES MUST BE FINDABLE IN THE FILE IT LOCATES IT IN.

⚠ **THIS WAS WRITTEN AS `G65` AND RENUMBERED AT PUSH TIME.** Two sibling lanes
took `g65_module_ring` and `g66_seeder_savepoints` from their own worktrees while
this one was working; all three lanes computed the next free number correctly and
two of them got the same one. That is `DEF-1787`'s mechanism — an allocated id is
a blob too — and law 11's answer is the one that caught it: re-derive the CONTENT
and the IDS from the pinned tip in one act, at push time, never from what you
read twenty minutes ago.

THE CHECK DEF-2792 ASKED FOR, AND WHY IT IS NOT THE ONE BUILT
-------------------------------------------------------------
`DEF-2792`'s prevention column prescribes the FORWARD direction: *"where a source
file names a DEF id in a trace or comment block, compare that row's `surface`
column against the file naming it and REPORT the pairs that do not overlap."*

**It was built, measured, and thrown away, and the measurement is the reason.**

    every DEF id in any source file          5,395 citations · 4,848 mismatch (90%)
    only the Trace header's `Defect:` field    596 citations ·   578 mismatch (97%)

Ninety-seven per cent. A file's Trace header names the defect that MOTIVATED the
file, and that defect's surface is almost always somewhere else — a migration
citing the pricing defect it exists to repair, a seam citing the outage that
proved it was needed. Those are correct, useful citations. A report at that
signal-to-noise is read once and never again, which is the failure this repo
keeps paying for; `DEF-2792` itself warns that its check *"must be a report and
not a hard gate at today's coverage"*, and the numbers say even a report does not
survive.

THE MIRROR DIRECTION, WHICH IS CHEAP AND WHICH WOULD HAVE CAUGHT IT
--------------------------------------------------------------------
Turn the question round: **the register points at a file; does that file carry
the id?**

    rows marked `fixed` whose surface names a file that exists   355 pairs
    the file carries no mention of the id                        103 pairs (29%)

Twenty-nine per cent is a set a person can read, and it is the exact shape of
`DEF-2792`: `DEF-340`'s surface names `docker-compose.yml:253`, the fix WAS made
there on 2026-08-19, and the file said `DEF-339`. **`DEF-340` was silent in the
one file the register said to look in.** That is what a lane grepping for it
found, and it is what this gate reports.

WHAT IT DOES NOT ASSERT, SAID PLAINLY
--------------------------------------
* **It is not a rule that every fix must leave a comment.** Plenty of fixes are
  just code, and demanding a trace comment would be satisfied by writing the
  comment rather than by doing the work — `CR-051`'s own words about why `G62`
  refuses to ask "is this task done".
* **It cannot tell a wrong id from an absent one.** Both look the same from
  here, and both cost a reader the same thing. `DEF-2792`'s own escape column is
  blunt about the limit: *"The only reader who can catch it is a person who
  knows what the other id was about."* This gate does not replace that reader;
  it hands them a list of 103 places instead of 1,850 files.
* **Open rows are out of scope.** An open row's file has no fix to be traceable
  from. Only `fixed` and `fixed-in-part` are read.

RATCHET, NOT A BAR. 103 today; the number may FALL and may never RISE, so a new
fix that lands untraceable fails on the commit that makes it while the existing
backlog is worked down. A fall must lower `TRACELESS_BASELINE` in the same
commit, or the gate keeps claiming debt already paid off.

PROVED RED BEFORE TRUSTED GREEN (law 7)
---------------------------------------
Part 0 replays `DEF-2792` itself, in memory: `DEF-340` is stripped from
`docker-compose.yml` and the finding must come back naming that pair. Nothing is
written to disk.

Python 3.12 stdlib only. Safe to run from any cwd.

    python3 10-scripts/gates/g65_fix_leaves_a_trace.py
    python3 10-scripts/gates/g65_fix_leaves_a_trace.py --report
"""

import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTER = REPO / "12-governance" / "10-defect-log.csv"

#: A file path inside a `surface` cell. Anchored on the repo's own top-level
#: directories so a bare word like "backend" or a screen id is not mistaken for
#: one — 55% of open high rows name no file at all (DEF-1933), and this gate
#: must be silent about those rather than guess.
PATH_IN_SURFACE = re.compile(
    r"\b((?:06-backend|07-frontend|10-scripts|09-infra|08-qa|04-docs|12-governance)"
    r"/[\w./-]+\.\w{1,5}|docker-compose\.yml|CLAUDE\.md)"
)

#: Only a CLOSED row makes a claim a file could carry.
CLOSED_STATUS = {"fixed", "fixed-in-part", "closed"}

#: Exact count at 2026-09-01, measured, never a round number.
#:
#: ⚠ 123 AND NOT THE 103 QUOTED IN THE DOCSTRING ABOVE. The 103 was measured
#: over code only (`06-backend`, `07-frontend`, `10-scripts`, `09-infra`); this
#: gate also reads a surface pointing at `04-docs` or `12-governance`, because a
#: ruling recorded in a rules file is as locatable as a line of Python and a
#: reader grepping for the id there is in exactly the same position. The two
#: numbers are both real and the wider one is the one this gate holds.
TRACELESS_BASELINE = 123


def _rows() -> list[dict[str, str]]:
    with REGISTER.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _pairs() -> list[tuple[str, str]]:
    """`(defect id, file)` for every closed row naming a file that exists."""
    out = []
    for row in _rows():
        if (row.get("status") or "").strip() not in CLOSED_STATUS:
            continue
        surface = row.get("surface") or ""
        for match in PATH_IN_SURFACE.finditer(surface):
            rel = match.group(1)
            if (REPO / rel).is_file():
                out.append((row["id"], rel))
    return sorted(set(out))


def traceless(strip: tuple[str, str] | None = None) -> list[tuple[str, str]]:
    """Pairs where the file the register points at never mentions the id.

    `strip` removes ONE id from ONE file in memory — the law-7 self-test uses it
    to replay DEF-2792, whose file today carries the right id.
    """
    cache: dict[str, str] = {}
    out = []
    for ident, rel in _pairs():
        if rel not in cache:
            cache[rel] = (REPO / rel).read_text(encoding="utf-8", errors="replace")
        text = cache[rel]
        if strip is not None and strip == (ident, rel):
            text = text.replace(ident, "DEF-XXX")
        if ident not in text:
            out.append((ident, rel))
    return out


def run() -> tuple[str, str]:
    if not REGISTER.exists():
        return "SKIP", "nothing to check — 12-governance/10-defect-log.csv not present"

    pairs = _pairs()
    found = traceless()

    # ── PART 0 · SELF-TEST (law 7): replay DEF-2792 itself ────────────────
    # DEF-340's surface names docker-compose.yml and the file carries the id
    # today, so a green run proves nothing on its own. Strip it in memory: the
    # pair must come back, or this gate is not reading the file at all.
    probe = ("DEF-340", "docker-compose.yml")
    if probe in pairs:
        replayed = traceless(strip=probe)
        if probe not in replayed:
            return "FAIL", (
                "SELF-TEST FAILED: removing DEF-340 from docker-compose.yml in memory did "
                "not produce a finding, so this gate is not reading the file the register "
                "points at — the whole of DEF-2792"
            )
    elif not found:
        return "FAIL", (
            "SELF-TEST FAILED: DEF-2792's own pair (DEF-340 / docker-compose.yml) is no "
            "longer in the checked set and nothing else is failing either, so nothing "
            "here can be shown to bite. Point the probe at another closed row whose "
            "surface names a file."
        )

    count = len(found)
    if count > TRACELESS_BASELINE:
        newest = [f"{i} says {p}" for i, p in found][-4:]
        return "FAIL", (
            f"traceless fixes ROSE to {count} from a baseline of {TRACELESS_BASELINE}: a row "
            f"marked closed names a file, and that file never mentions the id — so a lane "
            f"grepping for it finds nothing and concludes the fix was never made (DEF-2792, "
            f"which sat `open` for twelve days over exactly this). Name the defect in the "
            f"code you changed, or correct the row's surface. Recent: {'; '.join(newest)}"
        )
    if count < TRACELESS_BASELINE:
        return "FAIL", (
            f"traceless fixes FELL to {count} from {TRACELESS_BASELINE} — lower "
            f"TRACELESS_BASELINE in the SAME commit, or this gate keeps claiming debt that "
            f"is already paid off"
        )

    return "PASS", (
        f"{len(pairs)} closed row(s) name a file that exists; {count} of them are not "
        f"mentioned in that file (at the baseline of {TRACELESS_BASELINE}, may fall and "
        f"never rise). REPORTED, not blocked: an absent id and a WRONG id look the same "
        f"from here, and only a person who knows what the other id was about can tell — "
        f"this hands them {count} places instead of 1,850 files. "
        f"`--report` lists them; self-test: DEF-2792's own pair bites."
    )


def main() -> int:
    if "--report" in sys.argv:
        for ident, rel in traceless():
            print(f"{ident:10s} says {rel}, and {rel} never mentions it")
        return 0
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
