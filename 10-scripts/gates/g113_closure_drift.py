#!/usr/bin/env python3
"""G113 — a commit that says it fixed a defect, over a row that still reads open.

WHY THIS GATE EXISTS (2026-09-05)
---------------------------------
The register's open count was not trustworthy and the error ran ONE WAY: it was
too high. Earlier on 2026-09-05 the portal's 67 open rows were verified against
the code and 24 were real; forty-three described work that had already shipped.

THE MECHANISM IS ONE ACT SPLIT IN TWO, AND ONLY THE FIRST FEELS LIKE THE WORK.
A lane fixes a fault, writes an honest commit message saying so, and files its
own row about what it found. It does not go back and close the row that
REPORTED the fault, because closing someone else's row is a separate, riskier
edit to a file ten lanes are writing (that is exactly why `close_defect.py`
exists). So the same fault ends up recorded twice — once as an open report and
once as a closed fix — and only the second one is honest.

Nothing could see it. `DEF-WRK-4027` stopped every PostgreSQL migration on the
branch, was fixed at 17:10 in `5ab3d2df` with a commit message that names it in
its SUBJECT LINE, and its row still read `open` hours later. Every gate was
green, because no gate reads a commit message against the register.

WHAT IT CHECKS, AND WHY IT IS DELIBERATELY NARROW
-------------------------------------------------
It reads recent commit messages, finds the ones that ASSERT a defect is fixed,
and looks that defect up in the register. A row still reading `open` or
`reported` under such an assertion is the drift.

**Precision was the whole design problem.** A first draft matched any
fix-shaped word near a defect id and was right about 40% of the time over the
repo's history — it read *"must not be used until DEF-195 is fixed"* and
*"the day DEF-2967 is fixed the case goes red"* as closures. Both are the
OPPOSITE claim. A merge gate that is wrong three times in five gets switched
off, so this one:

  * matches only a short list of ASSERTING forms — `closes DEF-x`,
    `DEF-x is fixed`, `DEF-x — FIXED`, `fix: … (DEF-x)`;
  * refuses the match when a CONDITIONAL word governs it (`until`, `once`,
    `when`, `the day`, `so that`, `before`, `after`), which is what every one
    of the historic false positives had;
  * refuses it when the sentence carries a negation the repo actually uses —
    `parked`, `not fixed`, `filed, not fixed`, `still open`, `records what`;
  * and CARRIES A BASELINE, so drift that already exists does not block anyone.
    Only NEW drift fails, which is the ratchet shape G15 and G28 already use.

It is not trying to find every stale row — reading the CODE is the only thing
that does that, and it is what the 2026-09-05 audit had to do by hand. It
catches the specific, cheap case where the repo already told us in writing and
nobody wrote it down.

WHAT IT COSTS
-------------
One `git log` over a bounded window (400 commits) and one read of the register.
Under two seconds. No network.

⚠ PROVED RED THROUGH `run_gates`' OWN IMPORT PATH, not `python3 g113…py`
(`DEF-GOV-3733`: two gates were announced green while the suite reported
`gate crashed: module has no attribute 'run'`, because `__main__` and `run()`
are different entry points and only one of them is what the suite calls).
"""
from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTER = REPO_ROOT / "12-governance" / "10-defect-log.csv"
BASELINE = Path(__file__).resolve().parent / "g113_closure_drift_baseline.txt"

WINDOW = 400  # commits back from HEAD; the drift we care about is recent

# A row under one of these statuses is not asserting the work is done.
LIVE_STATUS = {"open", "reported"}

# ⚠ THE LOOKAHEAD IS LOAD-BEARING — CLAUDE.md's five-digit ruling. Without it
# `DEF-407` matches inside `DEF-4071`, a different and real defect.
ID = r"DEF-(?:[A-Z]{3}-)?\d{2,5}(?!\d)"

ASSERTING = [
    re.compile(r"\b(?:closes|closed|fixes|fixed|resolves|resolved)\s+(?:by\s+)?(" + ID + r")", re.I),
    re.compile(r"(" + ID + r")\s*(?:—|-|:|,)?\s*(?:is|was|are|were)\s+(?:now\s+)?(?:fixed|closed|resolved)\b", re.I),
    re.compile(r"(" + ID + r")\s*(?:—|-|:)\s*FIXED\b"),
    re.compile(r"\bfix(?:ed)?\s*:[^\n]{0,90}?\((" + ID + r")\)", re.I),
]

