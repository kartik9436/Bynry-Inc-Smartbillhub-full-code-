#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2837 (2026-08-31) — a lane's own push helper REVERTED a sibling's
#          decision-log ruling BY SUBTRACTION: 43 lines, gone from a file that
#          lane had only appended to. Every other law-11 check passed on it, and
#          one of them is the check that caused it.
#          DEF-1706 / DEF-1782 (2026-08-27) — the same subtraction, twice in one
#          day: 44 locale keys, and a defect row appended four minutes earlier.
#          DEF-GOV-3745 (2026-09-04) — this guard read the SHARED tree while
#          `push_paths.sh` hashed the caller's WORKTREE, so it answered about a
#          file nobody was pushing. See `_repo()`.
# Rules:   CLAUDE.md law 11 — "read `git diff --numstat` AS ARITHMETIC, not as a
#          glance" and "make your push helper REFUSE"
# Impacts: 10-scripts/push_paths.sh
# ───────────────────────────────────────────────────────
"""NO LINE MAY VANISH FROM A SHARED REGISTER. Run BEFORE the push, not after.

WHY THIS EXISTS AND WHY THE EXISTING CHECKS DO NOT COVER IT
------------------------------------------------------------
`push_paths.sh` already refuses when a NAMED PATH MOVED between your base and
the live tip, which closes DEF-2837's mechanism: you cannot build a blob against
one tip and commit it against another. **It does not close the damage.** A blob
can be stale for reasons that have nothing to do with the tip moving — you read
the file, worked for twenty minutes, and wrote back a whole-file copy of what you
read (DEF-1706). Or your editor rewrote a region. Or a script truncated its
destination before it had the bytes to put in it.

The result is a revert BY SUBTRACTION, and law 11 is emphatic that every check in
it passes on that: the file count is right, your own change IS present,
`git show <commit>` shows only your hunks — because the deleted work is not in
the diff at all, it is missing from the tree the diff is taken against.

Law 11's answer is *"read `git diff --numstat` AS ARITHMETIC"*. That is a human
reading a number after the damage is pushed. **This is the same reading, done by
a machine, before it.**

WHAT IT ASKS
------------
For each named path that is a shared append-only register: **is every line of
the tip's version still present in the version about to be pushed?**

A line may legitimately leave in exactly one shape, and only in a CSV register:
an IN-PLACE ROW REWRITE, which is what `close_defect.py` does — the row's first
field (its id) is still there, on a line whose bytes have changed. That is
recognised and allowed, and it is why the check is per-ID and not per-line for
CSV files.

Anything else — a row that is simply gone, a markdown section that vanished —
REFUSES, prints the lines, and the push does not happen.

WHY A LIST OF PATHS AND NOT EVERY FILE
--------------------------------------
Ordinary source files lose lines all day; that is what editing is. These files
do not: they are the shared record, six lanes append to them, and a line leaving
one is nearly always somebody else's work disappearing. Keeping the list short
is what keeps the refusal meaningful rather than something lanes learn to
override.

THE ESCAPE HATCH IS DELIBERATE AND LOUD
---------------------------------------
`ALLOW_REGISTER_DELETIONS=1` disables the refusal. It exists because a genuine
deletion happens — a duplicate id being removed, a row merged — and a guard with
no way past it gets deleted instead of used. It must be typed, per push, and it
prints what it let through.

    python3 10-scripts/push_register_guard.py <tip-sha> <path>...
    python3 10-scripts/push_register_guard.py --selftest
    exit 0  — nothing vanished (or no named path is a register)
    exit 4  — a line vanished; the push must not proceed
"""
import os
import re
import subprocess
import sys
from pathlib import Path


