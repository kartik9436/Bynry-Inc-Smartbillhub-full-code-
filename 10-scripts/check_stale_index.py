#!/usr/bin/env python3
"""Find index entries that would REVERT committed work, and disarm them.

WHY THIS EXISTS
---------------
Six lanes share one checkout and one INDEX. A lane that merges off-tree — with
`git merge-tree --write-tree` and `commit-tree`, which is the only way to merge
while the others are writing — moves HEAD without touching the working tree. The
index then still holds the PRE-merge blob for every file the merge changed, and
a bare `git commit` from any lane commits that: the merge is reverted, file by
file, by a commit nobody meant to make.

This happened five times on 2026-08-27. The largest instance staged a revert of
24 files including `WizardFrame.tsx` and `BillRunWizard.tsx` — the fix for a
blocker that had stopped the Product Owner billing anybody, landed minutes
earlier — plus `DateCell`, `FormModal` and the whole CR-042 import set.

⚠ AND CLAUDE.md LAW 11'S OWN REMEDY DOES NOT APPLY HERE. It says: *"A stale
index is a loaded gun: if you find one holding a revert, the working tree is the
truth — confirm `git diff HEAD` is empty, then `git reset` to disarm it."* In a
six-lane tree `git diff HEAD` is NEVER empty, so the precondition never holds
and a blanket `git reset` would throw away five lanes' staged work. The
question has to be asked PER PATH.

THE SIGNATURE
-------------
An entry is stale when the WORKING TREE matches HEAD and the INDEX does not.
That combination is never deliberate: nobody stages a version identical to a
base they have already moved past while holding the newer one on disk. A lane's
real work has the opposite shape — index ahead of HEAD, worktree ahead of index.

`--fix` runs `git reset -- <path>` for each, which touches the index only and
never the working tree. Exit 1 when any are found (0 after a successful --fix),
so it can be a gate or a pre-commit hook.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def git(*args: str) -> bytes:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True).stdout


def stale_paths() -> list[str]:
    staged = [p for p in git("diff", "--cached", "--name-only").decode().splitlines() if p]
    out = []
    for path in staged:
        blob = git("show", f"HEAD:{path}")
        if not blob:
            continue  # not in HEAD — a genuine addition, not a stale entry
        disk = REPO / path
        if not disk.is_file():
            continue  # a staged deletion; a different hazard, reported by git status
        if disk.read_bytes() == blob:
            out.append(path)
    return out


def main(argv: list[str]) -> int:
    fix = "--fix" in argv
    stale = stale_paths()
    if not stale:
        print("index: no entry would revert committed work")
        return 0
    print(f"⚠ {len(stale)} stale index entr(ies) — a bare `git commit` would REVERT these:")
    for path in stale:
        print(f"    {path}")
    if not fix:
        print("\nRe-run with --fix to `git reset` them (index only; the working tree is not touched).")
        return 1
    git("reset", "-q", "--", *stale)
    left = stale_paths()
    if left:
        print(f"\n⚠ {len(left)} still stale after --fix; disarm by hand.")
        return 1
    print(f"\ndisarmed {len(stale)}; the working tree was not touched")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
