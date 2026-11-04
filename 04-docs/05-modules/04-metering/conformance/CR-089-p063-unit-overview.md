# U4 · Unit → Overview — THE DRAWN SPEC

`S15 · PRM-03` · breadcrumb `Premises → Units → a unit` · **blueprint pages 63–67**

**Source:** `05-prototype/Premises & Units Blueprint 2.pdf`, the section opening at
the foot of page 63, **drawn on page 64**, specified on 65–67. Read as RENDERED
pages, not as extracted text — the row order, the two-line values and the button
tiers are drawn.

**State chip:** `EXISTS BEHIND`
**Commitments on the chip line:** `PUJ-27` · `PUJ-28` · `PUJ-29`

**CR-089 task rows this screen belongs to:** `A7` (a unit may carry its own point
and parcel, falling back to its building — `PUJ-27`) · `F2` (an occupied unit shows
its ACCOUNT — `PUJ-28`) · `F1` (the Overview carries the unit's own number —
`PUJ-29`) · `F3` (the four tiles belong to the page, not the tab).

**What this file is.** Only the **bordered grey frame** on pages 63–64 is the
specification. The **amber block** above it is what a clerk hits TODAY — the
problem, never the target — and the **teal `WHAT CHANGED`** block on 64–66 says
what moved and why. The grey frame is transcribed here character for character.

---

## 1 · Header

| slot | drawn |
|---|---|
| kicker | `UNIT` |
| title (H1) | `Unit 2` |
| sub-line 1 | `U-01145` **(bold, leading)** · `412 Cypress Row, Silver Creek, TX 78611` · `Residential` · `ACTIVE` *(pill, green)* `OCCUPIED` *(pill, grey)* |
| sub-line 2 | `Route 12 · Cycle 3 — from the building` |

⚠ **THE UNIT NUMBER LEADS THE SUB-LINE, AHEAD OF THE ADDRESS.** *"`U-01145`, ahead
of the address — the number a clerk reads down the phone and writes on a work
order."* The address is the BUILDING's and is not repeated as a fact row.

## 2 · Header actions — in the drawn order

Drawn **below the sub-lines, left-aligned**, as a row of three.

| # | label | tier |
|---|---|---|
| 1 | `✎ Edit` | secondary — and it is the stated PRIMARY ACTION |
| 2 | `Move` | secondary |
| 3 | `Change status` | **danger** (amber border, amber label) |

Page 65, verbatim: *"`✎ Edit`. `Move` and `Change status` beside it; only
`Change status` is in the danger tier."*

## 3 · Tabs — six, in this order, `Overview` active

`Overview` | `Assets` | `Plan` | `Account` | `Occupancy` | `Audit log`

Page 65: *"The six tabs are unchanged, and the second one stays `Assets`. An
earlier draft renamed it to `Meters`; PO ruling this session reverses that, on the
property and on the unit alike."*

## 4 · Tiles — four, each with a detail line

| # | value | label | detail line |
|---|---|---|---|
| 1 | `5` | `ASSETS` | `2 metered · 3 behind the meter` |
| 2 | `$61.40` | `OWED` | `due 24 Sep` |
| 3 | `Standard` | `PLAN` | `since 1 Jun 2026` |
| 4 | `—` | `OPEN WORK` | `nothing booked` |

