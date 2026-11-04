# P6 · Property → Common areas — THE DRAWN SPEC

`PRM-02` · breadcrumb `Premises → a premise → Common areas` · **blueprint page 25–28**

**Source:** `05-prototype/Premises & Units Blueprint 2.pdf` (the copy on
`origin/claude/confirm-understanding-3ktufc`), the section opening at the foot of
page 25, drawn on 26, specified on 27 and the RULES row at the top of 28. Read as
rendered pages.

**State chip:** `EXISTS BEHIND`
**Commitments on the chip line:** `PUJ-05` · `PUJ-13`

**CR-089 task rows this screen belongs to:** `C2` (common areas can be added from
their own tab) · `F3` (the four tiles on every property tab). `B5` fills this tab
from the create flow.

**What this file is.** Only the **bordered grey frame** on page 26 is the
specification. The amber block above it — *"Every new building arrives here reading
`None on this property` … There is no `+ Add` on the tab either"* — is the problem
statement, never the target.

---

## 1 · Header — identical to P4

| slot | drawn |
|---|---|
| kicker | `PREMISE` |
| title (H1) | `412 Cypress Row` |
| sub-line 1 | `P-00080` · `Silver Creek, TX 78611` · `Apartment complex` · `ACTIVE` *(pill)* |
| sub-line 2 | `Route 12 · Cycle 3 — bills on the 12th` |

## 2 · Header actions — in the drawn order

| # | label | tier |
|---|---|---|
| 1 | `✎ Edit` | primary |
| 2 | `+ New unit` | secondary |
| 3 | `Change status` | **danger** |

The screen's own **PRIMARY ACTION** is the toolbar's `+ Add a common area.`

## 3 · Tabs — six, in this order, `Common areas` active

`Overview` | `Units` | `Common areas` | `Assets` | `Work orders` | `Audit log`

## 4 · Tiles — the same four, with their detail lines

| # | value | label | detail line |
|---|---|---|---|
| 1 | `4` | `UNITS` | `3 occupied · 1 vacant` |
| 2 | `9` | `ASSETS` | `4 metered, all read this cycle` |
| 3 | `$0.00` | `OWED HERE` | `across 3 accounts` |
| 4 | `1` | `OPEN WORK ORDER` | `meter change, Thursday` |

## 5 · Toolbar — drawn above the table, one row

| # | element | drawn text |
|---|---|---|
| 1 | search input | placeholder `Search common areas…` |
| 2 | button, right-aligned | `+ Add a common area` |

No `ALL` chip and no `+ Filter` on this tab — that is the Units tab's toolbar, not
this one.

## 6 · Table columns — SEVEN, in this order

| # | column header | alignment | cell |
|---|---|---|---|
| 1 | `Common area` | left | bold — `Laundry`, `Corridor lighting` |
| 2 | `What it is` | left | **in words** — `Shared room`, `Shared lighting`, `car park` — never a type code |
| 3 | `Meters` | left | `E · W`, `E` |
| 4 | `Billed to` | left | the owner's party then its account, quiet — `Creekside Holdings LP` `A-10442` |
| 5 | `Owed` | **right, tabular** | `34.90`, `12.10` — two decimals |
| 6 | `Status` | left | pill: `ACTIVE` |
| 7 | *(no header)* | right | row actions as icons: `👁` `✎` `…` |

**Column 4 is the reason the tab exists.** *"A `Billed to` column naming the owner's
account, because `who pays for the corridor light` is the only question this tab
exists to answer."*

**Column 2 is words, not a code.** *"What it is, in words — shared room, shared
lighting, car park — rather than a type code."*

## 7 · Footer

Left: `Showing 2 of 2 · both bill to the owner's account`
Right: `⇤ ← Page 1 of 1 → ⇥`

