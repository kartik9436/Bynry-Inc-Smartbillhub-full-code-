#!/usr/bin/env python3
"""Change the STATUS of ONE row in the defect register, one line at a time.

WHY THIS EXISTS
---------------
`file_defect.py` is the append-only door: it opens the register in append mode
and writes ONE line, so no existing byte is read into memory to be written back.
That is the whole of its safety, and it is why it deliberately refuses to edit a
row.

But rows have to be closed. On 2026-08-19 a lane fixed six defects
(DEF-308…313), could not close them, and said so in its own handover: closing
six single fields in a 310-row register that six lanes write is *a separate,
riskier operation*. It is. The risk is not hypothetical and it is not about
carelessness:

    >>> rows = list(csv.reader(open(register)))
    >>> rows[N][11] = "fixed"
    >>> csv.writer(open(register, "w")).writerows(rows)

Those three lines are the obvious way to do it and they RE-SERIALISE ALL 317
ROWS. Python's csv writer makes its own choices about quoting and line endings,
so every row it touches can change on disk even when its content did not. The
result is a 317-line diff for a one-word edit, and inside that diff:

  * every other lane's in-flight row is now part of YOUR commit (DEF-168 — a
    pathspec commit takes the whole file, so it PUBLISHES as well as reverts);
  * a stale copy silently reverts rows another lane already pushed (DEF-165);
  * and nobody reads 317 hunks, so law 11's "read the hunks" check — the one
    that is supposed to catch exactly this — cannot be performed at all.

So this tool never re-serialises the file. It finds the one line, rewrites that
line's bytes, and splices it back between two byte slices it never parsed.

WHAT THIS GUARANTEES
--------------------
1. **Exactly one line changes.** The bytes before the target line and the bytes
   after it are copied verbatim, never decoded, never re-quoted. `git diff`
   shows `1 insertion(+), 1 deletion(-)` — a hunk a human can actually read.
2. **The target line is parsed and re-serialised on its own**, with QUOTE_ALL
   and the register's own `\n` terminator, so it comes back in the same shape
   the other 316 lines are already in.
3. **The vocabulary is the shared vocabulary, and the WRITE half of it.**
   `10-scripts/register_vocabulary.py` holds the register's controlled columns in
   ONE place, split in two: `STATUS_ACCEPTED_ON_READ` is the nine values G30 and
   G46 tolerate on the 1,872 rows that already exist, and `STATUS_WRITABLE` is
   the six a tool may write. This tool writes, so it uses the six. A tool and its
   checker disagreeing is how the register got prose in a status column in the
   first place; a tool and its checker being the SAME set is how the register
   stays stuck with nine values for ever.

   ⚠ **THIS NARROWED ON 2026-09-05 AND THAT IS DELIBERATE.**
   `12-governance/15-defect-register-truth.md` §7 measured nine status values
   where six would do — `fixed-in-part` and `partially-fixed` are one state
   spelled twice, `reported` means `open`, and `closed` says less than the three
   values that already exist for retiring a row. Its recommendation is a ratchet
   and it names the sequence: *"stop the tools emitting the losing spellings, let
   the 37 affected rows be corrected as they are touched for other reasons, and
   drop the retired values from the gate's vocabulary only when the count reaches
   zero."* Refusing them HERE is the first of those three steps. **Nothing is
   rewritten** — a mass edit of a file ten lanes append to is the operation this
   repo has lost work to more than once.
4. **A closing status must carry its commit.** G26 already fails a `fixed` row
   with an empty `fixed_commit`, against a baseline of 56 grandfathered rows
   that may only ever fall. Refusing here keeps that number falling.
5. **It re-reads the file afterwards and proves the edit**, because the lesson
   of DEF-300 is that a tool tested only with `--dry-run` never exercises the
   write-then-read round trip and cannot see its own output.

WHAT IT DELIBERATELY WILL NOT DO
--------------------------------
Touch more than one row per invocation, edit any column other than `status` and
`fixed_commit`, or commit anything. Committing is the caller's job and it is
still governed by law 11: build tip-plus-your-hunk through a private index.

USAGE
    python3 10-scripts/close_defect.py --id DEF-311 --status fixed \
        --fixed-commit "CR-016 2.25.1 d4218d6"
    python3 10-scripts/close_defect.py --id DEF-311 --status wontfix \
        --fixed-commit "" --allow-empty-commit --dry-run
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REGISTER = REPO / "12-governance" / "10-defect-log.csv"

sys.path.insert(0, str(REPO / "10-scripts"))
sys.path.insert(0, str(REPO / "10-scripts" / "gates"))
try:
    from register_vocabulary import STATUS_WRITABLE, explain_status
except Exception as exc:  # pragma: no cover - the import IS the contract
    sys.exit(f"cannot read the status vocabulary from register_vocabulary.py: {exc}")

# A closing status is one that asserts the work is over. Those must say WHERE.
# `partially-fixed` / `fixed-in-part` are deliberately NOT here: they describe a
# row that is still live, and demanding a commit for one would push lanes back
# to leaving it `open`.
CLOSING_STATUSES = {"fixed", "closed"}

# ⚠ THE LEADING QUOTE IS NOT OPTIONAL DECORATION — DEF-300. The register holds
# both `"DEF-12",…` and `DEF-12,…`; a regex that assumes one shape cannot see
# rows written in the other, which is how file_defect.py once failed to read
# its own output and allocated the same id three times.
# ⚠ TWO GROUPS, AND BOTH ARE LOAD-BEARING (DEF-3616). Group 1 is the WHOLE id —
# `DEF-3571` or `DEF-WRK-3571` — and group 2 is the bare number. The first
# widening of this pattern (2026-09-03, DEF-3552) taught it to FIND a
# module-tagged row and left the comparison below rebuilding `DEF-{number}`, so
# `--id DEF-WRK-3571` matched nothing while `--id DEF-3571` silently edited that
# very row. A matcher that finds the right line and then compares the wrong
# string is the shape this repo calls a check that cannot fail.
# ⚠ **`{2,4}` AND NOT `{3}` — THE THREE-LETTER ASSUMPTION MADE EXACTLY ONE ROW
# OF THE REGISTER UNCLOSEABLE, AND IT ANNOUNCED THAT AS AN ABSENCE
# (2026-09-08).** `DEF-FE-4058` was filed before `file_defect.py` began
# enforcing three capitals, so it carries a TWO-letter module code. Asked to
# close it, this tool matched nothing, fell through to the "near" branch —
# which reads the SAME pattern, so it found nothing either — and printed
# *"DEF-FE-4058 is not in 12-governance/10-defect-log.csv — nothing to close"*
# over a row sitting in the file. **A matcher that cannot see a row and
# reports that the row does not exist is `DEF-2804`'s shape** (`OQ-\d{3}`
# silently returning a different, real question), and it is worse than a
# refusal: it sends the caller to hand-edit a 2,292-row register, which is
# the operation this whole file exists to prevent.
# The register holds 728 module-tagged rows; 727 are three capitals and one
# is two. The class is widened rather than the row renamed, because
# renumbering an id that is already cited in the decision log, the G112 park
# file and a gate docstring is the mass shared-file rewrite law 11 exists to
# prevent. `file_defect.py` still WRITES three; this only READS what is there.
ID_RE = re.compile(r'^"?(DEF-(?:[A-Z]{2,4}-)?(\d+))"?,')


def _find_line(lines: list[bytes], want: str) -> int:
    """Index of the ONE line whose id is `want`. Duplicates are a hard error —
    G26 already refuses them, and editing one of two rows with the same id
    would leave the register disagreeing with itself."""
    hits = [
        i
        for i, raw in enumerate(lines)
        if (m := ID_RE.match(raw.decode("utf-8", "replace"))) and m.group(1) == want
    ]
    if not hits:
        # A number that exists under a DIFFERENT spelling is the likeliest
        # mistake now that ids carry a module (PO ruling 2026-09-03), so name
        # the id that IS there rather than reporting a bare absence. Closing
        # `DEF-WRK-3571` by typing `DEF-3571` would edit a row the caller did
        # not name, which is worse than refusing.
        number = want.rsplit("-", 1)[-1]
        near = [
            m.group(1)
            for raw in lines
            if (m := ID_RE.match(raw.decode("utf-8", "replace"))) and m.group(2) == number
        ]
        if near:
            sys.exit(
                f"{want} is not in {REGISTER.relative_to(REPO)}, but {', '.join(near)} is — "
                "ids carry their module since 2026-09-03. Pass the id exactly as the register spells it."
            )
        sys.exit(f"{want} is not in {REGISTER.relative_to(REPO)} — nothing to close")
    if len(hits) > 1:
        sys.exit(
            f"{want} appears on {len(hits)} lines ({', '.join(str(h + 1) for h in hits)}). "
            "That is a duplicate-id defect in its own right (G26 refuses it); fix the "
            "register before closing the row."
        )
    return hits[0]


def _serialise(cells: list[str]) -> bytes:
    """One row, on its own, in the shape the other 316 rows are already in."""
    buf = io.StringIO()
    csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\n").writerow(cells)
    return buf.getvalue().encode("utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", required=True, help="the row to change, e.g. DEF-311")
    ap.add_argument("--status", required=True, help=f"one of {sorted(STATUS_WRITABLE)}")
    ap.add_argument("--fixed-commit", default="", help="where it was fixed: a sha, a version, or both")
    ap.add_argument(
        "--allow-empty-commit",
        action="store_true",
        help="permit a closing status with no fixed_commit (it will make G26's baseline rise — say why)",
    )
    ap.add_argument("--dry-run", action="store_true", help="print the before/after line and write nothing")
    args = ap.parse_args()

    complaint = explain_status(args.status)
    if complaint:
        sys.exit(f"refused: nothing was written. {complaint}")
    if args.status in CLOSING_STATUSES and not args.fixed_commit.strip() and not args.allow_empty_commit:
        sys.exit(
            f"status {args.status!r} asserts the work is done, so it must say WHERE — pass "
            "--fixed-commit, or --allow-empty-commit if you truly cannot. G26 baselines 56 "
            "such rows and that number may only ever fall."
        )

    raw = REGISTER.read_bytes()
    trailing_newline = raw.endswith(b"\n")
    lines = raw.split(b"\n")
    if trailing_newline:
        lines = lines[:-1]  # the split's empty tail, not a row

    idx = _find_line(lines, args.id)
    before = lines[idx]
    cells = next(csv.reader([before.decode("utf-8")]))

    header = next(csv.reader([lines[0].decode("utf-8")]))
    if len(cells) != len(header):
        sys.exit(
            f"{args.id} has {len(cells)} fields against a {len(header)}-column header — "
            "that is a malformed row, and this tool will not rewrite one it cannot read."
        )
    si, fi = header.index("status"), header.index("fixed_commit")

    if cells[si] == args.status and cells[fi] == args.fixed_commit:
        print(f"{args.id} already reads status={args.status!r} fixed_commit={args.fixed_commit!r} — nothing to do")
        return 0

    print(f"{args.id}: status {cells[si]!r} -> {args.status!r} · fixed_commit {cells[fi]!r} -> {args.fixed_commit!r}")
    cells[si], cells[fi] = args.status, args.fixed_commit
    after = _serialise(cells).rstrip(b"\n")

    if args.dry_run:
        print("--dry-run: nothing written")
        return 0

    # THE SPLICE. Everything before and everything after is copied as bytes and
    # is never decoded, so it cannot be re-quoted, re-ordered or lost.
    head = b"\n".join(lines[:idx])
    tail = b"\n".join(lines[idx + 1 :])
    out = b"".join(
        [head, b"\n" if head else b"", after, b"\n" if tail else b"", tail, b"\n" if trailing_newline else b""]
    )
    REGISTER.write_bytes(out)

    # DEF-300: read back what was written. A tool that has never seen its own
    # output is a tool that has not been tested.
    check = REGISTER.read_bytes().split(b"\n")
    if trailing_newline:
        check = check[:-1]
    if len(check) != len(lines):
        sys.exit(f"REFUSED after write: line count moved {len(lines)} -> {len(check)}; restore from git and report this")
    changed = [i for i, (a, b) in enumerate(zip(lines, check)) if a != b]
    if changed != [idx]:
        sys.exit(f"REFUSED after write: {len(changed)} lines differ, expected exactly line {idx + 1}; restore from git")
    reread = next(csv.reader([check[idx].decode("utf-8")]))
    if reread[si] != args.status or reread[fi] != args.fixed_commit:
        sys.exit("REFUSED after write: the row does not read back as written; restore from git")
    print(f"written: line {idx + 1} of {len(check)}, and it is the only line that changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
