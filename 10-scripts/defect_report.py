#!/usr/bin/env python3
"""Report over 12-governance/10-defect-log.csv.

    python3 10-scripts/defect_report.py
    python3 10-scripts/defect_report.py --by module

Output is NEVER committed. The CSV is the single source; every view is derived
on demand — the same rule that stopped the OpenAPI schema drifting when it was
committed twice (decision log, 2026-08-10).

EDITING THE CSV — DON'T. CALL THE TWO DOORS (corrected 2026-08-27, DEF-1791)
---------------------------------------------------------------------------
⚠ **THIS SECTION USED TO SAY THE FILE WAS CRLF AND TOLD YOU TO PATCH IT WITH
`split(b"\r\n")`. IT IS NOT, AND THAT PROCEDURE DESTROYS THE FILE.** Measured
at the branch tip: the register holds **0 CR bytes and 980 LF**, so splitting its
bytes on the CRLF pair returns **ONE element of 2.1 MB** — the whole register as
a single "line", which your one-line mutation then rewrites in full.

The claim survived because it lives HERE, in a read-only reporting script that
never writes the register: there is no code path to exercise it and no gate that
reads prose for truth. The two tools that DO write disagreed with it and were
both right all along — hard-won law 1, in the file least able to notice.

**So do not hand-patch this file at all. There are two doors and they are tested:**

* `10-scripts/file_defect.py` — appends ONE row, in append mode, allocating the id
  against the working tree, `HEAD`, `@{upstream}` and every `refs/remotes/origin`
  ref, and refusing ids inside another lane's block in `14-id-reservations.md`.
  It DETECTS the terminator rather than assuming one.
* `10-scripts/close_defect.py` — changes the status of ONE row, one line at a
  time, splitting on the LF byte, and prints "it is the only line that changed".

**If you must touch a field neither door owns**, re-serialise only the records you
change and leave every other record's bytes alone: parse with `csv.reader` over a
line iterator that counts lines, so you know each record's span, then rewrite just
those spans in the quoting style that record already used. `file_defect.py` writes
`QUOTE_ALL`; older rows are `QUOTE_MINIMAL`; a whole-file `csv.writer` pass
silently re-quotes both and turns a one-field edit into a wide diff.

**Then check the diff is the size you intended.** A wide diff over this file is not
a cosmetic problem — it is data loss waiting on a concurrent lane, and that much of
the old text was always true. Re-measure the terminator in one keystroke rather
than trusting this paragraph: `grep -c $'\r' 12-governance/10-defect-log.csv`.

"""

import argparse
import collections
import csv
import pathlib
import sys

CSV_PATH = pathlib.Path(__file__).resolve().parents[1] / "12-governance" / "10-defect-log.csv"

# The fix-drift view is DERIVED from the gate that owns the question, never
# recomputed here — hard-won law 5, one source. G55 reads the commit subjects
# and this script prints the count where triage actually reads its numbers.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "gates"))


def fix_drift() -> None:
    """Open rows a commit subject NAMES — the population G55 reports, not blocks.

    ⚠ IT IS NOT A LIST OF FIXED DEFECTS AND MUST NEVER BE PRINTED AS ONE. A
    commit can name a defect it reproduces, files, or merely touches, and no
    regex separates those from a fix — measured on this branch, six of the nine
    rows known to be stale on 2026-08-30 are named by subjects carrying no verb
    at all, and two are named by no commit whatsoever. What the number says is
    *how many rows need a human glance before you triage from this register*,
    which is the question that aimed a whole lane at shipped work (DEF-1930)
    and left DEF-2464 reading `open` with its fix on the branch.
    """
    try:
        import g55_commit_fix_claims as g55
    except ImportError as exc:  # pragma: no cover - defensive
        print(f"\nFix drift\n  unavailable: {exc}")
        return
    subjects, why = g55._subjects()
    if not subjects:
        print(f"\nFix drift\n  unavailable: {why}")
        return
    _, mentioned, commits, reported = g55.findings()
    print("\nFix drift — rows that may already be fixed")
    print(
        f"  {mentioned} open row(s) are NAMED by a commit subject, across {commits} commits."
    )
    print("  An id in a commit subject is NOT proof of a fix, and this is not a")
    print("  complete list either — it is the set that needs a human glance.")
    print("  Full list: python3 10-scripts/gates/g55_commit_fix_claims.py --report")
    top = reported[:5]
    for row_id, sha, subject in top:
        print(f"    {row_id:<10} {sha}  {subject[:72]}")
    if mentioned > len(top):
        print(f"    … and {mentioned - len(top)} more")


