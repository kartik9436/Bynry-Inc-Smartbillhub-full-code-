#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-045 wave F task F.3 — "prove it": the toolbar standard is one
#           search, one filter set, one download glyph, one column chooser, on
#           every list.
# Defects:  DEF-1702 (wave D sized at SEVEN screens by walking them; the code
#           held nine) · DEF-1704 (a TENTH the audit that filed DEF-1702 still
#           missed) · DEF-1701 (declared filters nothing rendered)
# Rules:    BR-SHL-010 (only DECLARED capabilities render) · BR-SHL-011
#           (`f.<name>`) · B14 rules 12 + 19
# ───────────────────────────────────────────────────────
"""CR-045's toolbar sweep — every `DataTable` on one page, with its four slots.

WHY THIS FILE EXISTS RATHER THAN A PARAGRAPH IN THE CR
------------------------------------------------------
DEF-1702's own prevention column asks for it in one sentence: *"Size a
UI-consistency wave from a mechanised sweep of every screen rendering the
component, and put the sweep in the CR so the number can be re-derived."*
Wave D was sized at seven screens from a WALK; the code held nine; a later
audit still missed a tenth (DEF-1704). **Every count taken by looking at this
surface has been wrong, three times running.**

⚠ **AND THE FIRST MECHANISED SWEEP WAS WRONG TOO, WHICH IS THE REASON THIS IS
A SCRIPT AND NOT THE SHELL ONE-LINER THE CR PRINTS.** That one asked two
questions — does the file declare `filters:` and does it render `<FilterBar` —
and **a third mechanism exists**: `filterBarSlot` can be handed something that
is not a `FilterBar` at all. Five worklist tabs hand it a `WorklistSegments`
strip, so the one-liner scores them exactly as it scores a screen with no
toolbar furniture whatsoever. That is not a rounding error: it is the
difference between *"this screen needs a filter built"* and *"this screen has
a control that does not work"*, and they are different fixes.

So this asks FOUR questions of every `DataTable`, and reports the SHAPE rather
than a boolean, because the shapes have different owners:

    SEARCH    `searchFields` declared (DataTable draws the box only then)
    FILTER    one of five distinct states, below
    DOWNLOAD  `downloadSlot` passed
    COLUMNS   universal — DataTable always draws the chooser

THE FIVE FILTER STATES, AND WHO OWNS EACH
------------------------------------------
    wired        the slot holds a `<FilterBar>` — B14 rule 12's own control
    custom       the slot holds a BESPOKE panel that is handed a state writer
                 (`AuditFilterPanel`, the templates `Filters`). It filters;
                 it just is not rule 12's chips. A divergence, not a defect
    inert        the slot holds a control wired to NOTHING — every handler it
                 gets is `() => undefined`
    declared     declares `filters:`, passes NO slot          → DEF-1701
    bare         neither                                      → DEF-1702/1704
    n/a          the file renders no `DataTable`

⚠ **`inert` IS THE STATE THIS SWEEP EXISTS TO NAME, AND THE FIRST DRAFT OF
THIS SCRIPT GOT IT WRONG.** Classifying "slot without a `<FilterBar>`" as inert
scored `AuditLogPage` and `TemplateCatalog` — which carry real, working
bespoke panels — identically to four worklist tabs whose `WorklistSegments`
strip is handed `onSelect={() => undefined}` and narrows nothing at all. Those
are opposite findings: one is a copy question for B14, the other is a control
that lies. So the test is not *"is it a FilterBar"* but **"is it handed
anything that can write state"**, which is the property that actually decides
whether clicking it does something.

⚠ **THIS READS SOURCE TEXT, NOT RENDERED OUTPUT, AND SO DOES EVERY GATE HERE
(hard-won law 6).** It can prove a screen is bare; it cannot prove a wired one
draws correctly in Chromium. That still needs the walk — this exists so the
walk is checking nine known screens instead of discovering them.

Usage:  python3 10-scripts/cr045_toolbar_sweep.py [--csv]
Exit 0 always: it is a MEASUREMENT, not a gate. G45 is the gate.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEATURES = ROOT / "07-frontend" / "src" / "features"

#: `filters: [` only. `filters: state.filters` and `filters: { ...state.filters }`
#: are request plumbing, not capability declarations — G45 draws the same line
#: and for the same reason: matching the bare key fires on every list.
DECLARES = re.compile(r"^\s*filters:\s*\[", re.M)
#: A prop that hands the slot's occupant a way to CHANGE the request state.
#: `onSelect={() => undefined}` is deliberately not one: it is the shape four
#: worklist tabs use, and it is the whole reason `inert` is a separate state.
STATE_WRITER = re.compile(
    r"on(?:StateChange|Q|Category|Filter|Change|Apply|Select)=\{(?!\s*\(\s*\)\s*=>\s*undefined)"
)
SLOT = re.compile(r"filterBarSlot=")
FILTERBAR = re.compile(r"<FilterBar")
DATATABLE = re.compile(r"<DataTable")
SEARCHFIELDS = re.compile(r"^\s*searchFields:\s*\[", re.M)
DOWNLOAD = re.compile(r"downloadSlot=")

LINE_COMMENT = re.compile(r"//[^\n]*")
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
JSX_COMMENT = re.compile(r"\{\s*/\*.*?\*/\s*\}", re.S)


def strip_comments(text: str) -> str:
    """Blank comments so a rule DESCRIBED is never counted as a rule APPLIED.

    Hard-won law 1 in its most literal form: three files once described an
    OpenAPI CI-diff that no workflow ran. A sweep that counted the sentence
    `⚠ NO filterBarSlot, and this is the stated absence` as a `filterBarSlot`
    would report the exact opposite of the truth on `TransfersTab`, which
    carries that sentence and passes no slot.
    """
    text = JSX_COMMENT.sub(" ", text)
    text = BLOCK_COMMENT.sub(" ", text)
    return LINE_COMMENT.sub(" ", text)


def slot_bodies(src: str) -> list[str]:
    """The JSX handed to each `filterBarSlot`, brace-matched.

    Brace-matched rather than regexed to the next `}`: every one of these slots
    contains nested JSX expressions, and a lazy match stops inside the first
    one — which reports the slot as empty and is how a control gets scored as
    absent while it is on the screen.
    """
    bodies = []
    for m in SLOT.finditer(src):
        i = src.find("{", m.end() - 1)
        if i < 0:
            continue
        depth = 0
        for j in range(i, len(src)):
            if src[j] == "{":
                depth += 1
            elif src[j] == "}":
                depth -= 1
                if depth == 0:
                    bodies.append(src[i : j + 1])
                    break
    return bodies


def classify(src: str) -> dict[str, object]:
    tables = len(DATATABLE.findall(src))
    declared = len(DECLARES.findall(src))
    bodies = slot_bodies(src)
    slots = len(bodies)
    bars = sum(1 for b in bodies if FILTERBAR.search(b))
    writers = sum(1 for b in bodies if STATE_WRITER.search(b))
    if tables == 0:
        state = "n/a"
    elif declared > 0 and slots < declared:
        state = "declared"      # DEF-1701 — the config nobody reads
    elif bars > 0:
        state = "wired"
    elif slots > 0 and writers > 0:
        state = "custom"        # a real panel, just not rule 12's chips
    elif slots > 0:
        state = "inert"         # a control wired to nothing at all
    else:
        state = "bare"          # DEF-1702 / DEF-1704
    return {
        "tables": tables,
        "filter": state,
        "search": len(SEARCHFIELDS.findall(src)),
        "download": len(DOWNLOAD.findall(src)),
    }


def main() -> int:
    rows = []
    for path in sorted(FEATURES.rglob("*.tsx")):
        if ".test." in path.name or ".dom." in path.name:
            continue
        raw = path.read_text(encoding="utf-8")
        if "<DataTable" not in raw:
            continue
        info = classify(strip_comments(raw))
        rows.append((str(path.relative_to(FEATURES.parent)), info))

    if "--csv" in sys.argv:
        print("screen,datatables,filter_state,search_decls,download_slots")
        for name, i in rows:
            print(f"{name},{i['tables']},{i['filter']},{i['search']},{i['download']}")
        return 0

    width = max(len(n) for n, _ in rows)
    print(f"{'SCREEN'.ljust(width)}  TBL  FILTER     SEARCH  DOWNLOAD")
    print("-" * (width + 34))
    for name, i in rows:
        print(
            f"{name.ljust(width)}  {i['tables']:>3}  {str(i['filter']).ljust(9)}"
            f"  {i['search']:>6}  {i['download']:>8}"
        )

    tally: dict[str, int] = {}
    for _, i in rows:
        tally[str(i["filter"])] = tally.get(str(i["filter"]), 0) + 1
    print("-" * (width + 34))
    print(f"screens rendering a DataTable : {len(rows)}")
    print(f"DataTable instances           : {sum(int(i['tables']) for _, i in rows)}")
    for state in ("wired", "custom", "declared", "inert", "bare"):
        print(f"  filter {state:<9}          : {tally.get(state, 0)}")
    print(f"screens with NO search box    : {sum(1 for _, i in rows if not i['search'])}")
    print(f"screens with NO download slot : {sum(1 for _, i in rows if not i['download'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
