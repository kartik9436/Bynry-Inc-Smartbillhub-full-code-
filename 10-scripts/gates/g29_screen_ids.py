#!/usr/bin/env python3
"""G29 — every screen names an id its authority allocates, and the unnamed are counted.

WHY THIS GATE EXISTS (CR-016 addendum, PO 2026-08-19)
-----------------------------------------------------
The Product Owner asked for it in one sentence:

    "Cr16 - I want you to give sreen Id to each and Every screen and for time
     bing also display that as a tag - right bottom for every UI screen so that
     we know which scren has a problem - enrure engineer the screen IDs"

and **DEF-137 has been open since the first deployment saying the same thing
from the other end**:

    "S113 has no owning story, and screens do not carry their own id in the
     frontend, so no gate can [check screen coverage]"

G25 is the half that reads the INVENTORY against the STORIES. Its own docstring
says why it stops there — *"screens do not carry their id … a scan over-reports
absence for built screens and cannot distinguish them from genuinely missing
ones"* — and names what would unblock it. `07-frontend/src/routing/screenIds.ts`
is that thing: one table, one row per routed screen, carrying the id A1
allocates and the id r10 badges. This gate reads it.

════════════════════════════════════════════════════════════════════════════
THERE ARE TWO VOCABULARIES AND THIS GATE CHECKS BOTH AGAINST THEIR OWN SOURCE
════════════════════════════════════════════════════════════════════════════
* **A1** (`04-docs/01-spec/01-screen-inventory.md`) allocates `S1`–`S114`. It is
  the ticket vocabulary — every defect row, every story's `screens:`
  frontmatter and G25 resolve it. CLAUDE.md: *"Use A1 as the ticket vocabulary;
  never renumber."*
* **r10** (`05-prototype/r10-2026-08-16/SMARTBillHub.dc.html`) badges
  `DSH-01`, `PLN-01`, `PLN-01.charges` … Its id function is the source and is
  read here, not transcribed. **This is the one the PO ruled is VISIBLE**
  (2026-08-19: *"assign tags that are visible on screen those should be as per
  modules how we are using in r10"*).

They do not reconcile and neither is derivable from the other, so the map holds
both and this gate refuses an id that neither file defines. **An invented id is
the failure mode worth catching**: it renders on a screen, a PO photographs it,
a defect is filed against it, and no document anywhere can say what it is.

════════════════════════════════════════════════════════════════════════════
⚠ THE A1 PARSER HERE IS NOT G25's, AND THAT IS A FINDING, NOT A PREFERENCE
════════════════════════════════════════════════════════════════════════════
G25's `ROW_RE` reads the FIRST CELL of a table row. A1's S49–S60 addendum is a
TWO-COLUMN table — `| S49 | Assets list | | S55 | Reassign asset (modal) |` —
so **S55, S56, S57, S58, S59 and S60 are invisible to it**, and S61 and S62 are
declared as addendum HEADINGS with no table at all. G25 therefore sees 95 of the
103 screens A1 declares, and a gate that reused it would have called `S56` and
`S61` invented ids.

Measured, and reported rather than silently corrected: fixing G25's regex raises
its screen count and can newly fail it on screens no story claims, which is
another lane's ledger. This parser is the strict one; the discrepancy is in the
report.

════════════════════════════════════════════════════════════════════════════
WHAT IT ASSERTS
════════════════════════════════════════════════════════════════════════════
1. **Every `a1:` id in the map is an id A1 declares.** Nothing minted.
2. **Every `r10:` id in the map is one r10's own badge function emits** (a
   dotted sub-id is checked against its parent, because `PLN-01.charges` is
   r10's own convention and the tab name is data).
3. **No route pattern is mapped twice.**
4. **A row with no id at all carries a written reason** of at least 40
   characters, or a `noScreen:` classification. A one-word reason is how a
   register turns into an allowlist (the G25/G23 rule).
5. **THE RATCHET.** `screen_id_baseline.txt` holds EXACT counts of screens with
   no A1 id and screens with no r10 id. Exact, not a ceiling, for the G23/G25
   reason: a ceiling is a number nobody looks at again. A count going UP means
   a screen shipped with no id — RED. A count going DOWN means someone earned
   it and must lower the baseline in the same commit — also RED, because a
   register that keeps claiming debt it has paid off is how a gate stops being
   a gate (DEF-077).

════════════════════════════════════════════════════════════════════════════
PROVED RED BEFORE TRUSTED GREEN (hard-won law 7)
════════════════════════════════════════════════════════════════════════════
Three separate breaks, each run against the tree this landed on:

  · `/:tenant/dashboard` repointed from `a1: "S7"` to `a1: "S999"` →
    `G29 screen-ids | FAIL | 1 … "S999" is not an id A1 declares`
  · its `r10: "DSH-01"` changed to `r10: "DSH-99"` →
    `G29 screen-ids | FAIL | 1 … "DSH-99" is not a badge r10 draws`
  · `a1` blanked to `null` with no note →
    `G29 screen-ids | FAIL | … screens with no A1 id: 12, baseline says 11`

Restored, the gate is green. The exact transcripts are in the lane's report.

Python 3.12 stdlib only. Safe to run from any cwd. Nothing here ever writes.
"""

