#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Rule:     ⚠ **AMENDED 2026-09-28 BY PO RULING — `CR-151-BRC09`.** A build HAS
#           its own page again, at `/{tenant}/connections/{id}`, with seven
#           tabs (Overview · Units · Work · Charges · Documents · Messages ·
#           Audit). The Product Owner was shown three options — leave it, a
#           summary panel on the list, a full page — and chose the third. **So
#           the question this gate asked until today is now the wrong way
#           round**: every link to that address is correct, and a gate refusing
#           them would refuse the build it exists to protect.
#           ⚠ **EXACTLY ONE CLAUSE OF THE 2026-09-04 RULING MOVED, AND THIS
#           GATE NOW GUARDS THE REST.** `CR-070` §W.10 / §W.11 (PO 2026-09-04)
#           — *"youa re duplcaiting this - there is nothing called as
#           conenctions; Connection = Account only - you cannot have two
#           differnt screen - this is an integration problem"*, scoped the same
#           day: *"One screen too many. The objection is the duplicate
#           destination — a person should reach the build's progress, its
#           units, its work orders and its charges from the account, not from a
#           parallel screen."* **The objection was never *a page is wrong*. It
#           was *two places holding the same facts is wrong*, and that has not
#           moved an inch.** The Product Owner restated it themselves on
#           2026-09-28 by taking *Open premises* and *Open account* off the new
#           page's header — *"since we have given link for them in overview"*.
#           Wave-O judgments (2) and (3) are UNCHANGED and are what this file
#           now checks: money and its trail are facts about a PAYER, so the
#           page LINKS to the account rather than re-implementing or re-hosting
#           it; and the panels live ONCE and are composed.
# Rules:    B14 rule 43 (2026-09-20 — a piece of UI is built as a COMPONENT;
#           standalone code inside a page is not reuse) · CLAUDE.md hard-won
#           law 2 (built is not wired) · law 6 (no gate looks at rendered
#           output) · law 7 (prove a guard RED before trusting it green, IN THE
#           HARNESS THAT RUNS IT; and print what you SKIPPED beside what you
#           checked)
# Tests:    selftest() below (23 clauses) ·
#           07-frontend/src/features/work/buildViews.test.tsx ·
#           07-frontend/src/features/work/buildAddress.route.test.tsx — the
#           OTHER half of `CR-151-BRC09` R3, and the one this gate cannot do:
#           it fires the day the route is flipped and demands the screen id
#           back. This gate asks whether the page is a COPY; that test asks
#           whether the address and the screen-id map still tell one story.
# Impacts:  every commit that touches 07-frontend/src
# ───────────────────────────────────────────────────────
"""G93 — a build's panels live ONCE, and its money is the account's.

WHAT IT ASKS, IN THREE SENTENCES
---------------------------------
1. **Is a build panel DEFINED anywhere but its one home?**  A copy is the
   duplication the Product Owner objected to, wearing a different file name.
2. **Does the page mounted at the build address COMPOSE that home?**  A page
   that imports none of it has written its own, which is how the last one
   reached 1,464 lines.
3. **Does that page reach for the account's MONEY?**  Bills, payments,
   adjustments and journal lines are facts about a PAYER. The page links to
   them; it does not read them and it does not re-host the account's own tabs.

WHAT THIS FILE USED TO ASK, AND WHY THAT QUESTION WAS RETIRED
--------------------------------------------------------------
Until 2026-09-28 it asked *"does anything in the front end still send a person
to `/connections/<id>`?"*, because wave `O` had deleted the page and left the
address as a redirect. **That is now backwards.** The address is a page, the
links to it are the correct build, and the old body would have gone RED on
every one of them.

⚠ **AND THE OLD QUESTION HAD BEEN ANSWERING *FAIL* FOR SIX DAYS, WRONGLY, WITH
NOBODY READING IT.** Measured before this rewrite by running the previous body
against today's tree: **RED on `features/customers/ApplicationBecomesABuild.dom
.test.tsx:111` and `:155`**, which are `url.includes(\`/connections/${BUILD_ID}\`)`
inside a fetch stub — an **API** path, which §W.10 is explicit is still mounted,
still correct and still called. The exemption that was supposed to cover it
("`*Endpoints.ts` are exempt as a class") could not, because a `.dom.test.tsx`
stubbing `fetch` is not an endpoints module. Those lines arrived in `c6caadf2f`
on **2026-09-22**; `12-governance/23-gate-suite-baseline-2026-09-25.md` recorded
the failure on 2026-09-25 and marked it **UNDATED**, and three days later it was
still there. **A guard is a claim only while somebody reads its output** — law 7
— and the rewrite closes it not by widening an exemption but because the new
question does not ask about that path at all.

⚠ **THE GATE WAS AMENDED RATHER THAN DELETED, AND THAT WAS A CHOICE.** Deleting
it was the other option and it was refused: the duplication it guards is the
whole reason the last page was removed, and the ruling that brings the page
back explicitly keeps both rules that killed it. A gate that cannot fail is
worse than none — so if the checks below ever stop being able to bite, say so
out loud rather than leaving a green line that means nothing.

⚠ **THE FILE NAME AND THE SUITE LABEL STILL SAY `one-build-destination`, AND
THAT IS DELIBERATE RATHER THAN AN OVERSIGHT — READ THIS PARAGRAPH BEFORE
"FIXING" EITHER.** Renaming the module means editing `run_gates.py` in two
places (`GATES` and the label cross-check that refuses a mismatch), which is a
hot shared file two sibling lanes were running while this was written — law
11's revert-by-subtraction, on the one file that decides whether any gate runs
at all. It would also break the row in
`12-governance/23-gate-suite-baseline-2026-09-25.md` and the run-to-run
comparison in `last-run.json`, which key on the label. **The id is what
everything cites and the id has not moved.** What the gate ASKS is the three
sentences above; the name is where it came from. Say so here rather than leave
a reader to infer it from a title that is now history.

⚠ **AND NOTHING ELSE IN THIS REPO WOULD SEE ANY OF IT.** `tsc` is happy with a
second copy of a panel; it is a different symbol. eslint is happy. Every test
that asserts a panel renders would pass, because it DOES render — twice, in two
files, drifting apart from the day the second one lands. No gate reads rendered
output (law 6), so the only symptom is a clerk reading two different numbers for
one build.

1 · COMPOSED, NOT COPIED
-------------------------
A **build panel** is an exported component whose name starts `Build`,
`WorkOrder(s)` or `Connection` AND ends in a UI noun (`Panel`, `Tab`, `Tiles`,
`Header`, `Actions`, `Banner`, `Cell`, …). It may be DEFINED only in:

    07-frontend/src/features/work/buildViews.tsx      ← the composition
    07-frontend/src/features/work/buildRecord/*.tsx   ← its component kit

Defined anywhere else, it is a copy. **Every host imports; nothing redeclares.**

⚠ **`Page` IS NOT A UI NOUN HERE, ON PURPOSE.** `features/integrations/
ConnectionDetailPage.tsx` is a CONNECTOR's detail page — a different product
area that happens to share the word *connection* — and catching it would be
this gate crying about something it has no business with. `BuildRedirect` is
excluded the same way: a doorway is not a panel.

⚠ **THE HONEST LIMIT, STATED BECAUSE A DECLARED BLIND SPOT WITH NO NUMBER
BESIDE IT IS INDISTINGUISHABLE FROM AN EMPTY ONE (law 7).** This check is by
NAME, so a copy called `OverviewSummary` in some other folder walks straight
past it. That is why the pass line prints **how many panel definitions it found
and where**: a reader comparing that count against the home's own contents can
see a copy this rule cannot name. Check 2 is the other half of the answer.

2 · THE PAGE COMPOSES
----------------------
The component `App.tsx` mounts at `connections/:connectionId` — **derived from
the route table, never from a list in this file, so there is nothing here to go
stale when the page is renamed** — must import from the home, directly or
through a file it reaches.

⚠ **SKIPPED WHILE A DOORWAY IS MOUNTED, AND IT SAYS SO IN THE PASS LINE.** Until
the detail page lands, `App.tsx` mounts `BuildRedirect`, which composes nothing
because it renders nothing — it resolves where the build lives and navigates.
Refusing that would refuse the very ordering `CR-151-BRC09` §6a requires (the
redirect keeps answering until the page exists, or the address is live in front
of a screen that is not there — law 2's mirror). **The doorway is named below,
so a second one is a visible edit to this file**, and when the route is flipped
the name simply stops matching and the check starts applying on its own.

3 · MONEY LINKS
----------------
No file the page reaches may import the account's money reads or money panels,
or name a money API path. Banned by MODULE (`features/billing/…`,
`features/ledger/…`, `features/payments/…`), by SYMBOL (`AccountBillsTab`,
`PaymentsTable`, …) and by API PATH (`/invoices`, `/payments`, `/journal`, …).

⚠ **`*Shared` MODULES ARE ALLOWED, AND THE EXEMPTION IS THE POINT RATHER THAN A
LOOPHOLE.** `billingShared.billDetailPath` and `paymentsShared` are where the
LINK helpers and the labels live, and the ruling *requires* the link:
`01-overview.png` draws `One-time charges · $1,035.00 · INV-2026-00318`, where
the invoice number opens the bill on the account. A gate that banned the path
helper would ban the behaviour it exists to enforce.

⚠ **RE-HOSTING IS AS BAD AS RE-IMPLEMENTING, WHICH IS WHY THE SYMBOLS ARE NAMED
TOO.** Wave-O judgment (2), unchanged: *"Building a second copy inside a Build
tab is the duplicate destination the ruling is about, one level down."* Mounting
`AccountBillsTab` inside a Charges tab is that, exactly.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "07-frontend" / "src"

# ── THE HOME ──────────────────────────────────────────────────────────────
#: Where a build panel may be defined. Relative to the front-end source root so
#: the gate can be pointed at a temp tree by `selftest()`.
HOME_FILE = "features/work/buildViews.tsx"
HOME_DIR = "features/work/buildRecord"

#: The route table, at the front-end source root. Named rather than searched
#: for, exactly as the previous body named it, so a second one is a visible
#: edit to this file.
ROUTE_TABLE = "App.tsx"

#: The address this gate is about, as it appears in the route table. **TWO
#: parts, and they are matched separately on purpose.**
#:
#: ⚠ **THE FIRST DRAFT REQUIRED THE LITERAL `connections/:connectionId` AND THE
#: REAL `App.tsx` DOES NOT CONTAIN IT** — it composes the segment, as
#: ``path: `${CONNECTIONS_ROUTE.slice(1)}/:connectionId` ``. So the route was
#: never found, `scan()` took its "cannot locate the page" branch, and checks 2
#: and 3 SKIPPED — over a green pass line. **That is hard-won law 7's
#: *reporting zero over a scope it silently excludes*, manufactured inside the
#: gate written to obey that law**, and the self-test below is the only thing
#: that found it: four cases that should have bitten came back empty. It is
#: recorded here rather than quietly fixed because the shape is the lesson —
#: a derived scope that cannot find its subject looks exactly like a subject
#: with nothing wrong in it.
BUILD_ROUTE_PARAM = re.compile(r":connection(?:Id|_id)\b")
BUILD_ROUTE_WORD = re.compile(r"connections", re.I)

#: `element: <Something ... />` — the component the route mounts.
ROUTE_ELEMENT = re.compile(r"element:\s*<\s*([A-Z][A-Za-z0-9_]*)")

#: A doorway, not a page. While this is what the route mounts, check 2 is
#: SKIPPED and the pass line says so by name. When the route is flipped to the
#: real page this simply stops matching; there is nothing to remember.
DOORWAY = "BuildRedirect"

# ── CHECK 1 · THE PANEL VOCABULARY ────────────────────────────────────────
#: A component name that is a BUILD PANEL. Prefix says whose it is; the suffix
#: says it is a piece of UI rather than a page, a hook or a helper.
PANEL_PREFIX = r"(?:Build|WorkOrders?|Connection)"
PANEL_SUFFIX = (
    r"(?:Panel|Panels|Tab|Tabs|Tile|Tiles|Header|Actions|Action|Banner|Cell|"
    r"Cells|Card|Cards|Section|Table|List|Row|Rows|Strip|Summary|Timeline|"
    r"Grid|Drawer|Chip|Chips|Badge|Pill)"
)
#: ⚠ **THE MIDDLE IS OPTIONAL, AND THE FIRST DRAFT REQUIRED IT — WHICH SILENTLY
#: MISSED FIVE OF THE HOME'S FOURTEEN PANELS.** It read
#: `PREFIX [A-Z] [A-Za-z0-9]* SUFFIX`, so a name where the suffix follows the
#: prefix directly — `BuildActions`, `BuildTab`, `WorkOrdersTab`,
#: `WorkOrderPanel`, `ConnectionCell` — could not match at all, and a copy of
#: any of those five in another folder would have walked past the gate. It went
#: unnoticed for one run and was found by the PASS LINE, which prints the panel
#: count: nine, against fourteen a `grep` of the home shows. **That is law 7's
#: third habit paying for itself** — a check's output must distinguish pass from
#: fail to a READER, not merely to an exit code — and it is the reason the count
#: is printed rather than merely computed.
PANEL_DECL = re.compile(
    rf"^\s*export\s+(?:function|const)\s+({PANEL_PREFIX}[A-Za-z0-9]*{PANEL_SUFFIX})\b"
)

# ── CHECK 3 · WHAT COUNTS AS THE ACCOUNT'S MONEY ──────────────────────────
#: A module under one of the money features. `*Shared` is where the LINK
#: helpers live and is allowed — see the docstring.
#:
#: ⚠ **`features/` IS OPTIONAL BECAUSE A SIBLING FEATURE IS REACHED RELATIVELY.**
#: The repo's dominant style is `@/features/billing/…`, but a file inside
#: `features/work/` can just as correctly write `../billing/BillsListPage`, and
#: a pattern that demanded the `features/` segment would have seen the first
#: form and not the second — one spelling of the same import, invisible. The
#: symbol and API-path checks below would still have caught most of it, which
#: is precisely why this was worth closing: a gap that is *usually* covered by
#: another check is the kind nobody notices is open.
MONEY_MODULE = re.compile(
    r"""["'](?:@/)?(?:\.\./)*(?:features/)?(billing|ledger|payments)/([A-Za-z0-9_./-]+)["']"""
)