def _repo() -> Path:
    """The tree whose files are about to be pushed — the CALLER'S, not this
    script's.

    ⚠ **THIS WAS `Path(__file__).resolve().parent.parent` UNTIL `DEF-GOV-3745`
    (2026-09-04), AND THAT IS THE WRONG TREE WHENEVER A LANE FOLLOWS LAW 12.**
    CLAUDE.md law 12 says in as many words *"dispatch every lane into its own
    `git worktree`"* — and a lane that does, then runs the SHARED tree's copy of
    `push_paths.sh`, had this guard compare the pinned tip against the SHARED
    tree's registers while `push_paths.sh` hashed the WORKTREE's. Two different
    files, one verdict.

    **It refused a correct push on 2026-09-04** — the shared tree was one commit
    behind, so three lines a sibling had just added looked "vanished". **The
    mirror is the dangerous one and it is silent:** a genuine subtraction in the
    worktree PASSES whenever the shared tree still happens to hold the line, and
    the whole point of this guard is that nothing downstream would notice.

    `git rev-parse --show-toplevel` answers with the caller's worktree root, and
    falls back to this file's parent when git cannot answer at all.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=True,
        ).stdout.decode().strip()
        if out:
            return Path(out)
    except (subprocess.CalledProcessError, OSError):  # pragma: no cover — no git
        pass
    return Path(__file__).resolve().parent.parent


REPO = _repo()

#: The shared append-only record. Six lanes write these; a line leaving one is
#: almost always another lane's work being reverted by subtraction.
REGISTERS = {
    "12-governance/10-defect-log.csv",
    "12-governance/02-decision-log.md",
    "12-governance/01-open-questions.md",
    "12-governance/09-human-review-ledger.md",
    "12-governance/11-change-requests.md",
    "12-governance/14-id-reservations.md",
    "CHANGELOG.md",
}

#: For a CSV register a row may be REWRITTEN in place (close_defect.py changes
#: one row's status). The id is the first field and it must survive.
CSV_REGISTERS = {"12-governance/10-defect-log.csv"}

#: A MARKDOWN TABLE register whose rows open with `| <ID> |`. It gets the SAME
#: per-ID allowance as a CSV register, for the identical reason.
#:
#: ⚠ **ADDED 2026-09-18 (`DEF-GOV-5737`), AND IT IS A FALSE ALARM BEING REMOVED
#: RATHER THAN A RULE BEING RELAXED.** Closing an open question REWRITES its row
#: in place — CLAUDE.md requires the fan-out to move the row's STATUS *and* its
#: BODY, because a body left describing the open world is what a lane actually
#: reads (`DEF-WRK-4030`). Under whole-line comparison that rewrite reads as a
#: vanished line every single time, and the refusal ends by offering
#: `ALLOW_REGISTER_DELETIONS=1`.
#:
#: **That is the precise failure this file's own `_csv_id` docstring describes
#: one register over (`DEF-GOV-4029`):** *"a lane that meets a false alarm EVERY
#: time it closes a defect learns to set that variable by reflex — at which
#: point the real protection is gone on the one push that needed it."*
#: `DEF-3233` already records the prediction coming true. A standing false alarm
#: does not make a guard stricter; it trains lanes to switch it off.
#:
#: **THE ALLOWANCE IS NARROW AND A REAL DELETION STILL REFUSES:** the id must
#: still appear on some row of the new file. A row that is simply GONE takes its
#: id with it and is reported exactly as before — which is what the sabotage in
#: `--selftest` proves, because an allowance nobody has watched refuse is not a
#: guard (hard-won law 7).
ROW_ID_REGISTERS = {"12-governance/01-open-questions.md"}

#: `| OQ-RAT-12410 | …` — the id in the FIRST CELL of a markdown table row.
#:
#: ⚠ **WHAT STOPS `OQ-123456` READING AS `OQ-12345` HERE IS THE TRAILING
#: `\s*\|` ANCHOR, NOT THE LOOKAHEAD — MEASURED, NOT ASSUMED.** This comment
#: said the lookahead was load-bearing until the sabotage was actually run:
#: removing `(?!\d)` and re-running `--selftest` still returns `None` for a
#: six-digit id, because the cell must END after the id and `6` is neither a
#: backtick, a space nor a pipe. The lookahead is kept — it is CLAUDE.md's house
#: pattern (`DEF-2804`) and it costs nothing — but it is belt to the anchor's
#: braces, and the selftest probe asserts the PROPERTY (no silent truncation)
#: rather than crediting either mechanism.
MD_ROW_ID_RE = re.compile(r"^\|\s*`?(OQ-(?:[A-Z]{3}-)?\d{3,5})(?!\d)`?\s*\|")


def _md_row_id(line: str) -> str | None:
    """The id in a markdown table row's first cell, or `None`.

    `None` means WHOLE-LINE comparison, which is the stricter treatment and the
    right default: a prose line, a heading, a separator or a continuation is not
    a row and must not be allowed to disappear because some row elsewhere still
    carries its id.
    """
    m = MD_ROW_ID_RE.match(line)
    return m.group(1) if m else None


def _tip_bytes(tip: str, path: str) -> bytes | None:
    proc = subprocess.run(
        ["git", "show", f"{tip}:{path}"],
        capture_output=True,
        cwd=REPO,
        check=False,
    )
    return proc.stdout if proc.returncode == 0 else None


#: A row id at the start of a line, QUOTED OR NOT — the same pattern
#: `close_defect.py` matches with, and for the same reason.
CSV_ID_RE = re.compile(r'^"?(DEF-(?:[A-Z]{3}-)?\d+)"?,')


def _csv_id(line: str) -> str | None:
    """The row id — the first field — without parsing the whole row.

    ⚠ **THIS USED TO REQUIRE A LEADING QUOTE AND ITS DOCSTRING SAID SO:**
    *"these rows are QUOTE_ALL, so the id is between the first two quotes."*
    **That was true of 112 of the register's 1,857 lines** (`DEF-GOV-4029`).
    The other ~1,745 are written unquoted — `file_defect.py` appends through a
    writer that quotes only what needs it — so `_csv_id` returned `None` for
    almost every row and they fell back to WHOLE-LINE comparison.

    **What that cost is the guard's entire point.** The per-ID allowance exists
    so an IN-PLACE ROW REWRITE — exactly what `close_defect.py` does when it
    marks a row fixed — is not mistaken for a deletion. With the id invisible,
    every `close_defect.py` edit of an unquoted row REFUSED the push, naming a
    row that had not gone anywhere: `close_defect.py` re-serialises with
    QUOTE_ALL, so the old unquoted line "vanishes" and a quoted one appears.

    ⚠ **IT FAILED SAFE AND THAT IS WHY IT IS DANGEROUS.** A false refusal loses
    nothing, so nothing ever went red; but the refusal message ends by offering
    `ALLOW_REGISTER_DELETIONS=1`, and a lane that meets a false alarm EVERY time
    it closes a defect learns to set that variable by reflex — at which point
    the real protection is gone on the one push that needed it. Hard-won law 1:
    the docstring claimed a guarantee the data did not support, and it was
    believed because it was specific.

    A line that is not a row at all — a blank, the header, a continuation of a
    field containing a newline — still returns `None` and is compared whole,
    which is the stricter treatment and the right default.
    """
    m = CSV_ID_RE.match(line)
    return m.group(1) if m else None


def vanished(tip: str, path: str) -> list[str]:
    """Lines present in the tip's version and absent from the working copy."""
    before = _tip_bytes(tip, path)
    if before is None:
        return []  # a brand-new file cannot have lost anything
    after_file = REPO / path
    if not after_file.exists():
        return [f"THE WHOLE FILE IS GONE ({len(before.splitlines())} lines)"]
    after = after_file.read_bytes()

    old_lines = before.decode("utf-8", "replace").splitlines()
    new_lines = after.decode("utf-8", "replace").splitlines()
    new_set = set(new_lines)

    id_of = None
    if path in CSV_REGISTERS:
        id_of = _csv_id
    elif path in ROW_ID_REGISTERS:
        id_of = _md_row_id
    return lost_lines(old_lines, new_lines, id_of)


