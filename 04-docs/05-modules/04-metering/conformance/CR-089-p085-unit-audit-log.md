# U9 · Unit → Audit log — THE DRAWN SPEC

`S15 · PRM-03` · breadcrumb `Premises → Units → a unit → Audit log` ·
**blueprint pages 85–87**

**Source:** `05-prototype/Premises & Units Blueprint 2.pdf`. The section opens
half-way down **page 85** (title, question, breadcrumb, amber block, and the top
of the grey frame), the **bordered grey frame** completes on **page 86**, the
teal *WHAT CHANGED* block and the first half of the specification table are on
**86**, and the tail (`WHAT CHANGED · THE TAB HOLDS ITS OWN HISTORY` ·
`COGNITIVE LOAD` · `STATES` · `COMPONENTS` · `RULES`) is on **page 87**. Read as
rendered pages.

⚠ **THIS SCREEN'S SECTION BEGINS ON PAGE 85, INSIDE THIS LANE'S RANGE, AND ITS
TAIL FALLS ON PAGE 87.** The page-87 half is recorded here because it belongs to
this screen; `U10 · Edit a unit` opens on page 87 and is another lane's.

**State chip:** `EXISTS BEHIND`
**Commitments on the chip line:** `PUJ-17` `PUJ-43`

**CR-089 task rows this screen belongs to:** `F5` (*"the unit's audit tab draws
its rows"*, `PUJ-43`, recorded **ALREADY DONE BY WAVE C, VERIFIED HERE, AND
NOTHING WAS BUILT** — the unit page mounts the same `AuditTab` wave C fixed on
the property, `C6`) · `F3` (the four tiles).

**The question the screen answers, as drawn:** *who changed this unit, and what
did it say before?*

⚠ **ONLY THE BORDERED GREY FRAME ON PAGES 85–86 IS THE SPECIFICATION.** The amber
block is what a clerk hits today — *"On the unit I walked, the tab said «Nothing
has been recorded against this record in the window the log covers» and offered
«Open the audit log for this record →». **That sentence is honest and it is also
a dead end** — the tab tells a person their history is elsewhere, on a screen they
then have to find their way back from."*

---

## 1 · Header — identical to U7 and U8, drawn again in full

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

## 3 · Tabs — six, `Audit log` active

`Overview` | `Assets` | `Plan` | `Account` | `Occupancy` | **`Audit log`**

## 4 · Tiles — the same four, with their detail lines

| # | value | label | detail line |
|---|---|---|---|
| 1 | `5` | `ASSETS` | `2 metered · 3 behind the meter` |
| 2 | `$61.40` | `OWED` | `due 24 Sep` |
| 3 | `Standard` | `PLAN` | `since 1 Jun 2026` |
| 4 | `—` | `OPEN WORK` | `nothing booked` |

## 5 · Toolbar — drawn above the table, one row, left to right

| # | element | drawn text |
|---|---|---|
| 1 | search input | placeholder `Search this history…` |
| 2 | chip | `ALL` |
| 3 | filter control | `+ Filter ⌄` |

**No `Columns` control is drawn.** **Nothing is drawn on the right of the
toolbar.**

## 6 · Table columns — FIVE, in this order

| # | column header (exact) | alignment | cell as drawn |
|---|---|---|---|
| 1 | `When` | left | date **and time** — `1 Jun 2026, 09:14` |
| 2 | `Who` | left | a person's name — `D. Whitfield`, `K. Osei` |
| 3 | `What changed` | left | the field or the event, in words |
| 4 | `From` | left | the previous value, **as a column** |
| 5 | `To` | left | the new value |

**Five columns. No row-action column** — and this is where the unit's frame
differs from the property's on page 35, which draws a sixth, header-less `…`
column. `COGNITIVE LOAD` on page 87 confirms it: *"Five columns, one search, no
prose."*

**There is no `Expand` control and no disclosure anywhere in the drawn table.**

## 7 · The rows, in the order drawn

| # | When | Who | What changed | From | To |
|---|---|---|---|---|---|
| 1 | `1 Jun 2026, 09:14` | `D. Whitfield` | `Unit created` | `—` | `Unit 2` |
| 2 | `1 Jun 2026, 09:20` | `D. Whitfield` | `Plan` | *`None`* *(absent style, italic)* | `Residential Standard` |
| 3 | `1 Jun 2026, 11:02` | `K. Osei` | `Meter assigned` | `—` | `MTR-40218 · Electric` |