def bar(n: int, total: int, width: int = 28) -> str:
    return "█" * max(1, round(n / total * width)) if n else ""


def tally(rows, field: str) -> None:
    counts = collections.Counter(r[field] for r in rows)
    total = sum(counts.values())
    print(f"\nBy {field}")
    for value, n in counts.most_common():
        pct = 100 * n / total
        print(f"  {value or '(blank)':<26} {n:>3}  {pct:>4.0f}%  {bar(n, total)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--by", help="tally one column instead of the standard summary")
    args = parser.parse_args()

    if not CSV_PATH.exists():
        print(f"no defect log at {CSV_PATH}", file=sys.stderr)
        return 1
    rows = list(csv.DictReader(CSV_PATH.open()))
    if not rows:
        print("defect log is empty")
        return 0

    if args.by:
        if args.by not in rows[0]:
            print(f"unknown column {args.by!r}; columns: {', '.join(rows[0])}", file=sys.stderr)
            return 1
        tally(rows, args.by)
        return 0

    # ── THE HEADLINE, AND WHY IT PRINTS TWO NUMBERS (DEF-1786) ─────────────
    # "Open" has two defensible readings and they differ by more than a dozen
    # rows. On 2026-08-27 THREE different open counts were in circulation at
    # once — this script's 342, and 354 and 340 quoted from two governance
    # documents — and a figure line in 19-execution-sequence.md footed to its
    # own total while three of its four cells were wrong, because it had been
    # assembled from cells measured at different moments.
    #
    # So both readings print, side by side, with their severity split, and the
    # DEFINITION is on the line with the number. Quote a row from here; never
    # retype one. A count is true at a state or it is not true, so the state is
    # named too.
    WIDE = ("open", "reported", "fixed-in-part", "partially-fixed")
    SEV = ("critical", "high", "medium", "low")

    def split(pred):
        sel = [r for r in rows if pred(r)]
        by = collections.Counter(r["severity"] for r in sel)
        return len(sel), "  ".join(f"{s} {by[s]}" for s in SEV)

    wide_n, wide_by = split(lambda r: r["status"] in WIDE)
    narrow_n, narrow_by = split(lambda r: r["status"] == "open")

    print(f"{len(rows)} defects on file")
    print(f"  open = open+reported+fixed-in-part+partially-fixed : {wide_n:>4}   {wide_by}")
    print(f'  open = status == "open" alone                      : {narrow_n:>4}   {narrow_by}')
    print(f"  the two readings differ by {wide_n - narrow_n}; say which one you mean")

    for field in ("category", "found_in", "introduced_in", "severity", "module", "reported_by"):
        tally(rows, field)

    # The two health numbers. Everything above is description; these are the ones
    # that say whether the process is improving.
    deployed = [r for r in rows if r["found_in"] == "deployed"]
    unpreventable = [r for r in rows if r["prevention"] in ("none", "")]
    print("\nHealth")
    print(
        f"  reached a live deployment      {len(deployed):>3}/{len(rows)}"
        f"  ({100 * len(deployed) / len(rows):.0f}%) — each cost a support cycle, not minutes"
    )
    print(
        f"  closed with NO prevention      {len(unpreventable):>3}/{len(rows)}"
        f"  ({100 * len(unpreventable) / len(rows):.0f}%) — these can recur unchanged"
    )
    fix_drift()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
