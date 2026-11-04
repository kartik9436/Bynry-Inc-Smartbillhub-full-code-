#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects: DEF-CWP-3954 (26 of the portal's 50 screens had nothing pointing at
#          them) · DEF-CWP-3925 (six doors shut over live screens — the same
#          fault with the arrow reversed)
# Rules:   CLAUDE.md hard-won law 2 (*built is not wired*, and its mirror: a
#          live screen behind a dead control) · law 7 (proved RED first, and in
#          the harness that will run it — see PROVEN RED below) · CR-068 §9
#          (the CWP register) · B14 rule 31 (a door's visible value is the
#          bill number or the SR number, never a row id — asserted by the
#          screens' own tests, not here)
# Tests:   selftest() below · src/portal/bills/Bills.dom.test.tsx
# Impacts: 07-frontend/src/portal/** · 06-backend/apps/portal/selectors.py
#          (ERRAND_ROUTE) · gates/g100_doorless_screens.txt
# ───────────────────────────────────────────────────────
"""G100 — every screen in the CWP register is reachable by a walk of doors.

WHY THIS EXISTS
---------------
On 2026-09-05 a browser crawl of the customer portal found **26 of its 50
screens with no door into them**. Every one was shipped, routed, tested and
answering correctly at its own address: a signed-in customer's entire clickable
surface was **twelve destinations**, and on the bills list the only control was
a greyed *Pay* while the bill numbers were bold text — a person could see every
bill they had ever been sent and could not open one.

**Every check in the repo passed over it.** 42 portal test files, 391 cases,
`tsc`, every gate — because each wave tested ITS OWN screen at ITS OWN address,
and the question *has anything started pointing at it* belonged to nobody. That
is exactly what `G13` does for the other direction (a prop nothing passes), and
it is why this gate is shaped like `G13`: it asks the question no single wave's
tests can ask.

It is the THIRD occurrence of this shape. `DEF-CWP-3925` was six doors held
shut over screens that had landed; `DEF-CWP-3954` is twenty-six screens with no
door at all. Nothing mechanical stood between the two.

WHAT IT ASSERTS
---------------
Every row of `07-frontend/src/portal/routing/screenIds.ts` is REACHABLE — there
is a path of doors from the public front page or from the signed-in home to it.

⚠ **REACHABLE, NOT MERELY POINTED AT, AND THE DIFFERENCE IS A REAL DEFECT.**
The first draft of this gate asked only *does anything name this address*, and
it passed `CWP-039` and `CWP-040` — which is the very pair lane E called *the
shape in miniature*: `Methods.tsx` links to `/autopay`, `Autopay.tsx` links back
to `/payment-methods`, and **those were the only two references to either
address in the entire front end.** A closed loop with no entrance satisfies
"something points at it" and is exactly as unreachable as nothing pointing at
it. So the check is a walk, from the two places a customer actually starts.

**Which screen a door is ON comes from `data-screen="CWP-###"`**, the mark every
portal screen already carries for the walkthrough — so no second map has to be
kept in step (hard-won law 12's shape for pointers). A file with no
`data-screen` is FRAME rather than screen — `PortalShell`, `GuestFrame`, the
kit — and its doors are available from everywhere, which is what a tab strip
and a nav bar are.

**The two roots are `CWP-001` (the public front page) and `CWP-022` (where a
sign-in lands).** Seeding home as well as the front page is deliberate: a
customer arrives there with a password and no other history, so a screen only
`/home` can reach is genuinely reached.

A door is any of:

  * `to="/pay-now"` · `to={path("/pay-now")}` · `to={path(`/bills/${n}`)}` —
    a `<Link>`, a `NavLink`, or the kit's `ErrandLink` / `WhereNext`;
  * `to: "/home"` — the shell's tab table;
  * `href="help/x"` — a plain anchor, including a RELATIVE one;
  * `navigate(path("/pay/check"))` — **a `<button>` that navigates is a door.**
    The browser crawl cannot see one and says so; a static read can, and the
    two together are why the crawl's list and this gate's list differ by
    exactly the three form steps (`CWP-003`, `CWP-004`, `CWP-047`);
  * `ERRAND_ROUTE` in `apps/portal/selectors.py` — `CWP-046`'s cards are
    SERVER-routed, so a door can live in Python.

**A `to=` WITH NO LEADING SLASH IS ITS OWN FAILURE, named as one.**
`usePortalPath` CONCATENATES — `/${tenant}/portal` + `to` — so four live links
on the two arrears screens resolved to `/pine-hill/portalhelp-paying` and opened
nothing. It is not a relative link and React Router never saw it as one; the
string is in the DOM, so `tsc`, eslint and every `toContain` passed on it.

**Route declarations are not doors.** `portalRoutes.tsx` and `screenIds.ts` are
excluded: a route is what makes an address answer, which is the very thing that
was never in doubt.

**Test files are not doors.** A fixture that renders a screen proves nothing
about whether the product points at it — that was the whole of `DEF-CWP-3954`.

WHAT IT CANNOT SEE, STATED PLAINLY (hard-won law 1)
---------------------------------------------------
  * a destination the SERVER computes and the screen renders unread —
    `LevelPayStanding.tsx` does `to={view.join_at}`. Those are invisible here,
    which makes this gate STRICTER than the truth, never looser.
  * whether a door is CONDITIONAL. `Bills.tsx` draws its doors whatever the
    account holds; another screen might draw one only when the server says so,
    and this gate credits it either way. The crawl, against a real fixture, is
    what reads that.
  * whether the door is HELD. `DEF-CWP-3925`'s greyed cards would pass here.
    The walkthrough's `HELD` line is what reads those.

**Neither this gate nor any other replaces `10-scripts/cwp_portal_walkthrough.mjs`.**
Its crawl follows anchors in a real browser and answers *can a customer get
there*; this answers *does anything in the source point there*. A screen can
pass this and fail that.

PROVEN RED FIRST (law 7, both halves, 2026-09-05)
-------------------------------------------------
`selftest()` replays six cases on in-memory sources, and TWO of them found real
flaws in this gate before it was trusted:

  1. the clean world — must be silent;
  2. a register row nothing names;
  3. **two screens linking only to each other** — the `CWP-039` / `CWP-040`
     shape, which the counting draft passed;
  4. a `to` with no leading slash, which must be named as a typo AND leave its
     screen unreachable;
  5. **two comments that TALK about the fault** — `usePortalPath`'s own
     docstring and the note in `HelpPaying.tsx`. The first run against the real
     tree failed on exactly those, and a gate that reads the sentence
     describing a defect as the defect teaches the next lane to delete the
     explanation to make it pass;
  6. a screen excused by `g100_doorless_screens.txt` — must be silent.

Cases 3 and 5 are the ones the self-test caught. The RED PROOF ON THE REAL TREE
put `DEF-CWP-3954` back — the bill number as bold text, the money doors out of
`CWP-041`, one leading slash off — and the gate reported twenty problems
including *"the only doors into CWP-039 … are on screens nobody can reach"*.

Both proofs were run **through the `run_gates` registry** and not through
`__main__` — `DEF-GOV-3733` is a gate announced green on a proof that exercised
only the path a person uses by hand.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
REGISTER = REPO / "07-frontend" / "src" / "portal" / "routing" / "screenIds.ts"
PORTAL = REPO / "07-frontend" / "src" / "portal"
SELECTORS = REPO / "06-backend" / "apps" / "portal" / "selectors.py"
EXCEPTIONS = Path(__file__).resolve().parent / "g100_doorless_screens.txt"

#: `{ path: "/bills", id: "CWP-027", blueprint: "P13", title: "Bills" }`
REGISTER_ROW = re.compile(
    r'\{\s*path:\s*"([^"]*)",\s*id:\s*"(CWP-\d{3,5}(?!\d))",\s*blueprint:\s*"([^"]*)",\s*title:\s*"([^"]*)"'
)

#: The idioms a door is written in. Two spellings per shape — a double-quoted
#: literal and a backtick template — because a template CONTAINS quotes
#: (`` `/bills/${encodeURIComponent(n ?? "")}` ``) and one pattern that tried to
#: cover both stopped at the `""` inside and reported two live doors as absent.
#: ⚠ **TWO GROUPS, AND THE SPLIT IS LOAD-BEARING.** `usePortalPath`
#: CONCATENATES — `/${tenant}/portal` + `to` — so a `to` with no leading slash
#: is not a relative link, it is `/pine-hill/portalhelp-paying`, an address no
#: route serves. Four of those were live on 2026-09-05. A bare `href`, by
#: contrast, is resolved by the BROWSER against the page's own URL and is a
#: perfectly good door (`HelpPage` writes `href="help/<slug>"`). Reading both
#: the same way is how the first draft of this gate reported the typo as
#: healthy — which is `DEF-182`'s check that cannot distinguish pass from fail,
#: caught here by the self-test before the gate was trusted.
#:
#: Two spellings per shape — a double-quoted literal and a backtick template —
#: because a template CONTAINS quotes (`` `/bills/${encodeURIComponent(n ?? "")}` ``)
#: and one pattern that tried to cover both stopped at the `""` inside and
#: reported two live doors as absent.
CONCATENATED = (
    re.compile(r'\bto=\{?\s*path\(\s*"([^"]*)"'),
    re.compile(r"\bto=\{?\s*path\(\s*`([^`]*)`"),
    re.compile(r'\bto="([^"]*)"'),
    re.compile(r"\bto=\{\s*`([^`]*)`"),
    re.compile(r'\bto:\s*"([^"]*)"'),
    re.compile(r'\bnavigate\(\s*path\(\s*"([^"]*)"'),
    re.compile(r"\bnavigate\(\s*path\(\s*`([^`]*)`"),
)
BROWSER_RESOLVED = (
    re.compile(r'\bhref=\{?\s*path\(\s*"([^"]*)"'),
    re.compile(r"\bhref=\{?\s*path\(\s*`([^`]*)`"),
    re.compile(r'\bhref="([^"]*)"'),
    re.compile(r"\bhref=\{\s*`([^`]*)`"),
    re.compile(r'\bnavigate\(\s*"([^"]*)"'),
    re.compile(r"\bnavigate\(\s*`([^`]*)`"),
)

#: What a target normalises to when it can only ever open nothing.
BROKEN = "!"

#: `ERRAND_ROUTE = { "CWP-052": "/stop-or-restart", … }` — a server-side door.
PY_ERRAND_ROUTE = re.compile(r"ERRAND_ROUTE[^}]*\}", re.S)
PY_ROUTE_VALUE = re.compile(r':\s*"(/[^"]*)"')

#: `tel:`, `mailto:`, `https:` — a door out of the product, not into a screen.
SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")

#: Files in `portal/` that declare routes rather than open them.
NOT_A_DOOR_FILE = {"screenIds.ts", "portalRoutes.tsx"}

#: `/** … */`, `{/* … */}` and a whole-line `// …`.
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?m)^[ \t]*//.*$")


def strip_comments(text: str) -> str:
    """Prose is not a door.

    ⚠ **THE FIRST RUN OF THIS GATE AGAINST THE REAL TREE FAILED ON TWO
    COMMENTS**, and both were comments EXPLAINING this very fault:
    `primitives.tsx`'s docstring for `usePortalPath` says *"a relative
    `<Link to="report">` would work until…"*, and `HelpPaying.tsx` carries the
    note recording the slash-less bug `G100` was written for. A gate that reads
    the sentence describing a defect as the defect is the false positive
    `G78`'s header warns about — it teaches the next lane to delete the
    explanation to make the check pass.

    Only WHOLE-LINE `//` comments go: a trailing one shares its line with real
    code, and cutting from the first `//` would take the rest of a URL with it.
    """
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", text))


def normalise(raw: str, concatenated: bool) -> str:
    """A written target → the sub-path it opens, relative to `/{tenant}/portal`.

    ⚠ **`${…}` BECOMES `:x` AND NOT NOTHING.** `/bills/${n}` opens a bill; a
    substitution that dropped the segment would make it `/bills`, which is a
    different screen, and the gate would credit the list for the detail.

    Returns `""` for an address out of the product (`tel:`, `mailto:`) and
    `BROKEN + text` for a `to` that `usePortalPath` will glue onto the prefix.
    """
    text = raw
    for _ in range(6):  # innermost-first, so a nested `${ `${x}` }` collapses
        shrunk = re.sub(r"\$\{[^{}]*\}", ":x", text)
        if shrunk == text:
            break
        text = shrunk
    text = re.sub(r"\$\{.*?\}", ":x", text)
    text = text.split("?")[0].split("#")[0]
    if SCHEME.match(text):
        return ""
    # A hand-built absolute address — `/${tenant}/portal/start-service/${t}`.
    if "/portal/" in text:
        text = text[text.index("/portal/") + len("/portal") :]
    elif text.endswith("/portal"):
        text = "/"
    elif concatenated:
        # ⚠ `to=""` IS THE PORTAL ROOT AND IS CORRECT — `GuestFrame` writes it
        # for the brand and for *Home*. Anything else without a leading slash
        # is the typo above.
        if text == "":
            return "/"
        if not text.startswith("/"):
            return BROKEN + text
    else:
        text = re.sub(r"^(?:\.\./|\./)+", "", text)  # a relative href is a real door
    if text == "":
        return "/"
    if not text.startswith("/"):
        text = "/" + text
    if len(text) > 1:
        text = text.rstrip("/")
    return text or "/"


def opens(register_path: str, target: str) -> bool:
    """Does `target` open the screen served at `register_path`?

    Segment for segment, with a `:param` on EITHER side matching one segment:
    the register writes `/bills/:number` and a screen writes `/bills/:x`.
    """
    left = [s for s in register_path.split("/") if s]
    right = [s for s in target.split("/") if s]
    if len(left) != len(right):
        return False
    return all(a.startswith(":") or b.startswith(":") or a == b for a, b in zip(left, right))


#: `<div data-screen="CWP-027">` — the mark every portal screen already carries.
SCREEN_MARK = re.compile(r'data-screen=(?:"|\{")(CWP-\d{3,5}(?!\d))')

#: Where a customer starts: the public front page, and where a sign-in lands.
ROOTS = ("CWP-001", "CWP-022")


def read_file(name: str, text: str) -> tuple[set[str], set[str]]:
    """One source → `(the screens it draws, the addresses it opens)`."""
    if name.endswith(".py"):
        block = PY_ERRAND_ROUTE.search(text)
        values = [normalise(v, False) for v in (PY_ROUTE_VALUE.findall(block.group(0)) if block else [])]
        return set(), {v for v in values if v}
    body = strip_comments(text)
    doors: set[str] = set()
    for concatenated, group in ((True, CONCATENATED), (False, BROWSER_RESOLVED)):
        for pattern in group:
            for match in pattern.finditer(body):
                where = normalise(match.group(1), concatenated)
                if where:
                    doors.add(where)
    return set(SCREEN_MARK.findall(body)), doors


def reachable(rows: list[dict[str, str]], sources: dict[str, str]) -> set[str]:
    """The screen ids a customer can walk to from `ROOTS`.

    ⚠ **A FILE WITH NO `data-screen` IS THE FRAME**, and its doors belong to
    every node — that is what a tab strip is. A file that draws several screens
    (`ArrearsPages.tsx`, `SignInPages.tsx`) contributes its doors to each of
    them, which is generous in the safe direction: this gate is the merge
    guard and the browser crawl is the strict reading.
    """

    def ids_for(target: str) -> set[str]:
        return {r["id"] for r in rows if opens(r["path"], target)}

    everywhere: set[str] = set()
    edges: dict[str, set[str]] = {r["id"]: set() for r in rows}
    for name, text in sources.items():
        screens, doors = read_file(name, text)
        landing: set[str] = set()
        for door in doors:
            landing |= ids_for(door)
        if not screens:
            everywhere |= landing
            continue
        for screen in screens:
            edges.setdefault(screen, set()).update(landing)

    seen = {r["id"] for r in rows if r["id"] in ROOTS} | everywhere
    queue = list(seen)
    while queue:
        for there in edges.get(queue.pop(), set()) | everywhere:
            if there not in seen:
                seen.add(there)
                queue.append(there)
    return seen


def doors_in(sources: dict[str, str]) -> dict[str, set[str]]:
    """`{sub-path: {file, …}}` — every address the product writes."""
    found: dict[str, set[str]] = {}
    for name, text in sources.items():
        for where in read_file(name, text)[1]:
            found.setdefault(where, set()).add(name)
    return found


def check(register_text: str, sources: dict[str, str], allowed: set[str]) -> list[str]:
    rows = [
        {"path": p, "id": i, "title": t} for p, i, _b, t in REGISTER_ROW.findall(register_text)
    ]
    found = doors_in(sources)
    here = reachable(rows, sources)
    problems: list[str] = []
    for row in rows:
        if row["id"] in allowed or row["id"] in here:
            continue
        if any(opens(row["path"], where) for where in found):
            problems.append(
                f'the only doors into {row["id"]} {row["path"]} ({row["title"]}) are on screens '
                "nobody can reach — a closed loop with no entrance is as unreachable as no door"
            )
        else:
            problems.append(
                f'nothing in the product points at {row["id"]} {row["path"]} '
                f'({row["title"]}) — a screen nobody can reach is not shipped'
            )
    # The other half: a door that opens nothing. Four of these were live on
    # 2026-09-05 because `usePortalPath` CONCATENATES, so a `to` with no
    # leading slash became `/pine-hill/portalhelp-paying`.
    for where, files in sorted(found.items()):
        if where.startswith(BROKEN):
            problems.append(
                f'{sorted(files)[0]} writes to="{where[len(BROKEN):]}" with no leading slash — '
                f'usePortalPath concatenates, so that opens /{{tenant}}/portal{where[len(BROKEN):]}, '
                "which no route serves"
            )
            continue
        if where == "/" or any(opens(row["path"], where) for row in rows):
            continue
        problems.append(
            f'{sorted(files)[0]} points at "{where}", which no registered screen serves'
        )
    return problems


# ── the self-test's world ──────────────────────────────────────────────────
CLEAN_REGISTER = (
    '{ path: "/", id: "CWP-001", blueprint: "G1", title: "The public front page" },\n'
    '{ path: "/bills", id: "CWP-027", blueprint: "P13", title: "Bills" },\n'
    '{ path: "/bills/:number", id: "CWP-028", blueprint: "P14", title: "One bill" },\n'
    '{ path: "/help-paying", id: "CWP-056", blueprint: "P42", title: "Help paying" },\n'
)
CLEAN_SOURCES = {
    # No `data-screen` → the FRAME, so its tab is a door from everywhere.
    "shell/PortalShell.tsx": 'const TABS = [{ key: "bills", to: "/bills" }];',
    "bills/Bills.tsx": '<div data-screen="CWP-027">'
    '<Link to={path(`/bills/${encodeURIComponent(n ?? "")}`)}>{n}</Link>'
    '<ErrandLink to="/help-paying" /></div>',
    "guest/GuestFrame.tsx": '<Link to={path("")} />',
}
NO_DOOR_SOURCES = {k: v for k, v in CLEAN_SOURCES.items() if k != "bills/Bills.tsx"}
#: ⚠ **THE CASE THE FIRST DRAFT OF THIS GATE PASSED, AND IT IS THE REAL ONE.**
#: `CWP-028` and `CWP-056` link to each other and to nothing else, and nothing
#: else links to either — which is `Methods.tsx` ↔ `Autopay.tsx` exactly. A
#: check that only counts references calls this healthy.
LOOP_SOURCES = {
    "shell/PortalShell.tsx": 'const TABS = [{ key: "bills", to: "/bills" }];',
    "bills/BillDetail.tsx": '<div data-screen="CWP-028"><ErrandLink to="/help-paying" /></div>',
    "arrears/HelpPaying.tsx": '<div data-screen="CWP-056">'
    '<Link to={path(`/bills/${n}`)} /></div>',
    "guest/GuestFrame.tsx": '<Link to={path("")} />',
}
#: The clean world plus two comments that TALK about the fault — the first run
#: of this gate against the real tree failed on exactly these two shapes.
COMMENTED_SOURCES = dict(CLEAN_SOURCES, **{
    "components/primitives.tsx": '/** A relative `<Link to="report">` would silently point elsewhere. */',
    "arrears/HelpPaying.tsx": '        // `to="level-pay"` resolved to /pine-hill/portallevel-pay\n',
})
TYPO_SOURCES = dict(CLEAN_SOURCES, **{
    "bills/Bills.tsx": '<Link to={path(`/bills/${n}`)}>{n}</Link><ErrandLink to="help-paying" />',
})


def selftest() -> bool:
    if check(CLEAN_REGISTER, CLEAN_SOURCES, set()):
        return False
    doorless = check(CLEAN_REGISTER, NO_DOOR_SOURCES, set())
    typo = check(CLEAN_REGISTER, TYPO_SOURCES, set())
    excused = check(CLEAN_REGISTER, NO_DOOR_SOURCES, {"CWP-028", "CWP-056"})
    commented = check(CLEAN_REGISTER, COMMENTED_SOURCES, set())
    loop = check(CLEAN_REGISTER, LOOP_SOURCES, set())
    return (
        any("CWP-028" in p for p in doorless)
        and any("CWP-056" in p for p in doorless)
        # the slash-less `to` is named as a typo AND leaves CWP-056 doorless
        and any("no leading slash" in p for p in typo)
        and any("CWP-056" in p for p in typo)
        and not excused
        # prose describing the fault is not the fault
        and not commented
        # two screens linking only to each other are still unreachable
        and any("CWP-028" in p and "closed loop" in p for p in loop)
        and any("CWP-056" in p and "closed loop" in p for p in loop)
    )


def allowed_ids() -> set[str]:
    if not EXCEPTIONS.is_file():
        return set()
    out = set()
    for line in EXCEPTIONS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.add(line.split()[0])
    return out


def portal_sources() -> dict[str, str]:
    sources: dict[str, str] = {}
    for path in sorted(PORTAL.rglob("*.ts*")):
        if ".test." in path.name or path.name in NOT_A_DOOR_FILE:
            continue
        sources[str(path.relative_to(PORTAL))] = path.read_text(encoding="utf-8")
    if SELECTORS.is_file():
        sources["apps/portal/selectors.py"] = SELECTORS.read_text(encoding="utf-8")
    return sources


def run() -> tuple[str, str]:
    if not REGISTER.is_file():
        return "SKIP", "the portal register is not present — activates with the portal's first screen"
    if not selftest():
        return (
            "FAIL",
            "the gate's own self-test does not hold — it cannot tell a screen with a door from one "
            "without (DEF-182: a check whose output cannot distinguish pass from fail is worse than none)",
        )
    allowed = allowed_ids()
    problems = check(REGISTER.read_text(encoding="utf-8"), portal_sources(), allowed)
    if problems:
        head = " | ".join(problems[:6])
        more = f" (+{len(problems) - 6} more)" if len(problems) > 6 else ""
        return "FAIL", head + more
    rows = REGISTER_ROW.findall(REGISTER.read_text(encoding="utf-8"))
    excused = f", {len(allowed)} excused by name" if allowed else ""
    return "PASS", (
        f"all {len(rows)} registered portal screens are reachable by a walk of doors from the "
        f"front page or from home{excused}; self-test: a screen with no door, a closed loop of "
        "two screens linking only to each other, a door that opens nothing and a `to` missing "
        "its leading slash all bite"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