⚠ **THESE FOUR ARE THE PAGE'S, NOT THE TAB'S** (page 66, PO ruling: *"these KPIs
will be displayed across all views"*) — the same four ride Overview, Assets, Plan,
Account, Occupancy and the audit log, exactly as the header and the tab strip do.

## 5 · Fact rows — EIGHT, one column, in this exact order

| # | label | value, as drawn |
|---|---|---|
| 1 | `In this building` | `412 Cypress Row, Silver Creek, TX 78611` **on line 1**; line 2 `Apartment complex · 4 units · ` `Open it →` *(link)* |
| 2 | `Floor` | `Not recorded` *(absent style — italic grey)* |
| 3 | `Floor area` | `Not recorded` *(absent style)* |
| 4 | `Parcel` | `R-114-0082-004` ` · from the building` *(quiet qualifier)* |
| 5 | `On the map` | `30.752104, −98.238391` ` · from the building` then `Give this unit its own point` *(link)* |
| 6 | `Checked against GIS` | `CHECKED` *(pill)* ` · inherited with the building's point` |
| 7 | `Account` | line 1 `A-10517` **(bold)** ` · M. Alvarez · ` `ACTIVE` *(pill)* ` · since 1 Jun 2026 · Residential`; line 2 `Owes ` `$61.40` **(bold)**`, due 24 Sep · deposit $150.00 held · autopay on ` `Open the account →` *(link)* |
| 8 | `Services` | `Electric · Water` |

The stated count agrees: *"Four tiles, **seven facts, one map**, six tabs"* — the
map row is #5 and the other seven are the facts.

**Row 1 is the building as a ROW, with its street address IN it** (page 66):
*"It showed a property code under a heading that held the street, so one fact sat in
two places in two vocabularies. It is one row now, with the address in it and a link
that opens the building."*

**Rows 4–6 are the point/parcel clause** (page 65): *"A unit can carry its own
parcel and its own point, and where it does not, it says plainly that it is using
its building's. That is your ruling drawn: the address stays on the building, the
point may differ."* Page 66 adds: *"and the screen always says which of the two it
is showing. All 1,109 units carry nothing today."*

**Row 7 replaces an `Occupant` row** (page 65): *"An occupied unit shows its
account, not its occupant. The number, the holder, the status, what is owed and
when it is due, the deposit we are holding and whether autopay will take it — with
one link out."*

## 6 · Footer

**None is drawn.** The frame ends at the `Services` row.

## 7 · States — the blueprint's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **Using the building's point** | *"The row says `from the building`. This is the common case and it is stated rather than implied."* |
| **Its own point** | *"The row shows the unit's own figures and drops the `from the building` note, so the difference is visible at a glance — which is the whole reason the ruling exists."* |
| **Vacant** | *"The occupant row reads `Vacant — base charges bill to the owner`, never a dash. A dash on that row is read as `nothing is billed`, which is the opposite of true."* |
| **A common area** | *"The occupant row says so and no account can be opened on it."* |

Loading, error and permission-refusal states are **not drawn**.

## 8 · Cognitive load, as stated

*"Four tiles, seven facts, one map, six tabs. **Two sentences of description in
total.**"*

## 9 · Components named in the frame

`PageHeader` `KPIStrip` `PlainTable` `StatusPill` `MoveUnitModal` `UnitPlanModal`
`UnitPricingPanel` `MoneyCell` `InlineLinkTo` `ArrivesWith`

## 10 · Rules it must obey, as stated

*"An absence is italic and grey and never a zero. Consumption always carries its
unit. A unit label a clerk reads down the phone is shown; a database id never is.
The danger tier for taking a thing out of service."*

## 11 · FOR · HOW YOU GET HERE · PRIMARY ACTION (page 65)

* **FOR** — *"A clerk answering a question about one flat — who is in it, what is
  metering it, what it owes. It is where a service call lands after the address has
  been found."*
* **HOW YOU GET HERE** — *"The Units tab, the property's Units tab, an account, a
  meter, a work order, and the global search. Like the property page, it is reached
  from more places than it links to."*
* **PRIMARY ACTION** — `✎ Edit`.

## 12 · Absences — drawn as absent, do not fill them

* **No `Unit ID` fact row.** The number is in the header sub-line and nowhere else
  on this panel.
* **No `Label`, `Type`, `Common area` or `Occupancy` fact rows.** Type and both
  status words are in the header; the label is the H1.
* **No `Rate schedules` row** — that is the Plan tab's.
* **No `Premise` row showing a premise CODE.** The amber block names the code as
  the defect: *"The Premise row shows a code; the street is in the heading above
  it, so the two halves of one fact sit in two places."*
* **No prose paragraph.** Two sentences of description on the whole tab.
* **No footer, no pagination, no bulk bar.**

---

## CONTRADICTIONS FOUND IN THE BLUEPRINT — recorded, not resolved

Per the PO ruling of 2026-09-10, **the frame wins and the sentence gets corrected.**
Both of these are recorded for the PO; neither is acted on here.

1. **The STATES block names a row the frame does not draw.** Three of the four
   states above say *"the occupant row"*. The U4 frame has **no `Occupant` row** —
   it has an `Account` row, and page 65's own `WHAT CHANGED` puts the vacancy
   sentence there: *"A vacant unit says what that costs, **in the same place**. No
   account, base charges reaching the owner, and the owner's account named and
   linked — rather than a blank where the account row would be."* The word
   *occupant* is a leftover from the Units TABLE (page 22, column 5). Reading:
   the vacancy sentence belongs in fact row 7.

2. **The frame draws a `Parcel` row that the CR itself records as NOT BUILDABLE
   as drawn.** `CR-089` task `A7` says, verbatim: *"DONE for the POINT; the PARCEL
   is NOT built and is owed. `units.external_ref` is `BR-MET-404`'s legacy match
   key under a unique index, and two units in one building share one parcel — it
   would refuse the second."* The frame draws the parcel as the BUILDING's
   (`· from the building`), which needs no unit column at all — so the frame and
   the CR's blocker may not actually collide. Worth putting to the PO in one
   sentence rather than assumed either way.

---

## AMENDMENTS — what was BUILT on 2026-09-10 (`DEF-MET-4767`)

Maintenance, not build (`12-governance/22-product-maintenance-process.md`): the
screen exists and a beta user is on it.

**What was fixed.** The building row draws the STREET and is headed `In this
building`, where it drew the premise CODE under a heading reading `Premise` —
the amber block's own defect, *"one fact sat in two places in two
vocabularies"* · the retired qualifier *"A unit never moves between premises…"*
is gone from this screen · `Floor`, `Floor area`, `Unit` and `Type` say
`Not recorded` where they said `—`; the STYLE was already right (`Dash` carries
`.met-muted`, italic at 45%) and only the WORD changed · `Floor area` replaces
`Sq ft` and the value carries its unit (`745 sq ft`), which is the drawn row the
right way round · the services sub-line is a `·`-separated list in
`SERVICE_CODES`' seed order ending on a clause, where it read
`Sewer + Battery + Water + Trash + Solar + Fire available` with nothing sorting
it and the last word attaching itself to Fire.

### Departures, recorded rather than left to be found

1. **THE `Unit ID` FACT ROW STAYS, AND §12 NAMES IT AS AN ABSENCE.** *"No `Unit
   ID` fact row. The number is in the header sub-line and nowhere else on this
   panel."* It is here because the **PO asked for it by name** on 2026-09-08 —
   *"Unit → Overview - you are not showing unit ID here"* — which is `CR-089`
   `F1` / `PUJ-29`. A ruling beats a frame's absence list; hard-won law 13 says
   so and says not to re-ask. **Closed by ruling, not open.**
2. **ROWS THE FRAME DOES NOT DRAW ARE STILL DRAWN:** `Unit` (the label), `Type`,
   `This is a common area` and `Occupancy`. The frame's eight rows do not
   include them; each is a served fact with its own rule behind it
   (`BR-MET-036`, `BR-MET-101`) and removing four rows a clerk uses is a bigger
   act than this fix, on a screen whose stated budget is about DESCRIPTION
   rather than about facts. **Open.**
3. **ROW 1'S SECOND LINE IS NOT BUILT.** The frame draws `Apartment complex ·
   4 units · Open it →` beneath the address. `UnitRow` carries neither the
   building's TYPE nor its unit COUNT, so the two would have to be fetched or
   guessed; the link is built and the two facts are not. **Open.**
4. **THE `Services` ROW DRAWS LETTER SQUARES WHERE THE FRAME DRAWS WORDS**
   (`Electric · Water`). `ServiceTags` is shared by six screens and the units
   LIST frame draws the squares, so changing it here would change it there.
   **Open.**
5. **`Parcel` AND `Checked against GIS` ARE NOT FACT ROWS.** The point is drawn
   by `UnitPointFact` and says which of the two it is showing, per
   `BR-MET-1162`; the parcel is `CR-089` `A7`'s recorded blocker. Unchanged by
   this pass and still the CONTRADICTIONS section's question for the PO.