#: Modules elsewhere that are money reads by any other name.
MONEY_MODULE_EXTRA = re.compile(r"""["'][^"']*creditNoteEndpoints["']""")

#: Panels that BELONG to the account and may not be re-hosted on the build page.
#: Re-hosting is the duplicate destination one level down (wave-O judgment 2).
MONEY_SYMBOLS = (
    "AccountBillsTab",
    "AccountAdjustmentsTab",
    "AccountMoneyTabs",
    "AccountUsageTab",
    "PaymentsTable",
    "PaymentsMadePanel",
)
MONEY_SYMBOL = re.compile(r"\b(" + "|".join(MONEY_SYMBOLS) + r")\b")

#: A money API path. The page shows what THIS BUILD made and links for the rest,
#: so it never calls one of these itself.
MONEY_API = re.compile(
    r"""["'`]/(invoices|payments|journal-lines|journal|ledger|adjustments|"""
    r"""outstandings|credit-notes|bills|refunds|write-offs)\b"""
)

# ── COMMENT BLANKING (kept from the previous body, and for its reason) ────
#: `/* … */`, including the JSX `{/* … */}` form, across lines. Replaced with
#: spaces rather than deleted, so the line NUMBERS a finding reports stay true.
#:
#: ⚠ **THE OPENER MUST SIT AT A TOKEN BOUNDARY, AND THAT LOOKBEHIND IS THE
#: DIFFERENCE BETWEEN THIS GATE WORKING AND THIS GATE LYING.** `App.tsx` mounts
#: two sub-applications on wildcard routes — `{ path: "portal/*", … }` and
#: `{ path: "work/mobile/*", … }` — and a bare `/\*.*?\*/` reads the `/*` inside
#: those STRINGS as a comment opener. The nearest `*/` is 1,700 lines further
#: down, at the `/** What the BROWSER runs */` docblock, so **the whole route
#: table in between was blanked to spaces**, the build route was never found,
#: and the first draft of this gate reported that nothing is mounted there.
#: The previous body had the identical blanker and never met this because it
#: EXEMPTED `App.tsx` by name; the moment the route table became something this
#: gate reads, the flaw arrived with it. A comment opener is preceded by
#: start-of-line, whitespace, `{`, `(`, `,` or `=` — never by an identifier
#: character or another slash, which is exactly what `portal/*` and `https://x/*`
#: are.
BLOCK_COMMENT = re.compile(r"(?<![A-Za-z0-9_/])/\*.*?\*/", re.S)

