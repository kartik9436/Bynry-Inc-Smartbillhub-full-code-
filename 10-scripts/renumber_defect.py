#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects: DEF-CUS-6724 / 6725 / 6726 — three ids that each named TWO
#          different defects, filed by two lanes two minutes apart
#          (cabcdfa89 09:50:29, b55e7cb55 09:52:26, 2026-09-25). Both lanes
#          `DEF-GOV-6794` is the row for the ABSENCE this file closes: no
#          sanctioned tool renumbered a register row, so a gate could demand a
#          repair no lane could safely make.
#          computed max+1 correctly; neither could see the other's unpushed
#          rows. Textbook hard-won law 11.
# Rules:   CLAUDE.md hard-won law 11 (never round-trip a shared register; use
#          the tool that owns the file) · law 7 (prove a guard RED first) ·
#          law 1 (a docstring claiming a guarantee is not the guarantee — every
#          refusal below is executed, not described).
# Tests:   --selftest, which builds fixture registers in a temp directory and
#          asserts each refusal FIRES and leaves the file byte-identical.
# ───────────────────────────────────────────────────────
"""CHANGE THE ID OF ONE ROW IN THE DEFECT REGISTER, ONE LINE AT A TIME.

WHY THIS EXISTS
---------------
On 2026-09-25 two lanes filed against the same three numbers two minutes apart.
A lane sent to repair it found that **no sanctioned tool renumbers a register
row**, and the three that exist each say so in their own way:

  * `file_defect.py` is the append-only door. It opens the register in append
    mode and writes ONE line, so no existing byte is ever read back to be
    written out again. It **refuses to edit**, deliberately.
  * `close_defect.py` splices ONE line's bytes — but it writes only `status`
    and `fixed_commit`, and its `_find_line` treats a duplicate id as a hard
    error: *"fix the register before closing the row."* There was nothing to
    fix it WITH.
  * `merge_register.py` resolves an append/append conflict and refuses when
    both sides took the same id. It arbitrates a merge; it does not renumber.

So the only two options left were a hand edit of a 4,158-row file that ten
lanes append to — which law 11 exists to prevent — or nothing. **That absence
was the real defect**, and this file closes it.

THE OBVIOUS IMPLEMENTATION IS THE FORBIDDEN ONE
-----------------------------------------------
    >>> rows = list(csv.reader(open(register)))
    >>> rows[N][0] = new_id
    >>> csv.writer(open(register, "w")).writerows(rows)

Three lines, and they **re-serialise all 4,158 rows**. Python's csv writer makes
its own choices about quoting and line endings, so every line comes back changed
on disk even where its content did not. Two lanes did exactly this on 2026-09-06
and both were being careful. What it costs:

  * a stale copy silently reverts a row a sibling pushed since (DEF-165);
  * a pathspec commit naming only the register PUBLISHES every other lane's
    in-flight row with it (DEF-168);
  * and `git show` prints ~1,900 hunks, so law 11's *read every hunk and
    confirm each is yours* — the check written to catch precisely this —
    **cannot be performed at all.** A check you are unable to run is worse
    than one that fails.

So this tool never re-serialises the file. It finds the one line, rewrites that
line's bytes, and splices it back between two byte slices it never parsed.

WHAT IT GUARANTEES, AND EVERY ONE IS EXECUTED RATHER THAN DESCRIBED (law 1)
---------------------------------------------------------------------------
1. **The new id must be free EVERYWHERE, asked of the remote.** `allocate.py`
   already answers this for a fresh id and its reasoning is the reasoning here:
   a sibling in its own worktree has its rows in none of the places a listing
   can see until it pushes, so the question is put to every remote ref, the
   tip's tree and 4,000 commit messages — not to this checkout. A renumber that
   lands on a number a sibling has taken has moved the collision, not closed it.
   ⚠ It reads the number, never the id string: `DEF-BIL-6762` and
   `DEF-CUS-6762` are ONE number (CLAUDE.md, PO 2026-09-03), and G17's
   `number_collisions` fails on exactly that.
2. **The old id must appear EXACTLY the number of times you say it does.**
   Renumbering is used in two opposite situations — a duplicate (expect 2) and
   a single row being moved off a shared number (expect 1) — and getting that
   wrong edits a row the caller did not name. So the count is an ARGUMENT, not
   an assumption, and a mismatch refuses before anything is written.
3. **When the old id is on more than one row, `--match` must pick exactly one.**
   No positional guessing, no "the later one" heuristic: the caller names a
   substring that appears in the row they mean, and if it matches none or more
   than one, nothing is written.
4. **Exactly one line changes.** The bytes before and after the target line are
   copied verbatim, never decoded, never re-quoted. `git diff` reports
   `1 insertion(+), 1 deletion(-)`.
5. **It reads the file back and proves the edit** (DEF-300: a tool that has
   never seen its own output is a tool that has not been tested). Line count,
   which line moved, and that the row now reads as written.
6. **It prints every OTHER place the old id is cited**, because the register
   row is the easy half. An id is cited far more often than it is defined, and
   a renumber that moves the definition and leaves the citations behind turns
   every one of them into `G106`'s *a rule nobody can read*.

WHAT IT DELIBERATELY WILL NOT DO
--------------------------------
Touch more than one row per invocation · edit any column but `id` · move the
citations for you (it names them; you move them, and you count what you found
against what you changed) · commit anything. Committing is the caller's job and
is still governed by law 11 — build tip-plus-your-hunk and push through
`10-scripts/push_paths.sh`.

USAGE
    python3 10-scripts/renumber_defect.py --id DEF-CUS-6724 --to DEF-CUS-6790 \
        --expect 2 --match "blueprint p143" --dry-run
    python3 10-scripts/renumber_defect.py --selftest
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REGISTER = REPO / "12-governance" / "10-defect-log.csv"

# ⚠ THE LEADING QUOTE IS NOT OPTIONAL DECORATION, AND `{2,4}` IS NOT `{3}` —
# both lessons are `close_defect.py`'s and are quoted rather than re-learned.
# The register holds both `"DEF-12",…` and `DEF-12,…` (DEF-300), and one row
# carries a TWO-letter module code (`DEF-FE-4058`), which a `{3}` pattern
# reported as an ABSENCE rather than a refusal.
ID_RE = re.compile(r'^"?(DEF-(?:[A-Z]{2,4}-)?(\d+))"?,')
#: What a well-formed id looks like when a caller proposes one.
NEW_ID_RE = re.compile(r"^DEF-(?:[A-Z]{2,4}-)?(\d{3,5})$")


def _serialise(cells: list[str]) -> bytes:
    """One row, on its own, in the shape the other 4,157 rows are already in."""
    buf = io.StringIO()
    csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\n").writerow(cells)
    return buf.getvalue().encode("utf-8")


def _split(raw: bytes) -> tuple[list[bytes], bool]:
    trailing = raw.endswith(b"\n")
    lines = raw.split(b"\n")
    if trailing:
        lines = lines[:-1]  # the split's empty tail, not a row
    return lines, trailing


def _hits(lines: list[bytes], want: str) -> list[int]:
    return [
        i
        for i, raw in enumerate(lines)
        if (m := ID_RE.match(raw.decode("utf-8", "replace"))) and m.group(1) == want
    ]


def number_of(ident: str) -> int:
    m = NEW_ID_RE.match(ident)
    if not m:
        raise SystemExit(
            f"refused: {ident!r} is not a defect id this repo writes. The grammar is "
            "DEF-<MOD>-##### with three capitals, or bare DEF-##### for the ids filed "
            "before 2026-09-03 (CLAUDE.md, Screen IDs)."
        )
    return int(m.group(1))


def taken_anywhere(number: int) -> tuple[bool, str]:
    """Is this NUMBER claimed anywhere a listing can reach? Asked of the remote.

    ⚠ **THE REMOTE, NOT THIS CHECKOUT, AND THAT IS THE WHOLE POINT** — it is
    `allocate.py`'s reasoning and this defers to `allocate.py` rather than
    re-implementing it, because a second copy of that logic would drift from
    the first and the drift would be invisible (law 1, and DEF-5's one
    generated file). If `allocate.py` cannot be imported, this REFUSES rather
    than waving the renumber through: a check that silently becomes a no-op is
    the shape this repo files most often.
    """
    sys.path.insert(0, str(REPO / "10-scripts"))
    try:
        import allocate  # type: ignore
    except Exception as exc:  # pragma: no cover - the import IS the contract
        raise SystemExit(
            f"refused: cannot import allocate.py to ask whether the number is free ({exc}). "
            "Renumbering without that question answered moves the collision instead of "
            "closing it; nothing was written."
        )
    found, seen = allocate.numbers("defect")
    return number in found, ", ".join(seen)


def citations(ident: str) -> list[str]:
    """Every place OUTSIDE the register that names this id, `git grep -n`."""
    r = subprocess.run(
        ["git", "-C", str(REPO), "grep", "-n", "-F", ident],
        capture_output=True,
    )
    out = r.stdout.decode("utf-8", "replace").splitlines()
    return [line for line in out if not line.startswith("12-governance/10-defect-log.csv:")]


def renumber(
    register: Path, old: str, new: str, *, expect: int, match: str | None, dry_run: bool
) -> int:
    raw = register.read_bytes()
    lines, trailing = _split(raw)

    hits = _hits(lines, old)
    # ── GUARD 2 · the count is an argument, never an assumption ───────────
    if len(hits) != expect:
        raise SystemExit(
            f"refused: {old} is on {len(hits)} row(s) of {register.name} and you said "
            f"--expect {expect}. Nothing was written. "
            + (
                f"Rows: {', '.join(str(h + 1) for h in hits)}."
                if hits
                else "It is not in the register at all — check the spelling; ids carry "
                "their module since 2026-09-03."
            )
        )

    # ── GUARD 3 · with more than one hit, --match must pick exactly one ────
    if len(hits) == 1 and match is None:
        idx = hits[0]
    else:
        if match is None:
            raise SystemExit(
                f"refused: {old} is on {len(hits)} rows and no --match was given, so this "
                "tool would have to guess which one you mean. Nothing was written. Pass "
                "--match with text that appears in the row you mean."
            )
        picked = [i for i in hits if match.encode("utf-8") in lines[i]]
        if len(picked) != 1:
            raise SystemExit(
                f"refused: --match {match!r} picks {len(picked)} of the {len(hits)} rows "
                f"carrying {old}; it must pick exactly one. Nothing was written."
            )
        idx = picked[0]

    before = lines[idx]
    cells = next(csv.reader([before.decode("utf-8")]))
    header = next(csv.reader([lines[0].decode("utf-8")]))
    if len(cells) != len(header):
        raise SystemExit(
            f"refused: that row has {len(cells)} fields against a {len(header)}-column "
            "header — a malformed row, and this tool will not rewrite one it cannot read."
        )
    if cells[0] != old:
        raise SystemExit(
            f"refused: the line matched on {old} but its first cell reads {cells[0]!r}. "
            "A matcher that finds the right line and compares the wrong string is the "
            "shape this repo calls a check that cannot fail (DEF-3616). Nothing was written."
        )

    cells[0] = new
    after = _serialise(cells).rstrip(b"\n")

    print(f"{register.name} row {idx + 1} of {len(lines)}")
    print(f"  id: {old} -> {new}")
    print(f"  title: {cells[3][:96]}")
    if dry_run:
        print("--dry-run: nothing written")
        return 0

    # ── THE SPLICE. Head and tail are copied as BYTES and never decoded, so
    # they cannot be re-quoted, re-ordered or lost.
    head = b"\n".join(lines[:idx])
    tail = b"\n".join(lines[idx + 1 :])
    out = b"".join(
        [head, b"\n" if head else b"", after, b"\n" if tail else b"", tail, b"\n" if trailing else b""]
    )
    register.write_bytes(out)

    # ── DEF-300 · read back what was written ───────────────────────────────
    check, check_trailing = _split(register.read_bytes())
    if len(check) != len(lines) or check_trailing != trailing:
        raise SystemExit(
            f"REFUSED after write: line count moved {len(lines)} -> {len(check)}; "
            "restore from git and report this."
        )
    changed = [i for i, (a, b) in enumerate(zip(lines, check)) if a != b]
    if changed != [idx]:
        raise SystemExit(
            f"REFUSED after write: {len(changed)} line(s) differ, expected exactly line "
            f"{idx + 1}; restore from git."
        )
    reread = next(csv.reader([check[idx].decode("utf-8")]))
    if reread[0] != new:
        raise SystemExit("REFUSED after write: the row does not read back as written; restore from git.")
    # The byte proof, stated as arithmetic rather than as a glance (law 11).
    prefix = sum(len(l) + 1 for l in lines[:idx])
    print(f"written: line {idx + 1} is the only line that changed")
    print(f"  bytes 0..{prefix} and the {len(lines) - idx - 1} line(s) after it are byte-identical")
    return 0


# ─────────────────────────────────────────────────────────────────────────
# SELF-TEST — law 7: prove the guard goes RED before trusting it green, and
# prove it leaves the file BYTE-IDENTICAL when it refuses. A tool that edits a
# shared register and has not been shown to refuse is more dangerous than no
# tool, because it is trusted.
# ─────────────────────────────────────────────────────────────────────────
FIXTURE = (
    b'"id","reported_on","reported_by","title","surface","module","severity","found_in",'
    b'"introduced_in","category","escape_reason","status","fixed_commit","prevention"\n'
    b'"DEF-CUS-9001","2026-01-01","lane A","FIRST ROW - alpha","s","customers","high","x","y",'
    b'"not-built","none","open","",""\n'
    b'"DEF-CUS-9002","2026-01-01","lane A","SECOND ROW - beta","s","customers","high","x","y",'
    b'"not-built","none","open","",""\n'
    b'"DEF-CUS-9002","2026-01-01","lane B","THIRD ROW - gamma","s","customers","high","x","y",'
    b'"not-built","none","open","",""\n'
)


def _fixture(tmp: Path) -> Path:
    p = tmp / "10-defect-log.csv"
    p.write_bytes(FIXTURE)
    return p


def selftest() -> int:
    results: list[tuple[str, bool, str]] = []

    def bites(tag: str, fn, path: Path) -> None:
        """A refusal must FIRE, and must leave the file byte-identical."""
        before = path.read_bytes()
        try:
            fn()
        except SystemExit as exc:
            fired = bool(str(exc))
            intact = path.read_bytes() == before
            results.append((tag, fired and intact, f"refused {'and' if intact else 'BUT NOT'} "
                                                   f"byte-identical — {str(exc)[:120]}"))
            return
        results.append((tag, False, "DID NOT REFUSE — the guard is blind"))

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        reg = _fixture(tmp)
        bites(
            "expected once, found twice",
            lambda: renumber(reg, "DEF-CUS-9002", "DEF-CUS-9500", expect=1, match=None, dry_run=False),
            reg,
        )
        bites(
            "expected twice, found once",
            lambda: renumber(reg, "DEF-CUS-9001", "DEF-CUS-9500", expect=2, match=None, dry_run=False),
            reg,
        )
        bites(
            "not in the register at all",
            lambda: renumber(reg, "DEF-CUS-9999", "DEF-CUS-9500", expect=1, match=None, dry_run=False),
            reg,
        )
        bites(
            "two rows, no --match",
            lambda: renumber(reg, "DEF-CUS-9002", "DEF-CUS-9500", expect=2, match=None, dry_run=False),
            reg,
        )
        bites(
            "--match picks both",
            lambda: renumber(reg, "DEF-CUS-9002", "DEF-CUS-9500", expect=2, match="ROW", dry_run=False),
            reg,
        )
        bites(
            "--match picks none",
            lambda: renumber(reg, "DEF-CUS-9002", "DEF-CUS-9500", expect=2, match="delta", dry_run=False),
            reg,
        )
        bites("malformed new id", lambda: number_of("DEF-CUS-ABC"), reg)

        # The one that must go GREEN, so the self-test is not simply a tool
        # that refuses everything (law 7: describe the false pass too).
        before = reg.read_bytes()
        renumber(reg, "DEF-CUS-9002", "DEF-CUS-9500", expect=2, match="gamma", dry_run=False)
        after = reg.read_bytes()
        bl, al = before.split(b"\n"), after.split(b"\n")
        moved = [i for i, (a, b) in enumerate(zip(bl, al)) if a != b]
        ok = moved == [3] and b'"DEF-CUS-9500"' in al[3] and b"gamma" in al[3]
        results.append(("the legitimate edit", ok, f"exactly line(s) {[m + 1 for m in moved]} changed"))

    print("--- self-test (law 7 — a guard that cannot be shown to fail is not a guard) ---")
    for tag, ok, text in results:
        print(f"  {'BITES' if ok else 'BLIND'}  {tag:32s}  {text}")
    blind = [t for t, ok, _ in results if not ok]
    if blind:
        print(f"SELF-TEST BLIND: {len(blind)} clause(s) did not bite: {', '.join(blind)}")
        return 1
    print(f"self-test: {len(results)}/{len(results)} clauses bite")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--id", help="the id the row carries now, e.g. DEF-CUS-6724")
    ap.add_argument("--to", help="the id it should carry, e.g. DEF-CUS-6790")
    ap.add_argument(
        "--expect",
        type=int,
        default=1,
        help="how many rows carry --id right now (1 normally; 2 when repairing a duplicate)",
    )
    ap.add_argument("--match", help="text appearing in the ONE row you mean; required when --expect > 1")
    ap.add_argument(
        "--register",
        type=Path,
        default=REGISTER,
        help="the register file (defaults to the real one; the self-test points this at a fixture)",
    )
    ap.add_argument("--dry-run", action="store_true", help="print the change and write nothing")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.id or not args.to:
        ap.print_help()
        return 2

    number_of(args.id)  # the old id must be well formed too, or --match is guesswork
    want = number_of(args.to)
    if args.id == args.to:
        raise SystemExit("refused: --id and --to are the same id; nothing to do.")

    # ── GUARD 1 · the new NUMBER must be free everywhere ───────────────────
    if args.register == REGISTER:
        is_taken, seen = taken_anywhere(want)
        if is_taken:
            raise SystemExit(
                f"refused: {want} is already claimed somewhere ({seen}). Renumbering onto a "
                "taken number MOVES the collision instead of closing it — and the module "
                "segment is not part of the number, so DEF-XXX-{n} and DEF-YYY-{n} are one "
                "number (CLAUDE.md, PO 2026-09-03; G17 fails on exactly that). Take a fresh "
                "one with `python3 10-scripts/allocate.py defect`. Nothing was written."
                .replace("{n}", str(want))
            )
        print(f"{args.to}: free on every world allocate.py can see ({seen})")

    rc = renumber(
        args.register, args.id, args.to, expect=args.expect, match=args.match, dry_run=args.dry_run
    )

    # ── THE HALF THIS TOOL CANNOT DO FOR YOU, NAMED WITH A NUMBER ──────────
    # A blind spot with no number beside it is indistinguishable from an empty
    # one (law 7). So the citations are COUNTED and LISTED, never implied.
    if args.register == REGISTER:
        cites = citations(args.id)
        print(f"\ncitations of {args.id} OUTSIDE the register: {len(cites)}")
        for line in cites:
            print(f"  {line[:160]}")
        if cites:
            print(
                f"  ^ move every one of these to {args.to} that belongs to THIS row, and count "
                "what you changed against what you found. An id whose definition moved and "
                "whose citations did not is G106's 'a rule nobody can read'."
            )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