def gained_duplicates(tip: str, path: str) -> list[str]:
    """Ids that appear MORE times in the version about to be pushed than at the tip.

    ⚠ **THIS IS `DEF-GOV-7650`'s DURABLE HALF, AND IT EXISTS BECAUSE THE
    VANISHED-LINE CHECK ABOVE IS STRUCTURALLY BLIND TO IT.** `lost_lines`
    forgives a line whose id still appears SOMEWHERE in the new file — that is
    the per-ID allowance an in-place `close_defect.py` rewrite needs. The same
    allowance means a row APPENDED a second time under an id that already
    exists is not a lost line, is not a moved path, and is not a ragged row, so
    **every check this repo owns passes over it.** On 2026-09-27 that is exactly
    what happened: `DEF-GOV-6930` and `DEF-RAT-6960` each landed twice, one copy
    reading `fixed` with a version and the other `open` with nothing.
    `defect_report.py` then counted each defect twice and a reader could not
    tell which status was true.

    **What it cost is a guard, not a row.** `merge_register.py` is the ONE tool
    that refuses two lanes taking the same id, and it checks the WHOLE resolved
    file — so a duplicate already sitting in the register makes it refuse every
    register merge on that branch, for everybody, days after the fact. A safety
    tool that always refuses is a safety tool nobody uses (hard-won law 7: a
    guard is a claim only while somebody reads its output). The register row's
    own prevention names this file as where the check belongs, because this is
    the one thing that reads the register on every push.

    **IT IS A RATCHET AND NOT A BAN, DELIBERATELY.** It compares against the
    TIP's counts and reports only ids that got WORSE. A duplicate already on the
    branch therefore blocks nobody — it is somebody else's row to repair — while
    a push that CREATES one is refused and named. A flat ban would refuse all
    six lanes over a row none of them wrote, and `_csv_id`'s own docstring
    already records where that leads: a standing false alarm trains lanes to set
    `ALLOW_REGISTER_DELETIONS=1` by reflex, and the real protection is then gone
    on the push that needed it.

    Removing a duplicate is the intended repair and passes silently, because the
    count falls. That is the direction this check wants to be easy.
    """
    before = _tip_bytes(tip, path)
    after_file = REPO / path
    if before is None or not after_file.exists():
        return []
    id_of = _csv_id if path in CSV_REGISTERS else _md_row_id if path in ROW_ID_REGISTERS else None
    if id_of is None:
        return []  # no id extractor for this register: nothing can be counted
    return worsened_ids(
        before.decode("utf-8", "replace").splitlines(),
        after_file.read_bytes().decode("utf-8", "replace").splitlines(),
        id_of,
    )