#: `// …` to the end of the line, EXCEPT after a colon — which is what keeps
#: `https://…` from having its second half eaten.
LINE_COMMENT = re.compile(r"(?<!:)//[^\n]*")


def _code_only(text: str) -> str:
    """The file with its comments blanked out and its line count intact.

    ⚠ **THE FIRST DRAFT OF THE PREVIOUS BODY SKIPPED LINES STARTING `//`, `*`
    OR `/*`, AND IT WAS WRONG ON ITS FIRST REAL RUN.** A JSX comment opens with
    `{/*`, so every continuation line of the block explaining WHY the
    destination was retired was read as code and reported. A gate that fires on
    its own explanation is the DEF-182 shape — an output that cannot
    distinguish pass from fail — and the fix is to blank comments properly
    rather than to add a special case. **Kept, because this file's new body has
    exactly the same exposure**: the ruling it enforces is written in the
    comments of the files it reads.

    ⚠ **THE TWO PASSES RUN IN THE OPPOSITE ORDER FROM THE PREVIOUS BODY, AND
    THAT IS THE SECOND HALF OF THE SAME FIX.** Line comments are blanked FIRST,
    so a `/*` written inside a `//` comment — `App.tsx:400` explains the portal
    root as ``/{tenant}/portal/*`` — can never open a block that runs to the
    next `*/` a thousand lines away. Blanking a `//` that happens to sit inside
    a block comment is harmless: it was comment either way.
    """
    blanked = LINE_COMMENT.sub(lambda m: " " * len(m.group(0)), text)
    return BLOCK_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), blanked)


