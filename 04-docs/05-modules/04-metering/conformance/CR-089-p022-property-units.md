# P5 · Property → Units — THE DRAWN SPEC

`PRM-02` · breadcrumb `Premises → a premise → Units` · **blueprint page 22–25**

**Source:** `05-prototype/Premises & Units Blueprint 2.pdf` (the copy on
`origin/claude/confirm-understanding-3ktufc`), the section opening at the foot of
page 22, drawn on 23–24, specified on 25. Read as rendered pages.

**State chip:** `EXISTS BEHIND`
**Commitment on the chip line:** `PUJ-12`

**CR-089 task rows this screen belongs to:** `C1` (the Units tab carries what each
unit owes) · `F3` (the four tiles on every property tab). `E1`'s columns belong to
the **module's** Units list, not to this tab.

**What this file is.** Only the **bordered grey frame** on pages 23–24 is the
specification. The amber block above it lists the columns a clerk hits TODAY —
`Unit ID · Unit · Type · Meters · Occupancy · Status` — and that is the problem
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

The screen's own **PRIMARY ACTION** is the toolbar's `+ New unit`, *"which goes
straight to the add-units screen with this building already the subject."*

## 3 · Tabs — six, in this order, `Units` active

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
| 1 | search input | placeholder `Search units…` |
| 2 | chip | `ALL` |
| 3 | filter control | `+ Filter ⌄` |
| 4 | button, right-aligned | `+ New unit` |

## 6 · Table columns — EIGHT, in this order

| # | column header | alignment | cell |
|---|---|---|---|
| 1 | `Unit` | left | **the label leads, bold** (`1`), with the unit number **beneath it in the same cell**, quiet (`U-01144`). Default sort is the LABEL |
| 2 | `Type` | left | `Residential` |
| 3 | `Floor` | left | `Ground` / `First`; `none yet` in the absent style |
| 4 | `Meters` | left | `E · W`; `none yet` italic where there are none |
| 5 | `Occupant` | left | a **name and its account** — `M. Alvarez` then `A-10517` quiet. On a vacant unit it reads `Vacant — base charges bill to the owner`, italic |
| 6 | `Owed` | **right, tabular** | `61.40` · `0.00` · `118.05` · `0.00` — two decimals, no currency glyph on the rows |
| 7 | `Status` | left | pill: `OCCUPIED` / `VACANT` |
| 8 | *(no header)* | right | row actions as icons: `👁` `✎` `…` |

**Column 1 is ONE cell, not two.** *"The label leads and the unit number sits under
it, quiet, in the same cell — the shape the units list uses. Both are shown … what
changes is which of the two the eye meets first, and what the table sorts by."*

⚠ The first column is **not** a database id and the blueprint says so twice
(pages 23 and 25): it is `unit_no`, *"the number from the tenant's own series — a
printed reference, as legitimate as a property number."* An earlier draft calling it
a B14 rule 31 breach **is corrected**. Nothing is removed; only its weight changes.

**Column 5 replaces the old `Occupancy` state word.** *"Occupant instead of occupancy
— a name and its account, not a state word. The state is in the status pill where it
belongs."*

**Column 6 is the new one.** *"An `Owed` column, right-aligned and tabular, so a
landlord's question is answered by looking rather than by opening four units."*

**A vacant row never draws a dash in the occupant cell.** *"A dash on that row reads
as `nothing is billed`, which is the opposite of true."* The vacant row still draws
`0.00` in `Owed`.

## 7 · Footer

Left: `Showing 4 of 4 · 3 occupied, 1 vacant`
Right: `⇤ ← Page 1 of 1 → ⇥`

## 8 · States — the blueprint's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **No units** | The empty state **offers to add them**, and says a property with no units bills nothing. |
| **All vacant** | Every row carries the owner-billing sentence; the tab's own count says how many. |

Loading, error and permission-refusal states are **not drawn**.

## 9 · Cognitive load, as stated

*"Eight columns, one search, **no prose**."* — no explainer paragraph, no callout, no
hint line anywhere on this tab.

## 10 · Components named

`DataTable` `FilterBar` `RowActions` `StatusPill` `MoneyCell` `UnitCell`
`InlineLinkTo`

## 11 · Rules it must obey

*"A printed reference from the tenant's own series is shown; a database id never is.
Money right-aligned, two decimals, tabular. An absence is drawn as an absence."*

## 12 · Absences — drawn as absent, do not fill them

* No `Plan`, `Services` or `Select` column.
* No bulk-action bar.
* No `Unit ID` column of its own — the number lives inside column 1.


---

## AMENDMENTS — what was BUILT on 2026-09-10 (`DEF-4739` · `DEF-4740`)

The tab drew `PlainTable` with `Unit ID · Unit · Type · Meters · Occupancy ·
Status · Owed` — the amber block's own column list plus a money column in the
wrong place. It now draws the shared `DataTable` + `FilterBar` this file names
in §10, with the drawn eight in the drawn order, so the search box, the `ALL`
chip, `+ Filter ⌄`, the column chooser and the pagination footer are all on it.

**What was fixed:** `Unit ID` + `Unit` become ONE `Unit` cell (label bold,
number quiet beneath) · `Floor` arrives, with `none yet` in the absent style ·
`Occupancy` becomes `Occupant` (a name and its account) · `Owed` moves BEFORE
`Status` · the vacancy sentence moves into the `Occupant` cell · the hint line
*"Accounts attach to units, not to premises"* is deleted, per §9's *"no prose"*.

### ⚠ `Owed` ON A VACANT ROW — THE DRAWN `0.00` IS CONDITIONAL, BY PO RULING

PO, 2026-09-10: the vacancy sentence moves to `Occupant` and `Owed` shows
`0.00` — **"but keep the existing protection: show `0.00` only when the balance
really is zero, never manufactured over a real debt."**

So the built cell prints `0.00` for a unit whose ledger really reads zero, and
**`Not measured`** in the absent style for a unit with **no occupying account**,
where no ledger read happened at all. `owed_for_units` resolves the OCCUPYING
account (`BR-CUS-055`'s behaviour class), and a unit whose tenant moved out
**still owing** has a CLOSED account that map deliberately excludes — so a
manufactured zero there says *nothing is owed* over a real debt. That is
`DEF-138` word for word: a guard reading a column nobody writes and answering
`False` for every unit in the estate, one of which held an unpaid **108.88**.
The sentence a reader needs is on the same row, in `Occupant`.

### Departures, recorded rather than left to be found

1. **THE ROW-ACTION COLUMN (`👁 ✎ …`) IS NOT BUILT.** The whole unit row already
   opens its detail through the `Unit` cell, and what `✎` and `…` would commit
   is not stated anywhere in this frame. Three icons pointing at one destination
   and two unstated ones is dead UI (hard-won law 2), so the column is absent
   and this is the record of why. **Open.**
2. **THE TOOLBAR'S RIGHT-ALIGNED `+ New unit` IS NOT DUPLICATED.** §2 puts
   `+ New unit` in the header AND §5 puts it in the toolbar; B14 rule 4 allows
   one primary per screen and the header's is live. The EMPTY state carries it
   instead, which is where §8 asks for it (*"the empty state offers to add
   them"*).
3. **THE FOOTER SENTENCE SITS UNDER THE KIT'S PAGER, NOT INSIDE IT.** §7 draws
   `Showing 4 of 4 · 3 occupied, 1 vacant` as one line; `DataTable`'s pager is
   shared by 27 lists and says `1–4 of 4`, and the occupied/vacant clause is the
   line beneath it. Both numbers are present and true; only their line differs.