from __future__ import annotations

import re
from pathlib import Path

import common

INVENTORY = common.REPO_ROOT / "04-docs" / "01-spec" / "01-screen-inventory.md"
PROTOTYPE = (
    common.REPO_ROOT / "05-prototype" / "r10-2026-08-16" / "SMARTBillHub.dc.html"
)
MAP = common.REPO_ROOT / "07-frontend" / "src" / "routing" / "screenIds.ts"
BASELINE = Path(__file__).resolve().parent / "screen_id_baseline.txt"

#: THE THIRD AUTHORITY (PO instruction 2026-09-03, decision log the same day).
#: r10 is a FROZEN prototype and cannot grow new badges, so the 35 screens it
#: never drew had no id any authority defined and rendered no tag at all. The
#: ruling of 2026-08-19 says the visible tag follows *"modules how we are using
#: in r10"* — a SCHEME, not a closed list — so the missing ids are allocated in
#: that same grammar from a register in this repository, and read here.
#:
#: ⚠ **THIS DOES NOT WEAKEN CLAUSE 2 AND THE DISTINCTION IS THE WHOLE POINT.**
#: The gate still refuses an id NO authority defines; it now knows about one more
#: authority. The rejected alternative was accepting any id at all, which would
#: have retired the only check standing between us and *"an invented id renders
#: on a screen, a PO photographs it, a defect is filed against it, and no
#: document anywhere can say what it is"*.
ALLOCATED = Path(__file__).resolve().parent / "g29_allocated_badges.txt"

MIN_REASON = 40

#: An A1 id, exactly as A1 writes it. S31.2 and S31.3 are real; nothing else
#: carries a dot on the A1 side.
A1_ID = re.compile(r"^\*{0,2}(S\d+(?:\.\d+)?)(?:\s*[–—-]\s*S(\d+))?\*{0,2}$")

#: A screen id anywhere inside a markdown heading — A1 declares S61 and S62 as
#: addendum headings and gives them no table row at all.
HEADING_ID = re.compile(r"^#{2,4}\s+.*?\bS(\d+)\b")

#: r10's badge, as its own id function writes it: three capitals, a hyphen, a
#: short code, and optionally a dotted sub-id for a tab or a wizard step.
R10_LITERAL = re.compile(r"'([A-Z]{3}-[0-9A-Za-z]+)\.?'")


def inventory_screens() -> list[str]:
    """Every id A1 allocates — EVERY table cell, plus addendum headings."""
    if not INVENTORY.is_file():
        return []
    found: list[str] = []

    def add(screen: str) -> None:
        if screen not in found:
            found.append(screen)

    for line in common.read_text(INVENTORY).splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            for cell in stripped.strip("|").split("|"):
                match = A1_ID.match(cell.strip())
                if match is None:
                    continue
                start, end = match.group(1), match.group(2)
                if end is None:
                    add(start)
                else:
                    first = int(start[1:].split(".")[0])
                    for number in range(first, int(end) + 1):
                        add(f"S{number}")
            continue
        heading = HEADING_ID.match(stripped)
        if heading is not None:
            add(f"S{heading.group(1)}")
    return found


def prototype_badges() -> set[str]:
    """Every badge r10's own id function can emit, read from the prototype.

    ⚠ SCOPED TO THE `const sid = (() => {` BLOCK, not the whole 9,000-line file.
    Scanning the file at large returns 137 matches against the 92 the function
    actually emits, because r10's demo data is full of `PLN-01`-shaped strings
    that are account numbers, part SKUs and run ids. A vocabulary padded with
    those would accept an id r10 never badges — which is the one thing this
    check exists to refuse.
    """
    if not PROTOTYPE.is_file():
        return set()
    text = common.read_text(PROTOTYPE)
    start = text.find("const sid = (() => {")
    if start < 0:
        return set()
    end = text.find("})();", start)
    return set(R10_LITERAL.findall(text[start : end if end > start else len(text)]))


