#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2464's sibling finding (2026-08-30). The day's status report
#           measured EIGHT `DEF` rows reading `open` whose fix is on this
#           branch — three of them CRITICAL (DEF-2487, DEF-2519, DEF-2515;
#           also DEF-2518, DEF-2506, DEF-2503, DEF-2476, DEF-1712) — and
#           DEF-2464 itself makes nine: its row reads `open` with an empty
#           `fixed_commit` while commit 4e385f0 carries the fix.
#           Step 4 of 12-governance/19-execution-sequence.md triages FROM these
#           numbers, so a stale row aims a whole lane at work already shipped.
# Rules:    CLAUDE.md "Defect register" · r11 step 0 (check the packet is
#           current) · law 1 (a comment claiming a guarantee is not the
#           guarantee) · DEF-182 (a check whose output cannot distinguish pass
#           from fail is worse than no check, because it is trusted).
# ───────────────────────────────────────────────────────
"""G55 — a commit subject that CLAIMS a defect fixed may not point at an OPEN row.

THE THIRD MEMBER OF A FAMILY THAT ALREADY HAS TWO
--------------------------------------------------
    G50: prose claims a defect was FILED    → the row must EXIST.
    G51: code  claims a defect is CLOSED    → the row must not read `open`.
    G55: a COMMIT SUBJECT claims a fix      → the row must not read `open`.

Same shape, a third surface, and the one surface where a lane's claim is
timestamped and immutable.

⚠ WHY THIS IS NOT "EVERY OPEN ROW NAMED IN A COMMIT SUBJECT", AND THE NUMBERS
------------------------------------------------------------------------------
The obvious check is *flag every `open` row whose id appears in a commit
subject*. It was written and MEASURED FIRST, at branch tip `4e385f0`, over
1,863 commits and 1,088 register rows:

    open rows                                                 392
    (A) open + id appears in ANY commit subject               119
    (B) A, and `fixed_commit` is empty                        118
    (C) A, and a fix VERB appears anywhere in the subject      28
    (D) A, and the subject CLAIMS THE FIX of that id            1

**(B) is the narrowing that suggests itself, and it does not narrow.** A row
that reads `open` has an empty `fixed_commit` almost by construction — 391 of
the 392 — so (B) removes exactly one row from (A). It was measured rather than
assumed, and the measurement is why it is not the gate.

**(A) at 119 is a gate people learn to ignore.** G28's own docstring records the
ruling this repo already made about that number problem, and G44 words it: *"a
gate red from birth earns a `# noqa` instead of a fix"*.

**(C) at 28 cannot distinguish pass from fail.** Read the real subjects and the
verb usually belongs to a DIFFERENT id in the same sentence — `"CR-045 wave G —
DEF-1702 CLOSED, and the eleventh bare list is FILED as DEF-1783"` puts a
closure verb in the same subject as a row that is correctly open. Shipping it
would be DEF-182 for the sixth time.

So the BLOCKING clause is (D): the id and the claim about it are adjacent, which
is the only form that says something about *that* row. It finds one today and
that is the honest yield — G50's docstring records the identical choice, where
the broad version reported 24 dangling ids of which nearly all were artefacts of
the check, and was thrown away for the narrow question.

**(A) IS NOT DISCARDED — IT IS REPORTED, WHICH WAS THE OTHER OPTION AND IS THE
ONE TAKEN.** The count prints in this gate's own detail line on every run, the
full list is one command away (`--report`), and `10-scripts/defect_report.py`
— the script step 4 triages from — grew a `Fix drift` section carrying the same
number. A report that reaches the person doing the triage is worth more than a
red nobody reads. Recorded in `12-governance/02-decision-log.md`, 2026-08-30.

⚠ AN ID IN A COMMIT SUBJECT IS NOT PROOF OF A FIX, AND THIS GATE SAYS SO
--------------------------------------------------------------------------
A commit can name a defect it merely touches, reproduces, files or argues with.
Six of the nine known-stale rows above are named by subjects with no verb at all
— `"DEF-2515 (critical) — the worker carries no role, so the import writer must
not demand one"` is a fix, and `"DEF-2487 — the accounts import commit 500,
reproduced"` is not, and no regex separates them. **The report's claim is "these
need a human glance", never "these are fixed"**, and its own output says that
sentence. Two of the nine (DEF-2503, DEF-2476) appear in NO commit subject at
all, so the report is not even a complete list of what is stale — a fourth
reason it is a report and not a gate.

BANKED, BY NAME AND NOT BY COUNT
---------------------------------
One row is claimed fixed by a commit subject and still reads `open`:

    DEF-1712  e3adf2e6  "DEF-1712 resolved without the PO — the exclusion list
                         was a lane's inference, and the PO's own words settle it"

It is banked rather than closed because closing it is a governance judgment
about a PO ruling and not a tooling lane's call — the same posture
`g48`/`g49` take, and the reason those bank BY NAME: a named set fails at a
SECOND offender's own name instead of hiding inside a count, and goes RED as
stale when the row is finally closed (DEF-490's shape).

TRUNCATED HISTORY IS A SKIP, NOT A PASS — AND THE TEST IS DEPTH
----------------------------------------------------------------
`actions/checkout@v4` clones depth 1 by default: one commit, one subject, and
this gate would report a confident zero over a register it had not looked at —
a check that cannot fail (DEF-182). It SKIPs below `MIN_COMMITS` and names the
cause, and `.github/workflows/gates.yml` set `fetch-depth: 0` so the real
enforcement point never took that branch. ⚠ NOT ANY MORE — every workflow was disabled on 2026-09-04 (PO: Actions minutes exhausted); see .github/workflows/README.md. Run it by hand. A shallow local clone WILL
take that branch, so check the SKIP line rather than the exit code.

⚠ **THE FIRST DRAFT KEYED ON `git rev-parse --is-shallow-repository` AND WAS
WRONG, MEASURABLY.** This repo's working checkouts report that flag `true`
while holding **1,863 commits** — shallow and deep at once — so that gate
SKIPped on the very machine it was written on and would have SKIPped in CI too:
a gate whose only reachable outcome is SKIP, which is precisely the family of
failure G50/G51/G55 exist to close. Depth is the property that matters, so
depth is what is read.

RED PROOF (hard-won law 7)
---------------------------
With the bank emptied, at the tip:

    G55 FAIL — 1 commit subject(s) claim a fix for a row that still reads open,
    baseline 0: commit e3adf2e6 claims DEF-1712 is fixed ("DEF-1712 resolved
    without the PO …") and the register row reads 'open'. …

and PASS with DEF-1712 banked. The self-test below proves each clause bites on
text built here, so the proof does not expire when the tree moves.
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "12-governance" / "10-defect-log.csv"

#: Statuses that mean "this row is done with" (G51's list, deliberately shared
#: in shape so the two gates cannot drift into disagreeing about closure).
CLOSED_STATUSES = frozenset(
    {"fixed", "closed", "wontfix", "invalid", "duplicate", "fixed-in-part", "partially-fixed"}
)

_VERB = r"(?:fix(?:es|ed|ing)?|close[sd]?|closing|resolve[sd]?|resolving|repair(?:s|ed)?)"

#: `fix DEF-1`, `closes DEF-1 and DEF-2`, `resolved for DEF-3` — the verb in
#: front of the id, optionally over a short list of ids that all share it. The
#: separator admits `and`/`&`/`,`/`/`/`+` and NOTHING else, so the list cannot
#: run on into the rest of the sentence and adopt an id the verb never governed.
_JOIN = r"(?:\s*(?:,|/|&|\+|and)\s*)+"
CLAIM_BEFORE = re.compile(
    rf"\b{_VERB}\b(?:\s+(?:for|in|on|the)\b)?[:\s]+((?:DEF-(?:[A-Z]{3}-)?\d+{_JOIN})*DEF-(?:[A-Z]{3}-)?\d+)", re.I
)

#: `DEF-1 fixed`, `DEF-2 is now closed`, `DEF-3 CLOSED` — the id in front and
#: the state word within a few characters, never across a clause boundary
#: (`.`, `;`, `|`), which is what stops a verb belonging to a NEIGHBOURING id
#: being read as a claim about this one.
CLAIM_AFTER = re.compile(
    r"\b(DEF-(?:[A-Z]{3}-)?\d+)\b[^.;|]{0,12}?\b(?:is\s+|now\s+)?(?:fixed|closed|resolved|repaired)\b", re.I
)

#: Any mention at all — the REPORTED population (A above), never the blocking one.
ANY_MENTION = re.compile(r"\bDEF-(?:[A-Z]{3}-)?\d+\b")

#: Offenders that may stay while their row does. NAMED, not counted: a second
#: offender fails at its own name, and a bank left behind after its row closes
#: goes RED as stale.
BANKED: dict[str, str] = {
    "DEF-1712": (
        "claimed by e3adf2e6; closing the row is a governance judgment about a PO "
        "ruling on the CR-040 exclusion list, not a tooling lane's call"
    ),
}


def claimed_ids(subject: str) -> set[str]:
    """Every defect id this subject CLAIMS to have fixed. Adjacency only."""
    hits: set[str] = set()
    for match in CLAIM_BEFORE.finditer(subject):
        hits.update(re.findall(r"DEF-(?:[A-Z]{3}-)?\d+", match.group(1)))
    for match in CLAIM_AFTER.finditer(subject):
        hits.add(match.group(1))
    return hits


def _statuses() -> dict[str, str]:
    if not REGISTER.exists():
        return {}
    with REGISTER.open(encoding="utf-8", newline="") as fh:
        return {
            r["id"]: (r.get("status") or "").strip()
            for r in csv.DictReader(fh)
            if r.get("id", "").startswith("DEF-")
        }


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=180
    )


#: Below this many readable commits the history is a CI truncation, not a
#: branch, and a zero here would mean nothing. ⚠ THE TEST IS DEPTH, NOT THE
#: SHALLOW FLAG, and that was measured: this repo's own checkouts report
#: `is-shallow-repository true` while holding 1,863 commits, so a gate keyed on
#: the flag would SKIP on every machine including CI — a check that can only
#: ever SKIP, which is the failure this gate's own siblings exist to prevent.
MIN_COMMITS = 50


def _subjects() -> tuple[list[tuple[str, str]], str]:
    """(sha, subject) for every commit reachable from HEAD, or ([], why)."""
    log = _git("log", "--format=%H%x1f%s", "HEAD")
    if log.returncode != 0:
        return [], f"git log failed: {log.stderr.strip()[:200]}"
    out: list[tuple[str, str]] = []
    for line in log.stdout.splitlines():
        if "\x1f" in line:
            sha, subject = line.split("\x1f", 1)
            out.append((sha, subject))
    if len(out) < MIN_COMMITS:
        shallow = _git("rev-parse", "--is-shallow-repository").stdout.strip() == "true"
        return [], (
            f"only {len(out)} commit subject(s) are readable (fewer than {MIN_COMMITS}"
            f"{'; the checkout is shallow' if shallow else ''}) — this gate would report "
            "a confident zero over a register it never looked at. Check out with "
            "`fetch-depth: 0`. CI used to guarantee that and no longer runs "
            "(disabled 2026-09-04 — .github/workflows/README.md), so deepen "
            "the clone yourself."
        )
    return out, ""


def selftest() -> list[str]:
    """Prove each clause bites, on subjects written here rather than on the log."""
    broken: list[str] = []
    if claimed_ids("fix(i18n): the 19 wizard step labels land; DEF-717") != set():
        broken.append("a trailing id with the verb in a scope prefix was read as a claim")
    if "DEF-717" not in claimed_ids("fix DEF-717 — the wizard labels"):
        broken.append("`fix DEF-717` was not read as a claim")
    if "DEF-1" not in claimed_ids("DEF-1 is now fixed"):
        broken.append("`DEF-1 is now fixed` was not read as a claim")
    if claimed_ids("DEF-2487 — the accounts import commit 500, reproduced"):
        broken.append("a REPRODUCTION was read as a claim")
    if claimed_ids("DEF-2515 (critical) — the worker carries no role"):
        broken.append("a bare description was read as a claim")
    if claimed_ids("CR-045 wave G — DEF-1702 CLOSED, and the eleventh is FILED as DEF-1783") != {
        "DEF-1702"
    }:
        broken.append("a closure verb leaked across a clause onto a NEIGHBOURING id")
    if claimed_ids("closes DEF-10 and DEF-11") != {"DEF-10", "DEF-11"}:
        broken.append("a shared verb over two ids did not reach both")
    if claimed_ids("see DEF-9, whose shape recurs here"):
        broken.append("a mere mention was read as a claim")
    return broken


def findings() -> tuple[list[str], int, int, list[tuple[str, str, str]]]:
    """(offenders, mentioned-open count, commits read, the reported rows)."""
    statuses = _statuses()
    subjects, _ = _subjects()
    offenders: list[str] = []
    mentioned: dict[str, tuple[str, str]] = {}
    for sha, subject in subjects:
        for row_id in claimed_ids(subject):
            status = statuses.get(row_id)
            if status is None or status in CLOSED_STATUSES or row_id in BANKED:
                continue
            offenders.append(
                f"commit {sha[:8]} claims {row_id} is fixed (\"{subject[:70]}\") and the "
                f"register row reads '{status}'. Close the row with its fixed_commit, "
                "or reword the claim."
            )
        for row_id in set(ANY_MENTION.findall(subject)):
            if statuses.get(row_id) == "open" and row_id not in mentioned:
                mentioned[row_id] = (sha[:8], subject)
    reported = sorted(
        ((rid, sha, subject) for rid, (sha, subject) in mentioned.items()),
        key=lambda t: int(t[0].rsplit("-", 1)[1]),
    )
    return offenders, len(mentioned), len(subjects), reported


def run() -> tuple[str, str]:
    broken = selftest()
    if broken:
        return "FAIL", "the gate's own self-test did not bite: " + "; ".join(broken)
    if not _statuses():
        return "FAIL", f"no register at {REGISTER} — this gate has nothing to check"
    subjects, why = _subjects()
    if not subjects:
        return "SKIP", why

    offenders, mentioned, commits, _ = findings()
    # A bank entry may not outlive what justified it (DEF-490's shape), and a
    # MISTYPED one is worse than none: it silences nothing and looks like cover.
    statuses = _statuses()
    stale_bank = sorted(k for k in BANKED if statuses.get(k) in CLOSED_STATUSES)
    ghost_bank = sorted(k for k in BANKED if k not in statuses)
    if stale_bank or ghost_bank:
        parts = []
        if stale_bank:
            parts.append(
                f"{', '.join(stale_bank)} is banked here and its register row is now "
                "closed — take it out of BANKED, or the bank hides the next offender"
            )
        if ghost_bank:
            parts.append(
                f"{', '.join(ghost_bank)} is banked here and has NO register row — a "
                "mistyped bank entry silences nothing and reads as cover"
            )
        return "FAIL", "; ".join(parts)
    if offenders:
        return "FAIL", (
            f"{len(offenders)} commit subject(s) claim a fix for a row that still reads "
            f"open, baseline 0 ({len(BANKED)} banked by name): " + "; ".join(offenders)
        )
    return "PASS", (
        f"{commits} commit subject(s) read; 0 claim a fix for an open row "
        f"({len(BANKED)} banked by name). REPORTED, not blocked: {mentioned} open row(s) "
        "are NAMED by a commit subject — an id in a subject is not proof of a fix, so "
        "these need a human glance, not a status change. `python3 10-scripts/gates/"
        "g55_commit_fix_claims.py --report` lists them; self-test: 8/8 clauses bite"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--report",
        action="store_true",
        help="list the open rows named by a commit subject (the REPORTED population)",
    )
    args = parser.parse_args()

    if args.report:
        subjects, why = _subjects()
        if not subjects:
            print(f"G55 report unavailable — {why}")
            return 1
        _, mentioned, commits, reported = findings()
        print(
            f"{mentioned} open defect row(s) are named by a commit subject on this "
            f"branch, across {commits} commits.\n"
            "⚠ AN ID IN A COMMIT SUBJECT IS NOT PROOF OF A FIX. A commit can name a "
            "defect it reproduces, files, or merely touches. This list says WHICH ROWS "
            "NEED A HUMAN GLANCE, not which are fixed — and it is not complete either: "
            "a row fixed by a commit that never named it does not appear here.\n"
        )
        for row_id, sha, subject in reported:
            print(f"  {row_id:<10} {sha}  {subject[:96]}")
        return 0

    status, note = run()
    print(f"G55 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
