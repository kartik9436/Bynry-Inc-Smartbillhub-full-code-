#!/usr/bin/env bash
# ── Trace ──────────────────────────────────────────────
# Rules:  CLAUDE.md law 11 — the pinned-tip `commit-tree` push, its blob
#         re-derivation clause (DEF-1706 / DEF-1782) and its post-push
#         subtraction check (DEF-306, DEF-2474).
# ───────────────────────────────────────────────────────
#
# PUSH NAMED PATHS ONTO A SHARED BRANCH WITHOUT TOUCHING ANY OTHER LANE'S WORK.
#
#   ./10-scripts/push_paths.sh <branch> <base-sha> <message-file> <path>...
#
# `base-sha` is the commit whose content you started editing from. The script
# REFUSES when any named path moved between that base and the live tip — which
# is law 11's own prescription ("make your push helper REFUSE when a named path
# moved between your blob's base and the tip") and the only thing that catches
# the revert-by-subtraction that every other check in that law passes over.
#
# What it does, in order:
#   1. fetch, then pin the tip to a SHA **once** — `origin/<branch>` is a local
#      ref any sibling's fetch can move between two lookups (DEF-306).
#   2. refuse if any named path differs between <base-sha> and the tip.
#   3. build the tree from the PINNED TIP in a PRIVATE index, never the shared
#      one, hashing each path's working-tree bytes into it.
#   3b. REFUSE if a line VANISHED from a shared register (DEF-2837). This is
#      law 11's "read the numstat AS ARITHMETIC" done by a machine and done
#      BEFORE the push instead of by a person after it — see
#      `push_register_guard.py`.
#   4. commit-tree against the same pinned SHA and push.
#   5. verify by SUBTRACTION: `git diff --numstat <tip> <commit>` is printed and
#      must show deletions only where you intended them.
#
# ⚠ **STEP 2 CLOSES DEF-2837's MECHANISM AND NOT ITS DAMAGE, WHICH IS WHY 3b
# EXISTS.** A blob can be stale for reasons that have nothing to do with the tip
# moving: you read the file, worked for twenty minutes and wrote back a
# whole-file copy of what you read (DEF-1706), or a script truncated its
# destination before it had the bytes to put in it. The tip never moved, step 2
# is satisfied, and 43 lines of somebody else's ruling leave the branch.
#
# ⚠ `GIT_INDEX_FILE` is set PER COMMAND and never exported (DEF-613).
# ⚠ It touches no file on disk, so the caller must still move the working tree
#   afterwards (`git merge --ff-only`) — DEF-2474.
set -euo pipefail

BRANCH="$1"; BASE="$2"; MSG_FILE="$3"; shift 3
[ "$#" -gt 0 ] || { echo "no paths given" >&2; exit 2; }
[ -s "$MSG_FILE" ] || { echo "message file is empty" >&2; exit 2; }

# ⚠ COPY THE MESSAGE TO A PRIVATE FILE BEFORE ANYTHING ELSE (DEF-GOV-6892,
# 2026-09-27). The caller's message path is usually somewhere every lane in the
# container shares — `/tmp/claude-0/msg.txt` is what actually happened, and the
# session scratchpad is shared too, so "one directory down" is not the fix. A
# sibling wrote its own message over that path between the caller writing it and
# this script reading it at `commit-tree` time, and the commit landed carrying
# ANOTHER LANE'S SUBJECT over this lane's ten files.
#
# It is invisible to every check this repo has: the closing numstat named the
# intended paths, all four register guards said nothing vanished, and
# `git show` held no other lane's hunk. **Nothing anywhere reads a commit
# subject**, so a commit describing work it does not contain passes the whole
# toolchain — hard-won law 7's "reporting zero over a scope it silently
# excludes", one level up from files.
#
# Two lines fix it for every caller, which is why it lives here and not in a
# paragraph each lane has to remember.
_PRIVATE_MSG="$(mktemp "${TMPDIR:-/tmp}/push_paths_msg.XXXXXXXX")"
trap 'rm -f "$_PRIVATE_MSG"' EXIT
cat "$MSG_FILE" > "$_PRIVATE_MSG"
MSG_FILE="$_PRIVATE_MSG"

git fetch -q origin "$BRANCH"
TIP="$(git rev-parse "origin/$BRANCH")"
echo "pinned tip: $TIP"