def _read(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):  # pragma: no cover - defensive
        return ""


def _is_home(rel: str) -> bool:
    return rel == HOME_FILE or rel.startswith(HOME_DIR + "/")


def _sources(base: pathlib.Path) -> list[pathlib.Path]:
    return [
        p
        for p in sorted(base.rglob("*.ts*"))
        if p.suffix in (".ts", ".tsx") and p.is_file()
    ]


# ── CHECK 1 ───────────────────────────────────────────────────────────────
def _panel_definitions(base: pathlib.Path) -> tuple[list[tuple[str, int, str]], int]:
    """Every build-panel definition, and how many files were read."""
    found: list[tuple[str, int, str]] = []
    seen = 0
    for path in _sources(base):
        seen += 1
        rel = path.relative_to(base).as_posix()
        for number, line in enumerate(_code_only(_read(path)).splitlines(), start=1):
            match = PANEL_DECL.match(line)
            if match is not None:
                found.append((rel, number, match.group(1)))
    return found, seen


# ── THE PAGE'S REACH, DERIVED FROM THE ROUTE TABLE ────────────────────────
def _mounted_component(base: pathlib.Path) -> str | None:
    """What `App.tsx` mounts at `connections/:connectionId`, or None."""
    app = base / ROUTE_TABLE
    if not app.is_file():
        return None
    lines = _code_only(_read(app)).splitlines()
    for index, line in enumerate(lines):
        if BUILD_ROUTE_PARAM.search(line) is None or BUILD_ROUTE_WORD.search(line) is None:
            continue
        # The element sits within a few lines of its path, in either order.
        window = lines[max(0, index - 4) : index + 6]
        for candidate in window:
            match = ROUTE_ELEMENT.search(candidate)
            if match is not None:
                return match.group(1)
    return None


