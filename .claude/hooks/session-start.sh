#!/bin/bash
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-351 (2026-08-20, 240 commits) and five more on 2026-08-25, the
#           worst losing 152 commits from the working tree.
# Rules:    CLAUDE.md hard-won law 12 (run the head check FIRST), law 11 (push
#           after every step — a push is the only durable act here).
# ───────────────────────────────────────────────────────
#
# WHY THIS HOOK EXISTS
#
# Local HEAD silently rewinds between turns. The reflog is the diagnosis: after
# a rewind there is NO reflog entry for any of the session's commits and
# HEAD@{1} is the previous day's. A `git reset` would leave one. So the commits
# were never made in the `.git` present afterwards — the container filesystem,
# `.git` included, is restored from a session-start snapshot, and only what was
# PUSHED survives.
#
# ⚠ THE DAMAGE IS A WRONG CONCLUSION, NOT LOST WORK. `git status` is clean, no
# command fails, and every law-11 check passes, because they all ask what a
# COMMIT CONTAINS and assume HEAD is where you left it. A rewind moves the
# POINTER and touches no file. A file that "does not exist" may simply not
# exist YET; a rule that "was never written" may be written and pushed.
#
# So this runs before the session reads anything.
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}" || exit 0

echo "── SessionStart: is local HEAD still where it was left? ──"
if ./10-scripts/check_head_current.sh; then
  exit 0
fi

# BEHIND. Recover ONLY when nothing is mid-edit. `--ff-only` refuses rather than
# discards, so it cannot eat work — but a dirty tree means another lane is
# writing, and law 11 forbids moving a shared tree under its author.
if [ -n "$(git status --porcelain)" ]; then
  cat <<'MSG'

‼ HEAD IS BEHIND **AND THE TREE IS DIRTY** — NOT RECOVERING AUTOMATICALLY.
  Someone is mid-edit. Moving the tree under them is exactly what law 11
  forbids. Read the uncommitted work first, then fast-forward by hand:
      git merge --ff-only origin/<branch>
  Until then, treat every file in this tree as possibly stale.
MSG
  exit 0
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
echo "  tree is clean — fast-forwarding (the form that refuses rather than discards)"
if git merge --ff-only "origin/$BRANCH"; then
  echo "  recovered: $(git rev-parse --short HEAD)"
  # A rewind past a dependency change silently reinstalls the OLD set and turns
  # healthy tests red (DEF-351's second lesson). Re-sync before anything runs.
  if [ -d 07-frontend/node_modules ]; then
    echo "  re-syncing frontend dependencies after the rewind"
    (cd 07-frontend && npm install --silent) || echo "  ‼ npm install failed — run it by hand"
  fi
else
  echo "  ‼ fast-forward REFUSED — local has commits the remote lacks. Do not force. Inspect by hand."
fi
exit 0
