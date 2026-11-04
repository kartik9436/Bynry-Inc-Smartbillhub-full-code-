# Plans 38 · View · Units — THE DRAWN SPEC

`PLN-02 · Units` · route `/:tenant/plans-rates/plans/:id?tab=units` · **blueprint pages 110–112**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, screen `38`,
frame drawn on pages 110–111, specified on 111–112.

**State chip:** `NEW BUILD`
**Commitments on the chip line:** `PRB-21`

**WHAT WAS WRONG (page 110, verbatim):** *"A plan showed a count of 74 with no way to
see what was in it, nothing said whether 74 meant units, accounts or customers, and the
services were spelled out in full where every other screen in the module draws the
coloured badge."*

**THIS TAB DID NOT EXIST BEFORE `CR-087`.** PO ruling 2026-09-08: *"second tab can be
units and last tab can be audit"*.

---

## 1 · Header, actions, tabs — identical to the Overview

Back link `← Plans & Rates` · kicker `PLAN · SCW-RES · V1` · title
`Residential Standard` · pill `PUBLISHED` · the two-line sub-line · actions
`Duplicate HELD` · `Edit` · `Retire` (danger) · tabs `Overview | Units | Audit` with
**`Units` active**.

## 2 · Tab description — one sentence

`The units this plan prices, and what each one is.`

## 3 · Tiles and the absence bar — identical to the Overview

`UNITS 74 / on this plan today` · `SERVICES 2 / Electric · Water` ·
`MONTHLY BASE $20.0000 / Electric $12.00 · Water $8.00` ·
`CHANGE ALREADY DATED 01/01/2027 / Water rates, +4.0%`, then the `NOT WORKED OUT YET`
bar with its three rows.

⚠ **THE TILES AND THE BAR ARE DRAWN ON ALL THREE TABS.** They are page furniture, not
tab content — the same posture the units blueprint's `F3` ruling takes.

## 4 · The one panel — `Units on this plan`

| slot | drawn |
|---|---|
| panel title | `Units on this plan` |
| panel sentence | `Every unit this plan prices, whether or not somebody lives there.` |
| table | FIVE columns |

| # | header | alignment | drawn cells |
|---|---|---|---|
| 1 | `UNIT` | left | `Unit 1` · `Unit 2` · `Unit A` |
| 2 | `PREMISES` | left | `101 Silver Creek Rd` · `101 Silver Creek Rd` · `88 Quarry Hill Ct` |
| 3 | `SERVICES` | left | the coloured BADGES — `E W` · `E W` · `E W S` |
| 4 | `ACCOUNT` | left | `AC-2026-00001` · **`—` with a second line `Vacant — base charges still bill to the owner.`** · `AC-2026-00014` |
| 5 | `ON THIS PLAN SINCE` | left | `06/01/2026` · `06/01/2026` · `07/01/2026` |

**Under the table, a red-ruled callout:**

> **WHY UNITS AND NOT ACCOUNTS**
> `A plan is attached to a UNIT, not to an account — so a vacant unit is still on this`
> `plan and its base charges still reach the owner's bill. That is why this tab counts`
> `74 units and not 74 customers.`

⚠ **B14 rule 37 — `Unit 1`, `101 Silver Creek Rd`, `AC-2026-00001`, `74` are
ILLUSTRATIONS.** The SHAPE that matters: three rows, two of them the same premises, one
of them vacant.