IMPORT_OF = re.compile(r"""^\s*import\s+(?:type\s+)?(?P<what>[^;]*?)\s+from\s+["'](?P<spec>[^"']+)["']""")


def _component_file(base: pathlib.Path, component: str) -> pathlib.Path | None:
    """Where `App.tsx` imports `component` from, resolved to a file."""
    app = base / ROUTE_TABLE
    for line in _code_only(_read(app)).splitlines():
        match = IMPORT_OF.match(line)
        if match is None or re.search(rf"\b{re.escape(component)}\b", match.group("what")) is None:
            continue
        return _resolve(base, base / ROUTE_TABLE, match.group("spec"))
    return None


def _resolve(base: pathlib.Path, importer: pathlib.Path, spec: str) -> pathlib.Path | None:
    """`@/x/y` or `./y` → a file under the front-end source root, or None."""
    if spec.startswith("@/"):
        target = base / spec[2:]
    elif spec.startswith("."):
        target = (importer.parent / spec).resolve()
    else:
        return None  # a package
    for candidate in (
        target.with_suffix(".tsx"),
        target.with_suffix(".ts"),
        target / "index.tsx",
        target / "index.ts",
    ):
        if candidate.is_file():
            return candidate
    return None


#: How far the page's OWN composition is followed. The page and its tabs is one
#: hop; a tab's own sub-component is two. Beyond that a file belongs to the kit
#: rather than to the page, and the home is never followed at all — composing it
#: is what the page is supposed to do.
REACH_DEPTH = 2


def _page_reach(base: pathlib.Path, entry: pathlib.Path) -> list[pathlib.Path]:
    """The page file and the files it composes, by RELATIVE import only."""
    seen: dict[pathlib.Path, int] = {entry: 0}
    queue = [(entry, 0)]
    while queue:
        path, depth = queue.pop(0)
        if depth >= REACH_DEPTH:
            continue
        for line in _code_only(_read(path)).splitlines():
            match = IMPORT_OF.match(line)
            if match is None:
                continue
            spec = match.group("spec")
            if not spec.startswith("."):
                continue  # `@/…` is the shared kit, not the page's own code
            target = _resolve(base, path, spec)
            if target is None or target in seen:
                continue
            rel = target.relative_to(base).as_posix()
            if _is_home(rel) or ".test." in target.name:
                continue  # the home is COMPOSED, never part of the page
            seen[target] = depth + 1
            queue.append((target, depth + 1))
    return sorted(seen)


# ── CHECK 3 ───────────────────────────────────────────────────────────────
def _money_findings(base: pathlib.Path, reach: list[pathlib.Path]) -> list[str]:
    out: list[str] = []
    for path in reach:
        rel = path.relative_to(base).as_posix()
        for number, line in enumerate(_code_only(_read(path)).splitlines(), start=1):
            module = MONEY_MODULE.search(line)
            if module is not None and not module.group(2).split("/")[-1].endswith("Shared"):
                out.append(
                    f"{rel}:{number} the build page imports the account's money "
                    f"(features/{module.group(1)}/{module.group(2)}) — it must LINK instead"
                )
                continue
            if MONEY_MODULE_EXTRA.search(line) is not None:
                out.append(f"{rel}:{number} the build page imports a money read — it must LINK instead")
                continue
            symbol = MONEY_SYMBOL.search(line)
            if symbol is not None:
                out.append(
                    f"{rel}:{number} the build page re-hosts the account's own "
                    f"`{symbol.group(1)}` — that is the duplicate destination one level down"
                )
                continue
            api = MONEY_API.search(line)
            if api is not None:
                out.append(
                    f"{rel}:{number} the build page calls a money API path "
                    f"(/{api.group(1)}) — money is read on the account"
                )
    return out


# ── THE VERDICT ───────────────────────────────────────────────────────────
class Result:
    def __init__(self) -> None:
        self.findings: list[str] = []
        self.files_read = 0
        self.panels: list[tuple[str, int, str]] = []
        self.mounted: str | None = None
        self.reach: list[str] = []
        self.skipped: list[str] = []