⚠ **THE `From` CELL HAS TWO DRAWN FORMS AND THEY ARE DIFFERENT FACTS.** `—` where
the row is a creation or an assignment and there was no previous value at all;
*`None`* in the ABSENT style where the field previously held nothing.

⚠ **ORDER IS OLDEST FIRST** — `09:14`, `09:20`, `11:02` down the page.

⚠ **Every worked value above is an ILLUSTRATION.** The labels, the order, the
column count and the two `From` forms are the specification.

## 8 · Footer

Left: `Showing 3 of 3`
Right: `⇤ ← Page 1 of 1 → ⇥`

**No `Rows per page` control is drawn.**

## 9 · Specification table — pages 86–87

**FOR** — *"Anybody answering «why does this say that» about one flat."*

**HOW YOU GET HERE** — *"The unit's page → Audit log."*

**PRIMARY ACTION** — *"None. It is a record and nothing on it can be changed."*

**WHAT CHANGED · THE TAB HOLDS ITS OWN HISTORY** — *"It pointed at another screen
instead of showing what it had."*

**COGNITIVE LOAD** — *"Five columns, one search, no prose."*

## 10 · States — the blueprint's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **Just created** | *"One row. A new unit's history is one line and should look like one."* |
| **Beyond retention** | *"Says older entries have been removed on the retention schedule — not that nothing happened."* |

Loading, error and permission-refusal states are **not drawn**.

## 11 · Components named

`AuditTab` `AuditEventCell` `DataTable` `DateCell` `FilterBar`

## 12 · Rules it must obey, as stated

> *"Every money or service action is recorded with who, when and what. No
> database id on screen."*

## 13 · Absences — drawn as absent, do not fill them

* **No row-action column**, and the specification table's `PRIMARY ACTION` says
  why: *"None. It is a record and nothing on it can be changed."*
* **No `Columns` chooser.**
* **No `Rows per page` control.**
* **No prose** — no explainer, no callout, no hint line.
* **No `Open the audit log for this record →` control inside the frame** — see
  the contradiction recorded below.

---

## BLUEPRINT SELF-CONTRADICTIONS FOUND — recorded, NOT resolved

Per the 2026-09-10 PO ruling the **frame wins and the sentence gets corrected**.
One is found here and it is a case where following the ruling literally would
DELETE a live, separately-ratified control, so it is written out rather than
acted on.

1. **The link out — frame versus sentence.** The teal *WHAT CHANGED* block on
   page 86 says ***"The link out stays**, for the full log, but it is no longer
   the only thing on the tab."* The grey frame on page 86 **draws no such
   control**: the frame ends at the pager. By the ruling the frame wins; but the
   control the frame omits is required independently by `BR-AUD-010` (a
   per-entity tab is a WINDOW that links to S61 pre-filtered) and was
   **explicitly kept by PO ruling on 2026-09-10 — *"keep it as it is"*** — which
   is already recorded on this screen's sibling,
   `CR-089-p034-property-audit-log.md`. **So this is a frame that is stale
   against a later ruling, not a product that drifted**, and the same reasoning
   covers the window sentence in §6 of the diff below.
2. **`COMPONENTS` names `DataTable` and `FilterBar` here and `PlainTable` on the
   Occupancy tab two pages earlier.** Not a contradiction — recorded because it
   proves the component choice is being made per screen, so `PlainTable` on U8 is
   deliberate rather than a slip.

---

## THE DIFF — the live component against this frame, 2026-09-10

**Component:** the unit page mounts the SHARED `AuditTab` —
`07-frontend/src/features/metering/PremisesDetailPage.tsx` line **2554**, mounted
at `07-frontend/src/features/metering/UnitDetailPage.tsx` line **840** with
`entityType="unit"`.
**Catalogue:** `audit.col.*`, `metering.audit.*`, `audit.window.*` in
`07-frontend/src/i18n/locales/en.json` — **present in all eleven catalogues**,
zero English-only `defaultValue` keys.

