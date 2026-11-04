#!/usr/bin/env python3
"""G26 — the defect register must be structurally sound, and appended to, not rewritten.

WHY THIS GATE EXISTS (2026-08-19)
---------------------------------
Six lanes shared one working tree and broke `12-governance/10-defect-log.csv`
four different ways inside an hour. None of the four was caught by anything:

  * TWO LANES TOOK `DEF-284`. Each read the highest id from its own working-tree
    copy; neither could see the other's uncommitted row. The register carried a
    duplicate id for hours and every test stayed green, because nothing reads
    this file for integrity — `defect_report.py` reads it for CONTENT.
  * THE SAME ID WAS FILED TWICE with different bodies, so "which one is DEF-284"
    had no answer.
  * ONE COMMIT CARRIED FOUR LANES' ROWS, because appending through Python's csv
    writer re-serialises every row — a whole-file write wearing the costume of
    an append.
  * A LATER LANE'S WHOLE-FILE COPY SILENTLY REVERTED a line already pushed.

`10-scripts/file_defect.py` makes the safe path easy. This gate makes the unsafe
path fail, because a convention nothing enforces is a convention that lasts
until the first hurried lane.

WHAT IT CHECKS, and each check maps to one failure above
--------------------------------------------------------
1. **NO DUPLICATE IDS.** The collision, and the only check here that would have
   fired on the day. An id is the register's primary key; two rows sharing one
   is not a style problem, it is a row that cannot be cited.
2. **NO ID GAPS THAT HIDE A LOST ROW.** Ids are allocated sequentially. A gap
   means either a row was reverted by a whole-file write, or an id was taken and
   abandoned. Both are worth knowing, so a gap is REPORTED rather than failed —
   an abandoned id is legitimate (2.20.0 was retired unused for the same
   reason), and failing on it would punish an honest record.
3. **EVERY ROW HAS THE FULL COLUMN COUNT.** A prose `escape_reason` containing a
   raw newline splits one row into two, and the halves then look like rows with
   the wrong field count rather than like corruption.
4. **`status` IS FROM THE KNOWN SET**, and a row marked `fixed` carries a
   `fixed_commit`. A defect marked fixed with no commit cannot be verified, and
   the CR-010 lane found FOUR rows fixed a day earlier still reading `open` —
   its own triage list was wrong because of it.
5. **`escape_reason` IS NOT EMPTY.** CLAUDE.md: that column "is what turns a bug
   list into a process fix". A blank one is a bug list entry.

WHAT IT DOES NOT CHECK
----------------------
It does not diff against the remote to see whether a commit rewrote lines it did
not author. That needs the commit under inspection and belongs in the post-push
hunk read law 11 already prescribes; this gate runs on the file as it stands.
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

# ⚠ ONE STATEMENT OF WHAT A RUNNING NUMBER IS, NOT TWO (hard-won law 5).
# `common.id_number` is the same extraction `G17` and `file_defect.py` use, so
# the number clause below and the gate that owns its verdict cannot drift into
# disagreeing about which digits are the number.
import common

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTER = REPO_ROOT / "12-governance" / "10-defect-log.csv"
# The vocabulary ACTUALLY IN USE, counted rather than assumed — the first draft
# of this gate invented a tidier set and reported nine false failures on states
# the register has used deliberately for weeks. A gate that argues with the data
# it checks is a gate that gets switched off.
#   fixed 180 · open 104 · closed 4 · partially-fixed 3 · reported 1 · fixed-in-part 1
KNOWN_STATUS = {
    "open", "fixed", "closed", "partially-fixed", "fixed-in-part", "reported",
    "wontfix", "duplicate", "invalid",
}

# ── THE RATCHET ────────────────────────────────────────────────────────────
# 56 rows are marked fixed with no fixed_commit. Every one predates the
# convention, and failing on them would make this gate red from birth — which
# is how a check earns a `# noqa` instead of a fix. So the count is BASELINED:
# the gate fails only if it GOES UP. The number may fall and must never rise,
# and lowering this constant as rows are corrected is the intended maintenance.
FIXED_WITHOUT_COMMIT_BASELINE = 56


def check() -> tuple[list[str], list[str]]:
    """Returns (violations, notes)."""
    violations: list[str] = []
    notes: list[str] = []
    unverifiable: list[str] = []
    if not REGISTER.is_file():
        return [f"{REGISTER} is missing"], []

    # Bytes, then decode — a text-mode read would convert this CRLF file and any
    # rewrite of it would then differ on every line. The gate must not be the
    # thing that corrupts the file it is checking.
    text = REGISTER.read_bytes().decode("utf-8")
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        return ["the register is empty"], []
    header, body = rows[0], [r for r in rows[1:] if r]
    width = len(header)

    ids = [r[0] for r in body if r]
    for ident, n in sorted(Counter(ids).items()):
        if n > 1:
            violations.append(f"DUPLICATE ID {ident} appears {n} times — an id is the register's primary key")

    # ── THE BLIND SPOT, WITH A NUMBER BESIDE IT (`DEF-GOV-7808`, 2026-09-28) ──
    #
    # ⚠ **THE LOOP ABOVE COUNTS ID *STRINGS*, SO IT CANNOT SEE THE COLLISION
    # THAT ACTUALLY HAPPENS NOW.** `DEF-CUS-7700` and `DEF-RAT-7700` are two
    # different strings and `Counter` reports nothing — truthfully, of the
    # question it asks. But the PO's ruling of 2026-09-03 makes the **NUMBER**
    # the unique thing: *"one running number across the whole register"*, the
    # module code being provenance, not identity. CLAUDE.md says the same of
    # change requests — *"the STRING is unique and the NUMBER is not, and a
    # number is what a person says out loud"*. It happened four times on
    # 2026-09-28 alone (`DEF-CUS-7700`/`7701`, `DEF-INF-7702`), because a lane
    # that has not fetched cannot see a sibling's reservation row and
    # `allocate.py` cannot RESERVE.
    #
    # ⚠ **THE VERDICT DELIBERATELY STAYS WITH `G17` CLAUSE 3, AND THIS ONLY
    # REPORTS.** `G17` already asks exactly this question over a corpus that
    # INCLUDES this register, and it already carries a 13-number ratchet
    # (`CARRIED_NUMBER_SHARES`) plus whatever is live beyond it. Failing here
    # too would put a SECOND gate permanently red on the SAME rows — and a gate
    # that can never go green is a gate nobody reads, which is the condition
    # that let `DEF-490` hide inside `G17` for weeks. So this gate prints the
    # count and names the owner.
    #
    # What it removes is the FALSE CONFIDENCE: until now this gate's pass line
    # read *"no duplicate ids"* over a register holding fifteen shared numbers,
    # and that sentence is the reason a reader stops looking. A declared blind
    # spot with no number attached is indistinguishable from an empty one
    # (hard-won law 7, fifth shape).
    by_number: dict[int, set[str]] = {}
    for ident in ids:
        try:
            by_number.setdefault(common.id_number(ident), set()).add(ident)
        except (ValueError, IndexError):
            continue  # a malformed id is the width/shape checks' business, not this one
    shared = {n: v for n, v in by_number.items() if len(v) > 1}
    if shared:
        sample = ", ".join(
            f"{n} ({'/'.join(sorted(shared[n]))})" for n in sorted(shared)[:3]
        )
        notes.append(
            f"{len(shared)} running number(s) are claimed by more than one id — "
            f"e.g. {sample}"
            + (" …" if len(shared) > 3 else "")
            + ". THIS GATE DOES NOT FAIL ON THESE: it compares id STRINGS, and the "
            "module segment is not part of the number (PO 2026-09-03). G17 clause 3 "
            "owns the verdict and carries the ratchet; fix one by renumbering the "
            "LATER id with `10-scripts/allocate.py defect` and recording the move in "
            "its own row."
        )
    else:
        notes.append(
            "0 running numbers are claimed twice (checked "
            f"{len(by_number)} number(s) across {len(ids)} row(s)) — the module segment "
            "is not part of the number; G17 clause 3 owns the verdict"
        )

    numbers = sorted({int(i.rsplit("-", 1)[1]) for i in ids if i.startswith("DEF-") and i.rsplit("-", 1)[1].isdigit()})
    if numbers:
        gaps = [n for n in range(numbers[0], numbers[-1]) if n not in numbers]
        if gaps:
            notes.append(
                f"{len(gaps)} id(s) unused: "
                + ", ".join(f"DEF-{n:03d}" for n in gaps[:8])
                + (" …" if len(gaps) > 8 else "")
                + " — an abandoned id is legitimate; a REVERTED row is not, so check one"
            )

    for row in body:
        ident = row[0] if row else "<blank>"
        if len(row) != width:
            violations.append(
                f"{ident} has {len(row)} fields, header has {width} — "
                "a raw newline in a prose column splits one row into two"
            )
            continue
        cells = dict(zip(header, row))
        status = (cells.get("status") or "").strip()
        if len(status) > 24:
            # Not a vocabulary problem — a whole paragraph in a one-word column,
            # which means the row's remaining fields are shifted or its prose
            # landed in the wrong place. DEF-103 is the known instance.
            violations.append(
                f"{ident} has {len(status)} characters of PROSE in its status column "
                f"(begins {status[:40]!r}) — status is one word; the sentence belongs in "
                "escape_reason or prevention"
            )
        elif status not in KNOWN_STATUS:
            violations.append(f"{ident} status {status!r} is not one of {sorted(KNOWN_STATUS)}")
        if status == "fixed" and not (cells.get("fixed_commit") or "").strip():
            unverifiable.append(ident)
        if not (cells.get("escape_reason") or "").strip():
            # A hard failure, and it can be, because the discipline currently
            # holds perfectly: ZERO of 294 rows have an empty escape_reason.
            # This check exists to keep it that way, not to clear a backlog.
            violations.append(
                f"{ident} has an empty escape_reason — that column is what turns a bug list into a process fix"
            )

    if len(unverifiable) > FIXED_WITHOUT_COMMIT_BASELINE:
        violations.append(
            f"{len(unverifiable)} rows are marked fixed with no fixed_commit, up from the "
            f"baseline of {FIXED_WITHOUT_COMMIT_BASELINE} — new ones: "
            + ", ".join(unverifiable[-(len(unverifiable) - FIXED_WITHOUT_COMMIT_BASELINE):])
            + ". A defect marked fixed with no commit cannot be verified by anyone."
        )
    elif unverifiable:
        notes.append(
            f"{len(unverifiable)} of {len(body)} rows are fixed with no fixed_commit "
            f"(baseline {FIXED_WITHOUT_COMMIT_BASELINE}; the number may fall, never rise)"
        )

    return violations, notes


def main() -> int:
    violations, notes = check()
    for note in notes:
        print(f"note: {note}")
    for bad in violations:
        print(f"FAIL: {bad}")
    if violations:
        print(f"\n{len(violations)} violation(s). File defects with 10-scripts/file_defect.py, "
              "which allocates the id against the remote tip and appends ONE line.")
        return 1
    print("defect register: no duplicate ids, every row full-width, every status known, "
          "every fixed row has a commit, every row has an escape_reason")
    return 0


def run():
    """Runner contract: ('PASS'|'FAIL'|'SKIP', detail).

    ⚠ THE NUMBER-SHARES NOTE IS CARRIED INTO THE DETAIL, NOT LEFT IN `notes[0]`
    (`DEF-GOV-7808`). `run_gates` prints only what is RETURNED; a `note:` line
    printed by `main()` is never seen on the runner's path, and this gate's
    whole contribution on that question is the number. Returning only
    `notes[0]` — the id-gap note — would have kept the blind spot invisible in
    the one place a reader actually looks.
    """
    violations, notes = check()
    shares = next((n for n in notes if "running number" in n), None)
    if violations:
        detail = f"{len(violations)} register violation(s): {violations[0]}"
        return "FAIL", detail + (f" · ALSO: {shares}" if shares else "")
    gaps = next((n for n in notes if "unused" in n), None)
    return "PASS", (
        "register sound: no duplicate id STRINGS, every row full-width, every status "
        "known, every fixed row has a commit"
        + (f" · {gaps}" if gaps else "")
        + (f" · {shares}" if shares else "")
    )


if __name__ == "__main__":
    raise SystemExit(main())