## 8 · States — the blueprint's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **None** | Says what a common area is — *a shared space with its own meter, billed to the owner* — and **offers to add one**. |
| **No owner on the property** | `Billed to` reads `Needs an owner` **and links to it**, because a common area with nobody to bill is a real problem, not a blank cell. |

Loading, error and permission-refusal states are **not drawn**.

## 9 · Cognitive load, as stated

*"Seven columns, **no prose beyond the empty state**."* — no explainer paragraph, no
master-account callout, no stated-absence blocks anywhere on this tab.

## 10 · Components named

`CommonAreasTab` `DataTable` `StatusPill` `MoneyCell` `InlineLinkTo`

## 11 · Rules it must obey

*"Every list has an empty state that says what is missing and offers the action that
fills it. No database id on screen."*

## 12 · Absences — drawn as absent, do not fill them

* No `Plan` column.
* No master-account fact block above the table, no payer row, no coverage row.
* No `Common` pill inside the name cell — the tab is already about common areas.

---

## 13 · WHAT WAS BUILT AGAINST THIS FILE — 2026-09-10 (`2.234.16`)

`DEF-4739` (the component) and `DEF-4740` (the columns), the Common-areas half.
Decision log, same date: *"PRM-02's Common areas and Work orders tabs, against
the drawn frame"*.

**Built to the frame:** the shared `DataTable` in place of the in-panel table,
which restores the search box (`Search common areas…`), the column chooser and
the pagination footer · the **seven** drawn columns in the drawn order, `Plan`
removed · `+ Add a common area` as the toolbar's primary, with its `+` · the
`None` empty state saying what a common area IS and offering to add one · no
filters declared, which is how §5's *"no `ALL` chip and no `+ Filter`"* gets
drawn (`BR-SHL-010`: an undeclared capability never renders) · §9's *no prose*:
the `<h3>` and both paragraphs are gone and the stated absences are in a
disclosure CLOSED by default (B14 rule 32).

**`Billed to` is answerable and `DEF-560` is not the reason it was missing.**
That defect's reasoning — a master ANCHORS on one common area, `GET /accounts`
filters on `unit_id` — expired on 2026-09-01 when `CR-056` W1 / `BR-CUS-1010`
moved the master account onto the ADDRESS. One master at an address is the payer
for every common area on it. What survives is narrower: `POST /accounts/master`
accepts `unit_ids` to narrow coverage, so a premises with MORE THAN ONE master
cannot say which pays for a given area — that case says so in three words and
names none of them.

### WHERE THIS FILE IS WRONG, OR ASKS FOR SOMETHING THAT DOES NOT EXIST

* **§6 column 2 — the vocabulary does not exist.** *"Shared room, shared
  lighting, car park"* are not `unit_type` values; `BR-MET-084` seeds five, and
  the one a common area carries is `common_area`. The column draws the type in
  words through the catalogue, so it reads **Common area**, and a row created by
  this tab's own modal — which captures a name and the flag and nothing else —
  draws a **dash**. `DEF-MET-4750`. Minting the drawn three as unit types is new
  vocabulary and is the PO's, not ours.
* **§6 column 7 — one glyph of three.** `👁` opens the unit. The pencil and the
  overflow have nowhere to go: a common area is a unit and its edit lives on the
  unit's page. A control that opens nothing is hard-won law 2. `DEF-MET-4751`.
* **§7 — the footer's second half has no slot.** *"both bill to the owner's
  account"* cannot be added: `DataTable`'s footer is `Showing 1–N of M` plus the
  page size and the arrows, and growing a sentence slot on the shared table is
  `DEF-1700`'s shape and not this lane's to take. `DEF-MET-4753`.
* **§8 state 2 — *links to it* is read as the property's Overview.** That is
  where the Owner fact and its **Find an owner** control live. The blueprint
  does not say what *it* is, and the master-account create — the other candidate
  — is a different act with a different name.
* **§10 — `MoneyCell` yes, `InlineLinkTo` yes; `StatusPill` yes.** No component
  was invented.