⚠ **THIS IS THE ONE SCREEN OF THE THREE THAT LARGELY CONFORMS**, and the reason
is worth recording: it is the same component wave C rebuilt for the property tab
under `DEF-4739`/`DEF-4740`, so the property fix arrived here the moment it
landed. Backend audit rows exist for this entity type — `apps/metering/services.py`
writes `unit.created`, `unit.moved`, `unit.deleted` and `unit.plan_assigned` with
`entity="unit"` (lines 1877, 2340, 2412, 2553) — so the amber block's empty tab
is a data observation, not a wiring gap.

Walked in the skill's §4 order, stopping at the first difference per element.

### Presence

| # | drawn | built |
|---|---|---|
| 1 | search box, `ALL` chip, `+ Filter ⌄` | **built** — `FilterBar` at line 2780, with the action filter derived from the events this record actually has (line 2604) |
| 2 | five columns `When · Who · What changed · From · To` | **built**, in the drawn order (lines 2658–2755, `when` at 2660 through `to` at 2732) |
| 3 | no row-action column | **correctly absent** |
| 4 | detail line `nothing booked` under `OPEN WORK`; `due 24 Sep` under `OWED`; `since 1 Jun 2026` under `PLAN` | **absent** — page-level, the same three tile findings recorded on `CR-089-p077-unit-account.md` rows 10–12 |
| 5 | sub-line 2 `Route 12 · Cycle 3 — from the building`; kicker `UNIT`; H1 `Unit 2` | **absent / different** — page-level, recorded on `CR-089-p077-unit-account.md` rows 13, 26–28 |

### Presence — built and not drawn

