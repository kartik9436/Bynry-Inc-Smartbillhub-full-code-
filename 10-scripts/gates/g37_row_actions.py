#!/usr/bin/env python3
"""G37 — row actions are ICONS with an ACCESSIBLE NAME, and the vocabulary has one owner.

WHY THIS GATE EXISTS
--------------------
B14 rule 15 — *"Row actions are ICONS with tooltips, never text links"* — was
RATIFIED and enforced by NOTHING for months. What that cost is DEF-337, reported
from a live deployment: on Settings > Users & roles, *"Edit / Deactivate / Remove
/ Reset temp password sit as four red words in one cell"*. Sixteen tables were
like that and seven were not, and no check could tell the difference, because
every one of them is valid TSX that renders a working control.

The PO ruled the conversion on 2026-08-20 (*"Icons everywhere, per r10 and rule
15"*). This gate is what keeps it converted.

⚠ AND THE OBVIOUS CHECK IS THE ONE THAT MISSES THE WORSE FAILURE. "No text in
the actions cell" passes on an icon with NO ACCESSIBLE NAME — which renders
beautifully, passes every text-absence assertion in the suite, and is unusable
without a mouse. B14's own note on rule 15 says exactly this. So DEF-337's
prevention column demands the guard be proved RED **twice**: once on a text
link, once on a nameless icon. Both proofs are recorded at the bottom of this
file.

WHAT IT CHECKS
--------------
1. **A row-actions cell contains only row actions.** Inside a `<RowActions>`
   block, the only elements allowed are `<RowAction>` and `<RowActionLink>`. A
   raw `<button>`, a `<Button>` or a bare translated string in there is a text
   link wearing the new container — DEF-337 arriving again through the front
   door of its own fix.

2. **The accessible name is still written.** `RowAction` is the ONE place
   `aria-label` reaches a row action, and the type system forces callers to pass
   `label` — so the only way to lose every name at once is to stop writing the
   attribute in that component. The gate reads it there. This is the half that
   catches the nameless icon, and it is deliberately a check on ONE file: a
   check spread over 130 call sites would be a check nobody could keep.

3. **The icon vocabulary has one owner.** No `<svg` may be declared outside
   `components/icons.tsx`. That is DEF-348 — the "edit" pencil existed four
   times, byte for byte, under two names, because rule 15 listed its glyphs in
   PROSE and prose is not importable. PO ruling the same day: *"Tailwind, CSS,
   STylesheet, UI COmponents - we should ahve only one reference point not two"*.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not judge a button OUTSIDE a row-actions cell. A page header's primary
action, a wizard's Next, a panel's "Import chart of accounts" — none of those
are row actions and rule 15 does not reach them. The chart-panel import is the
worked example: it sat inside a `.settings-row-actions` box with no row under
it, and the conversion moved the BOX rather than making the control an icon.

It also cannot see a screen. Whether the chosen glyph MEANS the action to a
person is a browser question, and five of the fourteen glyphs have no r10
precedent at all — they are named in `icons.tsx` for the walkthrough to judge.
This gate keeps the shape; it cannot keep the meaning.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "07-frontend" / "src"
ICONS = SRC / "components" / "icons.tsx"
ROW_ACTIONS = SRC / "components" / "RowActions.tsx"

# Files that may declare an <svg> of their own. Each name here is a decision
# somebody wrote down, and the list is meant to stay at one.
SVG_OWNERS = {
    "components/icons.tsx": "the B14 rule 15 vocabulary — the one owner (DEF-348)",
    # ⚠ THE SECOND OWNER IS GONE, AND THAT IS THE POINT OF THIS LIST (DEF-349,
    # closed 2026-08-22). `components/AppShell.tsx` sat here for two days: the
    # shell drew a DIFFERENT family — twelve rail glyphs, the collapse/expand
    # hamburger, search and the notification bell, all stroke 2 where a row
    # action is stroke 1.6. They are not row actions and rule 15 does not reach
    # them, so this gate would have been wrong to fail them and equally wrong to
    # pretend they were not a second vocabulary; the allowlist made the
    # exception a decision somebody wrote down rather than a hole in the check.
    # They now live in `icons.tsx` behind a second geometry constant
    # (`SHELL_ICON`), byte-identical in the browser, and AppShell declares no
    # `<svg>` at all. The PO's "only one reference point not two" (2026-08-20)
    # does not say "one per family".
    #
    # ⚠ SO THIS DICT IS BACK TO ONE ENTRY — KEEP IT THERE. A second name here is
    # a second vocabulary by definition, and the only reason DEF-349 was ever
    # visible is that adding one costs an edit to this file.
}

OPEN_ROW_ACTIONS = re.compile(r"<RowActions>")
# Every glyph the rule-15 vocabulary exports. Read from icons.tsx so the list
# cannot fall behind the file it describes.
GLYPH_DECL = re.compile(r"^export function (\w+Icon)\(", re.M)
# A button that is NOT a row action, with a glyph inside it.
BUTTON_BODY = re.compile(r"<(Button|button)\b((?:(?!</?(?:Button|button)\b).)*?)</\1>", re.S)
# What a row-actions block is allowed to contain, beyond whitespace, JSX braces,
# comments and the two row-action elements themselves.
FORBIDDEN_IN_CELL = re.compile(r"<(button|Button|a|Link|ButtonLink|GuardedButton)\b")
SVG_DECL = re.compile(r"<svg[\s>]")
#: How a table column says it is the ACTIONS column. Every one of them labels
#: itself through the i18n catalogue, which is exactly why a source grep for the
#: LABELS ("Edit", "Delete") finds zero components — DEF-337's escape column.
ACTIONS_COLUMN = re.compile(r'["\'`][\w.]*\.col(?:umn)?\.actions["\'`]')

#: Files that name an actions column and legitimately draw no row action.
#: Each entry is a decision somebody wrote down, never a pattern.
#: Files clause 1b does not read. The first two OWN the vocabulary; the third is
#: CR-045 A.3's ratified exception and carries `DEF-1152` for the collision it
#: creates with the PO ruling of 2026-08-20. ⚠ ADD A NAME HERE WITH ITS RULING
#: QUOTED — never widen the pattern, and never delete the clause.
GLYPH_ON_BUTTON_EXEMPT = {
    "components/icons.tsx",
    "components/RowActions.tsx",
    "components/DownloadButton.tsx",  # CR-045 A.3, PO-ratified 2026-08-27 · DEF-1152
}

ACTIONS_COLUMN_EXCEPTIONS = {
    # A LINE EDITOR, not a list. The "column" is the remove control on a row of
    # a journal entry being TYPED — the entry does not exist yet, so there is no
    # record to act on and rule 15's "row action" does not describe it. Left as
    # a worded link deliberately; converting it would put a 16px glyph in a form.
    "features/ledger/JournalEntryModal.tsx": "the JE line editor — form rows, not records",
    # Already an icon control with an accessible name, drawn as a text glyph
    # rather than an SVG from the vocabulary. It satisfies rule 15's INTENT and
    # not its letter; folding it in needs the ✉ glyph added to icons.tsx, which
    # is a change to the vocabulary and belongs in its own commit.
    "features/notifications/NotificationRules.tsx": "an icon button, glyph not yet in icons.tsx",
}


def _strip_comments(text: str) -> str:
    """Blank out // and /* */ comments so prose about a rule never trips it.

    ⚠ THIS IS NOT FUSSINESS. Documenting a Route B escape hatch by example
    tripped `g31_declared_classes.py` FROM A COMMENT, twice — a gate that reads
    source has to be told the difference between code and a sentence about code.
    """
    # ⚠ **LINE COMMENTS GO FIRST — DEF-741.** A `//` line that spells a path
    # with a star in it (`// see src/i18n/locales/*.json`) contains `/*`, so
    # stripping BLOCK first opens a comment there and closes it at the next
    # `*/` anywhere below, blanking every line between. Measured 2026-08-26:
    # 3,620 bytes of real code across eight files. The gate reports PASS on
    # what it cannot see, which is the failure mode this repo keeps hitting.
    text = re.sub(r"//[^\n]*", lambda m: " " * len(m.group(0)), text)
    return re.sub(r"/\*.*?\*/", lambda m: re.sub(r"\S", " ", m.group(0)), text, flags=re.S)


def _blocks(text: str) -> list[tuple[int, str]]:
    """Every `<RowActions>…</RowActions>` body, with the line it starts on."""
    out = []
    for m in OPEN_ROW_ACTIONS.finditer(text):
        end = text.find("</RowActions>", m.end())
        if end == -1:
            continue
        out.append((text[: m.start()].count("\n") + 1, text[m.end() : end]))
    return out


def run() -> tuple[str, str]:
    problems: list[str] = []
    cells = 0
    actions = 0

    for path in sorted(SRC.rglob("*.tsx")):
        rel = str(path.relative_to(SRC))
        if rel.endswith(".test.tsx"):
            continue
        raw = path.read_text("utf-8", errors="replace")
        text = _strip_comments(raw)

        # ── 3. one owner for the vocabulary ──────────────────────────────
        if SVG_DECL.search(text) and rel not in SVG_OWNERS:
            problems.append(
                f"{rel} declares an inline <svg>. The B14 rule 15 vocabulary lives in "
                f"components/icons.tsx and nowhere else — that is DEF-348, where the same "
                f"pencil existed four times under two names. Import the glyph, or add it "
                f"to icons.tsx if it is genuinely new."
            )

        # ── 1. a row-actions cell contains only row actions ──────────────
        for line, body in _blocks(text):
            cells += 1
            actions += body.count("<RowAction")
            bad = FORBIDDEN_IN_CELL.search(body)
            if bad is not None:
                problems.append(
                    f"{rel}:{line} — a <{bad.group(1)}> inside <RowActions>. B14 rule 15: row "
                    f"actions are icons with tooltips, never text links (DEF-337). Use "
                    f"<RowAction> for a command and <RowActionLink> for a navigation."
                )

    # ── 1b. a glyph is a TABLE ACTION, never a button's label ────────────
    #
    # PO ruling 2026-08-20, on being shown the retire-✕-vs-delete-🗑 choice:
    # *"this only for table actions ; not for buttons"*. So the vocabulary is
    # scoped: `RowAction` draws glyphs, and an ordinary button says a word.
    #
    # ⚠ THE PRODUCT ALREADY OBEYED THIS when the ruling arrived — all 50 glyph
    # uses were row actions — which is exactly when a rule is cheapest to fix in
    # place and most likely to be broken later by someone who never heard it.
    #
    # ⚠ **AND ON 2026-08-27 A LATER PO RULING ASKED FOR EXACTLY ONE EXCEPTION,
    #    WHICH IS WHY THERE IS A NAMED SET BELOW AND NOT A PATTERN.** CR-045
    #    (ratified 2026-08-27) task A.3: *"`DownloadButton` → `↓` icon-only,
    #    `Download CSV` as `aria-label` + `title`, both the plain and the
    #    CSV/PDF menu variants. Glyph imported from `components/icons.tsx`
    #    (B14 rule 15 / G37), never inline"*. The PO's own words behind it:
    #    *"In tool bat you need filter also and icon forn downlon csv"*.
    #
    #    **This DOES reverse the 2026-08-20 ruling for this one control, and
    #    CR-045's step 2 says "None" — it did not spot the reversal.** Recorded
    #    as `DEF-1152` rather than resolved here, because a lane cannot decide
    #    which of two PO rulings wins. What the lane CAN observe: **B14 rule 4
    #    is RATIFIED and already lists `↓` as download BUTTON grammar**, beside
    #    `+ Noun`, `Verb →` and `Verb ✓` — so rule 4 and the 2026-08-20 ruling
    #    have been in tension since before either arrived, and the honest
    #    reading is that rule 4's markers are TYPOGRAPHIC (characters in copy,
    #    as the 39 ` →` keys in `en.json` are) while rule 15's are SVG row-action
    #    icons. CR-045 asks for the SVG on the button, which crosses that line.
    #
    #    The exemption is therefore NARROW, NAMED and CITED — the shape DEF-349
    #    set for this gate — and it covers one file, so the other 214 components
    #    are checked exactly as before.
    glyphs = set(GLYPH_DECL.findall(ICONS.read_text("utf-8", errors="replace")))
    glyph_re = re.compile(r"<(" + "|".join(sorted(glyphs)) + r")\s*/>")
    for path in sorted(SRC.rglob("*.tsx")):
        rel = str(path.relative_to(SRC))
        if rel.endswith(".test.tsx") or rel in GLYPH_ON_BUTTON_EXEMPT:
            continue
        body_text = _strip_comments(path.read_text("utf-8", errors="replace"))
        for m in BUTTON_BODY.finditer(body_text):
            hit = glyph_re.search(m.group(2))
            if hit is not None:
                line = body_text[: m.start()].count("\n") + 1
                problems.append(
                    f"{rel}:{line} — <{hit.group(1)}> inside a plain <{m.group(1)}>. PO ruling "
                    f"2026-08-20: the rule-15 glyph vocabulary is for TABLE ACTIONS, "
                    f'"not for buttons". Use <RowAction> in a row, or a word on a button.'
                )

    # ── 2. the accessible name is still written, on EVERY element that can
    #       be a row action ────────────────────────────────────────────────
    #
    # ⚠ THE FIRST VERSION OF THIS CHECK SEARCHED THE WHOLE FILE FOR THE STRING
    # AND WAS USELESS. `RowActions.tsx` renders THREE elements — RowAction's
    # button, and RowActionLink's two branches (a disabled button, an enabled
    # link) — and every one of them writes `aria-label={props.label}`. So
    # deleting the attribute from RowAction, which is every row action in the
    # product, left the string present twice and the gate printed PASS. It was
    # caught by DEF-337's prevention column insisting the guard be proved RED on
    # a NAMELESS ICON specifically, and by nothing else: the check ran, produced
    # confident output, and could not distinguish pass from fail. That is the
    # DEF-182 shape, one gate later.
    kit = _strip_comments(ROW_ACTIONS.read_text("utf-8", errors="replace"))
    # ⚠ NON-capturing group. `re.findall` with a capture returns the GROUP,
    # so `(Button|ButtonLink)` yields ["Button", "Button", "ButtonLink"] and
    # every one of them "lacks" the attribute. Caught because the gate went
    # loudly red on a healthy tree rather than quietly green on a sick one.
    rendered = re.findall(r"<(?:Button|ButtonLink)\b[^>]*>", kit, flags=re.S)
    if not rendered:
        problems.append(
            "components/RowActions.tsx renders no <Button> or <ButtonLink> at all — this gate "
            "cannot see what a row action is any more, which is a failure and not a pass."
        )
    nameless = [e for e in rendered if "aria-label={props.label}" not in e]
    if nameless:
        problems.append(
            f"{len(nameless)} of {len(rendered)} element(s) in components/RowActions.tsx render "
            f"WITHOUT `aria-label={{props.label}}`. That attribute is the only place a row "
            f"action gets an accessible name, and an icon without one passes every "
            f"text-absence check in the suite while being unusable without a mouse — the "
            f"failure the obvious guard misses (B14 rule 15's own note)."
        )

    # ── 4. AN ACTIONS COLUMN THAT NEVER REACHES CHECK 1 ──────────────────
    #
    # ⚠ THIS IS THE HOLE CHECKS 1-3 LEFT, AND IT HID FIVE TABLES FOR A DAY.
    # Every check above reads INSIDE a `<RowActions>` block, so a table that
    # never adopted the component is invisible to all of them: G37 printed
    # PASS over `BudgetBillsTab` ("Recheck the amount / Use my amount / Take
    # off budget billing" as three words in one cell) and over
    # `CostOfServicePage` ("Correct / Void") — which is DEF-337's own sentence,
    # still true, under a gate written to end it.
    #
    # A gate that can only see the files that already obey it measures
    # compliance among the compliant. So: a file that DECLARES AN ACTIONS
    # COLUMN must use the component. The declaration is findable because every
    # such column labels itself through the catalogue — `…col.actions` or
    # `…column.actions` — which is also the reason a grep for "Edit"/"Delete"
    # finds nothing (DEF-337's escape column says exactly this).
    for path in sorted(SRC.rglob("*.tsx")):
        rel = str(path.relative_to(SRC))
        if rel.endswith(".test.tsx") or rel in ACTIONS_COLUMN_EXCEPTIONS:
            continue
        text = _strip_comments(path.read_text("utf-8", errors="replace"))
        if ACTIONS_COLUMN.search(text) is not None and "<RowActions>" not in text:
            problems.append(
                f"{rel} declares an ACTIONS column and uses no <RowActions>. Every other "
                f"check in this gate reads inside that component, so a table without it is "
                f"invisible to all of them — which is how five text-link tables survived "
                f"DEF-337's own fix. Convert the cell, or name the file in "
                f"ACTIONS_COLUMN_EXCEPTIONS with the reason it is not a row action."
            )

    if problems:
        return "FAIL", f"{len(problems)} rule-15 problem(s): " + "; ".join(problems[:4]) + (
            f" (+{len(problems) - 4} more)" if len(problems) > 4 else ""
        )

    print(
        f"note: {cells} row-action cell(s) across the product, {actions} action(s); "
        f"{len(SVG_OWNERS)} file(s) may declare an <svg>"
    )
    return "PASS", "every row action is an icon with an accessible name, from one vocabulary"


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())


# ── RED PROOFS ─────────────────────────────────────────────────────────────
# Hard-won law 7: prove a new guard goes RED before trusting it green. DEF-337's
# prevention column asks for TWO, and the second is the one that matters.
#
# 1 · A TEXT LINK back in a cell. A `<button className="btn btn-ghost">{t(…)}</button>`
#     added inside SettingsCustomFields' <RowActions>:
#       FAIL: features/tenancy/SettingsCustomFields.tsx:377 — a <button> inside
#       <RowActions>. B14 rule 15: row actions are icons with tooltips, never
#       text links (DEF-337).
#
# 2 · AN ICON WITH NO ACCESSIBLE NAME. `aria-label={props.label}` deleted from
#     `RowAction` — every row action in the product, nameless:
#       FAIL: 1 of 3 element(s) in components/RowActions.tsx render WITHOUT
#       `aria-label={props.label}`.
#
#     ⚠ THIS PROOF FAILED THE FIRST TIME AND THE GATE PRINTED **PASS**. The
#     check searched the whole FILE for the string, and `RowActionLink`'s two
#     branches carry it too — so removing it from the component that renders
#     every row action left the string present twice and the gate said the
#     product was fine. It reads each rendered ELEMENT now. Nothing else would
#     have found this: the gate ran, produced confident output, and could not
#     distinguish pass from fail. That is DEF-182's shape — a check that is
#     trusted and cannot answer its own question — one gate later, and it was
#     found only because this proof was insisted on rather than assumed.
#
# 3 · A TABLE THAT NEVER ADOPTED THE COMPONENT (check 4, added 2026-08-21).
#     Proved RED against the tree BEFORE the Wave B conversion:
#       FAIL: 5 rule-15 problem(s): features/billing/BudgetBillsTab.tsx declares
#       an ACTIONS column and uses no <RowActions>. …
#     Five files, and the gate had printed PASS over all five since the day it
#     was written. ⚠ THE LESSON IS NOT "ADD A CHECK" — it is that checks 1-3 each
#     asked a correct question of the wrong population. A gate scoped to the
#     component it enforces can only ever measure compliance among the compliant,
#     and it reads as protection that is not there.
#
# 3 · A FIFTH PENCIL, drawn inline in AssetRegistryPage instead of imported:
#       FAIL: features/assets/AssetRegistryPage.tsx declares an inline <svg>.
#
# Each sabotage was reverted and the file verified byte-identical afterwards.
