#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2791 (2026-08-31) — SEVEN GUARDED MONEY FILES TELL THE READER
#           THEY ARE UNGUARDED. Each carries a paragraph in its own module
#           docstring saying, in the present tense, that no glob in
#           `10-scripts/gates/human_owned.txt` matches it and that G7 therefore
#           reports conform over it. Every one of them is guarded today and has
#           been for days or weeks.
# Rules:    CLAUDE.md hard-won law 1 (a comment claiming a guarantee is not the
#           guarantee — and a comment claiming an ABSENCE that has stopped being
#           true is worse) · CLAUDE.md law 13 (never put a settled question back
#           to the PO) · `human_owned.txt`'s own header, "who watches the
#           watchers" · law 7 (prove a guard goes RED first)
# Impacts:  10-scripts/gates/human_owned.txt · G7 · G53
# ───────────────────────────────────────────────────────
"""G63 — A GUARDED FILE MAY NOT TELL ITS READER IT IS UNGUARDED.

WHY THIS GATE EXISTS
--------------------
`G7` walks the guard list forward and reads markers. `G53` asks the reverse
question and reads markers. **Neither reads the PROSE, and prose is where the
claim lives**, so all of them pass on a money file whose own docstring says:

    ⚠ **NO GLOB IN `10-scripts/gates/human_owned.txt` MATCHES THIS FILE**, so
    G7 does not read the markers above.

Every sentence like that was TRUE when it was written. Each file was authored
while genuinely unguarded, correctly said so, and correctly asked for a glob
rather than adding itself — the guard list's own header makes adding one a
process event. A later PO ruling granted the glob and edited `human_owned.txt`;
**nothing edited the file that had asked.** The 2026-08-28 ruling that added
three files and the 2026-08-31 ruling that added fifty-six are the two largest
instances.

WHY IT IS WORSE THAN AN ORDINARY STALE COMMENT, IN ONE SPECIFIC WAY
-------------------------------------------------------------------
Hard-won law 1 is about a comment claiming a guarantee that does not exist. This
is that law RUNNING BACKWARDS: a comment claiming an ABSENCE that has stopped
being true. The sentence almost always ends by explaining that a lane may not
add itself and that the line is reported for the PO batch — which reads as a
LIVE INSTRUCTION rather than as history. So the next lane does the correct thing
for a condition that no longer exists: it files a finding that is already
closed, or it puts a settled question back to the PO, **which CLAUDE.md law 13
forbids in as many words** and which the PO has twice said costs them real
effort.

It is also invisible to the person granting the glob, because granting it means
editing `human_owned.txt` and the review ledger — not the file.

WHAT THIS CHECKS
----------------
For every file matched by a glob in `10-scripts/gates/human_owned.txt`: the file
must not contain a present-tense claim that no glob matches it.

**"Present tense" is decided by a MARKER, not by parsing English.** A file may
keep the historical paragraph — why a money file went unguarded for weeks is
worth knowing, and `DEF-2791` says to keep it — as long as a dated correction
stands with it. The correction is what makes the paragraph history:

    ⚠ CORRECTED 2026-08-31 — THE PARAGRAPH BELOW IS HISTORY, NOT THE CURRENT
    STATE. A glob in 10-scripts/gates/human_owned.txt DOES match this file now:
    <which ruling, and when>.

Any of the accepted stamps in `CORRECTION` below satisfies it. They are the
wordings lanes have actually used on 2026-08-28, 08-29 and 08-31, kept verbatim
rather than normalised, because rewriting seven files to suit a regex is the
mass shared-file edit law 11 exists to prevent.

WHY A GATE AND NOT A SWEEP
--------------------------
`DEF-2791`'s own prevention column says it: *"THE DURABLE FIX IS A GATE, NOT A
PROSE SWEEP, because a sweep rots again on the next ruling."* Every PO ruling
that widens the watched list re-creates this defect for free. This is the shape
CLAUDE.md asks for in the words *make your push helper REFUSE* — a check the
next lane inherits instead of a paragraph it has to remember.

PROVED RED BEFORE TRUSTED GREEN (law 7)
---------------------------------------
Part 0 below re-runs the detector with the correction stamps stripped IN MEMORY.
Every corrected file must come back as a finding, or this gate is matching the
claim sentence and nothing else and would pass on a file that never corrected
anything. Nothing is written to disk at any point.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

import fnmatch
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GUARD_LIST = REPO / "10-scripts" / "gates" / "human_owned.txt"

#: The claim, in the shapes the repo actually writes it. Matched over the whole
#: file with whitespace collapsed, because these sentences wrap across lines in
#: a docstring and a line-anchored search misses more than half of them.
CLAIM = re.compile(
    r"(?:no glob in\s+`?10-scripts/gates/human_owned\.txt`?\s+matches"
    r"|matches no glob in\s+`?10-scripts/gates/human_owned\.txt`?"
    r"|no glob in\s+human_owned\.txt\s+matches"
    r"|matches no glob in\s+human_owned\.txt"
    r"|this file matches no glob)",
    re.I,
)

#: A dated correction standing beside the paragraph makes it history. Three
#: wordings are in the tree today; all three are accepted verbatim.
CORRECTION = re.compile(
    r"(?:is history, not the current state"
    r"|that was true when it was written and is not true now"
    r"|this paragraph was true when written and is now false)",
    re.I,
)


def _globs() -> list[str]:
    out = []
    for line in GUARD_LIST.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s.split(None, 1)[0])
    return out


def _tracked() -> list[str]:
    return subprocess.run(
        ["git", "ls-files", "06-backend"],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    ).stdout.split()


def _matches(path: str, globs: list[str]) -> str | None:
    """The first glob in the guard list that covers `path`, or None.

    `fnmatch` treats `*` as crossing `/`, so `**` needs its own translation or
    `06-backend/**/migrations/*rls*` would behave differently here than it does
    in `G7`. Both forms are tried and the first hit wins.
    """
    for g in globs:
        if fnmatch.fnmatch(path, g):
            return g
        if "**" in g:
            pat = (
                re.escape(g)
                .replace(r"\*\*/", "(?:.*/)?")
                .replace(r"\*\*", ".*")
                .replace(r"\*", "[^/]*")
            )
            if re.fullmatch(pat, path):
                return g
    return None


def _findings(strip_corrections: bool = False) -> tuple[list[str], list[str]]:
    """`(uncorrected, corrected)` — guarded files carrying the claim.

    `strip_corrections` removes the dated stamps IN MEMORY, which is the law-7
    self-test: with them gone every corrected file must reappear as a finding.
    """
    globs = _globs()
    uncorrected: list[str] = []
    corrected: list[str] = []
    for rel in _tracked():
        if not rel.endswith(".py"):
            continue
        if _matches(rel, globs) is None:
            continue
        raw = (REPO / rel).read_text(encoding="utf-8", errors="replace")
        flat = re.sub(r"[\s#*`]+", " ", raw)
        if not CLAIM.search(flat):
            continue
        if not strip_corrections and CORRECTION.search(flat):
            corrected.append(rel)
        else:
            uncorrected.append(rel)
    return sorted(uncorrected), sorted(corrected)


def run() -> tuple[str, str]:
    if not GUARD_LIST.exists():
        return "SKIP", "nothing to check — 10-scripts/gates/human_owned.txt not present"

    uncorrected, corrected = _findings()

    # ── PART 0 · SELF-TEST (law 7): does the CORRECTION clause bite? ──────
    # Strip the stamps in memory. Every corrected file must come back, or this
    # gate is keyed on the claim sentence alone and would report a file that
    # corrected nothing as clean.
    if corrected:
        stripped, _ = _findings(strip_corrections=True)
        missing = sorted(set(corrected) - set(stripped))
        if missing:
            return "FAIL", (
                "SELF-TEST FAILED: with the dated correction stamps removed in memory, "
                f"{len(missing)} file(s) that carry one did NOT come back as findings "
                f"({', '.join(missing[:3])}) — this gate is not reading the stamp it "
                "claims to read"
            )

    if uncorrected:
        return "FAIL", (
            f"{len(uncorrected)} guarded file(s) tell the reader they are UNGUARDED "
            f"(DEF-2791). Each is matched by a glob in human_owned.txt today and its own "
            f"docstring says no glob matches it — so the next lane files a closed finding, "
            f"or puts a settled question back to the PO (law 13). KEEP the paragraph and "
            f"put a dated correction above it naming the ruling that granted the glob; do "
            f"not delete it, because why a money file went unguarded is worth knowing. "
            f"Now: {', '.join(uncorrected)}"
        )

    return "PASS", (
        f"{len(_globs())} glob(s) checked; no guarded file claims to be unguarded; "
        f"{len(corrected)} file(s) keep the historical paragraph under a dated correction; "
        f"self-test: stripping the stamps surfaces all {len(corrected)} again, so the "
        f"check bites"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