# ── 1b · REFUSE A BASE THAT IS THE TIP (DEF-GOV-4061) ─────────────────────
# Step 2 below compares each named path between <base-sha> and the tip. Hand it
# the CURRENT TIP as the base and it compares the tip against itself, so it can
# never fire — the guard is off, and the line it prints ("0 commit(s) behind the
# tip; no named path moved across them") is TRUE and reads exactly like a pass.
# A lane did that on 2026-09-05 and published the subtraction of 160 locale keys
# and a sibling's 27-line note.
#
# A base equal to the tip asserts "I have read nothing since the tip", which is
# only true of a lane that has done no work at all. It is therefore refused
# rather than warned about: this is the one check standing between a stale blob
# and a silent revert, and a guard you can switch off by accident is not a guard.
#
# ⚠ IT IS NOT A FLAT BAN, BECAUSE BASE == TIP IS ALSO THE *CORRECT* STATE AFTER
# THE RECOVERY LAW 11 PRESCRIBES — re-derive every blob from the pinned tip and
# push. So it is refused unless the lane says, explicitly, that it did that. The
# point is to make the difference between "I re-derived" and "I typed the tip
# because the last push refused me" a DELIBERATE act with a name, rather than a
# silent no-op that prints a reassuring line either way.
BASE_SHA="$(git rev-parse --verify --quiet "$BASE" || echo UNKNOWN)"
if [ "$BASE_SHA" = "$TIP" ]; then
  if [ "${REDERIVED_FROM_TIP:-}" = "1" ]; then
    echo "base == tip, and REDERIVED_FROM_TIP=1 asserts every named path was rebuilt from $TIP"
    echo "  (the moved-path check below cannot fire; the numstat at the end is your only proof)"
  else
    cat >&2 <<REFUSED