def allocated_badges() -> set[str]:
    """Every id `g29_allocated_badges.txt` allocates — the FIRST FIELD of a row.

    ⚠ NONE OF THESE ARE IN r10, and the register says so on its own face in
    capitals. That sentence is not decoration: without it the next reader greps
    the prototype for `WRK-19`, finds nothing, and concludes the map is wrong.

    A MISSING FILE YIELDS AN EMPTY SET AND NOT A CRASH, which is deliberate and
    is the same posture `baseline()` takes: the register is an authority the gate
    consults, so losing it must show up as *"that is not a badge r10 draws"* on
    35 rows — loud, specific and immediately diagnosable — rather than as one
    traceback that names no screen.
    """
    if not ALLOCATED.is_file():
        return set()
    found: set[str] = set()
    for raw in common.read_text(ALLOCATED).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        found.add(line.split()[0])
    return found


def map_rows() -> tuple[list[dict[str, object]], list[str]]:
    """One record per routed screen, read out of the frontend's map table."""
    problems: list[str] = []
    if not MAP.is_file():
        return [], [f"{common.rel(MAP)} is missing — the screen-id map is the whole feature"]

    text = common.read_text(MAP)
    start = text.find("export const SCREEN_ROUTES")
    if start < 0:
        return [], [f"{common.rel(MAP)} declares no SCREEN_ROUTES table"]
    body = text[start:]

    # One chunk per row: a row begins at its `path: "…"` key and runs to the
    # next one. `path` appears as a KEY only here — the interface writes
    # `readonly path: string`, which has no quote after the colon.
    marks = [(m.start(), m.group(1)) for m in re.finditer(r'path:\s*"([^"]+)"', body)]
    rows: list[dict[str, object]] = []
    for index, (offset, path) in enumerate(marks):
        end = marks[index + 1][0] if index + 1 < len(marks) else len(body)
        chunk = body[offset:end]
        rows.append(
            {
                "path": path,
                "a1": sorted(set(re.findall(r'a1:\s*"([^"]+)"', chunk))),
                "r10": sorted(set(re.findall(r'r10:\s*"([^"]+)"', chunk))),
                "note": (re.search(r'note:\s*\n?\s*"', chunk) is not None)
                or ("note:" in chunk),
                "noScreen": "noScreen:" in chunk,
                "reason": chunk,
            }
        )
    if not rows:
        problems.append(f"{common.rel(MAP)}'s SCREEN_ROUTES table parsed to zero rows")
    return rows, problems