| # | built | drawn |
|---|---|---|
| 6 | under the table: `Open the audit log for this record →` (a real `ButtonLink`, line 2575) and the sentence `Showing the last 2 years` (`audit.window.hot`, line 2792) | The frame draws neither. **KEPT DELIBERATELY** — `BR-AUD-010` plus the PO's 2026-09-10 *"keep it as it is"*, already recorded on the property sibling. The frame drew a three-row history where the whole history fits, so *is this all of it?* never arose in the drawing |
| 7 | `▦ Columns` chooser in the toolbar | The frame draws no such control. **The kit puts it on every list** (B14 rule 12's toolbar grammar); suppressing it on one screen is a per-screen exception to a ratified rule. Same departure as the property sibling's #1 |
| 8 | `Rows per page` select inside the pager (`DataTable.tsx` line 936) | The frame draws no such control |

### Labels and footer

| # | drawn | built |
|---|---|---|
| 9 | placeholder `Search this history…` | **matches** — `metering.premises.audit.search` = `Search this history…`. ⚠ The KEY is namespaced to premises and is read on the unit tab; cosmetic, but it is the reason a lane grepping `metering.units.*` finds no search key here |
| 10 | footer `Showing 3 of 3` and `⇤ ← Page 1 of 1 → ⇥` | the shared kit's pager: `table.pager.range` = `1–3 of 3`, then `Rows per page`, then `‹` `›`. **No first/last buttons and no `Page 1 of 1` text.** `table.pager.pageOf` = `Page {{page}} of {{pages}}` exists and is rendered by `ListPager`, not by `DataTable`. This is a kit-level departure shared by 27 lists, recorded rather than fixed for one tab |

### States

| # | drawn | built |
|---|---|---|
| 11 | **Just created** — *"One row. A new unit's history is one line and should look like one."* | **built correctly** — the table draws one row; a creation reads as the EVENT with `—` in `From` (lines 2687, 2717) |
| 12 | **Beyond retention** — *"Says older entries have been removed on the retention schedule — not that nothing happened."* | **NOT BUILT AS A DISTINCT STATE.** The only empty sentence is `metering.audit.empty` = *"Nothing has been recorded against this record in the window the log covers."* — **which is the amber block's own sentence, quoted on page 85 as the thing to fix.** It says which window was searched; it does not say entries were REMOVED. There is no `metering.audit.emptyRetention` key in any of the eleven catalogues |
| 13 | *(no empty-state CTA is drawn)* | ⚠ **THE EMPTY STATE RENDERS A DEAD BUTTON.** `empty.ctaLabel: t("metering.audit.openViewer")` with **`onCta: () => undefined`** (lines 2770–2779) — `DataTable` replaces the whole table region with `EmptyList` (`DataTable.tsx` line 458) and `EmptyList` wires that handler to a real `<Button>` (`StateFrame.tsx` line 126). So on an empty tab a clerk sees `Open the audit log for this record →` **twice**: once as a button that does nothing, and once below as the working `ButtonLink`. Hard-won law 2's mirror, and the amber block's *"dead end"* complaint is literally true of this state today |

### One more, found while reading rather than from the frame

| # | what |
|---|---|
| 14 | `config.screenId` is **`"PRM-02.audit"`** (line 2652) on both mounts, so the UNIT audit tab shares the PROPERTY audit tab's saved column order and visibility. A clerk who hides a column on a property's history silently hides it on every unit's history. Not a blueprint mismatch — reported because it is one line and it is invisible to every check |

### What matches

The five drawn columns, in order, with the drawn labels · the search box, the
`ALL` chip and `+ Filter ⌄` · `From` and `To` as real columns with no `Expand`
anywhere · the two `From` forms (`—` for a creation, an absent-style word for a
field that held nothing) · oldest-first order · the tab set · `DataTable` and
`FilterBar`, which is exactly what `COMPONENTS` names.

**Premises root cause 1 does not apply** — this tab already draws the shared
`DataTable` + `FilterBar`. **Root cause 2 does not apply.** **Root cause 3 does
not apply** (nothing commits). **Root cause 4 does not apply** (full parity).
**Root cause 5 applies only in the narrow, PO-ruled sense of row 6.**

### WHAT WAS FIXED — 2026-09-10, and what did not move

| row | disposition |
|---|---|
| **13** the dead empty-state CTA | **FIXED** (`DEF-MET-4764`). `EmptyList`'s `ctaLabel`/`onCta` were REQUIRED, so a list nobody can fill had no way to satisfy the type but a no-op handler — which `EmptyList` then wired to a live `<Button>`. Both are OPTIONAL now, additively, and a block with no label draws no button. The working `ButtonLink` below the table is untouched. `UnitAuditTabConformance.dom.test.tsx` counts the label's occurrences on an empty tab; proved red at the tip with *"expected 2 to be 1"* |
| **14** one `screenId` on two mounts | **FIXED** (`DEF-MET-4765`). `auditScreenId(entityType)` gives the unit `PRM-03.audit`; the property keeps `PRM-02.audit` EXACTLY so no clerk's saved column layout moves |
| **12** the **Beyond retention** state | **NOT BUILT, and it is a SERVER gap rather than a copy one.** The tab can say WHICH window it searched (`audit.window.hot`) and cannot say whether anything was REMOVED from it: `GET /audit-log` publishes no "older entries were pruned" signal, so a distinct sentence here would be a claim about a retention job this screen cannot see. Minting `metering.audit.emptyRetention` and rendering it on a guess is exactly the shape `DEF-127` describes. **For the PO / the audit lane:** the read needs to say whether the window was truncated |
| **6** the link out and the window sentence | **KEPT**, PO ruling 2026-09-10 *"keep it as it is"* + `BR-AUD-010`. Following the frame literally would delete a ratified control |
| **7** the `▦ Columns` chooser · **8** `Rows per page` | **KIT-LEVEL, NOT BUILT.** B14 rule 38 (ratified 2026-09-10) settles this class: where a drawing and the UI rules disagree about how a shared control is CONSTRUCTED, the UI rules win, the divergence is recorded and nothing is built. Suppressing the kit's toolbar on one screen would be a per-screen exception to a ratified rule |
| **10** the pager's shape | **KIT-LEVEL, NOT BUILT** — shared by 27 lists, same reasoning as above |
| **4** the tile detail lines · **5** the header sub-line | Page-level; see the U7 file's own WHAT WAS FIXED block |

### Confidence

* **Confident, from source and catalogue:** every row above. The dead empty-state
  CTA (row 13), the missing retention sentence (row 12) and the shared
  `screenId` (row 14) are all readable in the file.
* **Needs a running stack** (none in this container — no Django, no Postgres):
  reaching the **Beyond retention** state at all, which needs rows older than the
  hot window; confirming the empty state renders on a unit that genuinely has no
  audit rows (every seeded unit measured on 2026-09-09 carried some, per `F5`);
  and the rendered order and spacing of the toolbar against the drawing.
