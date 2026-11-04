#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   The Product Owner asked for a status of CR-051..055 twice on
#           2026-08-31 and got two different answers, because both registers
#           are derived from markers that are wrong in both directions. Nine
#           finished tasks were found that day whose row still read blocked or
#           pending, and 42 defect rows were closed the same day that had been
#           finished work reading `open`.
# Rules:    CLAUDE.md law 1 (a comment claiming a guarantee is not the
#           guarantee) · law 9/W (write back before the thing that depends on
#           it) · DEF-182 (a check whose output cannot distinguish pass from
#           fail is worse than no check, because it is trusted).
# ───────────────────────────────────────────────────────
"""G62 — a CR task row that says it is BLOCKED must name an id that is still live.

THE FOURTH MEMBER OF A FAMILY THAT ALREADY HAS THREE
-----------------------------------------------------
    G50: prose claims a defect was FILED     -> the row must EXIST.
    G51: code  claims a defect is CLOSED     -> the row must not read `open`.
    G55: a COMMIT SUBJECT claims a fix       -> the row must not read `open`.
    G62: a CR TASK claims it is BLOCKED      -> the blocker must still be live.

Same shape, a fourth surface, and the one surface the Product Owner reads a
status out of.

⚠ WHAT THIS DELIBERATELY DOES NOT CHECK, AND WHY, MEASURED FIRST
-----------------------------------------------------------------
The failure everyone wants a gate for is the OTHER direction: a task that is
DONE whose row does not say so. **No honest gate can ask that**, and CR-051's
own write-up of 2026-08-31 already recorded the reason in one sentence:

    "A gate that demanded a shipped row for every task would be satisfied by
     writing the row, not by doing the work."

That is exactly right, and it is why this file does not try. Prose that claims
completion is unfalsifiable by construction — the claim and the evidence are the
same string.

**A BLOCK IS DIFFERENT, AND THAT IS THE WHOLE IDEA.** A row saying *"BLOCKED ON
`OQ-291`"* makes a claim about a DIFFERENT FILE that a machine can go and read.
It cannot be satisfied by writing better prose: `OQ-291` has to actually be open
in `01-open-questions.md`, or the sentence is false. That is the same asymmetry
G50, G51 and G55 each found on their own surface.

THE NUMBERS, MEASURED BEFORE THIS WAS BUILT (2026-08-31, branch tip 2c26e1f7)
------------------------------------------------------------------------------
    CR task rows read                                        489
    rows CLAIMING a block                                      2
    blocks naming an id that is NOT live                       3

⚠ **TWO OF 489 IS THE HONEST YIELD AND IT IS WORTH SAYING OUT LOUD.** This gate
reads a small corner of the register. The corner it reads is the one that was
wrong: both rows claiming a block on 2026-08-31 were stale, and one of them —
CR-052 task 17 — is a signed rule (`BR-RAT-960`/`BR-RAT-961`) that had been BUILT
while its row still told a reader it was waiting on the Product Owner. G55's
docstring makes the identical argument for a narrow blocking clause over a broad
noisy one, and records that its own honest yield was ONE row.

⚠ **AND A STALE BLOCK IS THE EXPENSIVE HALF OF THE PROBLEM, NOT THE CHEAP ONE.**
An unrecorded completion makes the repo look further behind than it is, which
costs a re-derivation. A stale BLOCK sends a lane to wait for a person, or sends
a question back to the Product Owner that they already answered — which is
CLAUDE.md law 13 (*"never ask the PO the same thing twice"*), and the PO's own
words for what it costs: *"this is very exzuating and taxing as a human."*

BORN HONEST, WHICH IS THIS REPO'S OWN RECIPE
---------------------------------------------
The 2026-08-27 decision-log entry measured why some gate families breach and one
never does, and the finding was not about subject matter: **every holding gate
that carries a baseline had it set to what was actually there** (`G40` at 1,
`G34` at 4, `G38` at 84, `G30` at 56) and every permanently-red one was given a
number somebody wished for. *"A baseline that may fall and never rise is a
ratchet; a baseline nobody can reach is decoration."*

So `STALE_BLOCK_BASELINE` is **3**, which is what is there today, and it may
FALL and never RISE. Lowering it as the two rows are corrected is the intended
maintenance, and correcting them is a documentation edit in a file six lanes
share — deliberately not done in the same commit as the gate.

WHAT A ROW LOOKS LIKE
---------------------
A CR task row is a markdown table row whose FIRST cell is a bare task number:

    | 17 | W5 | **BUILT TO THE BOUNDARY — BLOCKED ON `OQ-291` AND `OQ-292`** | ...

`BLOCKED ON` / `BLOCKED BY` (either case) is the claim; every `OQ-` and `DEF-`
id in the same row is a named blocker. An id that reads CLOSED (a question) or
anything other than `open` (a defect) is a finding.

⚠ THE ID PATTERN IS `\\d{3,5}(?!\\d)` AND THE LOOKAHEAD IS LOAD-BEARING (DEF-2804).
`OQ-\\d{3}` does not SKIP `OQ-1190`, it returns `OQ-119` — a different, real
question — which is how a rating-math file's `OQ-1166` was read as `OQ-116` for
two days (DEF-2820). Without the lookahead `OQ-123456` reads as `OQ-12345`, the
same bug one order of magnitude up.

⚠ THE OPEN-QUESTION REGISTER IS TWO SHAPES AND READING ONLY ONE IS A CHECK THAT
CANNOT FAIL. Most questions are TABLE ROWS whose LAST cell is the status; some
are `## OQ-nnn` SECTIONS with a `**Status:**` line. The first draft of this file
read sections only and truncated table rows to 200 characters — so it found
`0` findings and reported PASS over the very row it was written for, because
`**CLOSED(→BR-RAT-960)**` sits at the END of a 4,000-character row. Both shapes
are read here and the self-test asserts both.

USAGE
    python3 10-scripts/gates/g62_cr_task_blockers.py            # PASS/FAIL
    python3 10-scripts/gates/g62_cr_task_blockers.py --report   # every claim
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
CHANGES = REPO / "12-governance" / "11-change-requests.md"
REGISTER = REPO / "12-governance" / "10-defect-log.csv"
QUESTIONS = REPO / "12-governance" / "01-open-questions.md"

# ── THE RATCHET ────────────────────────────────────────────────────────────
# 3 stale blocks on 2026-08-31, in 2 rows, both in CR-052:
#   task 17 -> OQ-291 (CLOSED→BR-RAT-960) and OQ-292 (CLOSED→BR-RAT-961)
#   task  9 -> DEF-2714 (fixed)
# The number may FALL and must never RISE.
STALE_BLOCK_BASELINE = 3

#: CLAUDE.md's id grammar. FIVE digits since the PO's ruling of 2026-08-31, and
#: the lookahead stops `OQ-1190` being read as `OQ-119` (DEF-2804).
ID_RE = re.compile(r"\b(OQ|DEF)-(\d{3,5})(?!\d)")

#: The claim. Either spelling, either case — a row saying "blocked by DEF-x" is
#: making the same statement as one saying "BLOCKED ON DEF-x".
BLOCK_RE = re.compile(r"BLOCKED\s+(?:ON|BY)", re.I)

#: A task row's first cell: a bare number, optionally with a letter suffix
#: (CR-052 carries a task `1a`).
TASK_CELL_RE = re.compile(r"^\s*\d{1,3}[a-z]?\s*$")

#: A defect row that is anything but `open` is not a live blocker. `reported` is
#: deliberately LIVE — it is a row nobody has triaged, not a closed one.
LIVE_DEFECT_STATUS = {"open", "reported"}


def defect_statuses() -> dict[str, str]:
    with REGISTER.open(newline="", encoding="utf-8") as handle:
        return {row["id"]: (row.get("status") or "").strip() for row in csv.DictReader(handle)}


def question_statuses() -> dict[str, str]:
    """`OQ-id -> the text that states its status`, from BOTH register shapes.

    Sections win over table rows where a question somehow has both, because a
    section is the fuller record and is what a human reads.
    """
    text = QUESTIONS.read_text(encoding="utf-8")
    out: dict[str, str] = {}

    # Shape 1 — `| OQ-nnn | … | **CLOSED(→BR-RAT-960)** |`. The status is the
    # LAST cell, which on this register is routinely thousands of characters
    # from the id. Truncating the row loses it (see the docstring).
    for line in text.splitlines():
        head = re.match(r"\|\s*(?:\*\*)?(OQ-(?:[A-Z]{3}-)?\d{3,5})(?!\d)", line)
        if head is None:
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) > 2:
            out[head.group(1)] = cells[-2]

    # Shape 2 — `## OQ-nnn — …` followed by a `**Status:**` line.
    for section in re.split(r"\n(?=## OQ-)", text):
        head = re.match(r"## (OQ-(?:[A-Z]{3}-)?\d{3,5})(?!\d)", section)
        if head is None:
            continue
        status = re.search(r"\*\*Status:\*\*\s*(.{0,120})", section)
        out[head.group(1)] = (status.group(1) if status else "?").strip()

    return out


def _question_is_live(status: str) -> bool:
    """A question is live unless its status says it is closed or answered."""
    upper = status.upper()
    if "✅" in status or "⚖️" in status:
        return False
    return not any(word in upper for word in ("CLOSED", "ANSWERED", "SUPERSEDED", "WITHDRAWN"))


def check(
    markdown: str | None = None,
    defects: dict[str, str] | None = None,
    questions: dict[str, str] | None = None,
) -> tuple[list[str], int, int]:
    """`(findings, task_rows_read, rows_claiming_a_block)`.

    Every argument is injectable so the self-test can put a known-bad row in
    front of it — a gate proved only against the live corpus is a gate whose
    RED branch nobody has ever seen (hard-won law 7).
    """
    text = CHANGES.read_text(encoding="utf-8") if markdown is None else markdown
    defect_status = defect_statuses() if defects is None else defects
    question_status = question_statuses() if questions is None else questions

    findings: list[str] = []
    rows = 0
    claims = 0
    current = "(no CR heading yet)"

    for number, line in enumerate(text.splitlines(), 1):
        heading = re.match(r"^##\s+(CR-\d+)", line)
        if heading is not None:
            current = heading.group(1)
        if not line.startswith("| "):
            continue
        cells = line.split("|")
        if len(cells) < 4 or not TASK_CELL_RE.match(cells[1]):
            continue
        rows += 1
        if BLOCK_RE.search(line) is None:
            continue
        claims += 1
        task = cells[1].strip()
        # DEDUPED. A row that names its blocker twice is one stale block, not
        # two — counting the mentions would make the baseline depend on how
        # often a sentence repeats itself.
        for ident in dict.fromkeys(f"{kind}-{num}" for kind, num in ID_RE.findall(line)):
            if ident.startswith("DEF-"):
                status = defect_status.get(ident)
                if status is None:
                    # G50 owns "a claim names a row that does not exist"; this
                    # gate does not double-report it.
                    continue
                live = status in LIVE_DEFECT_STATUS
            else:
                status = question_status.get(ident)
                if status is None:
                    continue
                live = _question_is_live(status)
            if not live:
                findings.append(
                    f"{current} task {task} (line {number}) says it is BLOCKED on {ident}, "
                    f"and {ident} reads {status!r} — the block is over, or the row is wrong "
                    "about which id blocks it"
                )

    return findings, rows, claims


# ── SELF-TEST ──────────────────────────────────────────────────────────────
# Each clause is shown to BITE on a case built for it. DEF-182: a check whose
# output cannot distinguish pass from fail is worse than no check.
_SELFTEST_DEFECTS = {"DEF-111": "open", "DEF-222": "fixed", "DEF-333": "reported"}
_SELFTEST_QUESTIONS = {
    "OQ-111": "open",
    "OQ-222": "**CLOSED(→BR-RAT-960)**",
    "OQ-1190": "open",
    "OQ-119": "**CLOSED**",
}
_SELFTEST_CASES: list[tuple[str, str, int]] = [
    ("a live defect block passes", "| 1 | W0 | BLOCKED ON `DEF-111` | Back |", 0),
    ("a FIXED defect block bites", "| 2 | W0 | BLOCKED ON `DEF-222` | Back |", 1),
    ("a `reported` defect is LIVE", "| 3 | W0 | BLOCKED ON `DEF-333` | Back |", 0),
    ("a live question block passes", "| 4 | W0 | BLOCKED ON `OQ-111` | Back |", 0),
    ("a CLOSED question bites", "| 5 | W0 | BLOCKED ON `OQ-222` | Back |", 1),
    ("lower-case 'blocked by' bites too", "| 6 | W0 | blocked by `OQ-222` | Back |", 1),
    ("a row naming its blocker twice counts ONCE", "| 7 | W0 | BLOCKED ON `OQ-222`, see `OQ-222` | Back |", 1),
    ("a row with NO block claim is not read", "| 8 | W0 | done, `OQ-222` closed it | Back |", 0),
    ("a non-task row is not read", "| # | Wave | BLOCKED ON `OQ-222` | Half |", 0),
    ("an unknown id is G50's, not ours", "| 9 | W0 | BLOCKED ON `DEF-99999` | Back |", 0),
    # DEF-2804 — the five-digit read. `OQ-1190` is live and `OQ-119` is closed,
    # so a three-digit pattern would report a finding here and there is none.
    ("`OQ-1190` is not read as `OQ-119`", "| 10 | W0 | BLOCKED ON `OQ-1190` | Back |", 0),
]


def selftest() -> list[str]:
    failures: list[str] = []
    for name, row, expected in _SELFTEST_CASES:
        found, _, _ = check(
            markdown="## CR-999 — a fixture\n\n" + row + "\n",
            defects=_SELFTEST_DEFECTS,
            questions=_SELFTEST_QUESTIONS,
        )
        if len(found) != expected:
            failures.append(f"self-test {name!r}: expected {expected} finding(s), got {len(found)}")
    return failures


def run() -> tuple[str, str]:
    """`(status, detail)` for `run_gates.py` — the SHAPE the runner unpacks.

    ⚠ DEF-2849 is three days old: `g60`'s `run()` returned a LIST where the
    runner does `status, detail = module.run()`, so that gate reported nothing
    but a crash from the hour it was written and `G42` passed it because G42
    checks that `run()` EXISTS. `main()` delegates here so the two entry points
    cannot disagree.
    """
    broken = selftest()
    if broken:
        return "FAIL", f"self-test does not bite: {broken[0]}"
    findings, rows, claims = check()
    detail = (
        f"{rows} CR task row(s) read, {claims} claim a block; "
        f"{len(findings)} name an id that is no longer live "
        f"(baseline {STALE_BLOCK_BASELINE}); self-test: {len(_SELFTEST_CASES)}/"
        f"{len(_SELFTEST_CASES)} clauses bite"
    )
    if len(findings) > STALE_BLOCK_BASELINE:
        return "FAIL", f"stale blocks ROSE to {len(findings)}, ceiling {STALE_BLOCK_BASELINE}: {findings[0]}"
    return "PASS", detail


def main() -> int:
    status, detail = run()
    if "--report" in sys.argv:
        findings, rows, claims = check()
        print(f"{rows} CR task row(s) read; {claims} claim a block; {len(findings)} stale.")
        print(
            "⚠ THIS GATE READS ONE CORNER OF THE RECORD ON PURPOSE. It cannot ask whether a "
            "task is DONE — prose claiming completion is its own evidence — so it asks the one "
            "thing about a task row that another file can falsify."
        )
        for finding in findings:
            print(f"  {finding}")
    print(f"G62 cr-task-blockers: {status} — {detail}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
