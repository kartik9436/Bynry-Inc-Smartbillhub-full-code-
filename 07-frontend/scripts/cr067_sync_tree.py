#!/usr/bin/env python3
"""Move the FILES to a pinned commit after a `commit-tree` push (DEF-2474).

`push_paths.sh` builds its tree from the pinned tip and updates **no file on
disk**, so `git reset --mixed <sha>` afterwards leaves every path a sibling
touched at the content this lane started with — a loaded revert under a clean
`git status`. This writes the pinned commit's bytes over every differing path,
recreates the ones the sync deleted, re-sets the executable bit from
`ls-tree`, and verifies by SUBTRACTION rather than by status.

    python3 scripts/cr067_sync_tree.py <sha>

⚠ EVERY BLOB IS BUILT IN MEMORY BEFORE ANYTHING IS WRITTEN. Law 11's near-miss
was a repair script that opened its destination before it had the bytes for it
and truncated CLAUDE.md to zero.
"""

import os
import pathlib
import stat
import subprocess
import sys


def run(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return result.stdout


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    tip = run("rev-parse", sys.argv[1]).strip()
    names = run("diff", "--name-only", tip).split()
    if not names:
        print(f"already at {tip[:8]} — nothing to write")
        return 0
    modes = {
        line.split("\t", 1)[1]: line.split()[0]
        for line in run("ls-tree", "-r", tip).splitlines()
    }
    blobs: dict[str, bytes] = {}
    for path in names:
        result = subprocess.run(["git", "show", f"{tip}:{path}"], capture_output=True)
        if result.returncode != 0:
            print(f"REFUSED: {path} is not in {tip[:8]} — decide it by hand, do not guess")
            return 1
        blobs[path] = result.stdout
    assert len(blobs) == len(names)
    for path, data in blobs.items():
        target = pathlib.Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if modes.get(path) == "100755":
            target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    leftover = run("diff", "--numstat", tip).strip()
    if leftover:
        print("STILL DIFFERING FROM THE TIP:\n" + leftover)
        return 1
    print(f"wrote {len(blobs)} path(s); `git diff --numstat {tip[:8]}` is now empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