# Every historic false positive had one of these governing the clause.
CONDITIONAL = re.compile(
    r"\b(until|once|when|whenever|the day|so that|before|after|if|unless|would be|will be|"
    r"cannot be|can be|to be|needs? to be|waiting)\b",
    re.I,
)
NEGATION = re.compile(
    r"\b(parked|not fixed|filed,? not fixed|still open|remains? open|left open|deferred|"
    r"records? what|reported rather than|not yet|no longer accurate)\b",
    re.I,
)


def _register() -> dict[str, str]:
    """id -> status, for every row wide enough to read. A malformed row is G26's."""
    out: dict[str, str] = {}
    with REGISTER.open(encoding="utf-8", newline="") as fh:
        rows = csv.reader(fh)
        header = next(rows)
        try:
            i_id, i_st = header.index("id"), header.index("status")
        except ValueError:
            return out
        for row in rows:
            if len(row) == len(header):
                out[row[i_id].strip()] = row[i_st].strip()
    return out


def _baseline() -> set[str]:
    if not BASELINE.exists():
        return set()
    return {
        ln.split("#", 1)[0].strip()
        for ln in BASELINE.read_text(encoding="utf-8").splitlines()
        if ln.split("#", 1)[0].strip()
    }


def _commits() -> list[tuple[str, str]] | None:
    """(sha, message) for the recent window. None when git cannot answer."""
    try:
        raw = subprocess.run(
            ["git", "log", f"-{WINDOW}", "--format=%H%x00%B%x01"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=60, check=True,
        ).stdout
    except Exception:
        return None
    out = []
    for chunk in raw.split("\x01"):
        if "\x00" not in chunk:
            continue
        sha, _, msg = chunk.partition("\x00")
        out.append((sha.strip(), msg))
    return out


def check() -> tuple[list[str], list[str], bool]:
    """(violations, notes, git_available)."""
    commits = _commits()
    if commits is None:
        return [], ["git log unavailable; nothing scanned"], False

    status = _register()
    if not status:
        return [], ["register unreadable; G26 owns that"], True
    baseline = _baseline()

    # id -> the first commit that asserted it closed
    asserted: dict[str, str] = {}
    for sha, msg in commits:
        for pat in ASSERTING:
            for m in pat.finditer(msg):
                did = m.group(1)
                # Judge the CLAUSE, not the message: a long commit body says many
                # things, and only the sentence around the id is a claim about it.
                lo = max(0, m.start() - 110)
                hi = min(len(msg), m.end() + 110)
                clause = msg[lo:hi]
                if CONDITIONAL.search(clause) or NEGATION.search(clause):
                    continue
                asserted.setdefault(did, sha[:8])

    violations, notes = [], []
    for did, sha in sorted(asserted.items()):
        st = status.get(did)
        if st is None:
            notes.append(f"{did} is asserted fixed in {sha} and is not in the register")
            continue
        if st in LIVE_STATUS:
            if did in baseline:
                notes.append(f"{did} baselined: {sha} says fixed, row reads {st!r}")
            else:
                violations.append(
                    f"{did}: commit {sha} says it is fixed and its row still reads {st!r} — "
                    f"close it with 10-scripts/close_defect.py --id {did} --status fixed "
                    f"--fixed-commit {sha}, or, if the commit is wrong, say so in the row"
                )
    stale = sorted(b for b in baseline if status.get(b) not in LIVE_STATUS)
    if stale:
        notes.append(
            f"{len(stale)} baselined id(s) are now closed and can leave "
            f"g113_closure_drift_baseline.txt: {', '.join(stale[:6])}"
        )
    notes.append(f"{len(asserted)} closure assertion(s) over the last {WINDOW} commits")
    return violations, notes, True


def main() -> int:
    violations, notes, _ = check()
    for note in notes:
        print(f"note: {note}")
    for bad in violations:
        print(f"FAIL: {bad}")
    if violations:
        print(
            f"\n{len(violations)} row(s) describe work a commit says is done. The register's "
            "open count is what the Product Owner plans from, and it drifts one way only."
        )
        return 1
    print("closure drift: every defect a recent commit says it fixed is closed in the register")
    return 0


def run():
    """Runner contract: ('PASS'|'FAIL'|'SKIP', detail)."""
    violations, notes, git_ok = check()
    if not git_ok:
        return "SKIP", "git log unavailable"
    if violations:
        return "FAIL", f"{len(violations)} defect(s) fixed in a commit and still open: {violations[0]}"
    return "PASS", "no closure drift" + (f" ({notes[-1]})" if notes else "")


if __name__ == "__main__":
    raise SystemExit(main())