REFUSED: <base-sha> is the current tip ($TIP), so the staleness check cannot fire.
  The base must be the commit you started EDITING FROM. Passing the tip compares
  the tip with itself, and any blob you read earlier is then published as a
  silent revert of everything a sibling pushed meanwhile (DEF-GOV-4061 — 160
  locale keys and a sibling's note went this way on 2026-09-05).
  Either pass the sha your worktree was created at or last pushed, OR — if you
  have genuinely rebuilt every named path from the tip's bytes just now — re-run
  with REDERIVED_FROM_TIP=1 to say so.
REFUSED
    exit 2
  fi
fi

# ── 1b · REFUSE A PATH THIS SCRIPT CANNOT CARRY ───────────────────────────
# ⚠ A DIRECTORY USED TO PUSH NOTHING AND SAY NOTHING (DEF-GOV, 2026-09-06).
# Step 3's loop tests `[ -f "$path" ]` and sends everything else down the
# `--force-remove` branch — so naming a directory was read as a request to
# DELETE it, which is a no-op when it was never tracked. The script then
# printed "pushed <sha>" over a commit that contained not one file from it.
# 150 rendered wireframes were "pushed" this way and none of them landed.
#
# That is hard-won law 7's *reporting zero over a scope it silently excludes*:
# the script was not lying — it committed exactly what it could see — and a
# reader had no way to tell an empty directory from an excluded one. Worse,
# for a directory that WAS tracked the same branch would have removed it.
#
# So: a path must be a regular file on disk, or already tracked at the tip
# (which is how a genuine deletion is expressed). A directory is refused by
# name, with the fix in the message, because "use find" is not obvious at the
# moment you are being refused.
for path in "$@"; do
  if [ -d "$path" ]; then
    echo "REFUSED: $path is a DIRECTORY. This script pushes FILES." >&2
    echo "         Name them explicitly, e.g.:" >&2
    echo "           find $path -type f -print0 | xargs -0 ./10-scripts/push_paths.sh BRANCH BASE MSG" >&2
    exit 5
  fi
  if [ ! -f "$path" ] && ! git cat-file -e "$TIP:$path" 2>/dev/null; then
    echo "REFUSED: $path is neither a file on disk nor tracked at the tip." >&2
    echo "         Nothing would be committed for it and nothing would be said." >&2
    exit 5
  fi
done

# ── 2 · REFUSE ON A MOVED PATH ────────────────────────────────────────────
moved=0
for path in "$@"; do
  # `--verify --quiet` or the missing-path case prints the ARGUMENT on stdout
  # and lands a multi-line value in the variable — which reads as "moved" for
  # every brand-new file this script exists to push.
  before="$(git rev-parse --verify --quiet "$BASE:$path" || echo MISSING)"
  after="$(git rev-parse --verify --quiet "$TIP:$path" || echo MISSING)"
  if [ "$before" != "$after" ]; then
    echo "REFUSED: $path moved between $BASE and the tip ($before -> $after)" >&2
    moved=1
  fi
done
[ "$moved" -eq 0 ] || {
  echo "re-apply your edits onto the tip's bytes and run again (law 11)" >&2
  exit 3
}

# ── 2b · IS THE BASE ON THIS BRANCH AT ALL? ───────────────────────────────
# The refusal above is only as good as <base-sha>, and a base off this branch —
# a typo, a sha from a sibling's worktree — makes it compare against something
# that was never here. Refuse that rather than proceed.
#
# ⚠ **WHAT THIS CANNOT CATCH, SAID PLAINLY SO NOBODY READS MORE INTO IT
# (hard-won law 1):** passing the CURRENT TIP as the base. That is an ancestor
# of itself, so this clause is satisfied, and step 2 then compares the tip with
# the tip and cannot fail. It is also the correct thing to pass when your
# working copy really is at the tip, so it cannot simply be banned. **Step 3b is
# what covers that case**, because it compares CONTENT against the tip and does
# not consult the base at all.
git merge-base --is-ancestor "$BASE" "$TIP" || {
  echo "REFUSED: $BASE is not an ancestor of the tip $TIP, so it is not a commit" >&2
  echo "         you can have edited from. Pass the sha your working copy came from." >&2
  exit 3
}
BEHIND="$(git rev-list --count "$BASE..$TIP")"
echo "base $BASE is $BEHIND commit(s) behind the tip; no named path moved across them"

# ── 3b · REFUSE ON A VANISHED REGISTER LINE (DEF-2837) ────────────────────
python3 "$(dirname "$0")/push_register_guard.py" "$TIP" "$@" || exit 4

# ── 3 · PRIVATE INDEX SEEDED FROM THE PINNED SHA ──────────────────────────
IDX="$(mktemp -t sbh-index.XXXXXX)"
trap 'rm -f "$IDX"' EXIT
GIT_INDEX_FILE="$IDX" git read-tree "$TIP"
for path in "$@"; do
  if [ -f "$path" ]; then
    blob="$(git hash-object -w "$path")"
    mode=644
    [ -x "$path" ] && mode=755
    printf '100%s %s\t%s\n' "$mode" "$blob" "$path" |
      GIT_INDEX_FILE="$IDX" git update-index --index-info
  else
    GIT_INDEX_FILE="$IDX" git update-index --force-remove "$path"
  fi
done
TREE="$(GIT_INDEX_FILE="$IDX" git write-tree)"
# ── 3c · REFUSE AN EMPTY COMMIT (DEF-GOV-5347, 2026-09-15) ────────────────
# If every named path already matches the tip, the tree just written IS the
# tip's tree, and commit-tree below would happily publish a commit that changes
# nothing under whatever subject the message file carries. That happened: a
# lane's file_defect.py call was refused, its script did not stop, and this
# helper pushed de79b37f — an empty commit titled "File DEF-SHL-5345 …" over a
# defect number that was somebody else's. Law 7's "incapable of failing" shape,
# in the one tool every push goes through. An empty commit is never a push this
# helper is for (CLAUDE.md: never push an empty commit), so it is refused by
# name rather than warned about.
if [ "$TREE" = "$(git rev-parse "$TIP^{tree}")" ]; then
  cat >&2 <<REFUSED
REFUSED: the tree built from your named paths is IDENTICAL to the tip's ($TIP).
  Nothing you named differs from the tip, so this would publish an EMPTY commit
  under the subject in $MSG_FILE. Either the change was never written (a tool
  refused and your script carried on — check its output), or it is already on
  the branch. Nothing was pushed.
REFUSED
  exit 2
fi

# ── 4 · COMMIT AGAINST THE SAME PINNED SHA, AND PUSH ──────────────────────
COMMIT="$(git commit-tree "$TREE" -p "$TIP" -F "$MSG_FILE")"
git push -q origin "$COMMIT:refs/heads/$BRANCH"
echo "pushed $COMMIT"

# ── 5 · VERIFY BY SUBTRACTION, NOT BY INSPECTION ──────────────────────────
echo "--- git diff --numstat $TIP $COMMIT ---"
git diff --numstat "$TIP" "$COMMIT"

# ── 6 · MOVE THE FILES TOO — THE HALF THIS SCRIPT COULD NOT DO (DEF-MET-4770)
#
# ⚠ **THE COMMIT IS FINE AND THE TREE IS NOT.** Step 3 builds from the PINNED
# TIP in a private index, which is exactly why it is safe — and it therefore
# updates NO FILE ON DISK. Every path a sibling pushed while you worked is still
# at the content you started from, and `git status` compares against `HEAD`,
# which is the thing that did not move, so it reports CLEAN over a loaded
# revert (DEF-2474).
#
# ⚠ **THIS RAN SIXTEEN TIMES BY HAND IN ONE SESSION (2026-09-10, DEF-MET-4770).**
# Four lanes, one shared tree: a whole tab's work sat 45 lines short of the
# branch an hour after it landed, and eight more files including one pushed
# minutes earlier. Each was found by running law 12's content-addressed test
# manually, and each time the tool that performs it was already in this
# directory and nothing called it. **The knowledge was written down and the
# fix was written down and neither was where a lane looks** — which is law 11's
# closing lesson, and this line is it being applied rather than restated.
#
# ⚠ **IT IS SAFE BY CONSTRUCTION AND IT IS NON-FATAL.** `sync_stale_tree.py`
# only moves a file whose exact blob is an OLDER version of that same path —
# proof that no lane authored it here. A MISS decides nothing and is left
# alone, because a wrong restore destroys a lane's work while a wrong skip
# costs a second run. And the push has ALREADY SUCCEEDED by this point, so a
# failure here must never be reported as a failed push: it warns and returns 0.
python3 "$(dirname "$0")/sync_stale_tree.py" "$COMMIT" || {
  echo "⚠ tree sync did not complete — the PUSH SUCCEEDED ($COMMIT)."
  echo "  Your working tree may hold stale copies of paths siblings pushed."
  echo "  Run: python3 10-scripts/sync_stale_tree.py $COMMIT"
}