def worsened_ids(old_lines: list[str], new_lines: list[str], id_of) -> list[str]:
    """The comparison itself, with no git and no filesystem in it — so
    `--selftest` exercises the real code rather than a paraphrase of it, which
    is the split `lost_lines` already got on 2026-09-18 and for the same reason.
    """

    def counts(lines: list[str]) -> dict[str, int]:
        tally: dict[str, int] = {}
        for line in lines:
            ident = id_of(line)
            if ident:
                tally[ident] = tally.get(ident, 0) + 1
        return tally

    was = counts(old_lines)
    now = counts(new_lines)
    return [
        f"{ident} appears {count}× (was {was.get(ident, 0)}× at the tip)"
        for ident, count in sorted(now.items())
        if count > 1 and count > was.get(ident, 0)
    ]


def lost_lines(
    old_lines: list[str],
    new_lines: list[str],
    id_of=None,
) -> list[str]:
    """The comparison itself, with no git and no filesystem in it.

    Split out from `vanished()` on 2026-09-18 so `--selftest` can exercise the
    real code rather than a paraphrase of it. Behaviour is unchanged: the two
    branches below are the two that were inline here before.
    """
    if id_of is not None:
        new_set = set(new_lines)
        new_ids = {i for i in (id_of(line) for line in new_lines) if i}
        lost = []
        for line in old_lines:
            if line in new_set:
                continue
            ident = id_of(line)
            if ident and ident in new_ids:
                continue  # rewritten in place — the row is still there
            lost.append(line)
        return lost

    # Markdown and text registers: multiset, so a repeated line deleted once is
    # still caught. Blank lines are ignored — they carry no record.
    lost = []
    remaining = list(new_lines)
    for line in old_lines:
        if not line.strip():
            continue
        if line in remaining:
            remaining.remove(line)
        else:
            lost.append(line)
    return lost


