# U8 · Unit → Occupancy — THE DRAWN SPEC

`S15 · PRM-03` · breadcrumb `Premises → Units → a unit → Occupancy` ·
**blueprint pages 83–85**

**Source:** `05-prototype/Premises & Units Blueprint 2.pdf`. The section opens
half-way down **page 83** (title, question, breadcrumb, amber block, and the top
of the grey frame), the **bordered grey frame** completes on **page 84**, the
teal *WHAT CHANGED* block and the first half of the specification table are on
**84**, and `STATES` · `COMPONENTS` · `RULES` are on **page 85**. Read as
rendered pages.

**State chip:** `EXISTS BEHIND`
**Commitment on the chip line:** `PUJ-42`

**CR-089 task rows this screen belongs to:** `F4` (*"a vacancy is a row on the
occupancy tab"*, `PUJ-42`, marked **DONE 2026-09-09**) · `F3` (the four tiles).

**The question the screen answers, as drawn:** *who has lived here, and when was
it empty?*

⚠ **ONLY THE BORDERED GREY FRAME ON PAGES 83–84 IS THE SPECIFICATION.** The amber
block is what a clerk hits today — *"The columns are `Occupant · Account · Start ·
End · Status`, which is close to right. **What is missing is the vacancy** — the
gaps between tenancies are not rows, so a landlord asking how long their flat
stood empty cannot be answered from the tab that exists to answer it."*

---

## 1 · Header — identical to U7, drawn again in full

| slot | drawn |
|---|---|
| kicker | `UNIT` |
| title (H1) | `Unit 2` |
| sub-line 1 | `U-01145` · `412 Cypress Row, Silver Creek, TX 78611` · `Residential` · `ACTIVE` *(pill)* · `OCCUPIED` *(pill)* |
| sub-line 2 | `Route 12 · Cycle 3 — from the building` |

## 2 · Header actions — in the drawn order

| # | label | tier as drawn |
|---|---|---|
| 1 | `✎ Edit` | secondary |
| 2 | `Move` | secondary |
| 3 | `Change status` | **emphasised / danger tier** |

## 3 · Tabs — six, `Occupancy` active

`Overview` | `Assets` | `Plan` | `Account` | **`Occupancy`** | `Audit log`

## 4 · Tiles — the same four, with their detail lines

| # | value | label | detail line |
|---|---|---|---|
| 1 | `5` | `ASSETS` | `2 metered · 3 behind the meter` |
| 2 | `$61.40` | `OWED` | `due 24 Sep` |
| 3 | `Standard` | `PLAN` | `since 1 Jun 2026` |
| 4 | `—` | `OPEN WORK` | `nothing booked` |

## 5 · Toolbar

**None is drawn.** The frame goes straight from the tile strip to the table
header — no search box, no `ALL` chip, no `+ Filter ⌄`, no column chooser.

## 6 · Table columns — SIX, in this order

| # | column header (exact) | alignment | cell as drawn |
|---|---|---|---|
| 1 | `Occupant` | left | a person's name, **bold on the current tenancy** (`M. Alvarez`); `Vacant` *italic, absent style* on a gap row |
| 2 | `Account` | left | `A-10517`; `—` on a gap row |
| 3 | **`From`** | left | `1 Jun 2026` |
| 4 | **`To`** | left | `28 May 2026`; ***`still here`*** *italic, absent style*, on the open tenancy |
| 5 | **`Left owing`** | **right, tabular** | `61.40` · `0.00` · `0.00` — two decimals, **no currency glyph** |
| 6 | `Status` | left | **pill**: `CURRENT` · `CLOSED` · `VACANT PERIOD` |

## 7 · The rows, in the order drawn — NEWEST FIRST

| # | Occupant | Account | From | To | Left owing | Status |
|---|---|---|---|---|---|---|
| 1 | `M. Alvarez` | `A-10517` | `1 Jun 2026` | *`still here`* | `61.40` | `CURRENT` |
| 2 | `R. Nakamura` | `A-10203` | `3 Feb 2025` | `28 May 2026` | `0.00` | `CLOSED` |
| 3 | *`Vacant`* | `—` | `1 Dec 2024` | `3 Feb 2025` | `0.00` | `VACANT PERIOD` |

⚠ **THE ORDER IS NEWEST FIRST**, and the vacancy still sits between the two
tenancies it separates — row 3 is the gap BEFORE row 2's tenancy, and it is drawn
BELOW it.

⚠ **THE GAP DRAWN IS THE LEADING ONE** — before the first tenancy — and its `From`
is not the close of any tenancy. The blueprint's `Never occupied` state says why:
*"One vacant row from the day the unit was created, so the tab is never blank."*

⚠ **THE GAP'S BOUNDING DATES ARE THE NEIGHBOURING TENANCIES' OWN DATES**, not
day-after / day-before: the `To` is `3 Feb 2025`, which is row 2's `From`. The
Account tab's `Vacant between` row on page 80 uses the same convention —
*"28 May to 1 Jun 2026 · 4 days"* names the two TENANCY dates with the count
between them.

⚠ **Every worked value above is an ILLUSTRATION.** The labels, the order, the
column count, the alignment and the presence of each row shape are the
specification.

## 8 · Footer

Left: `Showing 3 · this unit has been vacant once in two years`
Right: `⇤ ← Page 1 of 1 → ⇥`

*WHAT CHANGED*: *"A footer that counts the vacancies, which is the summary of the
whole tab in one line."*

## 9 · Specification table — page 84–85

**FOR** — *"A landlord's agent asking how long a flat stood empty, and a clerk
investigating an opening balance."*

**HOW YOU GET HERE** — *"The unit's page → Occupancy."*

**PRIMARY ACTION** — *"None. It is a history."*

**WHAT CHANGED · THE GAPS ARE ROWS** — *"A vacancy is a fact about the unit and it
was inferable only by subtracting dates."*

**COGNITIVE LOAD** — *"Six columns, no prose."*

## 10 · States — the blueprint's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **Never occupied** | *"One vacant row from the day the unit was created, so the tab is never blank."* |
| **Common area** | *"Shows the owner's account for the whole period; a common area is never vacant."* |

Loading, error and permission-refusal states are **not drawn**.

## 11 · Components named

`PlainTable` `DateCell` `MoneyCell` `StatusPill`

⚠ **`PlainTable` IS THE NAMED COMPONENT HERE, and that is not a slip** — the same
specification table names `DataTable` and `FilterBar` for the Audit tab two pages
later, so the choice is being made per screen. This tab draws no toolbar, so the
premises half's root cause 1 does **not** apply to it.

## 12 · Rules it must obey, as stated

> *"An absence is drawn as an absence, never an empty cell. Money right-aligned
> and tabular. No database id on screen."*

## 13 · Absences — drawn as absent, do not fill them

* **No `Closing read` and no `Final bill` column.** r10 drew seven columns; the
  blueprint draws six and those two are not among them.
* **No toolbar, no search, no filter, no column chooser.**
* **No row actions column.**
* **No prose** — no explainer, no callout, no hint line anywhere on the tab.

---

## BLUEPRINT SELF-CONTRADICTIONS FOUND — recorded, NOT resolved

Per the 2026-09-10 PO ruling the **frame wins and the sentence gets corrected**;
where two FRAMES disagree there is no such rule, so both are recorded.

1. **Frame versus frame — the same tenancy, two account numbers and two start
   years.** This frame draws `R. Nakamura · A-10203 · 3 Feb 2025`; the Account
   tab's frame on page 80 draws `R. Nakamura · A-10388 · 3 Feb 2024`.
2. **Frame versus frame — the 28 May → 1 Jun 2026 gap.** The Account tab draws it
   as a `Vacant between` row of four days; this table does not draw it at all,
   and this tab's own footer then reads *"this unit has been vacant once in two
   years"*. Either the footer's count or the table's row set is wrong in the
   illustration.
3. **Frame versus specification table — the pager.** The frame draws a pagination
   footer (`⇤ ← Page 1 of 1 → ⇥`); `COMPONENTS` names `PlainTable DateCell
   MoneyCell StatusPill` and no pager component at all. The frame wins by the
   ruling, so a pager is owed and the component list is the half to correct.

---

## THE DIFF — the live component against this frame, 2026-09-10

**Component:** `07-frontend/src/features/metering/UnitOccupancyTab` —
`07-frontend/src/features/metering/UnitDetailPage.tsx` line **2176**; the
timeline it draws from is `occupancyTimeline` at line **2376**.
**Catalogue:** `metering.units.occupancy.*` in
`07-frontend/src/i18n/locales/en.json` — **present in all eleven catalogues**,
zero English-only `defaultValue` keys on this screen.

Walked in the skill's §4 order, stopping at the first difference per element.

### Presence

| # | drawn | built |
|---|---|---|
| 1 | column 5 **`Left owing`**, right-aligned, tabular | **the column does not exist.** There is no `metering.units.occupancy.col.leftOwing` key in any of the eleven catalogues, and no `<th>` for it (headers at lines 2202–2206). ⚠ **AND THE FIGURE IS ALREADY ON THE PAYLOAD THIS TAB READS**: the tab calls `getAccounts({ filters: { unit_id } })` (line 2186) and `AccountRow.balance` — the LEDGER's own figure since `DEF-127`, `api/endpoints.ts` line 8848 — comes back on every row. This is the premises half's root cause 2 exactly: a served value with no column reading it |
| 2 | the footer line `Showing 3 · this unit has been vacant once in two years` | **absent.** `PlainTable` renders `<table>` and nothing else; no count, no vacancy summary. ⚠ The helper for exactly this line already exists — `TabFooterCounts`, `PremisesDetailPage.tsx` line **188**, written for this blueprint's footers and used on two premises tabs (lines 1955 and 2364) — and this tab does not call it |
| 3 | the pager `⇤ ← Page 1 of 1 → ⇥` | **absent.** The shared `ListPager` exists (`components/ListPager.tsx`) and is not used here |
| 4 | a **leading** vacancy row, from the unit's creation | **deliberately not built**, and the docstring says so at line 2363: *"⛔ NO LEADING GAP IS DRAWN … `UnitRow` carries no created-at."* So the blueprint's `Never occupied` state cannot be reached: with no accounts, line 2197 renders the sentence *"No account has ever been attached to this unit"* — **a blank tab**, which is precisely what that state exists to forbid |
| 5 | nothing else | **two `ArrivesWith` note blocks are built** (lines 2299 and 2315), each an `<h3>` plus a paragraph. See "built and not drawn" below |

### Presence — built and not drawn

| # | built | drawn |
|---|---|---|
| 6 | `ArrivesWith` — *"Closing read and final bill"* / *"…those two columns are left out rather than shown empty."* (line 2299, `tracks="DEF-509"`) | The frame draws **six columns and no prose**. ⚠ **THIS IS AN EXPLAINED ABSENCE WHOSE EXPLANATION HAS EXPIRED.** The note explains why r10's seventh and eighth columns are missing; the blueprint has since RATIFIED a six-column table that does not contain them. `DEF-509` is still `open` in `12-governance/10-defect-log.csv`, so the underlying gap is real — but it is no longer an absence this screen owes a clerk a paragraph about |
| 7 | `ArrivesWith` — *"Vacant periods"* / *"…whether that is the base charge alone or the full bill has not been decided."* (line 2315, `tracks="OQ-316"`) | Same: the frame says *"Six columns, no prose."* `OQ-316` is genuinely open and the sentence is true; where it belongs is a question for the PO, and on this frame it is prose on a tab that has a stated no-prose budget |

### Order

| # | drawn | built |
|---|---|---|
| 8 | **newest first** — current tenancy at the top | **oldest first**, and the docstring at line 2372 states it as a deliberate choice: *"Ordered oldest first — the reverse of what `GET /accounts` returns — because a timeline that reads downwards is the only order in which a gap sits BETWEEN the two tenancies that produced it."* The frame achieves the same adjacency reading upwards |

### Labels — character for character

| # | drawn | built (key → string) |
|---|---|---|
| 9 | `From` | `metering.units.occupancy.col.start` = **`Start`** |
| 10 | `To` | `metering.units.occupancy.col.end` = **`End`** |
| 11 | ***`still here`*** on the open tenancy | `metering.units.occupancy.current` = **`Current`** (line 2228) |
| 12 | `CURRENT` / `CLOSED` in the status column | the account's own `status_name` (line 2237) — the tenant's renameable label (`Active`, `Closed`…), a different vocabulary from the two occupancy words the frame draws |
| 13 | `VACANT PERIOD` in the status column of a gap row | the cell holds a sentence instead: `{{count}} days · Vacant — base charges bill to the owner` (lines 2287–2290) |

### Alignment and weight

| # | drawn | built |
|---|---|---|
| 14 | column 5 right-aligned and tabular; the frame's RULES line says *"Money right-aligned and tabular"* | no money column exists, so the rule has nothing to govern |
| 15 | `Status` as a **pill** in all three states; `COMPONENTS` names `StatusPill` | plain text (line 2237) and a qualifier span (line 2287). `StatusPill` is imported in this file and is **not used in this table** |
| 16 | `M. Alvarez` bold on the current row | plain (line 2213) |

### States

| # | drawn | built |
|---|---|---|
| 17 | **Never occupied** — *"one vacant row from the day the unit was created, so the tab is never blank"* | **not built** — see row 4. The tab goes blank with a sentence |
| 18 | **Common area** — *"shows the owner's account for the whole period; a common area is never vacant"* | **not built.** `UnitOccupancyTab` reads `unit.is_common_area` nowhere; a common area with no `accounts` row renders the same blank sentence as a never-occupied flat, and one with a gap between owner accounts would draw a `Vacant` row the state forbids |

### What matches

The six-tab strip and its order · the four tiles · `Occupant` and `Account` as
columns 1 and 2 · a vacancy drawn as a ROW at all, which is `F4`'s whole point ·
`Vacant` italic in the occupant cell and `—` in the account cell · the day count
on a gap · `PlainTable` being the right component for this tab.

**Premises root cause 1 does not apply** (the frame names `PlainTable` itself).
**Root cause 3 does not apply** (nothing commits here). **Root cause 4 does not
apply** (full catalogue parity). **Root causes 2 and 5 both apply** — rows 1 and
6/7 respectively.

### WHAT WAS FIXED — 2026-09-10, and what did not move

Everything below landed under `DEF-MET-4766` and is pinned by
`07-frontend/src/features/metering/UnitOccupancyConformance.dom.test.tsx`,
proved red at the tip first (15 of 15 failing, including *"expected Array(5) to
deeply equal Array(6)"*).

| row | disposition |
|---|---|
| **1** `Left owing` | **BUILT.** `AccountRow.balance` — the ledger's own figure since `DEF-127` — off the query this tab already made. Right-aligned and tabular; a null says *the books could not be read* and is NEVER `0.00`, because a zero under this header reads as *this tenant settled up* |
| **2** the footer counts line | **BUILT**, reusing `TabFooterCounts` (now exported rather than copied). ⚠ **The drawn line ends *"in two years"* and this one does not:** that window is the AUDIT log's (`BR-AUD-013`), and `GET /accounts?f.unit_id=` is bounded by nothing, so naming a period would be a claim about a range nobody applied. The count is what the drawing is for |
| **8** newest first | **BUILT**, reversed at RENDER so `occupancyTimeline`'s contract and unit tests are untouched. Each gap still sits between the two tenancies that produced it |
| **9/10** `From` / `To` · **11** `still here` | **BUILT.** And an open VACANCY got its OWN word — *still empty* — because the two shared one key and *still here* over an empty flat is the one reading this column must never produce |
| **12/13** the status cell | **BUILT** as a `StatusPill` carrying the TENANCY's state (`Current` · `Closed` · `Vacant period`). It printed the ACCOUNT's renameable `status_name`, which answers a different question on a row whose other five cells are about a stretch of time. **This is a deliberate vocabulary change and is recorded as one:** the account's own status is one click away on the Account tab |
| **16** the current occupant in bold | **BUILT** |
| **6** the `DEF-509` prose | **REMOVED.** An explained absence whose explanation EXPIRED — the frame ratifies six columns containing neither `Closing read` nor `Final bill`, so their absence is no longer owed a paragraph. `DEF-509` stays OPEN; its two catalogue keys were retired with the prose they worded |
| **7** the `OQ-316` prose | **KEPT.** A live question about MONEY on rows that ARE drawn is a different kind of absence. Where it belongs is still a question for the PO |
| **18** a common area is never vacant | **BUILT.** Gaps are suppressed for one, and an empty one gets the common-area sentence instead of *"no account has ever been attached"*. ⛔ The frame's *"shows the owner's account for the whole period"* half is **not** built: `owner_account` is on the Account tab's payload, not this one |
| **4/17** the LEADING vacancy · **Never occupied** | **NOT BUILT — a payload gap.** The stretch before the first tenancy has to start when the unit was CREATED and `UnitRow` carries no created-at. Inventing one from the first account's start draws a zero-day row on every unit in the product. **For the PO / the metering lane:** `GET /units/{id}` needs to serve `created_at` |
| **3** the pager | **NOT BUILT, and it would be furniture.** The tab is not paginated — it reads `per: 50` and draws every row — so `Page 1 of 1` would be a control over nothing, which is hard-won law 2's dead UI. B14 rule 38 (ratified 2026-09-10) covers the shape: the kit settles pager construction and the divergence is recorded rather than built. ⚠ **The real finding underneath is a CAP, not a pager:** a unit with more than 50 accounts silently truncates. Worth a row of its own when anyone believes that is reachable |

### Confidence

* **Confident, from source and catalogue:** every row above. Column presence,
  header strings, the ordering choice, the missing pill, the two prose blocks and
  the absent `Left owing` are all readable in the file and the catalogues.
* **Needs a running stack** (none in this container): the **Never occupied** and
  **Common area** states, which need seeded units to reach; whether the drawn
  gap-bounding convention (`28 May to 1 Jun`) or the built one (`29 May` to
  `31 May`) is what the PO expects to read, which is a walk-and-ask rather than a
  source question; and the rendered right-alignment of a money column that does
  not yet exist.