def scan(root: pathlib.Path | None = None) -> Result:
    base = FRONTEND if root is None else root
    result = Result()

    # 1 · COMPOSED, NOT COPIED
    panels, seen = _panel_definitions(base)
    result.panels = panels
    result.files_read = seen
    for rel, number, name in panels:
        if not _is_home(rel):
            result.findings.append(
                f"{rel}:{number} defines the build panel `{name}` outside its home "
                f"({HOME_FILE} / {HOME_DIR}/) — compose it, do not copy it"
            )

    # 2 & 3 · derived from the route table
    # ⚠ **NOT BEING ABLE TO FIND THE PAGE IS A FAILURE, NOT A SKIP, AND THAT
    # IS THE WHOLE LESSON OF THIS GATE'S FIRST DRAFT.** Checks 2 and 3 are
    # derived from the route table, so a route this file cannot parse silently
    # empties two thirds of the gate — and an empty scope and a clean scope
    # produce exactly the same green line. Law 7: a check reporting zero over a
    # scope it silently excludes is not lying, and is indistinguishable from a
    # check that found nothing wrong. So it goes RED and says what it could not
    # see.
    mounted = _mounted_component(base)
    result.mounted = mounted
    if mounted is None:
        result.findings.append(
            f"{ROUTE_TABLE}: nothing is mounted at connections/:connectionId that this "
            "gate can see, so checks 2 (does the page compose the shared panels) and 3 "
            "(does it reach for the account's money) could not run at all — they would "
            "report zero over an empty scope"
        )
        return result

    entry = _component_file(base, mounted)
    if entry is None:
        result.findings.append(
            f"{ROUTE_TABLE}: `{mounted}` is mounted at the build address but has no "
            "resolvable import there, so its files are unknown and checks 2 and 3 "
            "could not run at all"
        )
        return result

    reach = _page_reach(base, entry)
    result.reach = [p.relative_to(base).as_posix() for p in reach]

    if mounted == DOORWAY:
        result.skipped.append(
            f"check 2 (does the page compose the home): `{DOORWAY}` is mounted at "
            "the build address — a doorway renders no panels, so there is nothing "
            "to compose. It applies the moment the route is flipped to a page"
        )
    else:
        composes = False
        for path in reach:
            for line in _code_only(_read(path)).splitlines():
                match = IMPORT_OF.match(line)
                if match is None:
                    continue
                target = _resolve(base, path, match.group("spec"))
                if target is not None and _is_home(target.relative_to(base).as_posix()):
                    composes = True
                    break
            if composes:
                break
        if not composes:
            result.findings.append(
                f"{result.reach[0] if result.reach else mounted}: the page mounted at "
                f"the build address imports nothing from {HOME_FILE} or {HOME_DIR}/ — "
                "it has written its own panels rather than composing the shared ones "
                "(B14 rule 43; CR-151-BRC09)"
            )

    # 3 · MONEY LINKS
    result.findings.extend(_money_findings(base, reach))
    return result


def _report(result: Result) -> tuple[str, str]:
    if result.findings:
        head = " | ".join(result.findings[:3])
        more = f" (+{len(result.findings) - 3} more)" if len(result.findings) > 3 else ""
        return "FAIL", head + more

    # ⚠ THE PASS LINE PRINTS WHAT IT SKIPPED BESIDE WHAT IT CHECKED (law 7).
    # A declared blind spot with no NUMBER attached is indistinguishable from an
    # empty one, and this gate has two: a copy named outside the vocabulary, and
    # a check that does not apply while a doorway is mounted.
    parts = [
        f"{result.files_read} front-end file(s) read; "
        f"{len(result.panels)} build panel(s) defined, all in {HOME_FILE} / {HOME_DIR}/.",
        f"Build address mounts `{result.mounted}`; "
        f"{len(result.reach)} file(s) in its reach carry no money read, money panel or money API path.",
    ]
    for note in result.skipped:
        parts.append(f"SKIPPED — {note}.")
    parts.append(
        "Named-panel check only: a copy under a name outside the vocabulary is "
        "not visible to it; compare the panel count against buildViews.tsx."
    )
    return "PASS", " ".join(parts)


def run() -> tuple[str, str]:
    """The suite's entry point.

    ⚠ **PRESENT FROM THE FIRST COMMIT, AND `DEF-GOV-3733` IS WHY.** `G85` and
    `G87` were each shown RED and then green through `python3 <gate>.py`, which
    exercises `__main__` and never the path `run_gates` uses — both were
    announced green while the suite reported `gate crashed: AttributeError:
    module has no attribute 'run'`. A red proof through the wrong entry point is
    not a weaker proof; it is no proof of the thing that matters. **This body
    was proved RED through `run_gates.py` itself, twice, before it was trusted
    green** — see the Lifecycle block.
    """
    return _report(scan())


def main() -> int:
    result = scan()
    for line in result.findings:
        print(f"G93 FAIL: {line}")
    if result.findings:
        return 1
    print(f"G93 PASS: {_report(result)[1]}")
    return 0