def selftest() -> int:
    """PROVE THE ALLOWANCE BITES, not merely that it lets the good case past.

    Hard-won law 7: a guard is only trusted green once it has been watched go
    RED on the thing it was written for. The per-ID allowance added for
    `DEF-GOV-5737` is exactly the kind of change that can quietly turn a guard
    off, so the deletions it must STILL refuse are asserted here and not in a
    shell somebody ran once.
    """
    csv_old = ['"DEF-RAT-5733","2026-09-18","x","open",', '"DEF-RAT-5734","2026-09-18","y","open",']
    md_old = [
        "| OQ-RAT-12410 | body as it was | product | refs | where | **OPEN** |",
        "| OQ-RAT-12409 | another row | product | refs | where | **OPEN** |",
        "**The single home for every unresolved decision.**",
    ]
    cases = [
        # (name, old, new, id_of, expected number of lost lines)
        ("csv · row rewritten in place is ALLOWED",
         csv_old, ['"DEF-RAT-5733","2026-09-18","x","fixed","abc"', csv_old[1]], _csv_id, 0),
        ("csv · row REMOVED still refuses",
         csv_old, [csv_old[1]], _csv_id, 1),
        ("md · row rewritten in place is ALLOWED",
         md_old,
         ["| OQ-RAT-12410 | body REWRITTEN | product | refs | where | **CLOSED** |"] + md_old[1:],
         _md_row_id, 0),
        ("md · row REMOVED still refuses",
         md_old, md_old[1:], _md_row_id, 1),
        ("md · PROSE line removed still refuses (it carries no id)",
         md_old, md_old[:2], _md_row_id, 1),
        ("md · a register with NO row ids compares whole-line",
         md_old, md_old[1:], None, 1),
    ]
    bad = 0
    for name, old, new, id_of, expected in cases:
        got = len(lost_lines(old, new, id_of))
        ok = got == expected
        bad += 0 if ok else 1
        print(f"  {'ok  ' if ok else 'FAIL'} {name} (lost={got}, expected={expected})")

    # NO SILENT TRUNCATION of a longer id — the property, whichever part of the
    # pattern enforces it. `DEF-2804`: `OQ-\d{3}` did not SKIP `OQ-1190`, it
    # returned `OQ-119`, a different real question, and nothing raised.
    probes = [
        ("| OQ-RAT-12410 | x |", "OQ-RAT-12410"),
        ("| OQ-291 | x |", "OQ-291"),
        ("| OQ-123456 | x |", None),        # must NOT read as OQ-12345
        ("**prose, not a row**", None),
        ("|---|---|", None),
    ]
    for line, expected in probes:
        got = _md_row_id(line)
        ok = got == expected
        bad += 0 if ok else 1
        print(f"  {'ok  ' if ok else 'FAIL'} id of {line[:28]!r} -> {got!r} (expected {expected!r})")

    # ── DEF-GOV-7650 · THE DUPLICATE RATCHET, WATCHED REFUSING ────────────
    # Law 7: the case this was written for is the FIRST one asserted here, and
    # it is the real register's own shape — a row appended a second time with
    # its status changed, which `lost_lines` forgives by design.
    dup_cases = [
        ("dup · the SAME id appended a second time REFUSES",
         csv_old,
         csv_old + ['"DEF-RAT-5733","2026-09-18","x","fixed","abc"'],
         _csv_id, 1),
        ("dup · an ordinary new row is fine",
         csv_old,
         csv_old + ['"DEF-RAT-5735","2026-09-18","z","open",'],
         _csv_id, 0),
        ("dup · an in-place rewrite is fine (the count does not move)",
         csv_old,
         ['"DEF-RAT-5733","2026-09-18","x","fixed","abc"', csv_old[1]],
         _csv_id, 0),
        ("dup · REMOVING a duplicate is the repair and passes",
         csv_old + [csv_old[0]], csv_old, _csv_id, 0),
        ("dup · a duplicate ALREADY at the tip blocks nobody (ratchet)",
         csv_old + [csv_old[0]], csv_old + [csv_old[0]], _csv_id, 0),
        ("dup · a THIRD copy of an already-duplicated id REFUSES",
         csv_old + [csv_old[0]], csv_old + [csv_old[0], csv_old[0]], _csv_id, 1),
        ("dup · markdown rows count the same way",
         md_old,
         md_old + ["| OQ-RAT-12410 | a second copy | product | refs | where | **OPEN** |"],
         _md_row_id, 1),
    ]
    for name, old, new, id_of, expected in dup_cases:
        got = len(worsened_ids(old, new, id_of))
        ok = got == expected
        bad += 0 if ok else 1
        print(f"  {'ok  ' if ok else 'FAIL'} {name} (gained={got}, expected={expected})")

    print("selftest: PASS" if bad == 0 else f"selftest: {bad} FAILURE(S)")
    return 0 if bad == 0 else 1


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "--selftest":
        return selftest()
    if len(argv) < 3:
        print("usage: push_register_guard.py <tip-sha> <path>...", file=sys.stderr)
        print("       push_register_guard.py --selftest", file=sys.stderr)
        return 2
    tip, paths = argv[1], argv[2:]
    named = [p for p in paths if p in REGISTERS]
    if not named:
        return 0

    allow = os.environ.get("ALLOW_REGISTER_DELETIONS") == "1"
    failed = False
    failed_on_deletion = False

    # ── THE OTHER DIRECTION: AN ID THAT NOW APPEARS TWICE (DEF-GOV-7650) ──
    # Deliberately NOT under ALLOW_REGISTER_DELETIONS: that variable says "this
    # deletion is intended", which is no answer at all to "you have just filed
    # the same id twice". A duplicate is never intended, so there is nothing to
    # allow — renumber with `allocate.py defect --verify` and push again.
    for path in named:
        gained = gained_duplicates(tip, path)
        if not gained:
            print(f"register guard: {path} — no id gained a duplicate")
            continue
        print(
            f"REFUSED: {len(gained)} id(s) appear MORE times in {path} than at "
            f"{tip[:8]}. A duplicate id disables merge_register.py for EVERY lane on "
            f"this branch — it refuses any register merge while one exists — and "
            f"defect_report.py counts the row twice (DEF-GOV-7650).",
            file=sys.stderr,
        )
        for line in gained[:6]:
            print(f"    ! {line}", file=sys.stderr)
        if len(gained) > 6:
            print(f"    … and {len(gained) - 6} more", file=sys.stderr)
        print(
            "    Re-read the register from the pinned tip, re-allocate with "
            "`10-scripts/allocate.py defect --verify <N>`, and push again.",
            file=sys.stderr,
        )
        failed = True

    for path in named:
        lost = vanished(tip, path)
        if not lost:
            print(f"register guard: {path} — nothing vanished ({len(lost)} lines lost)")
            continue
        head = "ALLOWED" if allow else "REFUSED"
        print(
            f"{head}: {len(lost)} line(s) present in {tip[:8]}:{path} are ABSENT from the "
            f"version about to be pushed. That is a revert BY SUBTRACTION (DEF-2837) and "
            f"every other law-11 check passes on it — the file count is right, your own "
            f"change is present, and the lost work is not in the diff at all.",
            file=sys.stderr,
        )
        for line in lost[:6]:
            print(f"    - {line[:160]}", file=sys.stderr)
        if len(lost) > 6:
            print(f"    … and {len(lost) - 6} more", file=sys.stderr)
        if not allow:
            failed = True
            failed_on_deletion = True

    # ⚠ THE CLOSING ADVICE IS PRINTED ONLY FOR THE FAILURE IT ANSWERS. Offering
    # `ALLOW_REGISTER_DELETIONS=1` under a DUPLICATE refusal would be the exact
    # reflex `_csv_id`'s docstring warns about — a lane sets the variable, the
    # duplicate sails through anyway (the variable does not gate it) and the
    # deletion protection is switched off for nothing.
    if failed_on_deletion:
        print(
            "\nRe-derive the file from the pinned tip and re-apply YOUR OWN edits to THAT "
            "(law 11: `git show \"$TIP\":<path>` into a temp file, edit that, hash that — "
            "never a working copy you read earlier). If the deletion is genuinely intended, "
            "say so out loud: ALLOW_REGISTER_DELETIONS=1.",
            file=sys.stderr,
        )
    if failed:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
