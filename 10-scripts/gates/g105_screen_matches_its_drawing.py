#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CWP-3989 (audit row D14 — nothing in this repo compares a built
#          portal screen with its layout drawing) · the twenty-five rows whose
#          escape_reason it is
# Rules:   04-docs/05-modules/15-portal/08-screen-layouts.md (the drawing, and
#          this gate's ONLY source of truth about shape) · B14 rule 36 (compose
#          the shared kit) · CR-068 §13 · CLAUDE.md hard-won law 7 (proved RED
#          first, through run_gates and never through __main__ — DEF-GOV-3733)
# Tests:   selftest() below
# Impacts: 07-frontend/src/portal/routing/screenIds.ts · portalRoutes.tsx ·
#          every portal screen · g105_layout_baseline.txt
# ───────────────────────────────────────────────────────
"""G105 — every portal screen composes the TEMPLATE its drawing gives it.

WHY THIS EXISTS (audit row `D14`, `DEF-CWP-3989`)
-------------------------------------------------
On 2026-09-05 somebody opened all fifty portal addresses in a browser and
compared each with `08-screen-layouts.md`. **Twenty-five of the thirty-nine
screens that could be judged were short of their own drawing**, and the audit's
own verdict on why nothing caught it is the reason this file exists:

    Forty-two portal test files and 391 cases pass over all of the above,
    because each asserts the facts ITS screen shows rather than the shape the
    drawing gives it. A SCREEN THAT SHOWS THE RIGHT FACTS IN THE WRONG SHAPE
    PASSES EVERYTHING.

No gate read the drawing. No test cited it. This one reads it.

⚠ **THE DURABLE PART IS THE SOURCE, NOT THE ASSERTIONS.** Every other check in
this repo that knows anything about a portal screen carries its own hardcoded
list of screens, so the day the drawing changes the check goes quietly stale and
nothing says so. This gate derives the whole expectation from
`08-screen-layouts.md` at run time: change a screen's template there and the
gate changes its mind in the same commit. That is what makes it worth more than
the twenty-five rows it was written for.

WHAT IT ASKS — THE HEADING **AND THE BODY** (`DEF-CWP-4018`, 2026-09-05)
------------------------------------------------------------------------
The first version of this gate read a screen's HEADING only: the template code
after the em dash, plus any landmark the heading itself names in backticks. That
is **49 assertions over 46 screens** — and the drawing's own preamble says where
the rest of it lives:

    Each entry names the **frame**, the **template**, the **regions
    top-to-bottom** and the **components** from `09-component-inventory.md` — and
    nothing that is not in that inventory.

The *"exact pieces and their arrangement"* audit row D14 is about are in the
BODY. Reading the heading alone checked **42 of the 378 (screen, piece) pairs the
drawing states — eleven per cent** — and asked **thirteen screens nothing at all**,
because T6 and T7 carry no template landmark. So the body is read too: every
piece an entry names in backticks that the portal's shared kit actually exports.

    heading only     49 assertions · 46 screens · 6 distinct pieces
    heading + body  229 assertions · 50 screens · 28 distinct pieces

⚠ **THE VOCABULARY IS READ FROM THE KIT AT RUN TIME, NOT LISTED HERE.** A name in
a drawing that is not a kit export is prose or another app's component (`Button`,
`Select`, `R9`) and is not this gate's business. Add a piece to the kit, name it
in a screen's drawing, and this gate starts checking it in that commit — the same
property that makes reading the drawing worth more than hardcoding it.

⚠ **AND THE DRAWING'S NAME IS NOT ALWAYS THE BUILT NAME — THIS GATE SHIPPED
ASKING FOR A COMPONENT THE PORTAL DOES NOT HAVE.** The drawing's T5 is
`DataTable`; the portal's realisation of it is `PortalListTable`, deliberately
(`listTable.tsx` gives the reason: the staff `DataTable`'s CSS paints a grey
surface that is wrong on a white portal column). Matching tags raw, the first
version recorded **seven lists as owing a shape six of them already had** —
`CWP-023`, `CWP-027`, `CWP-031`, `CWP-034`, `CWP-037` and `CWP-041` had all been
given a toolbar, a search box, sortable headings, row icons and a footer in three
commits that landed BEFORE the gate did. The baseline said of them *"all eight
portal lists draw `MiniTable`, which is none of those"*, and that sentence was
already false when it was written. `ALIAS` is where a drawing name is resolved to
a built one, and every entry in it is verified against the source rather than
taken from a defect row — see the note there about `Panel`, which was nearly
aliased away and would have made this gate greener by being wrong.

THE THIRD LANDMARK: A LIST'S SEARCH BOX AND ITS FOOTER
-------------------------------------------------------
Audit row D14 named three landmarks — *"does it emit a page heading, does it
have a rail where the drawing gives it one, does a list have a search box and a
footer"*. The first belongs to `pageHeadCensus.test.ts`, the second is `TwoCol`.
The third is `furniture()`, and it is a separate question from composing the
table: a screen can render `PortalListTable` and pass no `search`, and audit
finding 2 was six lists with no search box, no sortable heading and no footer
between them.

It works because **every call site carries `screen="CWP-###"`**, so a list is
addressable individually. That matters: `Readings.tsx` and `Equipment.tsx` are
reached through one loader, and a union of their sources cannot tell one's
footer from the other's — the first draft of this clause reported CWP-034's
footer as wrong because CWP-037 next door had turned its own off.

WHAT IT STILL DOES NOT ASK
--------------------------
`PageHead` is deliberately absent: `portal/components/pageHeadCensus.test.ts`
(`DEF-CWP-4000`) is a census over the same source asking exactly that question,
and two checks on one fact are two checks that can disagree.

Sorting is not asked for. The drawing marks a sortable column `⇅` and
`PortalListTable` takes `sortable` per column; tying one to the other means
matching a column heading in prose to a column key in code, which is a guess.
Named here so it is a decision rather than a gap.

Presence, not arrangement. The drawing says *"main `Card` … rail `Panel`"* and
this gate asks only that both are composed somewhere in the screen. A screen that
puts the rail's panel in the main column passes. That is the honest limit of a
composition check and it is why the audit's DOM walk is still worth doing.

HOW A SCREEN IS RESOLVED — THREE HOPS, ALL STATIC
--------------------------------------------------
    08-screen-layouts.md   `### CWP-027 · P13 · Bills — T5`
      → screenIds.ts       `{ path: "/bills", id: "CWP-027" }`
      → portalRoutes.tsx   `{ path: "/bills", element: <BillsPage /> }`
      → the import of `BillsPage`, then the files IT reaches.

⚠ **THE LAST HOP IS NOT OPTIONAL AND THE FIRST DRAFT GOT IT WRONG.** Every
routed portal component is a LOADER — `BillsPage` fetches and renders
`<BillsView>` from another file — so the landmark is never in the file the route
names. A version of this gate that read only that file reported every screen in
the portal as shapeless, which is a check that cannot distinguish pass from
fail. It follows relative and `@/` imports into `src/portal/**` and
`src/components/**`, to a bounded depth, and takes the union of the JSX tags
that source renders.

WHAT IT THEREFORE CANNOT SEE, STATED SO NOBODY ASSUMES IT
----------------------------------------------------------
It reads source, not a rendered page. A screen that imports `TwoCol` and renders
it behind a condition that is never true passes here. It proves the narrower
thing — **the screen is composed from the shape its drawing gives it** — for
every screen at once, which is what nothing did before. A DOM walk of fifty
routed screens with their own mocked reads is the stronger check and it is not
this one; its cost is recorded in `DEF-CWP-3989`.

RATCHET, NOT A BAR — the repo's own G14/G29/G40 discipline
-----------------------------------------------------------
The portal diverges from its drawing today in ways four lanes are fixing right
now. A gate that failed on all of them would be reverted within the hour. So
today's divergences are recorded one per line in `g105_layout_baseline.txt`
**with the reason each is owed**, and the count MAY FALL and MAY NEVER RISE. A
fall must lower the baseline in the same commit, or the gate keeps claiming debt
that is already paid off.

⚠ **THE BASELINE FILE IS THE DELIVERABLE THAT OUTLIVES THE GATE.** It is the
worklist audit row D14 asks for, in one place, in the drawing's own vocabulary.

PROVEN RED BEFORE TRUSTED GREEN (law 7)
----------------------------------------
`selftest()` runs the whole resolver over in-memory sources and requires EIGHT
sabotages to bite — a T5 screen composing no list table, a T3 screen with no
rail, a screen whose heading names `KpiRow` and whose source has none, and two
BODY pieces (a `ButtonRow` and a `Card`) on a T7 screen the heading asks nothing
of. It also requires: the healthy shape to pass, so the gate cannot be green by
matching nothing; a DEFERRED entry to be silent; an unrouted screen to be silent;
the body to be read at all; and the drawing's `DataTable` to resolve to
`PortalListTable` while NOT resolving to `MiniTable`.

⚠ It runs inside `run()`, which is the entry point `run_gates.py` calls. A gate
proved only by `python3 <gate>.py` is proved through `__main__` and not through
the path the suite uses — `DEF-GOV-3733`, where two gates were announced green
while the suite reported they had no callable `run`.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DRAWING = REPO / "04-docs" / "05-modules" / "15-portal" / "08-screen-layouts.md"
SRC = REPO / "07-frontend" / "src"
SCREEN_IDS = SRC / "portal" / "routing" / "screenIds.ts"
ROUTES = SRC / "portal" / "routing" / "portalRoutes.tsx"
BASELINE = Path(__file__).with_name("g105_layout_baseline.txt")

#: The handful the TEMPLATE codes stand for. Each is a SHAPE the drawing states
#: and a screen can fail while showing entirely correct facts. `PageHead` is
#: deliberately absent — see the docstring; it belongs to `pageHeadCensus.test.ts`.
LANDMARKS = ("CardGrid3", "Stepper", "TwoCol", "TwoEqual", "DataTable", "KpiRow")

#: ⚠ **THE DRAWING'S NAME IS NOT ALWAYS THE BUILT NAME, AND READING TAGS RAW
#: MADE THIS GATE ASK FOR A COMPONENT THE PORTAL DOES NOT HAVE (`DEF-CWP-4018`).**
#: `08-screen-layouts.md` is written in `09-component-inventory.md`'s vocabulary,
#: and the inventory says so out loud — its `DataTable` entry reads *"staff
#: `DataTable` + `FilterBar` + `ListPager`, one table type"*. The portal's
#: realisation of that one table type is `PortalListTable` in
#: `portal/components/listTable.tsx`, and **no portal screen renders a tag
#: called `DataTable` — nor will one ever.** So the first version of this gate
#: recorded seven lists as owing a shape six of them had already been given, in
#: a worklist its own docstring calls the deliverable that outlives it.
#: Each entry is `drawing name -> the name the portal builds it under`.
ALIAS = {
    # The inventory's own words, above. `PortalListTable` IS the toolbar ·
    # sortable headings · row icons · footer the drawing's T5 asks for.
    "DataTable": "PortalListTable",
    # `DEF-CWP-3966` recorded this pair while measuring three screens by hand:
    # *"the spec's Panel is the kit's Card and its ChartPanel is UsageBars — I
    # nearly reported the chart missing when wave H had added it days ago."*
    # ⚠ **ONLY THE SECOND HALF OF THAT SENTENCE SURVIVED CHECKING, AND THE FIRST
    # HALF IS WORTH KEEPING HERE AS THE WARNING IT IS.** `Panel` was written into
    # this map on that row's authority and then taken out again: there IS a
    # `Panel`, at `src/components/Panel.tsx`, and `portal/guest/HelpPage.tsx`
    # and `CentresPage.tsx` render ten of them between them. Aliasing it to
    # `Card` would have quietly excused every screen that draws a `Panel` where
    # its drawing says `Card` — the gate would have gone GREENER by being wrong,
    # which is the failure this whole file exists to stop. `ChartPanel` stays,
    # and it is verified the same way rather than taken on trust: nothing under
    # `src/portal/**` or `src/components/**` defines or renders a `ChartPanel`
    # at all, so a screen could not compose one if it wanted to.
    "ChartPanel": "UsageBars",
}

#: Where the portal's shared kit lives. The vocabulary this gate will hold a
#: screen to is READ FROM THESE FILES AT RUN TIME rather than listed here, for
#: the same reason the expectation is read from the drawing: a hardcoded list
#: goes quietly stale and nothing says so. Add a piece to the kit, name it in a
#: screen's drawing, and this gate starts checking it in that commit.
KIT_FILES = ("primitives.tsx", "content.tsx", "listTable.tsx")
KIT_EXPORT = re.compile(r"^export (?:function|const) ([A-Z][A-Za-z0-9_]*)", re.M)

#: Pieces the drawing names that the portal borrows from the PRODUCT-WIDE kit
#: rather than owning. `Panel` is the rail's panel and it is the single most
#: drawn piece in the whole file — 35 of the 229 assertions this gate makes. It
#: is read from its own source for the same reason the portal kit is: so the
#: gate cannot ask for something that does not exist.
SHARED_FILES = (("Panel.tsx", "Panel"),)

#: Template → the one landmark that template's shape is. T6 and T7 carry none,
#: on purpose and for the reason the docstring gives.
TEMPLATE_LANDMARK = {
    "T1": "CardGrid3",
    "T2": "Stepper",
    "T3": "TwoCol",
    "T4": "TwoEqual",
    "T5": "DataTable",
}

#: A drawing entry that says the screen is not to be built is not a divergence.
#: The words are the drawing's own.
NOT_BUILT = re.compile(r"DEFERRED|do not build|\*\*blocked\*\*", re.I)

HEADING = re.compile(r"^### (CWP-\d+)\s*·\s*\S+\s*·\s*(.+?)\s*—\s*(.+)$", re.M)
ID_ROW = re.compile(r'\{\s*path:\s*"([^"]+)"\s*,\s*id:\s*"(CWP-\d+)"')
ROUTE_ROW = re.compile(r'\{\s*path:\s*"([^"]+)"\s*,\s*element:\s*<([A-Za-z0-9_]+)')
IMPORT_LINE = re.compile(r'import\s*(?:type\s*)?\{([^}]*)\}\s*from\s*"([^"]+)"', re.S)
JSX_TAG = re.compile(r"<([A-Z][A-Za-z0-9_]*)")
#: Dotted, so the drawing's `Panel.Warning` / `Panel.Info` / `Panel.Emergency`
#: variants are read as the piece they are a variant OF.
TICKED = re.compile(r"`([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*)`")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def kit_vocabulary() -> set[str]:
    """Every piece the portal's shared kit exports, read from the kit itself.

    This is the set of names the gate is willing to hold a screen to. A name in
    a drawing that is NOT a kit export is prose or another app's component
    (`Button`, `PageHead`, `Select`) and is not this gate's business — `PageHead`
    in particular belongs to `pageHeadCensus.test.ts`, see the docstring.
    """
    names: set[str] = set()
    for fname in KIT_FILES:
        names |= set(KIT_EXPORT.findall(_read(SRC / "portal" / "components" / fname)))
    # A borrowed piece counts only if it really is exported from where we think.
    # ⚠ This clause is the one that caught `Panel` being aliased away to `Card`
    # on the strength of a hand-written defect row (see `ALIAS`).
    for fname, export in SHARED_FILES:
        if export in KIT_EXPORT.findall(_read(SRC / "components" / fname)):
            names.add(export)
    return names


def parse_drawing(text: str, vocabulary: set[str] | None = None) -> dict[str, set[str]]:
    """`CWP-###` -> every piece its drawing entry asks it to compose.

    TWO SOURCES, AND THE SECOND ONE IS THE POINT (`DEF-CWP-4018`):

    * **the heading** — the template codes after the em dash (`T6 + T5` is two of
      them) and any landmark the heading names in backticks (`T3 with a KpiRow
      first`). This is all the first version of the gate read, and it is 49
      assertions over 46 screens;
    * **the body** — every kit piece the entry names in backticks. The drawing's
      own preamble says each entry *"names the frame, the template, the regions
      top-to-bottom and the components from `09-component-inventory.md` — and
      nothing that is not in that inventory"*, so the body is where *"the exact
      pieces and their arrangement"* actually live. Reading only the heading
      checked **42 of the 378 (screen, piece) pairs the drawing states**; reading
      the body takes the assertions to 229.

    A screen the drawing says is not to be built is dropped — a drawing for the
    record is not a promise. `vocabulary` defaults to the live kit; the selftest
    passes its own so it can run with no `src/` at all.
    """
    vocab = kit_vocabulary() if vocabulary is None else vocabulary
    allowed = vocab | set(ALIAS)
    wanted: dict[str, set[str]] = {}
    entries = list(HEADING.finditer(text))
    for i, m in enumerate(entries):
        screen, spec = m.group(1), m.group(3)
        end = entries[i + 1].start() if i + 1 < len(entries) else len(text)
        body = text[m.end():end]
        if NOT_BUILT.search(spec) or NOT_BUILT.search(body[:400]):
            continue
        marks = {TEMPLATE_LANDMARK[t] for t in re.findall(r"\bT[1-8]\b", spec) if t in TEMPLATE_LANDMARK}
        marks |= {n for n in TICKED.findall(spec) if n in LANDMARKS}
        marks |= {n.split(".")[0] for n in TICKED.findall(body)} & allowed
        # ⚠ **NORMALISE TO THE NAME THE PORTAL BUILDS IT UNDER, HERE, ONCE.** The
        # drawing calls the same piece two things in one entry — `Panel` in the
        # rail and `Card` in the main column are both the kit's `Card` — so a
        # mark set left in the drawing's words carries the same requirement
        # twice and the worklist grows a line that can never be closed on its
        # own. Normalising also makes the baseline name the component a lane has
        # to import, which is the thing they need.
        marks = {ALIAS.get(n, n) for n in marks}
        if marks:
            wanted[screen] = marks
    return wanted


def composes(mark: str, drawn: set[str]) -> bool:
    """Is the drawing's `mark` present, under the drawing's name OR the name the
    portal actually builds it under? See `ALIAS` — reading tags raw is what made
    this gate demand `DataTable` of seven screens that had already been given
    exactly that shape as `PortalListTable`."""
    return mark in drawn or ALIAS.get(mark, mark) in drawn


def _module_to_path(spec: str, importer: Path) -> Path | None:
    """A TS module specifier to a file on disk, or None if it leaves our reach."""
    if spec.startswith("@/"):
        base = SRC / spec[2:]
    elif spec.startswith("."):
        base = (importer.parent / spec).resolve()
    else:
        return None                      # a package, never a screen of ours
    for cand in (base.with_suffix(".tsx"), base.with_suffix(".ts"),
                 base / "index.tsx", base / "index.ts"):
        if cand.is_file():
            return cand
    return None


def rendered_tags(entry: Path, depth: int = 4) -> set[str]:
    """Every JSX tag the source reachable from `entry` renders.

    Bounded, and confined to `src/portal/**` and `src/components/**`: a screen's
    loader renders a view in another file (see the docstring), so one file is
    never the answer, and the whole of `src/` would be.
    """
    seen: set[Path] = set()
    tags: set[str] = set()
    frontier = [(entry, depth)]
    while frontier:
        path, left = frontier.pop()
        if path in seen or not path.is_file() or path.name.endswith(".test.tsx"):
            continue
        seen.add(path)
        text = _read(path)
        tags |= set(JSX_TAG.findall(text))
        if left <= 0:
            continue
        for names, spec in IMPORT_LINE.findall(text):
            if not any(n.strip()[:1].isupper() for n in names.replace("\n", " ").split(",") if n.strip()):
                continue                 # nothing component-shaped comes in here
            nxt = _module_to_path(spec, path)
            if nxt and (SRC / "portal") in nxt.parents or nxt and (SRC / "components") in nxt.parents:
                frontier.append((nxt, left - 1))
    return tags


def screen_sources() -> tuple[dict[str, Path], list[str]]:
    """`CWP-###` -> the file its route mounts, plus screens with no route."""
    paths = {sid: p for p, sid in ID_ROW.findall(_read(SCREEN_IDS))}
    routes_text = _read(ROUTES)
    by_path = dict(ROUTE_ROW.findall(routes_text))
    where: dict[str, str] = {}
    for names, spec in IMPORT_LINE.findall(routes_text):
        for raw in names.replace("\n", " ").split(","):
            name = raw.strip().split(" as ")[-1].strip()
            if name:
                where[name] = spec
    out: dict[str, Path] = {}
    unrouted: list[str] = []
    for sid, path in paths.items():
        comp = by_path.get(path)
        spec = where.get(comp or "")
        file = _module_to_path(spec, ROUTES) if spec else None
        if file:
            out[sid] = file
        else:
            unrouted.append(sid)
    return out, unrouted


def divergences(
    drawing_text: str | None = None,
    sources: dict[str, Path] | None = None,
    tags_of=None,
    vocabulary: set[str] | None = None,
) -> list[str]:
    """`CWP-### <Piece>` for every piece a screen's drawing gives it and its
    source does not compose. Sorted, so the baseline is a stable set."""
    wanted = parse_drawing(
        drawing_text if drawing_text is not None else _read(DRAWING), vocabulary
    )
    if sources is None:
        sources, _ = screen_sources()
    tags_of = tags_of or rendered_tags
    found: list[str] = []
    for sid, marks in wanted.items():
        entry = sources.get(sid)
        if entry is None:
            continue                     # no route: G82's question, not this one
        drawn = tags_of(entry)
        for mark in sorted(marks):
            if not composes(mark, drawn):
                found.append(f"{sid} {mark}")
    return sorted(found)


#: The one list table, and the two props the drawing has an opinion about.
#: Every call site carries `screen="CWP-###"` (its `data-list` hook), so a list
#: is addressable INDIVIDUALLY — which matters, because `Readings.tsx` and
#: `Equipment.tsx` are reached through one loader and a union of their sources
#: cannot tell one's footer from the other's.
LIST_CALL = re.compile(r"<PortalListTable\b")
LIST_SCREEN = re.compile(r'screen="(CWP-\d+)"')


def list_call_sites() -> dict[str, tuple[bool, bool]]:
    """`CWP-###` -> (passes a search box, turns the footer off).

    Only a file holding EXACTLY ONE `<PortalListTable` is read, so the props
    found in it can only belong to that one call. A file that grows a second
    list drops out of this check rather than being guessed at, and the piece
    check above still covers it.
    """
    out: dict[str, tuple[bool, bool]] = {}
    for path in sorted((SRC / "portal").rglob("*.tsx")):
        if ".test." in path.name or ".dom." in path.name:
            continue
        text = _read(path)
        if len(LIST_CALL.findall(text)) != 1:
            continue
        m = LIST_SCREEN.search(text)
        if m:
            out[m.group(1)] = (_draws_a_search_box(text), "footer={false}" in text)
    return out


#: THE THREE SPELLINGS OF *this list has a search box*, and the gate has to know
#: all three or it reports a screen for a control that is on it.
#:
#: ⚠ **WIDENED 2026-09-19 (`DEF-CWP-5747`), AND IT IS STRICTER RATHER THAN
#: LOOSER — IT SEES TWO SHAPES IT COULD NOT SEE.** `search=` was the only one
#: this gate knew, and it stopped being the whole truth twice:
#:
#:   1. `DEF-CWP-4879` (2026-09-11) moved `CWP-041`'s box OUT of the table,
#:      because the table lives inside `max-md:hidden` and a box drawn by it
#:      does not exist on a phone at all. The screen has drawn its own
#:      `type="search"` input ever since and this gate has reported it as
#:      MISSING for eight days — dated by running `furniture()` at the tip.
#:   2. `DEF-CWP-5747` (this commit) moved the predicate to the SERVER on five
#:      lists, so the placeholder travels on the window — `search: { placeholder`
#:      — rather than as a `search=` prop. Without this clause the gate would
#:      have reported `CWP-023` and `CWP-027` for a box that is on the screen.
#:
#: This is `G13`'s widening in another family: a gate that knows ONE idiom
#: reports zero over the ones it cannot see, and *"a declared blind spot with no
#: number attached is indistinguishable from an empty one"* (hard-won law 7).
SEARCH_IDIOMS = (
    "search=",                 # the prop, client-held
    "search: { placeholder",   # the server window's, `DEF-CWP-5747`
    'type="search"',           # the screen's own box, `DEF-CWP-4879`
)


def _draws_a_search_box(text: str) -> bool:
    return any(idiom in text for idiom in SEARCH_IDIOMS)


def furniture(drawing_text: str | None = None, calls: dict | None = None) -> list[str]:
    """`CWP-### search` / `CWP-### footer` where a list's toolbar or footer is
    not what its drawing says.

    ⚠ **THIS IS THE THIRD OF THE THREE LANDMARKS AUDIT ROW D14 NAMED** — *"does
    it emit a page heading, does it have a rail where the drawing gives it one,
    **does a list have a search box and a footer**"*. The first belongs to
    `pageHeadCensus.test.ts`, the second is `TwoCol` above, and this is the
    third. Composing the table is not the same as composing its furniture: a
    screen can render `PortalListTable` and pass no `search`, and finding 2 of
    the audit was six lists with no search box, no sortable heading and no page
    footer between them.

    ONLY entries that NAME `DataTable` are judged. `CWP-046`'s drawing gives it
    a `MiniTable` inside a `Panel` — no toolbar and no footer by definition —
    and the screen builds it with `PortalListTable` and `footer={false}`. That
    is a real divergence and it is the PIECE check's to make, not this one's;
    judging it here would report *"the footer is wrong"* about a screen whose
    footer is the only part that is right.
    """
    text = drawing_text if drawing_text is not None else _read(DRAWING)
    calls = list_call_sites() if calls is None else calls
    found: list[str] = []
    entries = list(HEADING.finditer(text))
    for i, m in enumerate(entries):
        sid, spec = m.group(1), m.group(3)
        end = entries[i + 1].start() if i + 1 < len(entries) else len(text)
        body = text[m.end():end]
        if NOT_BUILT.search(spec) or NOT_BUILT.search(body[:400]):
            continue
        if "DataTable" not in body and "DataTable" not in spec:
            continue
        if sid not in calls:
            continue                     # composes no list at all — the piece check's finding
        has_search, footer_off = calls[sid]
        # ⚠ **THE PHRASES ARE MATCHED OVER UNWRAPPED TEXT (`DEF-CWP-5747`,
        # 2026-09-19).** `08-screen-layouts.md` is hand-wrapped prose, so
        # `CWP-037`'s own words — *"Status (StatusChip …), no footer"* — fall
        # across a line break as `no\nfooter`, and a substring test for
        # `"no footer"` could not see the drawing saying exactly what it says.
        # This gate reported that screen's footer as WRONG for as long as the
        # wrap has been there, over a screen whose footer is the only part that
        # is right — law 7's *looking at the wrong thing*, caused by a newline.
        flat = " ".join(body.split())
        if ("toolbar search" in flat or "toolbar: search" in flat) and not has_search:
            found.append(f"{sid} search")
        if ("no footer" in flat) != footer_off:
            found.append(f"{sid} footer")
    return sorted(found)


def _load_baseline() -> set[str]:
    text = _read(BASELINE)
    return {
        line.split("#", 1)[0].strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    } - {""}


def selftest() -> str | None:
    """Six sabotages must bite and the healthy shape must pass (law 7).

    ⚠ **RUN FROM `run()`, WHICH IS THE PATH `run_gates.py` USES** — a gate proved
    only through `python3 <gate>.py` is proved through `__main__` and not through
    the entry point the suite calls (`DEF-GOV-3733`, where two gates were
    announced green while the suite reported they had no callable `run`).
    """
    drawing = (
        "### CWP-900 · P1 · A list — T5\n`DataTable` here.\n\n"
        "### CWP-901 · P2 · A page with a rail — T3\nrail.\n\n"
        "### CWP-902 · P3 · Big numbers — T3 with a `KpiRow` first\n\n"
        "### CWP-903 · P4 · Not served — T5\n\n"
        "### CWP-904 · P5 · Deferred — T5 — **DEFERRED, do not build**\n\n"
        "### CWP-905 · P6 · A focused task — T7\n"
        "main `Card` [`KVList` two rows · `ButtonRow` one control] · "
        "rail [`Panel.Warning` nothing can charge a card].\n"
    )
    vocab = {"Card", "KVList", "ButtonRow", "TwoCol", "KpiRow", "PortalListTable", "UsageBars"}
    healthy = {
        "CWP-900": {"PortalListTable"},          # the BUILT name, never `DataTable`
        "CWP-901": {"TwoCol"},
        "CWP-902": {"TwoCol", "KpiRow"},
        "CWP-905": {"Card", "KVList", "ButtonRow"},
    }
    src = {k: Path(f"/{k}") for k in healthy}
    if parse_drawing(drawing, vocab).get("CWP-904") is not None:
        return "a drawing entry marked DEFERRED was still required"
    if parse_drawing(drawing, vocab).get("CWP-902") != {"TwoCol", "KpiRow"}:
        return "a landmark named in a screen's own heading was not read from it"
    # ── The body, which the first version of this gate never opened. CWP-905 is
    #    T7: it carries NO template landmark at all, so heading-only reading
    #    asked it nothing. Its body names three kit pieces and a `Panel.Warning`.
    if parse_drawing(drawing, vocab).get("CWP-905") != {"Card", "KVList", "ButtonRow"}:
        # `Panel.Warning` in the rail and `Card` in the main column are ONE
        # requirement, not two — see the normalisation in `parse_drawing`.
        return (
            "the pieces a screen's drawing BODY names were not read — this gate "
            "would be back to checking 42 of the 378 pairs the drawing states"
        )

    def tags(entry: Path, _d: int = 4) -> set[str]:
        return set(healthy[entry.name])

    if divergences(drawing, src, tags, vocab):
        return "the healthy shape did not pass — this gate would fail everything"
    for sabotage, expect in (
        ({"CWP-900": set()}, "CWP-900 PortalListTable"),
        ({"CWP-901": set()}, "CWP-901 TwoCol"),
        ({"CWP-902": {"TwoCol"}}, "CWP-902 KpiRow"),
        # The body's own three, one per kind: a panel, a list of facts, a row of
        # controls. Each is a shape a screen can miss while its facts are right.
        ({"CWP-905": {"Card", "KVList"}}, "CWP-905 ButtonRow"),
        ({"CWP-905": {"KVList", "ButtonRow"}}, "CWP-905 Card"),
    ):
        broken = dict(healthy) | sabotage

        def broken_tags(entry: Path, _d: int = 4, _b=broken) -> set[str]:
            return set(_b[entry.name])

        if expect not in divergences(drawing, src, broken_tags, vocab):
            return f"sabotage did not bite: expected {expect!r}"
    # ── `DEF-CWP-4018`: the drawing's name is not always the built name. CWP-900
    #    composes `PortalListTable` and is HEALTHY above; a gate that matched tags
    #    raw would report it as owing `DataTable` forever, which is exactly the
    #    seven stale worklist lines this clause was written for.
    if parse_drawing(drawing, vocab).get("CWP-900") != {"PortalListTable"}:
        return (
            "the drawing's `DataTable` was not resolved to the name the portal "
            "builds it under — this gate would demand a component no portal "
            "screen renders, which is DEF-CWP-4018 all over again"
        )
    if composes("DataTable", {"MiniTable"}):
        return "the alias map matched too much — MiniTable is not the T5 table"
    # ── The third landmark D14 named: a list's search box and its footer.
    fdraw = (
        "### CWP-910 · P7 · A searchable list — T5\n"
        "`DataTable` toolbar search · columns · footer.\n\n"
        "### CWP-911 · P8 · A short list — T5\n"
        "`DataTable` columns · icons, no footer.\n\n"
        "### CWP-912 · P9 · A panel table — T3\n`Panel` with a `MiniTable` inside.\n"
    )
    ok = {"CWP-910": (True, False), "CWP-911": (False, True), "CWP-912": (False, True)}
    if furniture(fdraw, ok):
        return f"the healthy list furniture did not pass: {furniture(fdraw, ok)}"
    for broken, expect in (
        ({"CWP-910": (False, False)}, "CWP-910 search"),   # toolbar search, none passed
        ({"CWP-910": (True, True)}, "CWP-910 footer"),     # footer drawn, turned off
        ({"CWP-911": (False, False)}, "CWP-911 footer"),   # "no footer", left on
    ):
        if expect not in furniture(fdraw, dict(ok) | broken):
            return f"list-furniture sabotage did not bite: expected {expect!r}"
    # `CWP-912`'s drawing names no `DataTable`, so its footer is not judged here
    # even though it is turned off — see `furniture()`.
    if any(d.startswith("CWP-912") for d in furniture(fdraw, dict(ok) | {"CWP-912": (False, False)})):
        return "a screen whose drawing names no DataTable was judged on its list furniture"
    # ── THE TWO THINGS WIDENED ON 2026-09-19 (`DEF-CWP-5747`), EACH PROVED
    #    BOTH WAYS. A widening that only ever answers *yes* is a check that
    #    cannot fail (law 7), which is worse than the blind spot it replaced.
    #
    # (a) THE THREE SPELLINGS OF A SEARCH BOX. Each must be SEEN, and a file
    #     with none of them must still be reported.
    for idiom in SEARCH_IDIOMS:
        if not _draws_a_search_box(f"<PortalListTable screen=\"CWP-910\" {idiom} …"):
            return f"a search box written as {idiom!r} was not seen — the gate would report it missing"
    if _draws_a_search_box('<PortalListTable screen="CWP-910" rows={rows} />'):
        return (
            "a list with NO search box of any kind was read as having one — this "
            "widening would have turned the search check off rather than taught it"
        )
    #
    # (b) THE DRAWING'S PHRASES SURVIVE ITS OWN LINE WRAPPING. `08-screen-
    #     layouts.md` is hand-wrapped, so `CWP-037`'s *"…, no footer →"* falls
    #     across a newline; a substring test for `"no footer"` could not see it
    #     and this gate reported that screen for as long as the wrap existed.
    wrapped = (
        "### CWP-913 · P10 · A wrapped short list — T5\n"
        "`DataTable` columns · icons, no\nfooter → `InfoBar`.\n"
    )
    if furniture(wrapped, {"CWP-913": (False, True)}):
        return (
            "a drawing that says `no footer` across a LINE BREAK was still read as "
            "asking for a footer — the phrase test is back to reading raw text"
        )
    if "CWP-913 footer" not in furniture(wrapped, {"CWP-913": (False, False)}):
        return (
            "unwrapping the drawing turned the footer check OFF — a screen that "
            "draws a footer its drawing refuses is no longer reported"
        )
    # A drawing entry with no route must be silent here, not a false finding.
    if any(d.startswith("CWP-903") for d in divergences(drawing, src, tags, vocab)):
        return "a screen with no route was reported as a layout divergence (G82's question)"
    return None


def run() -> tuple[str, str]:
    if not DRAWING.is_file():
        return "SKIP", f"nothing to check — {DRAWING.name} not present"
    if not SRC.is_dir():
        return "SKIP", "nothing to check — 07-frontend/src not present"

    failure = selftest()
    if failure:
        return "FAIL", (
            f"SELF-TEST FAILED: {failure}. A check whose output cannot distinguish "
            f"pass from fail is worse than no check, because it is trusted."
        )

    wanted = parse_drawing(_read(DRAWING))
    sources, unrouted = screen_sources()
    found = sorted(set(divergences()) | set(furniture()))
    baseline = _load_baseline()
    new = sorted(set(found) - baseline)
    paid = sorted(baseline - set(found))

    if new:
        return "FAIL", (
            f"{len(new)} screen(s) do not compose a piece their drawing names, and "
            f"are not in {BASELINE.name}: {'; '.join(new[:6])}"
            f"{f' (+{len(new) - 6} more)' if len(new) > 6 else ''}. "
            f"08-screen-layouts.md names the pieces and their arrangement per screen; a screen "
            f"that shows the right facts in the WRONG SHAPE passes every other check in this "
            f"repo (audit row D14, DEF-CWP-3989). Compose the piece, or — if the drawing is "
            f"what is wrong — amend it there and this gate changes its mind with it."
        )
    if paid:
        return "FAIL", (
            f"{len(paid)} baselined divergence(s) are now composed — delete them from "
            f"{BASELINE.name} in the SAME commit, or the ratchet keeps claiming debt that is "
            f"already paid off: {'; '.join(paid[:8])}"
        )

    measured = sum(len(v) for k, v in wanted.items() if k in sources)
    pieces = len({m for k, v in wanted.items() if k in sources for m in v})
    lists = len(list_call_sites())
    return "PASS", (
        f"{len(sources)} routed portal screen(s) read against 08-screen-layouts.md, heading "
        f"AND body; {measured} piece(s) asked for by the drawing across {pieces} distinct kit "
        f"components, plus the toolbar and footer of {lists} list(s); {len(found)} owed and all "
        f"{len(baseline)} of them baselined with a reason; "
        f"{len(unrouted)} drawn screen(s) have no route (G82's question, not this "
        f"one); self-test: the healthy shape passes and all eight sabotages bite"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 0 if status in ("PASS", "SKIP") else 1


if __name__ == "__main__":
    raise SystemExit(main())
