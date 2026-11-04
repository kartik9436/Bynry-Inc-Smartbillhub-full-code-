# U6 · Unit → Plan — THE DRAWN SPEC

`S15 · PRM-03` · breadcrumb `Premises → Units → a unit → Plan` · **blueprint
pages 71–76**

**Source:** `05-prototype/Premises & Units Blueprint 2.pdf`, the section opening at
the foot of page 71, **drawn on pages 72–74**, specified on 74–76. Read as RENDERED
pages — the plan panel's row order, the four-column service table and the footer
bar are drawn.

**State chip:** `EXISTS BEHIND`
**Commitments on the chip line:** `PUJ-33` · `PUJ-34` · `PUJ-35` · `PUJ-45`

**CR-089 task rows this screen belongs to:** `H1` (one date format, with a named
month — `PUJ-33`) · `H2` (one floor sentence, and eligibility written for a clerk —
`PUJ-34`) · `H3` (a zero base says what the service is priced on — `PUJ-35`) ·
`F6` (a unit's plan is applied or changed from its edit form — `PUJ-45`) · `F3`
(the four tiles on every unit tab).

**What this file is.** Only the **bordered grey frame** on pages 72–74 is the
specification. The amber block on 71–72 was **walked on the real screen** —
*"Ottumwa Water Works, `SCW-U-001` · Unit 1, 101 Silver Creek Rd"* — and its own
opening sentence is a warning worth keeping: *"This tab is already rich, and the
earlier draft of this page underdrew it badly … The revision below keeps all of it
and fixes five things."*

---

## 1 · Header

| slot | drawn |
|---|---|
| kicker | `UNIT · 101 SILVER CREEK RD` |
| title (H1) | `Unit 1` |
| sub-line 1 | `SCW-U-001` **(bold, leading)** · `Ottumwa, IA` · `Residential` · `ACTIVE` *(pill)* `OCCUPIED` *(pill)* |
| sub-line 2 | `Water · Sewer · Trash · Solar · Battery · Fire — the six this unit can take` |

⚠ **THE SERVICES LINE IS A LIST WITH `·` SEPARATORS, IN SEED ORDER, AND IT ENDS ON
A CLAUSE RATHER THAN A WORD.** Page 74, verbatim: *"The services line is a list, in
the order the eleven services are defined — `Water · Sewer · Trash · Solar ·
Battery · Fire` — not `"Sewer + Battery + Water + Trash + Solar + Fire available"`,
where the last word attaches itself to Fire."*

## 2 · Header actions — in the drawn order

Drawn **top-right, on the kicker/title row**, as a row of three.

| # | label | tier |
|---|---|---|
| 1 | `✎ Edit` | secondary |
| 2 | `Move` | secondary |
| 3 | `Change status` | **danger** |

Page 74: *"`Edit` and `Change status` join `Move` in the header, per your ruling.
The unit page offered `Move` alone."*

## 3 · Tabs — six, in this order, `Plan` active

`Overview` | `Assets` | `Plan` | `Account` | `Occupancy` | `Audit log`

## 4 · Tiles — the same four page tiles, with their detail lines

| # | value | label | detail line |
|---|---|---|---|
| 1 | `5` | `ASSETS` | `2 metered · 3 behind the meter` |
| 2 | `$61.40` | `OWED` | `due 24 Sep` |
| 3 | `Standard` | `PLAN` | `since 1 Jun 2026` |
| 4 | `—` | `OPEN WORK` | `nothing booked` |

⚠ **THE FIRST TILE IS HEADED `ASSETS`, NOT `METERS`** — the amber block names
`METERS` as the defect. See the CONTRADICTIONS section below for the base-charges
tile the teal block asks for and the frame does not draw.

## 5 · `THE PLAN` — a section kicker over EIGHT fact rows, in this exact order

| # | label | value, as drawn |
|---|---|---|
| 1 | `Current plan` | `Sample — Residential` ` · version 1 · published` *(quiet qualifier)* |
| 2 | `Plan code` | `SCW-RES` |
| 3 | `Effective from` | `1 Jun 2026` |
| 4 | `Base charges` | `$22.00 a month` ` · the six service base charges below add to this` |
| 5 | `Minimum bill` | `No floor is set — a bill can be any amount, including nothing` *(absent style — italic grey)* |
| 6 | `Locked to this unit` | `No` ` · a change here does not need a supervisor` |
| 7 | `Vacant standby` | `No` ` · nothing bills while the unit is empty` |
| 8 | `Eligibility` | `Not checked — no plan on this system asks for proof yet` *(absent style)* |

**Rows 6 and 7 carry a clause, never a bare word** (page 74): *"Locked and standby
say what they mean rather than `No` twice: whether a supervisor is needed, and
whether anything bills while the unit is empty."*

**Row 8 is written for a clerk, not about our code** (page 74): *"Eligibility says
what a clerk needs — `not checked, no plan on this system asks for proof yet` —
instead of explaining that the rules are stored and no code reads them."*

**Row 3 appears ONCE ON THE WHOLE TAB** (page 74): *"`Effective from` appears once.
It was on the plan panel **and again in the pricing panel below**, in two different
formats — which is how a clerk concludes there are two dates."*

**Row 4 is the one sum a person can check** (page 74): *"the six service bases add
to exactly that `$22.00` — the one sum on this screen a person can check, so the
screen says it is a sum."*

## 6 · `WHAT EACH SERVICE IS PRICED ON` — a section kicker over a FOUR-column table

| # | header | alignment |
|---|---|---|
| 1 | `Service` | left, **bold value** |
| 2 | `Base a month` | **right, tabular** — two decimals, **no currency glyph on the rows** |
| 3 | `Priced on` | left — the shape, then ` · ` the schedule name, quiet |
| 4 | `Minimum` | **right** — `none` in the absent style |

**The six drawn rows, in order:**

| Service | Base a month | Priced on | Minimum |
|---|---|---|---|
| `Water` | `8.00` | `Inclining tiers` ` · Sample — Residential water` | `none` |
| `Sewer` | `9.00` | `A percentage of water` ` · Sample — Sewer` | `none` |
| `Trash` | `0.00` | `Per cart, monthly — not measured` ` · Sample — Trash` | `none` |
| `Solar` | `0.00` | `By capacity` ` · Sample — Solar capacity` | `none` |
| `Battery` | `5.00` | `By capacity` ` · Sample — Battery capacity` | `none` |
| `Fire` | `0.00` | `By the size of the line, times how many` ` · Sample — Fire capacity` | `none` |

**The footnote drawn beneath the table, quiet, three lines:**

> `A base of 0.00 does not mean free — it means this service carries no standing`
> `charge and is priced entirely by the column beside it. No floor is set on any of the six,`
> `so none has a minimum.`

Page 74: *"The seven copies of "No floor is set on this plan." become **one sentence
and six absences**. The plan row says what no floor means; each service says `none`
in the absence style."*

## 7 · `WHAT A PLAN CHANGE WOULD DO` — a bordered consequence box, three sentences

> `A new plan takes effect from the date you choose and never mid-cycle. Bills`
> `already issued keep the plan they were made on. This unit is occupied, so a`
> `change made here is an error correction and is recorded with your reason — the`
> `ordinary way is through the account.`

## 8 · Footer bar — one row, two halves, at the BOTTOM of the frame

| side | drawn |
|---|---|
| left | `Showing what applies today, 8 Sep 2026 · ` `look at another period` *(link)* |
| right | `Change plan →` *(button, outline/secondary)* |

⚠ **THE PERIOD PICKER FOLDS AWAY TO ONE LINK.** Page 74: *"The period picker folds
away. `Showing what applies today` with one link to look at another period. **Four
controls and a sentence were open permanently** for a question almost nobody asks,
above the answer everybody came for."*

Page 75, PRIMARY ACTION: *"`Change plan →`. An arrow, because it opens a chooser
rather than writing. On an occupied unit it is an error-correction override and says
so before it commits."*

## 9 · States — the blueprint's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **No plan** | *"Says the unit cannot be billed until it has one, in those words, and offers the chooser. `rate_plan_id` is null on a real number of units, so this is not a rare state."* |
| **Locked to this unit** | *"The change is held with a five-word refusal and names the role that may do it."* |
| **Occupied** | *"The change is an override: the reason box is required and the audit row records it. The ordinary route is the account's own change-plan flow, and the screen says so."* |
| **A schedule priced in the wrong unit** | *"The service says a bill cannot be produced until the conversion is settled — the one condition on this screen that stops money, so it is stated on the row and not in a footnote."* |
| **The rates could not be read** | *"None are shown and the panel says nothing is assumed in their place. An empty rate table is the one thing worse than no table."* |
| **An example month** | *"Never shown. Nothing in this product prices a plan outside a bill run, and no signed rule says what a new tenant is assumed to use — so the panel states that rather than inventing a figure."* |

## 10 · Cognitive load, as stated

*"Four tiles, **eight plan rows, six service rows, one consequence line**. The
period picker is one link. **Nothing else is on screen until asked for.**"*

## 11 · Components named in the frame

`UnitPlanModal` `UnitPricingPanel` `PlainTable` `MoneyCell` `DateCell` `StatusPill`
`ArrivesWith`

## 12 · Rules it must obey, as stated

*"Money two decimals on screen, four in store. A consequence preview before a commit
that changes service state. An absence is drawn as an absence. **No rule id or
internal code in clerk-facing copy.** A description budget of one sentence per
section."*

## 13 · FOR · HOW YOU GET HERE (page 75)

* **FOR** — *"A clerk asked why a bill looks the way it does, a supervisor moving a
  unit onto a new tariff, and whoever is opening an account on it — the pricing
  panel exists because a move-in has to show the rates the first bill will use."*
* **HOW YOU GET HERE** — *"The unit's page → Plan. The same panel is drawn at step 4
  of a move-in, so a change here changes what a new customer is shown."*

## 14 · The DATE RULE, because it is the whole of `PUJ-33`

**Every date on this tab is a named month: `1 Jun 2026`, `8 Sep 2026`.** Page 75
lists the four shapes it replaces: *"`06/01/2026` on the tile and in the plan panel;
`2026-06-01` for the same date in the pricing panel; `01/09/2026` and `30/09/2026`
in the period boxes, which are day-first; `2026-09-01 to 2026-09-30` in the sentence
above them. Named months throughout, so no reading is possible but the right one."*

⚠ **THE `PLAN / since 1 Jun 2026` TILE IS INSIDE THIS RULE** — it is drawn with a
named month on the frame.

## 15 · Absences — drawn as absent, do not fill them

* **No second plan block.** `Plan`, `Code`, `Status`, `Effective from`,
  `Base charges` and `Minimum bill` appear ONCE, in the eight rows of §5.
* **No `Rate schedules` fact row** in the plan panel.
* **No `Services included` section heading** — the heading is `WHAT EACH SERVICE IS
  PRICED ON`.
* **No open period controls** — no date boxes, no `Show this period`, no
  `Back to today`. One link.
* **No plan-history arrives-with block.**
* **No `Eligibility check` verdict** — the row states the absence and stops.

---

## CONTRADICTIONS FOUND IN THE BLUEPRINT — recorded, not resolved

Per the PO ruling of 2026-09-10, **the frame wins and the sentence gets corrected.**
Recorded for the PO; not acted on here.

1. **THE BASE-CHARGES TILE.** Page 74's `WHAT CHANGED` says, verbatim: *"**The base
   charges tile is the money tile.** `$22.00 a month before any usage` is the figure
   a clerk is asked for; the meter count was on it instead, and the meter count is
   on the Assets tab."* Page 75 repeats it as `WHAT CHANGED · THE TILE THAT IS NOT A
   TILE`. **The drawn frame on page 72 carries the four PAGE tiles unchanged** —
   `5 ASSETS` · `$61.40 OWED` · `Standard PLAN` · `— OPEN WORK` — and no
   `$22.00 BASE CHARGES` tile anywhere. The frame is also the coherent reading: page
   66's `F3` ruling says *"these KPIs will be displayed across all views … Assets ·
   Owed · Plan · Open work now sit on every tab of the unit"*, which a per-tab
   substitution would break. **Reading: the four page tiles stand, `$22.00` is fact
   row 4, and the sentence is stale — most likely written before `F3` landed.**

2. **THE HEADER ACTIONS ARE IN A DIFFERENT PLACE FROM U4 AND U5.** U6 draws
   `✎ Edit · Move · Change status` **top-right on the title row**; U4 (page 64) and
   U5 (page 68) draw the same three **below the sub-lines, left-aligned**. Same
   screen, same header, two layouts, and nothing in either section says the header
   changes by tab. **Reading: one of the two is a drafting slip. It needs one
   sentence to the PO rather than a lane picking.**

3. **THE SUB-LINE CARRIES A DIFFERENT FACT FROM U4 AND U5.** U6's second sub-line is
   the services list; U4's and U5's is `Route 12 · Cycle 3 — from the building`.
   The two sections use different exemplar tenants (Silver Creek's `U-01145` vs
   Ottumwa's `SCW-U-001`), so this may simply be two views of one header that shows
   both lines. **Recorded because a lane building from one section alone would drop
   the other line.**

---

## AMENDMENTS — what was BUILT on 2026-09-10 (`DEF-MET-4767` · `DEF-MET-4769`)

Maintenance.

**What was fixed.** **`Effective from` appears ONCE on the tab**, which is page
74's own named defect — *"It was on the plan panel **and again in the pricing
panel below**, in two different formats — which is how a clerk concludes there
are two dates."* Wave `H` made the two formats agree; this removes the second
copy · **`Locked to this unit` and `Vacant standby` carry their clause** —
*"whether a supervisor is needed, and whether anything bills while the unit is
empty"* — instead of two rows both reading `No`, which are answers to two
different questions and indistinguishable without it · **the period picker folds
to one link**, `look at another period`, where *"**four controls and a sentence
were open permanently** for a question almost nobody asks, above the answer
everybody came for"* · **`Change plan →` is the outline tier and sits at the
END of the tab**, below the pricing panel, where it was a PRIMARY above it ·
**the `Rate schedules` fact row is gone** (§15) — the panel below names the
schedule on every service row · **the plan-history arrives-with block is gone**
(§15), and the GAP is unchanged: `BR-CUS-013`'s per-unit history is still
rating-owned and unread, `DEF-473` is still open. What went is a paragraph
explaining our implementation to a clerk, which B14 rule 32 forbids · **the
`Eligibility` row moves LAST**, its drawn position · **22 message keys that
existed in NONE of the eleven catalogues are fanned in** (`DEF-MET-4769`),
including every control of the period picker — a `defaultValue` renders English
forever and G15's parity check compares the catalogues to each other, never to
the call sites.

### Departures, recorded rather than left to be found

1. **THE FRAME'S EIGHT PLAN ROWS ARE SIX HERE, AND `Plan code`, `Base charges`
   AND `Minimum bill` ARE IN THE PANEL BELOW.** Those three come from
   `GET /units/{id}/pricing`, which the fact list does not query; the panel does
   and draws all three. So the facts are all on the tab and one block short of
   being one block. `planFactsAbove` already suppresses the four the tab DOES
   state, so the remaining move is for the tab to read the pricing query too.
   **Open.**
2. **THE FOOTER BAR IS NOT ONE ROW.** §8 draws `Showing what applies today,
   8 Sep 2026 · look at another period` on the left and `Change plan →` on the
   right, in one bar at the bottom. The sentence is rendered by
   `UnitPricingPanel`, which the **move-in wizard also mounts** — composing one
   row across the two would put a plan-change control inside a panel that must
   never offer one (`BR-CUS-029`, and the panel's own docstring: *"IT SHOWS; IT
   DOES NOT CHOOSE"*). The button is at the bottom of the tab, the sentence at
   the top of the panel. **Open.**
3. **THE `$22.00 BASE CHARGES` TILE IS NOT BUILT** — with the PO, and the
   CONTRADICTIONS section above already reads the frame's four page tiles as
   the coherent one. Unchanged by this pass.
4. **THE HEADER ACTIONS AND THE SECOND SUB-LINE** (contradictions 2 and 3) are
   unchanged and still need one sentence to the PO. The services sub-line's
   SHAPE is built — `·` separators, seed order, a closing clause — on the header
   this product actually has.
5. **THE CLOSING CLAUSE USES THE NUMERAL, NOT THE WORD.** The frame writes *"the
   six this unit can take"*; the count is THIS unit's own, so a unit offering two
   services must not say six, and eleven catalogues cannot spell out numbers.
   `{{count}}` is the only reading that is right on every row. **B14 rule 37
   covers this: the drawn `six` is an illustration.**
6. **THE PERIOD CONTROLS ARE A NATIVE `<details>`, NOT A CUSTOM DISCLOSURE.**
   B14 rule 32 makes a stated absence a `<details>` closed by default, it is
   keyboard-operable with no code, and its `summary` IS the link the frame
   draws. **B14 rule 38 in practice: the drawing says a link, the kit says how.**
