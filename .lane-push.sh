#!/usr/bin/env bash
# Wave I lane push helper — hard-won law 11, every clause.
#
#   * the tip is resolved ONCE into $TIP and both read-tree and commit-tree use
#     that SHA (DEF-306);
#   * every blob is RE-DERIVED from the pinned tip at push time rather than
#     hashed from a working copy read earlier (DEF-1706 / DEF-1782) — the
#     re-derivation is a real three-way merge (base = the commit this worktree
#     started from, ours = the working file, theirs = the tip), so a sibling's
#     appended register row survives and a genuine collision CONFLICTS loudly
#     instead of being silently subtracted;
#   * $GIT_INDEX_FILE is set per command, never exported (DEF-613);
#   * the working tree is never moved — no checkout, no stash, no reset (law 11);
#   * verification is by SUBTRACTION and read as arithmetic (DEF-1706).
#
# usage:  .lane-push.sh <base-sha> "<commit message>" <path> [<path>...]
set -euo pipefail

BASE="$1"; shift
MSG="$1"; shift
BRANCH=claude/product-version-gh1br4
WORK="$(mktemp -d)"
IDX="$WORK/index"

git fetch -q origin "$BRANCH"
TIP="$(git rev-parse "origin/$BRANCH")"          # ← resolved ONCE
echo "tip pinned at $TIP"
echo "base was     $BASE"

GIT_INDEX_FILE="$IDX" git read-tree "$TIP"

for p in "$@"; do
  if [ ! -e "$p" ]; then echo "MISSING $p" >&2; exit 1; fi
  mine="$WORK/mine"; base="$WORK/base"; theirs="$WORK/theirs"
  cp "$p" "$mine"
  git show "$BASE:$p" > "$base" 2>/dev/null || : > "$base"
  git show "$TIP:$p"  > "$theirs" 2>/dev/null || : > "$theirs"
  # ⚠ **THE ANCESTRY CHECK, AND IT IS THE ONE THIS HELPER WAS MISSING
  # (DEF-WRK-4040).** The old condition was "if the tip moved this file since my
  # base, merge; otherwise my copy IS the merge result" — which assumes my
  # working copy equals base-plus-my-edits. When a worktree was synced from an
  # EARLIER tip and a sibling landed work in between, my copy is OLDER than the
  # base, base and tip are identical, the merge is skipped, and the push
  # publishes a REVERSION of the sibling's work with a perfect file count,
  # correct hunks and a clean `git status`. That cost wave H's whole front end
  # and 1,001 locale keys before the numstat caught it.
  #
  # So: refuse when a named path's TIP content is absent from my copy in a way
  # that only a deletion explains. `git merge-file` alone cannot tell "I removed
  # this" from "I never had it" — this can, by asking whether my base blob is
  # the blob the tip's history actually has.
  if ! git merge-base --is-ancestor "$BASE" "$TIP" 2>/dev/null; then
    echo "REFUSING: $BASE is not an ancestor of $TIP — re-sync before pushing" >&2
    exit 1
  fi
  if cmp -s "$base" "$theirs" && cmp -s "$base" "$mine"; then
    # unchanged everywhere — nothing of mine to carry
    :
  elif cmp -s "$base" "$theirs"; then
    # The tip has not moved this file since my base. My copy is the merge ONLY
    # if it is base-plus-my-edits; if it is base-MINUS-someone's-work, this
    # branch is how that gets published. So diff it and refuse a net deletion
    # the author did not ask for.
    removed="$(diff "$theirs" "$mine" | grep -c '^<' || true)"
    # ⚠ **THE OVERRIDE IS PER PATH, AND THE FIRST VERSION OF IT WAS NOT — WHICH
    # COST FIVE SIBLING DEFECT ROWS TWENTY MINUTES AFTER THIS GUARD WAS WRITTEN
    # (DEF-WRK-4045).** A single `LANE_ALLOW_DELETIONS=1` for a whole push
    # switches the check off for EVERY path in the same command, so one file
    # that legitimately shrinks silently licenses the reversion of all the
    # others. An override that is global is not an override, it is an off
    # switch. Name the path: `LANE_ALLOW_DELETIONS="a/b.txt c/d.json"`.
    case " ${LANE_ALLOW_DELETIONS:-} " in *" $p "*) allowed=1 ;; *) allowed=0 ;; esac
    if [ "${removed:-0}" -gt 0 ] && [ "$allowed" -eq 0 ]; then
      echo "REFUSING $p: your copy DROPS $removed line(s) the tip has." >&2
      echo "  If that is deliberate, re-run with LANE_ALLOW_DELETIONS=\"$p\"." >&2
      echo "  If it is not, your working copy predates the tip — re-derive it." >&2
      exit 1
    fi
  else
    echo "  re-deriving $p (the tip moved it since $BASE)"
    if ! git merge-file -p "$mine" "$base" "$theirs" > "$WORK/merged"; then
      echo "CONFLICT re-deriving $p — a sibling changed the same lines. Resolve by hand." >&2
      exit 1
    fi
    # never truncate the destination before the bytes exist (the CLAUDE.md
    # near-miss): build in full, assert non-empty, only then write.
    [ -s "$WORK/merged" ] || { echo "EMPTY merge for $p — refusing" >&2; exit 1; }
    cp "$WORK/merged" "$mine"
  fi
  mode="$(git ls-tree "$TIP" -- "$p" | awk '{print $1}')"
  [ -n "$mode" ] || mode=100644
  blob="$(git hash-object -w "$mine")"
  GIT_INDEX_FILE="$IDX" git update-index --add --cacheinfo "$mode,$blob,$p"
done

TREE="$(GIT_INDEX_FILE="$IDX" git write-tree)"
COMMIT="$(printf '%s\n' "$MSG" | git commit-tree "$TREE" -p "$TIP")"
echo "commit $COMMIT"

echo "── verify by subtraction (deletions must be only where intended) ──"
git diff --numstat "$TIP" "$COMMIT"

git push -q origin "$COMMIT:$BRANCH"
echo "pushed $COMMIT -> $BRANCH"
rm -rf "$WORK"