def selftest() -> int:
    """Break it on purpose, in a temp tree — never on the real one.

    ⚠ **EACH CASE BUILDS A WHOLE MINIATURE FRONT END**, because two of the three
    checks are derived from the route table rather than from a list, and a case
    that wrote one file could not exercise them at all. A self-test that cannot
    reach two thirds of the gate is law 7's *incapable of failing* wearing a
    green tick.
    """
    import tempfile

    def tree(root: pathlib.Path, files: dict[str, str]) -> None:
        for rel, body in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")

    # The smallest front end this gate recognises: a route table, a home, a page.
    HOME = 'export function BuildTabPanel() { return null; }\n'
    APP_REDIRECT = (
        'import { BuildRedirect } from "@/features/work/BuildRedirect";\n'
        "const routes = [\n"
        "  {\n"
        "    path: `${CONNECTIONS_ROUTE.slice(1)}/:connectionId`,\n"
        "    element: <BuildRedirect />,\n"
        "  },\n"
        "];\n"
    )
    APP_PAGE = (
        'import { BuildDetailPage } from "@/features/work/BuildDetailPage";\n'
        "const routes = [\n"
        "  {\n"
        "    path: `${CONNECTIONS_ROUTE.slice(1)}/:connectionId`,\n"
        "    element: <BuildDetailPage />,\n"
        "  },\n"
        "];\n"
    )
    BASE = {
        "features/work/buildViews.tsx": HOME,
        "features/work/BuildRedirect.tsx": "export function BuildRedirect() { return null; }\n",
        "App.tsx": APP_REDIRECT,
    }
    GOOD_PAGE = (
        'import { BuildTabPanel } from "./buildViews";\n'
        'import { ChargesTab } from "./ChargesTab";\n'
        "export function BuildDetailPage() { return null; }\n"
    )

    cases: list[tuple[str, dict[str, str], bool]] = [
        (
            "today's tree — home, doorway, no page",
            dict(BASE),
            False,
        ),
        (
            "a build panel copied into another feature",
            {**BASE, "features/customers/Copy.tsx": "export function BuildOverviewPanel() { return null; }\n"},
            True,
        ),
        (
            "a build panel copied INSIDE work, next to the home",
            {**BASE, "features/work/Copy.tsx": "export function BuildRecordTiles() { return null; }\n"},
            True,
        ),
        # ⚠ FIVE OF THE HOME'S FOURTEEN PANELS PUT THE SUFFIX STRAIGHT AFTER
        # THE PREFIX, AND THE FIRST DRAFT COULD NOT MATCH ANY OF THEM. One case
        # per name, so the vocabulary cannot narrow again without going red.
        (
            "a copy of `BuildActions` (suffix straight after the prefix)",
            {**BASE, "features/customers/C1.tsx": "export function BuildActions() { return null; }\n"},
            True,
        ),
        (
            "a copy of `BuildTab`",
            {**BASE, "features/customers/C2.tsx": "export function BuildTab() { return null; }\n"},
            True,
        ),
        (
            "a copy of `WorkOrdersTab`",
            {**BASE, "features/customers/C3.tsx": "export function WorkOrdersTab() { return null; }\n"},
            True,
        ),
        (
            "a copy of `WorkOrderPanel`",
            {**BASE, "features/customers/C4.tsx": "export function WorkOrderPanel() { return null; }\n"},
            True,
        ),
        (
            "a copy of `ConnectionCell`, declared as a const",
            {**BASE, "features/customers/C5.tsx": "export const ConnectionCell = () => null;\n"},
            True,
        ),
        (
            "the kit's own panels, in buildRecord/",
            {**BASE, "features/work/buildRecord/BuildPremisePanel.tsx": "export function BuildPremisePanel() { return null; }\n"},
            False,
        ),
        (
            "the integrations connector's detail page (not a panel)",
            {**BASE, "features/integrations/ConnectionDetailPage.tsx": "export function ConnectionDetailPage() { return null; }\n"},
            False,
        ),
        (
            "the doorway itself (not a panel)",
            dict(BASE),
            False,
        ),
        (
            "a page that composes the home",
            {**BASE, "App.tsx": APP_PAGE, "features/work/BuildDetailPage.tsx": GOOD_PAGE,
             "features/work/ChargesTab.tsx": "export function ChargesTab() { return null; }\n"},
            False,
        ),
        (
            "a page that composes NOTHING from the home",
            {**BASE, "App.tsx": APP_PAGE,
             "features/work/BuildDetailPage.tsx": "export function BuildDetailPage() { return null; }\n"},
            True,
        ),
        (
            "the Charges tab importing the account's Bills tab",
            {**BASE, "App.tsx": APP_PAGE, "features/work/BuildDetailPage.tsx": GOOD_PAGE,
             "features/work/ChargesTab.tsx":
                 'import { AccountBillsTab } from "@/features/billing/BillsListPage";\n'
                 "export function ChargesTab() { return null; }\n"},
            True,
        ),
        (
            "the Charges tab calling a money API path",
            {**BASE, "App.tsx": APP_PAGE, "features/work/BuildDetailPage.tsx": GOOD_PAGE,
             "features/work/ChargesTab.tsx":
                 'const rows = client.get(`/invoices?account=${id}`);\n'
                 "export function ChargesTab() { return null; }\n"},
            True,
        ),
        (
            "the Charges tab importing a ledger read",
            {**BASE, "App.tsx": APP_PAGE, "features/work/BuildDetailPage.tsx": GOOD_PAGE,
             "features/work/ChargesTab.tsx":
                 'import { listJournalLines } from "@/features/ledger/journalEndpoints";\n'
                 "export function ChargesTab() { return null; }\n"},
            True,
        ),
        (
            "the Charges tab importing a money module RELATIVELY, not through @/",
            {**BASE, "App.tsx": APP_PAGE, "features/work/BuildDetailPage.tsx": GOOD_PAGE,
             "features/work/ChargesTab.tsx":
                 'import { somethingMoneyish } from "../payments/paymentsEndpoints";\n'
                 "export function ChargesTab() { return null; }\n"},
            True,
        ),
        (
            "the Overview tab LINKING to a bill through billingShared",
            {**BASE, "App.tsx": APP_PAGE, "features/work/BuildDetailPage.tsx": GOOD_PAGE,
             "features/work/ChargesTab.tsx":
                 'import { billDetailPath } from "@/features/billing/billingShared";\n'
                 "export function ChargesTab() { return null; }\n"},
            False,
        ),
        (
            "a comment quoting the ruling about /invoices and AccountBillsTab",
            {**BASE, "App.tsx": APP_PAGE, "features/work/BuildDetailPage.tsx": GOOD_PAGE,
             "features/work/ChargesTab.tsx":
                 "// money LINKS: never AccountBillsTab, never `/invoices` from here\n"
                 "export function ChargesTab() { return null; }\n"},
            False,
        ),
        (
            "a link to /connections/<id> — LAWFUL NOW, and the old body refused it",
            {**BASE, "features/customers/NewConnectsTab.tsx": 'const to = `/connections/${row.id}`;\n'},
            False,
        ),
        # ⚠ THESE THREE EXIST BECAUSE THE FIRST DRAFT FAILED EXACTLY HERE, AND
        # PASSED WHILE DOING SO. A route this gate cannot parse empties checks
        # 2 and 3, and an empty scope reads like a clean one (law 7).
        (
            "the route written as a LITERAL rather than composed",
            {**BASE, "App.tsx":
                'import { BuildDetailPage } from "@/features/work/BuildDetailPage";\n'
                'const routes = [{ path: "/:tenant/connections/:connectionId", element: <BuildDetailPage /> }];\n',
             "features/work/BuildDetailPage.tsx": "export function BuildDetailPage() { return null; }\n"},
            True,  # composes nothing — and the point is that the route WAS found
        ),
        (
            "no build route in the table at all — the scope would be empty",
            {"features/work/buildViews.tsx": HOME,
             "App.tsx": "const routes = [{ path: 'premises', element: <PremisesPage /> }];\n"},
            True,
        ),
        (
            "a route whose element has no import — the page cannot be located",
            {**BASE, "App.tsx":
                "const routes = [{ path: `${CONNECTIONS_ROUTE.slice(1)}/:connectionId`, "
                "element: <BuildDetailPage /> }];\n"},
            True,
        ),
    ]

    failed = 0
    for label, files, should_bite in cases:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            tree(root, files)
            result = scan(root)
            bit = bool(result.findings)
            if bit != should_bite:
                print(
                    f"selftest RED-PROOF FAILED: {label} — expected "
                    f"{'a finding' if should_bite else 'no finding'}, got {result.findings}"
                )
                failed = 1
            else:
                print(f"selftest ok: {label} → {'caught' if bit else 'allowed'}")
    return failed


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    raise SystemExit(main())

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-151-BRC09 §6 task R2 · PO ruling 2026-09-28 · supersedes in part the decision-log row of 2026-09-04 ("A BUILD HAS ONE DESTINATION")
# generated: 2026-09-04 by the CR-070 wave O build lane; REWRITTEN 2026-09-28 by the CR-151-BRC09 REVERSAL lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: proved RED through run_gates.py (NOT through __main__ — DEF-GOV-3733), twice and on two different checks — once on a build panel copied into 07-frontend/src/features/customers/ on purpose, once on an `AccountBillsTab` import put into the file the route reaches. Green after both were removed. TWENTY-THREE self-test clauses bite, including the two that prove the REVERSAL: a link to /connections/<id> is now ALLOWED, and a page that composes nothing from the home is REFUSED.
# ⚠ TWO FAULTS IN THIS FILE'S OWN FIRST DRAFT, BOTH FOUND BY ITS OWN OUTPUT AND BOTH RECORDED IN THE CODE RATHER THAN QUIETLY FIXED: (1) the inherited comment-blanker read the `/*` inside `App.tsx`'s `"portal/*"` ROUTE STRING as a comment opener and blanked 1,700 lines, so the build route was never found and checks 2 and 3 SKIPPED behind a green line — law 7's "reporting zero over a scope it silently excludes", manufactured inside the gate written to obey it; the previous body had the identical blanker and never met it because it exempted `App.tsx` by name. (2) the panel vocabulary required a capital between the prefix and the suffix, so it could not see `BuildActions`, `BuildTab`, `WorkOrdersTab`, `WorkOrderPanel` or `ConnectionCell` — five of the home's fourteen — and a copy of any of them would have passed. Found by the PASS LINE printing nine where a grep of the home shows fourteen.
# exceptions: `*Shared` modules under features/billing|ledger|payments are allowed by class, because that is where the LINK helpers live and the ruling REQUIRES the link — stated in the docstring with the drawn example · `BuildRedirect` is named as the doorway so check 2 is skipped while it is mounted, and the pass line says so
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
