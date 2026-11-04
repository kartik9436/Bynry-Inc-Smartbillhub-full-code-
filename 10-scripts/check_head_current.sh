#!/usr/bin/env bash
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-351 (2026-08-20) — a lane's local branch pointer was rewound 240
#           commits mid-session. `git status` was clean, no command failed, and
#           the tree looked healthy; it surfaced only because a directory
#           listing for an unrelated reason ended at g27 where it should have
#           ended at g37.
# Rules:    CLAUDE.md law 11 (in a shared tree, scope the commit)
# ───────────────────────────────────────────────────────
#
# IS LOCAL HEAD STILL WHERE YOU LEFT IT?
#
# ⚠ EVERY LAW-11 CHECK IN CLAUDE.md IS ABOUT WHAT A COMMIT CONTAINS — the file
# count, the hunks, re-reading each file from HEAD after pushing — and every one
# of them ASSUMES HEAD IS WHERE YOU LEFT IT. DEF-351 moved the branch POINTER
# and touched no file, so all of them passed while the working tree was 240
# commits stale.
#
# Two things saved that session and both are worth knowing:
#   1. The private-index commit procedure seeds from `origin/<branch>`, NOT from
#      local HEAD, so a rewound HEAD could not reach a commit. Nothing was lost.
#   2. `npm ci` afterwards — a rewind past a dependency change silently
#      reinstalls the OLD dependency set, and six Tailwind-compiler tests went
#      red on a repo that was perfectly healthy.
#
# ⚠ AND PROVING THIS CHECK RED ALMOST CAUSED THE DEFECT A SECOND TIME. The
# sabotage was run in `git worktree add --detach` — chosen precisely BECAUSE
# law 11 forbids moving the shared tree — and then `git update-ref
# refs/heads/<branch>` inside it. **A worktree isolates the FILES, not the
# REFS**: `.git/refs` is shared by every worktree, so that command rewound the
# real branch pointer for every lane, exactly as the defect did. It was spotted
# and restored in the next command, and no checkout ran, so no file moved.
#
# To rehearse a rewind safely, point a DETACHED HEAD at the old commit and pass
# the branch name as an argument, or clone into /tmp. Never write a shared ref.
#
#     ./10-scripts/check_head_current.sh              # current branch
#     ./10-scripts/check_head_current.sh <branch>
#
# Exits 0 when HEAD is at or ahead of its upstream, 1 when it is behind.
set -euo pipefail

BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"
git fetch -q origin "$BRANCH" 2>/dev/null || true

# ── REFUSE IN WORDS, NEVER LET GIT ABORT (DEF-GOV-4276) ────────────────────
# ⚠ IN A `git worktree` THE DERIVED NAME IS THE WORKTREE'S OWN BRANCH — say,
# `worktree-agent-abfdb00e10eb1836b` — WHICH HAS NO REMOTE. `git rev-parse
# origin/<that>` then aborts the whole script under `set -e` with
#     fatal: ambiguous argument 'origin/worktree-…': unknown revision
# and prints no verdict at all. The script is not incapable of running — the
# branch has been an argument since it was written, and line 38 says so — but a
# lane following law 12 literally ("run it as the FIRST command of every
# session") sees a git error rather than PASS or FAIL, and a fatal from a
# checking tool reads as *the tool is broken*, which is the one conclusion that
# stops it ever being run again. Law 7: a check's output must distinguish pass
# from fail TO A READER, not merely to an exit code.
#
# It bites in a worktree specifically, which is where CLAUDE.md law 12 tells
# every lane to work — the cheapest mitigation for the very rewind this script
# exists to detect.
if ! git rev-parse --verify --quiet "origin/$BRANCH" >/dev/null; then
  cat >&2 <<UNKNOWN
CANNOT CHECK: there is no origin/$BRANCH to compare HEAD against.
  '$BRANCH' is what this checkout calls its current branch. In a git worktree
  that is the WORKTREE's name, which is local only and has no remote — so there
  is nothing to be behind, and this is not a pass.
  Name the branch you are pushing to:
    ./10-scripts/check_head_current.sh <branch>
  If you do not know it, 'git branch -r' lists what the remote has.
UNKNOWN
  exit 2
fi

HEAD_REV="$(git rev-parse HEAD)"
UP_REV="$(git rev-parse "origin/$BRANCH")"

if [ "$HEAD_REV" = "$UP_REV" ]; then
  echo "PASS: HEAD is the tip of origin/$BRANCH ($(git rev-parse --short HEAD))"
  exit 0
fi

BEHIND="$(git rev-list --count "$HEAD_REV..$UP_REV")"
AHEAD="$(git rev-list --count "$UP_REV..$HEAD_REV")"

if [ "$BEHIND" -eq 0 ]; then
  echo "PASS: HEAD is $AHEAD commit(s) ahead of origin/$BRANCH, nothing behind"
  exit 0
fi

cat <<MSG
FAIL: local HEAD is $BEHIND commit(s) BEHIND origin/$BRANCH (and $AHEAD ahead).
      HEAD  $(git rev-parse --short "$HEAD_REV")  $(git log -1 --format=%s "$HEAD_REV" | cut -c1-64)
      tip   $(git rev-parse --short "$UP_REV")  $(git log -1 --format=%s "$UP_REV" | cut -c1-64)

Anything you conclude from this working tree is $BEHIND commits stale, and a
directory that "does not have" a file may simply not have it YET. If the tree is
clean, recover with a fast-forward — the form that refuses rather than discards —
then reinstall dependencies, because a rewind past a dependency change silently
reinstalls the old set:

      git merge --ff-only origin/$BRANCH
      (cd 07-frontend && npm ci)

If the tree is NOT clean, someone else is mid-edit: leave it alone and say so.
MSG
exit 1
