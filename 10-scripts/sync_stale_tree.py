#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Rules:  CLAUDE.md law 12 — the working-tree half of the rewind recovery, its
#         content-addressed test, its mode clause and its delete half ·
#         law 11 — the commit-tree push leaves the tree stale and
#         `git status` reports CLEAN over it (DEF-2474); the banned commands
#         (`checkout --`, `restore`, `stash`, `reset --hard`, `clean`) appear
#         nowhere in this file, because it exists precisely because people
#         reach for them
# ───────────────────────────────────────────────────────
"""BRING THIS WORKING TREE UP TO A PINNED TIP — AND `git status` CANNOT SEE THE
THING THIS FIXES.

WHAT IT IS FOR, IN ONE PARAGRAPH
--------------------------------
`push_paths.sh` builds its commit from the PINNED TIP in a private index, which
is exactly why it is safe — and it therefore **updates no file on disk**. After
it returns, every path a sibling pushed while you worked is still at the content
you started from. `git status` compares the tree against **`HEAD`**, and `HEAD`
is the thing that did not move, so it reports **CLEAN over a loaded revert**: the
next ordinary pathspec commit publishes it, with a correct file count, with your
own change present, and with nothing in the diff to notice. On 2026-08-30 that
was 39 files including all eleven locale catalogues (`DEF-2474`). This tool is
the step law 12 prescribes in prose and that nothing in `10-scripts/` performed.

It is the TREE's counterpart to two tools that already exist and answer different
questions: `check_head_current.sh` asks whether the branch POINTER moved, and
`check_stale_index.py` asks whether the shared INDEX holds a revert. Neither
looks at file content.

    python3 10-scripts/sync_stale_tree.py <tip-ish> [--dry-run] [--depth N]

⚠ **IT MOVES FILES AND NOTHING ELSE.** It does not touch the index, it does not
move `HEAD`, and it makes no commit — so a sibling's staged work is untouched and
`git reset` is still yours to run afterwards, deliberately, when you mean to.

HOW IT DECIDES, AND THE DECISION IS CONTENT-ADDRESSED
------------------------------------------------------
For every path that differs from the tip it asks law 12's own question: **is this
file's exact blob an OLDER version of this same path?** — `git hash-object`, then
walk `git log --format=%H -- <path>` comparing `git rev-parse <commit>:<path>`.

  * **HIT** — the content is a version this repository already had, so **no lane
    authored it here** and it is safe to move. RESTORED (or, for a file the tip
    does not have, REMOVED).
  * **MISS** — decides nothing, so the file is **LEFT ALONE**. It is either real
    in-flight work or a half-edited stale file, and only its owner can tell. The
    tool reports the miss with a superset verdict as *information* — additions
    only reads like a lane writing on the tip; missing lines reads like a stale
    base — and **acts on neither**.

That asymmetry is the whole safety property: a wrong RESTORE destroys a lane's
work, a wrong SKIP costs a second run.

THE FOUR CLAUSES THAT ARE EACH PAID FOR BY A REAL INCIDENT
-----------------------------------------------------------
1. **The mode is restored in the SAME LOOP as the write**, keyed off
   `git ls-tree <tip>`. Law 12's own prescribed command —
   `git show <tip>:<path> > <path>` — is a shell redirect, so it creates the file
   with the default mode and **drops the executable bit on every `100755` file it
   touches**. The procedure the law recommends manufactures the defect the law
   warns about, and a mode-only difference is invisible to every check that reads
   content: bytes compare equal, `git diff --numstat` prints nothing.
   `10-scripts/allocate.py` was turned non-executable this way on 2026-09-04.
2. **The content is built in full and asserted non-empty BEFORE the destination
   is opened.** A repair script here once did `open(dst, "w")` and only then read
   its input; the read failed, the output was already truncated, and `CLAUDE.md`
   went to zero bytes. It survived because a numstat printed `0 519`.
3. **It DELETES as well as writes.** A path the tree has and the tip does not is
   the mirror case, and it arrives from an ordinary sibling action rather than a
   rewind: a migration is pushed, a later lane renames it, and any tree that
   synced in between holds BOTH spellings — Django then refuses **every test in
   the process** with *"multiple leaf nodes in the migration graph"*, naming
   neither lane (`DEF-2872`). A write-only sync is half a sync. The same
   content-addressed test gates the removal, in the same direction: hit removes,
   miss leaves.
4. **It verifies by SUBTRACTION and prints what it skipped beside what it
   touched.** `git diff --numstat <tip>` must end empty for the paths it moved,
   and the summary carries three numbers. A declared blind spot with no number
   attached is indistinguishable from an empty one — `G32` reported `0
   unresolved`, truthfully, over 21 live refusals it could not see.

WHAT WOULD MAKE THIS PASS WRONGLY
---------------------------------
Asked before it was trusted, because a check whose false pass you cannot describe
is a check you do not understand:

  * **A HIGH-CHURN PATH WHOSE HISTORY WALK IS TRUNCATED.** The defect register
    has thousands of revisions; at `--depth 200` a genuinely stale copy older
    than the window is a MISS and is left. That is the safe direction and it is
    the reason the depth is printed in the summary rather than buried — a lane
    seeing `left: 3` on the registers should look, not shrug.
  * **A FILE THAT IS STALE AND WAS NEVER COMMITTED AT THAT CONTENT.** Half-edited
    staleness has no history entry, so it MISSES and is left. The tool cannot fix
    it and does not pretend to; the superset verdict beside it is what tells a
    human which way to look.
  * **A COINCIDENTAL BLOB MATCH.** If a lane's live edit happens to reproduce an
    older revision byte for byte, the test HITS and the file is moved to the tip.
    Nothing is lost that the repository does not already hold, which is the exact
    claim the test makes and no more.
  * **A TIP THAT MOVED WHILE IT RAN.** The tip is resolved to a SHA **once**, at
    the top, and every command uses that SHA — `DEF-306` is a tree and a parent
    taken from two lookups of a ref a sibling moved between them.
  * **AN EMPTY RUN REPORTED AS SUCCESS.** A tree already in sync and a tree the
    tool could not read are different states; the summary says `nothing differed`
    for the first and the command fails loudly for the second.

PROVED RED FIRST (law 7), IN THE HARNESS A CALLER USES
-------------------------------------------------------
`--selftest` builds a real git repository in a temp directory and drives the same
`sync()` the CLI calls. Four cases, each of which the first draft got wrong:
a stale file is restored; a live edit is LEFT; a `100755` file keeps its bit
across the restore; and a leftover file that is **not** in the tip's history is
left alone while one that IS gets removed. If any case fails the command exits
non-zero and says which.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


#: ⚠ **WITHOUT THIS, THIS WHOLE TOOL ABORTS ON THE FIRST NON-ASCII PATH AND
#: LEAVES THE TREE STALE — which is the exact state it exists to prevent
#: (`DEF-GOV-5208`, 2026-09-14).** `git ls-tree` and `git diff --name-only`
#: C-QUOTE any path outside plain ASCII: this repo's blueprint PDFs are named
#: with an EM-DASH, so they came back as
#:
#:     "05-prototype/03 SMARTBillHub \342\200\224 Meter Reads blueprint.pdf"
#:
#: — literal quotes, octal escapes, and **not a path any `git show` can open.**
#: The `GitError` that followed killed `sync()` mid-loop, so every file after
#: it in the walk was abandoned silently while `push_paths.sh` printed
#: "pushed". **The push was always fine; the tree was left loaded**, and every
#: post-push check in law 11 reads COMMITS, so all of them passed over it.
#:
#: Proved on the real path before and after: quoted → `git show` exits 128;
#: unquoted → 4,779,186 bytes, the PDF.
_QUOTE_PATH_OFF: tuple[str, ...] = ("-c", "core.quotePath=false")


class GitError(RuntimeError):
    """A git command this tool depends on did not answer. Never swallowed."""


def git(*args: str, repo: Path, check: bool = True) -> str:
    """Run one git command in `repo` and return stdout.

    ⚠ Every call this module makes is a READ except `git show`/`ls-tree`, which
    are also reads. There is no `checkout`, `restore`, `stash`, `reset` or
    `clean` anywhere in this file, and there must not be: all five are banned by
    law 11 and this tool exists because they are what people reach for.
    """
    result = subprocess.run(["git", *_QUOTE_PATH_OFF, *args], cwd=repo,
                            capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise GitError(f"git {' '.join(args)} → {result.returncode}: {result.stderr.strip()}")
    return result.stdout


def git_bytes(*args: str, repo: Path) -> bytes:
    result = subprocess.run(["git", *_QUOTE_PATH_OFF, *args], cwd=repo,
                            capture_output=True, check=False)
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)} → {result.returncode}")
    return result.stdout


def tip_modes(tip: str, *, repo: Path) -> dict[str, str]:
    """`{path: "100644" | "100755" | …}` for every blob at the tip.

    Read ONCE, so the mode restore in the write loop costs no extra process per
    file and cannot be skipped for the last one.
    """
    modes: dict[str, str] = {}
    for line in git("ls-tree", "-r", tip, repo=repo).splitlines():
        if not line.strip():
            continue
        meta, _, path = line.partition("\t")
        modes[path] = meta.split()[0]
    return modes


def blob_is_a_known_version(path: str, *, repo: Path, depth: int) -> bool:
    """Law 12's content-addressed test: is this exact blob an OLDER version of this path?

    A HIT proves no lane authored the content — the repository already held it —
    so moving the file destroys nothing. A MISS proves NOTHING and the caller
    must leave the file alone; it is absence of evidence, not evidence of
    absence, and the walk is depth-limited besides.
    """
    on_disk = Path(repo, path)
    if not on_disk.is_file():
        return False
    current = git("hash-object", "--", path, repo=repo).strip()
    if not current:
        return False
    for commit in git("log", f"--max-count={depth}", "--format=%H", "--", path, repo=repo).split():
        historical = git("rev-parse", f"{commit}:{path}", repo=repo, check=False).strip()
        if historical == current:
            return True
    return False


def superset_verdict(path: str, tip: str, *, repo: Path) -> str:
    """Information only, printed beside a MISS. This tool never acts on it.

    `additions only` reads like a lane legitimately writing on the tip;
    `loses N line(s)` reads like a lane writing on a stale base. Which it is, is
    a question for the person who owns the file.
    """
    try:
        at_tip = git_bytes("show", f"{tip}:{path}", repo=repo).splitlines()
    except GitError:
        return "not at the tip"
    on_disk = Path(repo, path)
    if not on_disk.is_file():
        return "absent from the tree"
    present = set(on_disk.read_bytes().splitlines())
    lost = sum(1 for line in at_tip if line not in present)
    return "additions only" if lost == 0 else f"loses {lost} line(s) the tip has"


def write_from_tip(path: str, tip: str, *, repo: Path, mode: str | None) -> None:
    """Write the tip's bytes over `path`, then set its mode — in ONE step.

    The bytes are fetched IN FULL and the destination is opened only afterwards
    (clause 2). The `chmod` is here rather than in a later pass because a restore
    that writes bytes and does not set the mode is half a restore, and it is the
    half that leaves no trace (clause 1).
    """
    blob = git_bytes("show", f"{tip}:{path}", repo=repo)  # in hand BEFORE the open
    destination = Path(repo, path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "wb") as handle:
        handle.write(blob)
    if mode == "100755":
        os.chmod(destination, 0o755)
    elif mode == "100644":
        os.chmod(destination, 0o644)


def paths_differing(tip: str, *, repo: Path) -> list[str]:
    """Tracked paths whose content differs from the tip."""
    return [p for p in git("diff", "--name-only", tip, repo=repo).splitlines() if p]


def paths_the_tip_does_not_have(tip: str, *, repo: Path) -> list[str]:
    """Untracked, un-ignored files that do not exist at the tip (clause 3).

    ⚠ `--exclude-standard` matters: without it this walks `node_modules` and
    every build artefact, and the content test would then be asked about
    hundreds of thousands of files it can only answer MISS for. An ignored file
    is not the tree being out of sync, it is the tree working.
    """
    out = []
    for path in git("ls-files", "--others", "--exclude-standard", repo=repo).splitlines():
        if not path:
            continue
        missing = subprocess.run(
            ["git", "cat-file", "-e", f"{tip}:{path}"],
            cwd=repo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        if missing != 0:
            out.append(path)
    return out


def sync(tip_ish: str, *, repo: Path, depth: int = 200, dry_run: bool = False) -> dict[str, list[str]]:
    """Move the STALE half of the tree to the tip. Files only, never the index.

    Returns `{"restored": [...], "removed": [...], "left": ["<path> — why"]}`.
    """
    # ⚠ THE TIP IS RESOLVED ONCE. `origin/<branch>` is a local ref any sibling's
    # fetch can move between two lookups, and a tree taken from one commit with a
    # parent from another reverts everything between them by subtraction
    # (DEF-306).
    tip = git("rev-parse", "--verify", f"{tip_ish}^{{commit}}", repo=repo).strip()
    if not tip:
        raise GitError(f"{tip_ish!r} does not resolve to a commit")
    modes = tip_modes(tip, repo=repo)
    report: dict[str, list[str]] = {"restored": [], "recreated": [], "removed": [], "left": [],
                                    "failed": []}

    for path in paths_differing(tip, repo=repo):
        if path not in modes:
            # tracked here, gone at the tip — the delete half decides it below
            if blob_is_a_known_version(path, repo=repo, depth=depth):
                if not dry_run:
                    Path(repo, path).unlink(missing_ok=True)
                report["removed"].append(path)
            else:
                report["left"].append(f"{path} — not a version this repo held; only its owner can say")
            continue
        # ⚠ A FILE ABSENT FROM THE TREE IS RE-CREATED UNCONDITIONALLY, and this
        # branch must come BEFORE the content test. `blob_is_a_known_version`
        # hashes the copy ON DISK to decide whether moving it destroys a lane's
        # work; with no file there is nothing to hash, so it returns False and
        # the path fell to LEFT. That is the wrong answer for the one case where
        # the risk is lowest: there is no edit on disk to protect, and law 12
        # names this case explicitly — the restore "also recreates files the
        # rewind deleted".
        #
        # It cost 3,265 lines of a sibling wave sitting missing under a
        # stop-hook that kept asking for them to be committed as DELETIONS
        # (DEF-GOV, 2026-09-06). The tool was proved on four sabotages and this
        # shape was not one of them — law 7's "ask what would make this check
        # pass wrongly", answered too narrowly.
        #
        # The one residual risk, stated rather than hidden: a lane that
        # DELIBERATELY deleted a file and has not yet pushed sees it come back.
        # That is real, strictly smaller than losing a pushed wave, and it is
        # why re-creations are reported on their own line instead of being
        # folded into "restored".
        # ⚠ **A FAILURE ON ONE PATH MUST NOT ABANDON THE REST OF THE WALK**
        # (`DEF-GOV-5208`). Until 2026-09-14 a single `GitError` propagated out
        # of `sync()` and every file after it was left stale while the caller
        # printed "pushed" — the amplifier that turned a quoting bug into a
        # loaded revert of the whole tree. The root cause is fixed above; this
        # is the blast radius, and it is kept small on purpose: the failure is
        # RECORDED AND PRINTED, never swallowed, and `main` exits non-zero on it
        # (law 7 — a scope a tool could not cover must be reported with a
        # NUMBER, or an empty result is indistinguishable from a skipped one).
        if not (repo / path).is_file():
            try:
                if not dry_run:
                    write_from_tip(path, tip, repo=repo, mode=modes.get(path))
                report["recreated"].append(path)
            except (GitError, OSError) as exc:
                report["failed"].append(f"{path} — {exc}")
        elif blob_is_a_known_version(path, repo=repo, depth=depth):
            try:
                if not dry_run:
                    write_from_tip(path, tip, repo=repo, mode=modes.get(path))
                report["restored"].append(path)
            except (GitError, OSError) as exc:
                report["failed"].append(f"{path} — {exc}")
        else:
            report["left"].append(f"{path} — {superset_verdict(path, tip, repo=repo)}")

    for path in paths_the_tip_does_not_have(tip, repo=repo):
        if blob_is_a_known_version(path, repo=repo, depth=depth):
            if not dry_run:
                Path(repo, path).unlink(missing_ok=True)
            report["removed"].append(path)
        else:
            report["left"].append(f"{path} — untracked and never committed at this content")

    return report


# ── the self-test's synthetic repository ──────────────────────────────────
def _run(*args: str, repo: Path) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def selftest() -> list[str]:
    """Drive `sync()` — the function the CLI calls — over a real temp repository.

    Returns the list of failures; empty means every sabotage bit.
    """
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        _run("init", "-q", "-b", "main", repo=repo)
        _run("config", "user.email", "selftest@example.invalid", repo=repo)
        _run("config", "user.name", "selftest", repo=repo)

        (repo / "stale.txt").write_text("v1\n", encoding="utf-8")
        (repo / "live.txt").write_text("v1\n", encoding="utf-8")
        script = repo / "tool.sh"
        script.write_text("#!/bin/sh\necho v1\n", encoding="utf-8")
        os.chmod(script, 0o755)
        (repo / "renamed.txt").write_text("v1\n", encoding="utf-8")
        _run("add", "-A", repo=repo)
        _run("commit", "-qm", "v1", repo=repo)

        # the tip moves: three files change, one is deleted
        (repo / "stale.txt").write_text("v2 from the tip\n", encoding="utf-8")
        (repo / "live.txt").write_text("v2 from the tip\n", encoding="utf-8")
        script.write_text("#!/bin/sh\necho v2\n", encoding="utf-8")
        os.chmod(script, 0o755)
        (repo / "renamed.txt").unlink()
        (repo / "vanished.txt").write_text("a sibling pushed this\n", encoding="utf-8")
        _run("add", "-A", repo=repo)
        _run("commit", "-qm", "v2", repo=repo)
        tip = git("rev-parse", "HEAD", repo=repo).strip()

        # now put the tree back into the state a commit-tree push leaves it in:
        #   stale.txt  — untouched by any lane, still v1        → RESTORE
        #   tool.sh    — the same, and it is 100755             → RESTORE, mode kept
        #   live.txt   — a lane is mid-edit on it               → LEAVE
        #   renamed.txt— a leftover the tip does not have, but
        #                the repo DID hold this content         → REMOVE
        #   brand_new.txt — untracked, never committed          → LEAVE
        (repo / "stale.txt").write_text("v1\n", encoding="utf-8")
        script.write_text("#!/bin/sh\necho v1\n", encoding="utf-8")
        os.chmod(script, 0o644)  # the bit is dropped, as a shell redirect would
        (repo / "live.txt").write_text("a lane is writing this right now\n", encoding="utf-8")
        (repo / "renamed.txt").write_text("v1\n", encoding="utf-8")
        (repo / "brand_new.txt").write_text("nobody has ever committed this\n", encoding="utf-8")
        # vanished.txt — at the tip, ABSENT from the tree: a lane pushed it while
        #                this tree stood still. Nothing on disk to protect. → RE-CREATE
        (repo / "vanished.txt").unlink(missing_ok=True)

        report = sync(tip, repo=repo, depth=50)

        if "stale.txt" not in report["restored"]:
            failures.append("a STALE file was not restored")
        if (repo / "stale.txt").read_text(encoding="utf-8") != "v2 from the tip\n":
            failures.append("stale.txt holds the wrong bytes after the restore")
        if "live.txt" in report["restored"]:
            failures.append("a LIVE edit was overwritten — the content test did not protect it")
        if (repo / "live.txt").read_text(encoding="utf-8") != "a lane is writing this right now\n":
            failures.append("live.txt lost a lane's in-flight work")
        if "tool.sh" not in report["restored"]:
            failures.append("the executable was not restored")
        if not os.access(repo / "tool.sh", os.X_OK):
            failures.append("the 100755 bit was NOT restored — clause 1 does not hold")
        if "renamed.txt" not in report["removed"]:
            failures.append("a leftover the repo already held was not removed — clause 3 does not hold")
        if (repo / "renamed.txt").exists():
            failures.append("renamed.txt is still on disk after being reported removed")
        if "brand_new.txt" in report["removed"]:
            failures.append("an untracked file nobody ever committed was DELETED — unacceptable")
        if not (repo / "brand_new.txt").exists():
            failures.append("brand_new.txt was destroyed")
        if "vanished.txt" not in report["recreated"]:
            failures.append("a file ABSENT from the tree and present at the tip was not re-created — the write half is incomplete")
        if not (repo / "vanished.txt").exists():
            failures.append("vanished.txt is still missing after the sync")

        # clause 4 — after the run, the paths it moved must not differ from the tip
        remaining = set(paths_differing(tip, repo=repo))
        if "stale.txt" in remaining or "tool.sh" in remaining:
            failures.append("a restored path still differs from the tip — subtraction check fails")

        # and a dry run must move nothing
        (repo / "stale.txt").write_text("v1\n", encoding="utf-8")
        sync(tip, repo=repo, depth=50, dry_run=True)
        if (repo / "stale.txt").read_text(encoding="utf-8") != "v1\n":
            failures.append("--dry-run wrote to the tree")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move the STALE half of this working tree to a pinned tip. Files only.",
        epilog="It does not touch the index and does not move HEAD; git status cannot see what it fixes.",
    )
    parser.add_argument("tip", nargs="?", help="the tip to sync to, e.g. origin/<branch> or a SHA")
    parser.add_argument("--dry-run", action="store_true", help="report and write nothing")
    parser.add_argument(
        "--depth", type=int, default=200, help="how far back to walk each path's history (default 200)"
    )
    parser.add_argument("--selftest", action="store_true", help="prove the four cases and exit")
    args = parser.parse_args()

    if args.selftest:
        failures = selftest()
        for line in failures:
            print(f"SELFTEST FAIL: {line}")
        print("selftest: 4/4 cases bite" if not failures else f"selftest: {len(failures)} case(s) FAILED")
        return 1 if failures else 0

    if not args.tip:
        parser.error("a tip is required (or --selftest)")
    if shutil.which("git") is None:
        print("git is not on PATH", file=sys.stderr)
        return 2

    repo_root = Path(git("rev-parse", "--show-toplevel", repo=Path.cwd()).strip())
    failures = selftest()
    if failures:
        # A tool whose own sabotage does not bite has a worthless verdict, and
        # this one MOVES FILES. It refuses to run rather than report success.
        for line in failures:
            print(f"SELFTEST FAIL: {line}", file=sys.stderr)
        print("refusing to touch the tree: this tool's own self-test does not hold", file=sys.stderr)
        return 1

    report = sync(args.tip, repo=repo_root, depth=args.depth, dry_run=args.dry_run)
    for path in report["restored"]:
        print(f"restored  {path}")
    for path in report["recreated"]:
        # its own line, never folded into "restored": this is the one action
        # that can undo a lane's deliberate, unpushed deletion, so it is the one
        # a reader must see.
        print(f"re-created {path} — was ABSENT from the tree")
    for path in report["removed"]:
        print(f"removed   {path}")
    for line in report["left"]:
        print(f"LEFT      {line}")
    for line in report["failed"]:
        # ⚠ LOUD, ON stderr, AND IT CHANGES THE EXIT CODE. A path this tool
        # could not write is a path still holding pre-tip content, which is the
        # loaded revert law 12 describes. Printing it quietly would reproduce
        # `DEF-GOV-5208` one layer up.
        print(f"FAILED    {line}", file=sys.stderr)

    touched = len(report["restored"]) + len(report["removed"])
    if not touched and not report["left"] and not report["failed"]:
        print(f"\nnothing differed from {args.tip} — the tree is already in sync")
        return 0
    if report["failed"]:
        print(
            f"\n⚠ {len(report['failed'])} path(s) COULD NOT BE SYNCED and are still stale.\n"
            f"  The push itself is unaffected. Re-run this tool after fixing the cause;\n"
            f"  until then treat those paths as holding pre-tip content (law 12).",
            file=sys.stderr,
        )
        return 1
    print(
        f"\n{len(report['restored'])} restored · {len(report['removed'])} removed · "
        f"{len(report['left'])} LEFT for their owner (history walked {args.depth} deep)"
    )
    if report["left"]:
        print("  ⚠ a LEFT path is not a pass: it is a file this tool could not prove safe to move.")
    if args.dry_run:
        print("  (--dry-run: nothing was written)")
    else:
        print(f"  now verify by subtraction: git diff --numstat {args.tip}")
        print("  and move HEAD yourself — this tool does not, deliberately.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