def baseline() -> tuple[dict[str, int], list[str]]:
    """`<key> <count>` per line. Exact numbers, never ceilings."""
    counts: dict[str, int] = {}
    problems: list[str] = []
    if not BASELINE.is_file():
        return counts, [f"{common.rel(BASELINE)} is missing — the ratchet has no register"]
    for number, raw in enumerate(common.read_text(BASELINE).splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2 or not parts[1].isdigit():
            problems.append(f"line {number}: expected `<key> <count>`")
            continue
        counts[parts[0]] = int(parts[1])
    return counts, problems


def run():
    screens = inventory_screens()
    if not screens:
        return "SKIP", "04-docs/01-spec/01-screen-inventory.md not present or has no screen rows"

    drawn = prototype_badges()
    allocated = allocated_badges()
    # The three authorities, unioned for the check and kept apart for the report:
    # a reader needs to know WHICH file defines an id, because only one of the
    # three can be looked up in a screenshot of the prototype.
    badges = drawn | allocated
    rows, problems = map_rows()
    if not rows:
        return "FAIL", "; ".join(problems)

    known_a1 = set(screens)
    seen_paths: set[str] = set()

    for row in rows:
        path = str(row["path"])

        # 3. no route mapped twice.
        if path in seen_paths:
            problems.append(f"{path} is mapped twice — one route, one row")
        seen_paths.add(path)

        # 1. every A1 id is one A1 declares.
        for screen in row["a1"]:  # type: ignore[union-attr]
            if screen not in known_a1:
                problems.append(
                    f'{path} claims A1 id "{screen}" — that is not an id A1 declares. '
                    f"A screen A1 has no row for gets `a1: null` and a note saying so; "
                    f"minting one renumbers a vocabulary CLAUDE.md says is never renumbered"
                )

        # 2. every r10 id is one r10's own badge function emits.
        for badge in row["r10"]:  # type: ignore[union-attr]
            parent = badge.split(".", 1)[0]
            if parent not in badges:
                problems.append(
                    f'{path} claims badge "{badge}" — no authority defines it. It is '
                    f"not a badge r10 draws ({common.rel(PROTOTYPE)}) and it is not "
                    f"allocated in {common.rel(ALLOCATED)}. An id no authority defines "
                    f"is an id nobody can look up when it appears in a bug report — if "
                    f"this screen genuinely needs a new id, allocate it in the register "
                    f"with the route it names and why, in r10's own grammar"
                )

        # 4. a row with neither id must say why.
        if not row["a1"] and not row["r10"] and not row["noScreen"]:
            chunk = str(row["reason"])
            note = re.search(r"note:\s*((?:.|\n)*?)(?:\n\s*\},)", chunk)
            length = len(re.sub(r"[^A-Za-z0-9 ]", "", note.group(1))) if note else 0
            if length < MIN_REASON:
                problems.append(
                    f"{path} has no A1 id, no r10 id and no reason of {MIN_REASON}+ "
                    f"characters. An unnamed screen is hard-won law 8 — write down what "
                    f"it is and why no authority numbers it"
                )

    # 5. THE RATCHET.
    registered, register_problems = baseline()
    problems.extend(register_problems)
    # A REDIRECT AND THE CATCH-ALL ARE NOT SCREENS, so they are excluded rather
    # than counted as debt: `/pricing` renders nothing, it forwards to `/`, and
    # counting it as "a screen with no id" would put seven permanent rows in a
    # register whose whole job is to be worked down to zero.
    screens = [row for row in rows if not row["noScreen"]]
    measured = {
        "screens_without_a1": sum(1 for row in screens if not row["a1"]),
        "screens_without_r10": sum(1 for row in screens if not row["r10"]),
        "screens_total": len(screens),
        "routes_total": len(rows),
    }
    for key, count in sorted(measured.items()):
        if key not in registered:
            problems.append(f"{key} is not in {common.rel(BASELINE)} — add it with its count")
        elif registered[key] != count:
            direction = "ROSE" if count > registered[key] else "fell"
            problems.append(
                f"{key} {direction}: {count} now, {registered[key]} registered. "
                + (
                    "A screen shipped with no id — give it one or record why it has none."
                    if count > registered[key]
                    else "Someone earned it: lower the baseline in the SAME commit, so the "
                    "register cannot keep claiming debt it has paid off (DEF-077)."
                )
            )

    if problems:
        return "FAIL", (
            f"{len(problems)} screen-id problem(s): " + common.summarize(problems, 3)
        )
    # The badge count is reported SPLIT BY AUTHORITY, never as one number. Only
    # r10's half can be looked up in a screenshot of the prototype; the allocated
    # half exists nowhere but this repository, and a reader who cannot tell them
    # apart will go hunting r10 for an id it has never drawn.
    return "PASS", (
        f"{measured['screens_total']} screens mapped across {measured['routes_total']} routes; "
        f"{measured['screens_total'] - measured['screens_without_r10']} carry the visible badge "
        f"the tag shows, {measured['screens_total'] - measured['screens_without_a1']} an A1 id; "
        f"{measured['screens_without_a1']} have no A1 id and {measured['screens_without_r10']} "
        f"no visible badge, each with a written reason. A1 declares {len(known_a1)} screens; "
        f"the badge vocabulary is {len(badges)} ids — {len(drawn)} DRAWN by r10 and "
        f"{len(allocated)} ALLOCATED in {common.rel(ALLOCATED)}, which r10 does not draw and "
        f"no screenshot of it will ever show."
    )


if __name__ == "__main__":
    status, detail = run()
    print(f"G29 screen-ids | {status} | {detail}")
    rows, _ = map_rows()
    print("\n--- routed screens with NO id from either authority ---")
    for row in rows:
        if not row["a1"] and not row["r10"] and not row["noScreen"]:
            print(f"  {row['path']}")
    print("\n--- routed screens with an A1 id and NO r10 badge (no visible tag) ---")
    for row in rows:
        if row["a1"] and not row["r10"]:
            print(f"  {row['path']:<48} {', '.join(row['a1'])}")  # type: ignore[arg-type]
    print("\n--- routed screens with an r10 badge and NO A1 id (no owning story) ---")
    for row in rows:
        if row["r10"] and not row["a1"]:
            print(f"  {row['path']:<48} {', '.join(row['r10'])}")  # type: ignore[arg-type]
    raise SystemExit(0 if status != "FAIL" else 1)