**THE VACANT ROW IS THE POINT (page 112, verbatim):** *"`Vacant — base charges still
bill to the owner` in place of an empty Account cell. A clerk who reads a dash concludes
nothing is billed, which is the opposite of the truth."*

**SERVICES ARE THE BADGE, THE PRODUCT ALREADY SHIPS ONE (page 111, verbatim):** *"`E`
and `W` in the service's own colour, from `ratingShared`'s own map — not the full names
spelled out, which is what this row had. Three badges fit where three name chips wrapped
to a second line and pushed every row taller, and it is the same 20-pixel square r10
drew and the plan list already uses, so a service looks the same wherever a clerk meets
it. **The letter is never derived from the name:** six of the eleven services collide on
their initial — Sewer, Solar and Storm water all give S, Trash and Thermal both give T,
Broadband and Battery both give B — so the four that arrived after r10 take two
characters in the same square. The full name is still the tooltip and the accessible
name; a letter alone is not something a screen reader can announce."*

## 5 · FOR · HOW YOU GET HERE · PRIMARY ACTION (page 111)

* **FOR** — *"A clerk asked how many customers a price change will touch, and a
  supervisor checking a vacant property is still billing its standing charge."*
* **HOW YOU GET HERE** — *"The `Units` tab."*
* **PRIMARY ACTION** — ***"None."***

## 6 · COGNITIVE LOAD (page 112)

*"One table, five columns, sorted by premises so the units of one building sit
together."*

## 7 · STATES (page 112)

| state | drawn behaviour |
|---|---|
| **No units** | *"No unit is on this plan yet, so a price change here reaches nobody."* |
| **More than a page** | *"Paged from the server, and the tile's count is the total rather than the page's."* |
| **A unit whose account is closed** | *"Named as closed rather than blank, with the date."* |

## 8 · WHAT THE SERVER NEEDS (page 112, verbatim)

*"A new list read — the count exists and the list does not. Rating counts unit-plan
assignments already (that is where 74 comes from) and there is no endpoint that returns
them: unit, premises, services, account or vacancy, and the date it joined the plan. It
must be paged from the server (`NFR-3`) and its total must be the whole set rather than
the page, or the tile and the table will disagree the moment a plan passes one page."*

## 9 · COMPONENTS named in the frame (page 112)

`Panel` `ListTable` `Callout accent`

## 10 · RULES, as stated (page 112) — one clause more than the other screens

*"… A figure that does not exist is stated with its reason and never drawn at the
weight of one that does. **A count names what it counts.**"*

## 11 · Absences — drawn as absent, do not fill them

* **No primary action, and no action of any kind on a row.**
* **No search box, no filter chips, no column selector on this table.**
* **No pagination footer drawn** — though the STATES row says it is paged.

---

## DIFF AGAINST THE RUNNING CODE — `2.234.19`

`07-frontend/src/features/rating/PlanDetail.tsx`, `UnitsTab` at `:1104`.

### Conforming — this tab is the closest thing in the range to its drawing

| drawn | code | evidence |
|---|---|---|
| the tab exists, second of three | `PLAN_DETAIL_TABS[1] === "units"` | `PlanDetail.tsx:267` |
| the tab description, **verbatim** | `rating.planDetail.explainer.units` = *"The units this plan prices, and what each one is."* | `en.json` |
| the panel title, **verbatim** | `rating.planUnits.heading` = *"Units on this plan"* | `PlanDetail.tsx:1125` |
| the panel sentence, **verbatim** | `rating.planUnits.note` = *"Every unit this plan prices, whether or not somebody lives there."* | `PlanDetail.tsx:1127` |
| five columns, in the drawn order | `["unit","premises","services","account","since"]` | `PlanDetail.tsx:1140-1144` |
| the five column labels, **verbatim** | `Unit · Premises · Services · Account · On this plan since` | `en.json` `rating.planUnits.col.*` |
| the vacant cell is the SENTENCE, not a dash | `row.vacant ? <Absent reason={t("rating.planUnits.vacant")} />` | `PlanDetail.tsx:1170-1177` |
| the sentence, **verbatim** | `rating.planUnits.vacant` = *"Vacant — base charges still bill to the owner."* | `en.json` |
| the callout, label and body, **near-verbatim** | `rating.planUnits.whyLabel` = *"Why units and not accounts"*; `why` = *"A plan is attached to a unit, not to an account, so a vacant unit is still on this plan and its base charges still reach the owner's bill."* | `PlanDetail.tsx:1211` |
| services drawn as the shared BADGE, letter never derived from the name | `<ServiceTags services={row.services} />`, services travelling as CODES | `PlanDetail.tsx:1161-1169` |
| paged from the server, total = the whole set | `getPlanUnits(planId, {page, per})`; `total = unitsQuery.data?.count` — a SQL `COUNT`, not the page length | `PlanDetail.tsx:1112-1121`, `:1198-1206` |
| **A unit whose account is closed** state | `row.account_closed && <Kicker>{rating.planUnits.closed}</Kicker>` | `PlanDetail.tsx:1178-1183` |
| **No units** state | `rating.planUnits.empty` | `PlanDetail.tsx:1133` |
| no row actions, no primary action | none rendered | `PlanDetail.tsx:1136-1194` |
| the address is WALKED to the premises (hard rule 8) | `row.premises_address`, served by the seam | decision log 2026-09-08, `PRB-21` |
| no database id on screen (B14 rule 31) | the cell prints `unit_label ?? unit_no`, never `unit_id` | `PlanDetail.tsx:1154` |

### Findings

1. **THE CALLOUT LOSES ITS SECOND SENTENCE.** The frame's callout ends
   *"That is why this tab counts 74 units and not 74 customers."* — which is the
   sentence that answers *74 of what*, the whole complaint in `WHAT WAS WRONG`. The
   code's `rating.planUnits.why` stops at *"…the owner's bill."*
2. **NOTHING SORTS BY PREMISES ON THE SCREEN.** The frame's COGNITIVE LOAD row says
   *"sorted by premises so the units of one building sit together"*, and the drawn
   rows demonstrate it (two `101 Silver Creek Rd` rows adjacent). `UnitsTab` sends no
   `sort` parameter (`PlanDetail.tsx:1112-1115`) and declares no default order; the order
   is whatever `GET /plans/{id}/units` returns. Not verified against the endpoint from
   this lane — recorded as unconfirmed, because it is a server-side ordering question
   and the screen states nothing about it either way.
3. **THE `PREMISES` CELL HAS AN ABSENCE PATH THE FRAME DOES NOT DRAW.**
   `PlanDetail.tsx:1155-1160` renders `rating.planUnits.noAddress` when
   `premises_address` is null. Correct behaviour under hard rule 8 and worth keeping;
   recorded only because §2.5 of the build method asks for drawn absences to be listed
   and this one is not among them.
4. **THE `SERVICES` CELL HAS AN ABSENCE PATH THE FRAME DOES NOT DRAW.** Same shape —
   `rating.planUnits.noServices` (`PlanDetail.tsx:1161-1166`).
5. **THE TILES AND THE ABSENCE BAR DO NOT MATCH THE DRAWING ON THIS TAB EITHER.** The
   four tiles are the Overview's four (`Units · Revenue · Services · Exceptions`) and
   there is no `NOT WORKED OUT YET` bar — **full evidence in `CR-087-p105`, finding 1.**
   Recorded here because the frame draws them on this tab too.

### Divergences recorded under B14 rule 38 — the UI rules win, nothing is built

* **The frame draws NO pagination footer** and its own STATES row says the table is
  paged. **B14 rule 16 puts the footer on every list table** — `Showing 1–50 of N ·
  Rows per page … · ⇤ ← Page x of y → ⇥`. The code renders the shared `ListPager`
  (`PlanDetail.tsx:1198-1206`). **Rule wins; the drawing loses; nothing is removed.**
* **The frame draws no toolbar** — no search, no filter chips, no column selector.
  **B14 rule 12 puts the toolbar on a list table**, and rule 19 requires a prompt
  naming the fields. This table is a PANEL table rather than a list screen and carries
  neither. Recorded as an open question of classification rather than a defect: the
  same shape appears on the metering module's per-object tabs. **Not built from this
  lane.**
* **The frame draws the table as a plain `ListTable` inside a `Panel`.** The code
  hand-rolls `<table>` with the module's `TH`/`TD` constants
  (`PlanDetail.tsx:1136-1194`) rather than composing the kit's `DataTable`. B14 rule
  20's two type tiers ride on `text-table`, which the `TH`/`TD` constants carry
  (`PlanDetail.tsx:426`, its own comment: *"THE SAME TABLE SKIN … DECLARED A THIRD
  TIME"*). **Rule 36's *"compose the kit"* — recorded, not fixed.**

---

## FOR THE PRODUCT OWNER

Nothing on this tab conflicts with a signed rule, and it is the screen in this range
that most closely matches its drawing. The only judgement worth one sentence is
whether a **panel table inside a detail tab** carries B14 rule 12's toolbar. It appears
on four screens in this module and on the metering module's tabs, so it is a rule
question rather than a screen question.
