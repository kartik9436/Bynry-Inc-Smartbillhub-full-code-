#!/usr/bin/env python3
"""Append ONE row to the defect register, safely, in a shared working tree.

WHY THIS EXISTS
---------------
`12-governance/10-defect-log.csv` is written by every lane. On 2026-08-19, six
lanes shared one tree and the register produced, in a single hour:

  * an ID COLLISION — two lanes independently took `DEF-284`, because each read
    the highest id from its own working-tree copy and neither could see the
    other's uncommitted row;
  * a DUPLICATE ROW — the same id filed twice with different content;
  * FOUR LANES' ROWS SWEPT INTO ONE COMMIT — a lane appended through Python's
    `csv` writer, which RE-SERIALISES EVERY ROW. That is a whole-file write
    wearing the costume of an append, so the pathspec commit that named only the
    register carried every other lane's in-flight edit with it;
  * A SILENT REVERT — a later lane committed its own whole-file copy over a
    line another lane had already pushed.

Every one of those passes the checks CLAUDE.md law 11 prescribes: the file count
is right, the author's own change IS present, and on a 290-row register no human
reads 290 hunks. The law is not wrong — it is aimed at a different mechanism.
The mechanism here is that **a tool which looks like an append is a whole-file
write**, and the fix is to make appending the only thing that is easy to do.

WHAT THIS GUARANTEES
--------------------
1. **The next id is allocated against the REMOTE TIP as well as the working
   tree**, so a lane cannot take an id another lane has already pushed, and
   cannot take one a sibling has staged locally either. This alone would have
   prevented the collision.
2. **The file is opened in append mode and ONE line is written.** No existing
   byte is read into memory to be written back, so no other lane's row can be
   carried, altered, or reverted — not by accident and not by a bug in this
   script.
   ⚠ **THAT IS A STATEMENT ABOUT THE WRITE AND NOT ABOUT THE FILE (DEF-3523).**
   Guarantee 1 reaches the REMOTE for the id. Nothing reaches the remote for the
   BYTES: they come from whatever tree this script is standing in, and nothing
   here asked whether that tree was current. In a lane whose worktree is behind,
   the two combine into a register whose newest row is right and which is missing
   every row pushed since that tree was made — measured live on 2026-09-03 at
   **17 rows**, where committing that one path would have deleted them BY
   SUBTRACTION, with a correct file count, with the author's own row present, and
   with `git show` printing only that hunk. Every check law 11 prescribes passes
   on it, which is why it needed a number rather than a paragraph.
   **The numbers were already on screen and were not labelled as a hazard.** The
   `ids read from:` line has always ended `(+16 unseen)` for a branch holding rows
   this copy lacks; it reads as *"I looked in plenty of places"* and it is in fact
   the loss, counted. So the walk is now done a second time against the WORKING
   TREE rather than against the running total, and what it finds is printed as a
   warning that says what will happen.
   Two things it deliberately does NOT do: it does not REFUSE (nothing may stand
   between a lane and filing a defect — the same reason the fetch is best-effort),
   and it does not silently rewrite your copy from the tip, because in a shared
   tree that deletes a sibling's UNPUSHED row, which is this defect running
   backwards. The hard stop stays at push time in `push_register_guard.py`; what
   the warning closes is that an ordinary pathspec commit never reaches that
   guard, and that a lane which does reach it finds out only after the work.
3. **The line terminator is DETECTED and preserved** — read from the HEADER
   LINE, and from nowhere else. (It is LF today; this line claimed CRLF as
   a fact until DEF-1791.) A `text=True`
   read silently converts CRLF to LF; writing that back changes every line in
   the file while leaving the line COUNT identical — a 580-line diff for a
   one-field edit, which looks exactly like the corruption it is.
   ⚠ **THIS DETECTION ASKED THE WRONG QUESTION UNTIL 2026-09-01 (DEF-2598)** and
   put NINE BLANK LINES in the register. It was `b"\r\n" if b"\r\n" in raw`,
   which is true when a single stray carriage return sits inside a quoted prose
   field anywhere in the file; seven are in there. The file ends with a bare
   `\n`, the "did the last line finish?" test then fails, and a terminator is
   written before the row — a blank line, every time. `line_terminator()` reads
   the header line, which carries no free text and cannot acquire one.
4. **Every field is quoted and embedded newlines are refused**, so a prose
   `escape_reason` cannot break the row into two.

⚠ **CALLING THIS FROM A SHELL: DO NOT PUT BACKTICKS IN AN ARGUMENT.** Twice on
2026-08-28 a row landed with a word missing from the middle of a sentence — the
shell had run the backticked text as a command and substituted its empty output,
so `` `surface` `` became nothing at all and the title read *"THE REGISTER'S
COLUMN IS ONLY HALF A LOCATION"*. Nothing errors: the row is well-formed, every
gate passes, and only re-reading the row shows the hole. Write the word plain, or
build the argument in a quoted heredoc where no substitution happens.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not edit an existing row. Closing a defect changes one field on one line
and is a different, riskier operation; do it as REMOTE-TIP-plus-your-own-hunk
through a private `GIT_INDEX_FILE`, per law 11, and check the diff prints 2.

Usage:
    python3 10-scripts/file_defect.py --title "..." --surface "..." \
        --module rating --severity high --found-in "..." --introduced-in "..." \
        --category silent-null --escape-reason "..." --prevention "..." \
        [--reported-by "..."] [--dry-run]

Prints the allocated id on success.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REGISTER = REPO / "12-governance" / "10-defect-log.csv"

# The vocabularies live in ONE module so this tool, close_defect.py and the two
# gates cannot drift apart — a second copy of a vocabulary is free to disagree
# with the first, which is what put two vocabularies in the severity column to
# begin with. The import IS the contract: if it fails, this tool must not write
# a row it cannot check (hard-won law 3 — the unsafe option is the one you type).
sys.path.insert(0, str(REPO / "10-scripts"))
try:
    from register_vocabulary import explain_category, explain_severity, explain_status
except Exception as exc:  # pragma: no cover - the import IS the contract
    sys.exit(f"cannot read the register's vocabularies from register_vocabulary.py: {exc}")
# ⚠ THE LEADING QUOTE IS NOT OPTIONAL DECORATION — DEF-300.
# This tool writes rows with QUOTE_ALL, so every row it appends begins
# `"DEF-297",` and NOT `DEF-297,`. The first version of this regex matched only
# the unquoted form, which meant THE TOOL COULD NOT SEE ITS OWN OUTPUT: every
# invocation re-read a register missing every row this tool had ever written and
# handed out the same id again. Three rows across two lanes took DEF-297 within
# minutes — the exact collision this script exists to prevent, caused by the
# script. G26 caught it on the next run.
ID_RE = re.compile(rb'^"?DEF-(?:[A-Z]{3}-)?(\d+)"?,')  # module segment optional — PO 2026-09-03
COLUMNS = [
    "id", "reported_on", "reported_by", "title", "surface", "module", "severity",
    "found_in", "introduced_in", "category", "escape_reason", "status",
    "fixed_commit", "prevention",
]

#: Every row this tool files starts open. Named rather than inlined so that
#: `validate_inputs` can put it through the same vocabulary check a lane's
#: `--status` would go through, and so that changing it is a visible act.
NEW_ROW_STATUS = "open"


def _ids_in(blob: bytes) -> set[int]:
    return {int(m.group(1)) for m in (ID_RE.match(ln) for ln in blob.splitlines()) if m}


def _git(*args: str) -> bytes:
    """Bytes, never text=True — that would rewrite CRLF on the way in."""
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True).stdout


def _current_branch() -> str:
    """The branch name, for the pre-allocation fetch. Empty on a detached HEAD,
    where `git fetch origin HEAD` is still a lawful no-op refresh."""
    return _git("rev-parse", "--abbrev-ref", "HEAD").decode().strip()


def known_ids(*, fetch: bool = True) -> tuple[set[int], list[str]]:
    """Every id this repo knows about, from three places, and where each came from.

    ⚠ `fetch=False` IS FOR THE RE-DERIVATION IMMEDIATELY BEFORE THE WRITE, and
    it is not an optimisation. Law 11's id clause says to re-derive an allocated
    id from the pinned tip AT PUSH TIME because a sibling can take it while you
    work; the same is true, on a shorter clock, between this function returning
    and the row being appended — the two fetches below take seconds, and a
    sibling appending to this very file in that window is the ordinary case in a
    shared tree. The second reading must NOT fetch again: it is asking whether
    the world moved since the first reading, and re-fetching would fold new
    remote rows into the answer and make the question unanswerable.

    The working tree alone is NOT enough: it cannot see a row a sibling lane has
    committed but not pushed, nor one already on the remote — which is why it FETCHES first (DEF-325):
    `@{upstream}` is a local tracking ref and is only as fresh as the last
    fetch. Reading all three is
    the whole point — the 2026-08-19 collision happened between two lanes each of
    which had read only its own copy.
    """
    # ⚠ FETCH FIRST — `@{upstream}` IS A LOCAL REF (DEF-325, 2026-08-19).
    # The docstring below used to promise this function could see "one already
    # on the remote". It could not. `@{upstream}` is a remote-TRACKING ref: it
    # reflects the remote as of the last `git fetch` in this checkout, and in a
    # shared tree where lanes push every few minutes it is routinely minutes
    # stale. Two lanes took DEF-323 forty minutes apart because the second had
    # not fetched since before the first pushed — the very collision this
    # function exists to prevent, committed by the function that prevents it.
    # A comment claiming a guarantee is not the guarantee (hard-won law 1).
    #
    # The fetch is best-effort and quiet: no network (offline, proxy, CI without
    # credentials) must never stop a lane filing a defect. When it fails the
    # tracking ref is simply as stale as it was, which is the old behaviour, and
    # the caller still sees every source counted in the printed line.
    if fetch:
        _git("fetch", "--quiet", "origin", _current_branch() or "HEAD")
    # ⚠ AND FETCH EVERY OTHER BRANCH TOO — THREE SOURCES WERE ALL ONE BRANCH
    # (DEF-977, 2026-08-27). Working tree, `HEAD` and `@{upstream}` sound like
    # three independent readings and in a worktree lane they are three readings
    # of the SAME branch: a lane's upstream is its own `worktree-agent-*` ref,
    # which by construction has never seen another lane's rows. So two lanes
    # that branched from the same tip both read the same highest id and both
    # return the next one — which is exactly what happened, twice within
    # minutes, and neither invocation could have known. DEF-284 (the collision
    # this tool was written for) was between two lanes sharing a WORKING TREE;
    # this is the same collision one level out, between branches, and the fix
    # has to look there.
    if fetch:
        _git("fetch", "--quiet", "origin")

    seen: set[int] = set()
    sources: list[str] = []
    if REGISTER.is_file():
        got = _ids_in(REGISTER.read_bytes())
        seen |= got
        sources.append(f"working tree ({len(got)})")
    for ref in ("HEAD", "@{upstream}"):
        blob = _git("show", f"{ref}:12-governance/10-defect-log.csv")
        if blob:
            got = _ids_in(blob)
            new = got - seen
            seen |= got
            sources.append(f"{ref} ({len(got)}{f', +{len(new)} unseen' if new else ''})")
    # Every remote branch that carries the register, so an id taken on a sibling
    # lane is visible before it has merged anywhere. Best-effort like the fetch:
    # a ref that cannot be read is skipped, never fatal — nothing must stop a
    # lane filing a defect. Only the refs that ADD an id are named in the
    # printed line; a dozen branches all agreeing is noise.
    refs = _git("for-each-ref", "--format=%(refname)", "refs/remotes/origin").decode()
    for ref in sorted(r.strip() for r in refs.splitlines() if r.strip()):
        if ref.endswith("/HEAD"):
            continue
        blob = _git("show", f"{ref}:12-governance/10-defect-log.csv")
        if not blob:
            continue
        got = _ids_in(blob)
        new = got - seen
        seen |= got
        if new:
            sources.append(f"{ref.split('refs/remotes/', 1)[-1]} (+{len(new)} unseen)")
    return seen, sources


def rows_this_branch_has_and_this_file_does_not() -> tuple[list[tuple[str, int]], bool]:
    """Per remote branch: how many defect rows it holds that this copy lacks.

    Returns the shortfall per branch, worst first, and whether the branch this
    tree pushes to could be identified at all.

    ⚠ **AGAINST THE WORKING TREE, NOT AGAINST A RUNNING TOTAL, AND THAT IS THE
    WHOLE DIFFERENCE.** `known_ids()` above accumulates as it walks, so its
    `(+N unseen)` means *new since the last ref I read* — a number that answers
    "did this ref tell me anything" and NOT "is my file missing rows". The second
    question is the one that decides whether committing this file deletes
    somebody's work, so it is asked separately and plainly here.

    ⚠ **WHICH BRANCH TO COMPARE AGAINST IS THE WHOLE DIFFICULTY, AND BOTH
    OBVIOUS ANSWERS ARE WRONG (DEF-977's lesson, one level on).** A dispatched
    lane's local branch is `worktree-agent-<id>`; there is no
    `origin/worktree-agent-<id>` and its upstream is frequently unset, so a check
    keyed on either is SILENT in exactly the lane most likely to be stale — that
    is how the first draft was written, and it reported nothing at all on a tree
    seventeen rows behind. Comparing against EVERY `origin/*` ref is the other
    obvious answer and it is noise: a sibling lane's branch always holds rows this
    branch has never had, so the warning fires on a perfectly current file and is
    learnt to be ignored — measured at `+7` and `+2` from two unrelated branches
    on a file that was exactly in step with its own.
    **The discriminator that works is ANCESTRY, and it needs no configuration:**
    the branch a lane pushes to is one whose tip contains this HEAD. It picked the
    right branch and rejected both others on the tree this was written in. When
    NOTHING contains HEAD — local commits not yet pushed, or a rewind — the answer
    is not silence, which would be a check that cannot fail; it reports the worst
    case across all refs and says out loud that it could not tell which branch.

    Counted by ID and never by line: the two are not the same number, and mixing
    them is how this defect was first reported as 34 rows when it was 17. Older
    rows carry embedded newlines, so a line count is not a row count. An id
    present on a branch and absent here is unambiguous — somebody filed it, and a
    commit of this file would take it out.

    No fetch here: `known_ids()` has already done it, twice, and a second one
    would only cost time.
    """
    if not REGISTER.is_file():
        return [], True
    local = _ids_in(REGISTER.read_bytes())
    refs = [
        r.strip()
        for r in _git("for-each-ref", "--format=%(refname)", "refs/remotes/origin")
        .decode()
        .splitlines()
        if r.strip() and not r.strip().endswith("/HEAD")
    ]
    mine = [
        ref
        for ref in refs
        if subprocess.run(
            ["git", "-C", str(REPO), "merge-base", "--is-ancestor", "HEAD", ref],
            capture_output=True,
        ).returncode
        == 0
    ]
    identified = bool(mine)
    behind: list[tuple[str, int]] = []
    for ref in sorted(mine or refs):
        blob = _git("show", f"{ref}:12-governance/10-defect-log.csv")
        if not blob:
            continue
        missing = len(_ids_in(blob) - local)
        if missing:
            behind.append((ref.split("refs/remotes/", 1)[-1], missing))
    behind.sort(key=lambda pair: pair[1], reverse=True)
    return behind, identified


def warn_if_register_is_stale() -> None:
    """Say it at the moment of allocation, with the figure and the remedy.

    ⚠ **A WARNING AND NOT A REFUSAL, ON PURPOSE.** Nothing may stand between a
    lane and filing a defect; that is why the fetch is best-effort and it is why
    this is too. The row is still written and the id is still correct. What
    changes is that the lane learns, BEFORE it works, that the file it just
    appended to is not the one the branch has — which is the only moment at which
    the warning is cheap to act on.
    """
    behind, identified = rows_this_branch_has_and_this_file_does_not()
    if not behind:
        return
    worst_ref, worst = behind[0]
    named = " · ".join(f"{ref} (+{count})" for ref, count in behind[:4])
    hedge = (
        ""
        if identified
        else "   (no remote branch contains this HEAD, so this is the WORST CASE across all\n"
        "    of them rather than the branch you are on — check which one you push to.)\n"
    )
    print(
        f"\n⚠  THIS TREE'S REGISTER IS BEHIND. {worst_ref} holds {worst} defect row(s)\n"
        f"   that the file just appended to does not: {named}\n"
        f"{hedge}"
        f"   The id above is CORRECT — it was allocated against the remote. The FILE is not.\n"
        f"   Committing this one path from here DELETES those rows BY SUBTRACTION: the file\n"
        f"   count is 1, your own row IS present, and `git show` prints only your hunk,\n"
        f"   because the deleted rows are not in the diff at all (CLAUDE.md law 11).\n"
        f"   BEFORE YOU PUSH: rebuild the register from the tip and re-apply YOUR ROW to that.\n"
        f"   `./10-scripts/push_paths.sh` runs `push_register_guard.py` and refuses this push.\n"
        f"   An ordinary pathspec commit does not, and nothing downstream of it will either.\n"
        f"   ⚠ Do NOT just overwrite this file with the tip's bytes in a SHARED tree — another\n"
        f"   lane's unpushed row may be in it, and that is this same loss running backwards.\n",
        file=sys.stderr,
    )


RESERVATIONS = REPO / "12-governance" / "14-id-reservations.md"
_BLOCK_RE = re.compile(r"DEF-(?:[A-Z]{3}-)?(\d+)[–-](\d+)")


def reserved_blocks() -> list[tuple[int, int, str]]:
    """The ACTIVE DEF blocks another lane is holding, from 14-id-reservations.md.

    ⚠ WHY AN ALLOCATOR HAS TO READ A PROSE FILE (DEF-978, 2026-08-27).
    A reservation handed to a lane in its dispatch exists only in that sentence.
    `max + 1` walks straight through it, so ten minutes after a block was
    reserved this tool returned DEF-1001 out of the middle of it. The block is
    only real if the thing that allocates can see it, and the register of blocks
    is a document people maintain — so this reads the document. A malformed or
    missing file yields no blocks and the old behaviour, because nothing must
    stop a lane filing a defect.
    """
    if not RESERVATIONS.is_file():
        return []
    lines = RESERVATIONS.read_text(encoding="utf-8").splitlines()

    # ⚠ THE STATE IS READ FROM THE **State** COLUMN BY NAME, NOT BY SEARCHING THE
    #   WHOLE LINE (DEF-1182, 2026-08-27). This used to be
    #       if "**ACTIVE**" not in line: continue
    #   — a literal substring over the entire row — and it was blind to FIVE held
    #   blocks on the day it was measured, four of them beyond doubt:
    #
    #     DEF-1060-1089  state "**ACTIVE — NARROWED 2026-08-27.**"  (ACTIVE, but
    #                    the exact string `**ACTIVE**` never appears)
    #     DEF-1390-1419  \
    #     DEF-1420-1449   > state "**RESERVED, not started**" — held, and the old
    #     DEF-1450-1479  /  check knew only one of the two words a row can carry
    #
    #   The failure is silent and it hands the SAME id to two lanes: the allocator
    #   walks straight into a range somebody is already filing into. It did exactly
    #   that today and the stale-defect audit reproduced it.
    #
    #   Reading the named column also fixes the second half nobody had noticed:
    #   `cells[-1]` is only the state while every row has four cells, and rows in
    #   this repo's tables DO vary in width — DEF-1087 is the register-wide version
    #   of that same mistake. A header lookup cannot drift when a row gains a cell.
    state_index = 3  # the documented column order, used only if no header is found
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if [c.lower() for c in cells[:4]] == ["block", "lane", "opened", "state"]:
            state_index = 3
            break

    blocks: list[tuple[int, int, str]] = []
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) <= state_index:
            continue
        state = cells[state_index].upper()
        # RELEASED wins wherever both words appear: a released row often explains
        # in the same cell which ids the block was ACTIVE for, and that prose must
        # not re-reserve a range somebody has finished with.
        if "RELEASED" in state:
            continue
        if "ACTIVE" not in state and "RESERVED" not in state:
            continue
        match = _BLOCK_RE.search(cells[0]) if cells else None
        if match:
            owner = cells[1] if len(cells) > 1 else "another lane"
            blocks.append((int(match.group(1)), int(match.group(2)), owner))
    return blocks


def next_id(seen: set[int], mine: str = "") -> str:
    """`max + 1`, then UP past any block another lane is holding.

    ⚠ **IT STEPPED DOWN UNTIL 2026-09-03 AND THAT IS DEF-1221: THE TOOL THAT
    EXISTS TO PREVENT ID COLLISIONS CAUSED ONE, AND REPORTED SUCCESS DOING IT.**
    The reasoning for down was written here in good faith — *"stepping up would
    leap over the whole reserved range and strand every id in it"* — and it is
    wrong in both halves. The ids inside an ACTIVE block are not stranded: they
    belong to the lane holding that block, which files into them with `--block`.
    And below the watermark there is nothing to be beside; there is only somebody
    else's reservation, or a gap that is legitimately abandoned.

    **What it did instead:** `max + 1`, and then, for every ACTIVE block that
    contained the candidate, drop to `low - 1` — cascading down through stacked
    blocks — and then decrement past every taken id and every other block. On
    2026-08-27 the register's watermark was DEF-1179, the caller held
    DEF-1220–1249, and the tool returned **DEF-1080**, inside the CR-043 bills
    lane's ACTIVE block. On 2026-09-03, from the branch tip, it offered
    **DEF-2337** — twelve hundred below the frontier, inside no reservation and
    therefore inside nobody's promise, which is DEF-1787's collision shape. Every
    note it prints names a block it STEPPED PAST; none names the block it landed
    IN, so its output reads as the guard working.

    **UP is the fix, and it is better than the refusal DEF-1221's row proposed.**
    That row said the descending scan *"must at minimum REFUSE rather than
    return"*, on the grounds that a refusal costs a lane a minute and a collision
    costs two lanes a merge. Both true — but a refusal still stands between a
    lane and filing a defect, and a lane that cannot file one stops filing them.
    Walking UP costs nothing and cannot land inside a reservation: from `max + 1`,
    jump to `high + 1` for any block containing the candidate and repeat. It
    terminates because the blocks are finite, it never returns an id below the
    frontier, and it always returns an id.

    The price is that ids inflate past a stack of reserved blocks — DEF-3540
    rather than DEF-3524 when 3520–3539 is held. That is the correct price: the
    grammar allows five digits (PO ruling 2026-08-31) and the register stands in
    the three thousands, so there is room, and a gap is legitimate where a
    collision is not.

    ⚠ **AND IT NOW PRINTS THE POSITIVE FINDING, WHICH IS DEF-1182's OTHER HALF**
    and was never done: *"allocated DEF-nnnn; it is inside no active block"*. A
    tool that lists the blocks it skipped and says nothing about where the answer
    landed has given the lane the wrong half of the answer — silence about a
    block reads as clearance of it, which is the *check that cannot distinguish
    pass from fail* that law 11 records twice about `git --stat`.

    ⚠ **`mine` EXISTS BECAUSE THIS FUNCTION USED TO STEP DOWN PAST THE CALLER'S
    OWN BLOCK (DEF-1814).** A lane is dispatched with a reservation, and the
    reservation's whole purpose is that the lane files INTO it — but the tool had
    no identity, so "a block another lane is holding" matched every block
    including the caller's. The R1–R7 lane, reserved DEF-1810–1839, was handed
    DEF-1793…1796 and 1809 and renumbered five rows by hand. **Hand-renumbering
    is exactly the operation this file exists to remove**, and one of the numbers
    it was pushed onto (DEF-1793) had been taken by another lane minutes earlier.

    Pass `--block 1810-1839` and this allocates INSIDE that range, skipping only
    the blocks that belong to someone else. An unreserved `mine` is refused
    rather than trusted: claiming a block nobody gave you is the collision this
    guards against, wearing a flag.
    """
    if not seen:
        return "DEF-001"
    blocks = reserved_blocks()

    if mine:
        try:
            low_s, high_s = mine.replace("DEF-", "").split("-")
            claim = (int(low_s), int(high_s))
        except ValueError:
            raise SystemExit(f"refused: --block {mine!r} is not a LOW-HIGH range, e.g. 1810-1839")
        if not any((l, h) == claim for l, h, _ in blocks):
            raise SystemExit(
                f"refused: DEF-{claim[0]}-{claim[1]} is not an ACTIVE block in "
                f"{RESERVATIONS.name}. Reserve it there first — a block claimed on "
                f"the command line and nowhere else is the promise that does not "
                f"survive the chat (DEF-1814, and this file's own opening line)."
            )
        others = [b for b in blocks if (b[0], b[1]) != claim]
        candidate = claim[0]
        while candidate <= claim[1] and (candidate in seen
                                         or any(l <= candidate <= h for l, h, _ in others)):
            candidate += 1
        if candidate > claim[1]:
            raise SystemExit(
                f"refused: every id in DEF-{claim[0]}-{claim[1]} is taken. Reserve a "
                f"second block in {RESERVATIONS.name} rather than spilling out of this one."
            )
        print(f"note: allocating inside your own block DEF-{claim[0]}-{claim[1]}", file=sys.stderr)
        return f"DEF-{candidate:03d}"

    candidate = max(seen) + 1
    # ⚠ UP, NEVER DOWN (DEF-1221). One loop, and the order inside it matters:
    # a block is jumped CLEAR (to `high + 1`) rather than stepped through, so a
    # stack of adjacent blocks resolves in one pass per block instead of one pass
    # per id. `owner` is printed because a lane that is told only "reserved"
    # cannot go and ask anybody (DEF-1182).
    while True:
        holder = next(
            ((low, high, owner) for low, high, owner in sorted(blocks) if low <= candidate <= high),
            None,
        )
        if holder is not None:
            low, high, owner = holder
            print(
                f"note: DEF-{candidate} is inside {low}-{high}, held by {owner};"
                f" stepping UP to the first free id above it",
                file=sys.stderr,
            )
            candidate = high + 1
            continue
        if candidate in seen:
            candidate += 1
            continue
        break
    # ⚠ THE POSITIVE FINDING, not only the negative ones (DEF-1182). Without this
    # line the tool lists the blocks it avoided and says nothing about where the
    # answer sits, and silence about a block reads as clearance of it.
    print(f"note: allocated DEF-{candidate}; it is inside no active block", file=sys.stderr)
    return f"DEF-{candidate:03d}"


#: Fields that must carry something. `required=True` in argparse is satisfied by
#: `--title ""`, which files a row nobody can act on and which no gate reports.
NON_EMPTY = ("title", "surface", "module", "found_in", "introduced_in",
             "category", "escape_reason", "prevention")


def validate_inputs(a: argparse.Namespace) -> list[str]:
    """Everything wrong with what this lane typed, as sentences it can act on.

    ⚠ **THIS RUNS BEFORE THE FETCH, ON PURPOSE.** `known_ids()` does two network
    fetches and walks every remote ref; a lane that typed `--severity major` should
    learn so in milliseconds, not after five seconds of git. It also runs on the
    `--dry-run` path, because a dry run whose only difference from the real one is
    that it cannot fail is not a rehearsal of anything.

    ⚠ **AND IT REFUSES RATHER THAN CORRECTS.** See `register_vocabulary`: guessing
    that `major` means `high` is a script destroying the evidence the register
    exists for. The refusal names the survivor and the lane retypes one word.
    """
    problems: list[str] = []

    for field in NON_EMPTY:
        if not str(getattr(a, field, "") or "").strip():
            problems.append(f"--{field.replace('_', '-')} is empty; a row nobody can read is not a record")

    complaint = explain_severity(a.severity)
    if complaint:
        problems.append(complaint)

    # ⚠ CATEGORY IS CHECKED HERE AND CAN ONLY BE CHECKED HERE, WHICH IS NOT TRUE
    # OF THE OTHER TWO. G46 refuses a retired severity on any row of the register,
    # because four values can be listed and 2,395 rows tested against them. It
    # CANNOT do that for `category`: 1,016 distinct strings already exist and
    # refusing them would make the gate red over history nobody may rewrite. So
    # the gate counts the legacy rows and this line is the only place the twelve
    # are ever enforced — hard-won law 2's shape, a rule whose single enforcement
    # point must therefore actually run. `10-scripts/gates/g46_register_
    # vocabularies.py::selftest` asserts that it bites, on every suite.
    complaint = explain_category(a.category)
    if complaint:
        problems.append(complaint)

    # `status` is a constant in `build_row` today rather than a flag. It is checked
    # anyway and through the SAME vocabulary as `close_defect.py`, so that the day
    # somebody adds `--status` — or edits that constant — the check is already
    # standing there. A vocabulary enforced at one of its two writers is a
    # vocabulary with a hole in it.
    complaint = explain_status(NEW_ROW_STATUS)
    if complaint:
        problems.append(f"this tool's own constant is wrong: {complaint}")

    # A SEVERITY SITTING IN `module` IS A SHIFTED ROW, and every other cell is then
    # suspect too — G46 reports exactly this on DEF-358 and refuses to guess which
    # module was meant. Catching it here costs one comparison. The module column is
    # NOT otherwise closed: modules are added by ruling (work became the eleventh on
    # 2026-09-03) and a tool that refused an unknown one would refuse the first row
    # filed against every new module.
    if (a.module or "").strip().lower() in {"critical", "high", "medium", "low", "major", "minor"}:
        problems.append(
            f"--module {a.module!r} is a SEVERITY. Your arguments are shifted one to the "
            "left; check every one of them before filing (G46 reports this shape on "
            "DEF-358 and will not guess which module you meant)."
        )
    return problems


def validate_register_shape() -> list[str]:
    """The register's header must be the columns this tool writes, in this order.

    ⚠ **WHY THE HEADER AND NOT THE ROWS.** `build_row` serialises `COLUMNS` in
    order. If somebody adds a fifteenth column to the register, every row this
    tool appends is one field SHORT — and a short row does not look broken, it
    looks like a row whose later fields have all moved one place left. That is
    `DEF-WRK-4051` exactly: 23 fields against a 14-column header put the word
    `for the registry)` in the `status` column, and nothing could tell what the
    row said. Comparing the header costs one line of I/O and it is the whole
    check: a tool cannot detect the drift by reading its own output.

    Only the first line is read. The file is not loaded — this tool's entire
    guarantee is that nothing already in the register is read into memory to be
    written back (see the module docstring), and a 1,900-row read here would
    quietly undo it.
    """
    with REGISTER.open("rb") as fh:
        header_line = fh.readline()
    header = next(csv.reader([header_line.decode("utf-8", "replace").rstrip("\r\n")]), [])
    header = [c.strip() for c in header]
    if header == COLUMNS:
        return []
    missing = [c for c in COLUMNS if c not in header]
    extra = [c for c in header if c not in COLUMNS]
    return [
        f"the register's header is {len(header)} column(s) and this tool writes "
        f"{len(COLUMNS)}, or they are in a different order — appending here would "
        f"shift every field of the new row (DEF-WRK-4051's shape). "
        f"header={header} · writes={COLUMNS}"
        + (f" · missing from the header: {missing}" if missing else "")
        + (f" · in the header and not written: {extra}" if extra else "")
    ]


def validate_row_round_trips(row: str) -> list[str]:
    """Read back the line this tool is about to write and count its fields.

    A row is only a row if a CSV reader gets `len(COLUMNS)` fields out of it.
    `DEF-WRK-4051` was written by something that escaped a quote the way a
    programming language does — `\"` where CSV doubles it — so the field closed
    early and the reader saw 23 columns. Downstream nothing reports a BROKEN
    row; it reports a SHORTER one, which reads as data.

    `csv.writer` gets the escaping right today, so this clause is insurance
    rather than a live catch — said plainly rather than left for a reader to
    assume it has teeth (hard-won law 1). What it protects is the next change to
    `build_row`: the moment anybody assembles this line by hand or by f-string,
    which is how the malformed row got there in the first place, this fails.
    """
    fields = next(csv.reader([row]), [])
    if len(fields) == len(COLUMNS):
        return []
    return [
        f"the row this tool built reads back as {len(fields)} field(s), not "
        f"{len(COLUMNS)} — it would land in the register with its columns shifted "
        f"(DEF-WRK-4051). Do not write it."
    ]


def build_row(a: argparse.Namespace, ident: str) -> str:
    values = {
        "id": ident,
        "reported_on": a.reported_on or date.today().isoformat(),
        "reported_by": a.reported_by,
        "title": a.title,
        "surface": a.surface,
        "module": a.module,
        "severity": a.severity,
        "found_in": a.found_in,
        "introduced_in": a.introduced_in,
        "category": a.category,
        "escape_reason": a.escape_reason,
        "status": NEW_ROW_STATUS,
        "fixed_commit": "",
        "prevention": a.prevention,
    }
    for key, val in values.items():
        if "\n" in val or "\r" in val:
            sys.exit(f"refused: --{key.replace('_','-')} contains a newline, which would split the row in two")
    buf = io.StringIO()
    csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="").writerow([values[c] for c in COLUMNS])
    return buf.getvalue()


def line_terminator(raw: bytes) -> bytes:
    r"""The register's terminator, read from its HEADER LINE and nowhere else.

    ⚠ **THIS USED TO BE `b"\r\n" if b"\r\n" in raw else b"\n"`, AND THAT PUT
    NINE BLANK LINES IN THE REGISTER (DEF-2598).** A carriage return sitting
    inside a quoted `escape_reason` — seven of them are in there, written before
    `build_row` learned to refuse one — makes `b"\r\n" in raw` TRUE for the whole
    file. The file itself ends with a bare `\n`, so `raw.endswith(nl)` is False,
    the appender writes a terminator "to finish the last line", and the result is
    a **blank line before every row**, plus a row terminated differently from its
    neighbours.

    **Nothing caught it and nothing could**: G26 accepts blank lines, the row is
    well-formed, and this tool's own docstring says the terminator is detected
    and preserved — a comment claiming a guarantee (hard-won law 1). It surfaced
    only because a one-row append reported *2 insertions* instead of 1.

    The header line is the right place to read it from: it is line 1, it is
    fixed, it contains no free text, and it cannot acquire a stray carriage
    return the way a prose column can. A file whose header ends `\r\n` is CRLF;
    anything else is LF.
    """
    end = raw.find(b"\n")
    if end > 0 and raw[end - 1 : end] == b"\r":
        return b"\r\n"
    return b"\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for flag, required in [
        ("title", True), ("surface", True), ("module", True), ("severity", True),
        ("found-in", True), ("introduced-in", True), ("category", True),
        ("escape-reason", True), ("prevention", True),
    ]:
        p.add_argument(f"--{flag}", required=required, default="")
    p.add_argument("--reported-by", default="an AI lane")
    p.add_argument("--reported-on", default="")
    p.add_argument("--block", default="",
                   help="the reservation block YOU were dispatched with, e.g. 1810-1839. "
                        "Allocates inside it instead of stepping down past it (DEF-1814). "
                        "Must already be ACTIVE in 12-governance/14-id-reservations.md.")
    p.add_argument("--id-module", default="",
                   help="three-capital module code written INTO the id — DEF-WRK-3552 — per the PO ruling of "
                        "2026-09-03 ('add prefix going forward Def-Wrk-nnnn'). The number is still the register "
                        "maximum plus one across every module; omit for a governance or tooling defect that no "
                        "module owns, which keeps the bare DEF-nnnn.")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    if not REGISTER.is_file():
        sys.exit(f"refused: {REGISTER} does not exist")

    # ⚠ VALIDATE BEFORE THE NETWORK AND BEFORE THE WRITE. Everything below this
    # block costs seconds (two fetches and a walk of every remote ref); a word
    # from the wrong vocabulary can be refused in milliseconds. Every problem is
    # reported at once rather than one per run — a lane that has to invoke this
    # four times to learn four things stops using the tool.
    problems = validate_inputs(a) + validate_register_shape()
    if problems:
        sys.exit(
            "refused: nothing was written.\n  "
            + "\n  ".join(problems)
            + "\n\nWHY THIS IS REFUSED HERE RATHER THAN REPORTED BY A GATE: a gate can only "
            "speak once the row is on the branch, by which time the lane that knew what it "
            "meant has moved on and somebody else is reading the row to guess. "
            "(DEF-WRK-4079 / DEF-MET-4081, 2026-09-05 — two rows filed with the retired "
            "severity on the same day G46 was taken green twice.)"
        )

    seen, sources = known_ids()
    ident = next_id(seen, a.block)
    if a.id_module:
        if not re.fullmatch(r"[A-Z]{3}", a.id_module):
            raise SystemExit(f"refused: --id-module {a.id_module!r} is not three capitals, e.g. WRK")
        ident = ident.replace("DEF-", f"DEF-{a.id_module}-", 1)
    row = build_row(a, ident)
    malformed = validate_row_round_trips(row)
    if malformed:
        sys.exit("refused: nothing was written.\n  " + "\n  ".join(malformed))
    print(f"ids read from: {' · '.join(sources)}", file=sys.stderr)
    # ⚠ AFTER the sources line, BEFORE the row is written, and on the --dry-run
    # path too: the lane reads this at the moment it is about to work, which is
    # the only moment the warning is cheap to act on (DEF-3523).
    warn_if_register_is_stale()

    if a.dry_run:
        print(f"would append as {ident}:", file=sys.stderr)
        print(row)
        return 0

    # ⚠ RE-DERIVE THE ID, UNCONDITIONALLY, IMMEDIATELY BEFORE THE WRITE — law 11's
    # id clause on a shorter clock. `known_ids()` above fetched twice and walked
    # every remote ref, which takes seconds; in a shared tree a sibling appending
    # to this very file inside that window is the ordinary case, not the rare one.
    # `allocate.py --verify` exists for the same question at push time and says
    # plainly what it cannot do: "nothing writes to the remote, so two lanes
    # calling it in the same second still collide. It removes the STALE read."
    # This removes the stale read at the last moment there is one to remove.
    # No fetch: the question is whether the world moved since the reading above,
    # and fetching again would fold new remote rows in and make it unanswerable.
    taken, _ = known_ids(fetch=False)
    number = int(ident.rsplit("-", 1)[1])
    if number in taken - seen:
        sys.exit(
            f"refused: nothing was written. {ident} was taken while this run was "
            f"reading the remote — somebody appended it in the last few seconds. "
            f"Run this again; it will allocate the next free id. "
            f"(Law 11: an allocated id is a blob too, and both lanes' arithmetic is "
            f"correct — what is wrong is WHICH WORLD the maximum came from.)"
        )

    raw = REGISTER.read_bytes()
    nl = line_terminator(raw)
    # APPEND MODE. Nothing already in the file is read into memory to be written
    # back, so nothing already in the file can be changed by this write.
    with REGISTER.open("ab") as fh:
        if not raw.endswith(nl):
            fh.write(nl)
        fh.write(row.encode("utf-8") + nl)
    print(ident)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
