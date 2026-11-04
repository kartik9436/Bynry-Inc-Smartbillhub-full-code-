# Plans 39 · View · Audit — THE DRAWN SPEC

`PLN-02 · Audit` · route `/:tenant/plans-rates/plans/:id?tab=audit` · **blueprint pages 112–115**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, screen `39`,
frame drawn on page 113, specified on 114–115.

**State chip:** ⚠ `EXISTS BEHIND` **· `NO COMMITMENT`**
Page 2's own definitions: `EXISTS BEHIND` = *"the screen is drawn and the data behind
it is served"*; `NO COMMITMENT` = *"A screen no specification covers … and that absence
is the finding, not an oversight."*

**WHAT WAS WRONG (page 112, verbatim):** *"The Effective column was an em-dash on every
row but one, explaining that a plan version has no start date of its own."*

---

## 1 · Header, actions, tabs — identical to the Overview

Back link `← Plans & Rates` · kicker `PLAN · SCW-RES · V1` · title
`Residential Standard` · pill `PUBLISHED` · the two-line sub-line · actions
`Duplicate HELD` · `Edit` · `Retire` (danger) · tabs `Overview | Units | Audit` with
**`Audit` active**.

## 2 · Tab description — one sentence

`What this plan has said, and from when.`

## 3 · Tiles and the absence bar — identical to the Overview

The same four tiles and the same `NOT WORKED OUT YET` bar.

## 4 · The one panel — `Audit`

| slot | drawn |
|---|---|
| panel title | **`Audit`** |
| table | FIVE columns |

| # | header | alignment | drawn cells |
|---|---|---|---|
| 1 | `VERSION` | left | `v2` · `v1` |
| 2 | `EFFECTIVE` | left | **`01/01/2027 →`** · **`06/01/2026 – 12/31/2026`** |
| 3 | `WHAT CHANGED, AND WHY` | left | `Water schedule rebound after the 2027 filing` · `—` with a second line, the honest-first-row sentence |
| 4 | `BY` | left | `Dana Whitfield` · `—` |
| 5 | `STATUS` | left | `PUBLISHED` *(green pill)* · `SUPERSEDED` *(grey pill)* |

⚠ **`EFFECTIVE` CARRIES A RANGE ON EVERY ROW.** Page 114, verbatim: *"The Effective
column was an em-dash on every row but one, with the sentence *a plan version does not
carry its own start date*. **It carries a range now, taken from the next version's
start — which is what a date span means and needed no new column.**"*

**THE HONEST FIRST ROW (page 114, verbatim):** *"A plan whose first version predates the
history says so, once, in full: nothing was stored about who or why, and every change
since is recorded. History is never invented backwards, and saying it once beats an
em-dash on every field."* The drawn sentence: `This plan's first version predates the
version history, so nothing was stored about who set it or why. Every change since is
recorded in full.`

**Under the table, a red-ruled callout:**

> **WHAT THIS IS AND IS NOT**
> `This history is a record of what the plan said. Which version a bill is priced from`
> `is a separate question and nothing here changes what an account is charged.`

Page 114: *"Its own note. This tab records what the plan said; it does not decide what a
bill charges. Confusing the two is how somebody concludes a bill is wrong."*

⚠ **B14 rule 37 — `v2`, `Dana Whitfield`, `01/01/2027`, `Water schedule rebound after
the 2027 filing` are ILLUSTRATIONS.**

## 5 · WHAT CHANGED · THE NAME (page 114, verbatim)

*"It was `Versions`. Eight detail screens in this product call this tab `Audit`, and
Plans & Rates was the only module using its own word — corrected on all four objects,
not just the one that was asked about."*

## 6 · FOR · HOW YOU GET HERE · PRIMARY ACTION (page 114)

* **FOR** — *"An auditor, or a clerk asked why a plan changed."*
* **HOW YOU GET HERE** — *"The `Audit` tab."*
* **PRIMARY ACTION** — *"`Edit`, from the header, which creates the next row."*

## 7 · STATES (page 114)

| state | drawn behaviour |
|---|---|
| **Never versioned** | *"No version of this plan has been recorded yet. Version history began on 21 August 2026 and is never filled in backwards."* |
| **A reason nobody wrote** | *"An em-dash with `no reason was written down` — a fact about the record."* |
| **The person has left** | *"No longer has an account."* |

## 8 · COMPONENTS named in the frame (page 114)

`Panel` `VersionTable` `StatusPill` `Callout accent`

## 9 · Absences — drawn as absent, do not fill them

* **No `Dated` banner at the foot of the tab.**
* **No second note below the callout.**
* **No pagination footer.**
* **No row action of any kind.**

---

## DIFF AGAINST THE RUNNING CODE — `2.234.19`

`07-frontend/src/features/rating/PlanDetail.tsx`, `VersionsTab` at `:1357`.

### Conforming

| drawn | code | evidence |
|---|---|---|
| **the tab is called `Audit`** | `PLAN_DETAIL_TABS[2] === "audit"`; `rating.planDetail.tab.audit` = *"Audit"*; the old `?tab=versions` still resolves | `PlanDetail.tsx:267`, `:290` |
| the tab description, **verbatim** | `rating.planDetail.explainer.audit` = *"What this plan has said, and from when."* | `en.json` |
| the current version is shown even when unrecorded | `planVersionLines` prepends it rather than leaving the tab empty | `PlanDetail.tsx:1310-1330` |
| **A reason nobody wrote** state, verbatim | `rating.planDetail.versions.noReason` = *"No reason was written down"* | `en.json` |
| **The person has left** state | `rating.planDetail.versions.unknownPerson` = *"A user who no longer has an account"* | `PlanDetail.tsx:1404` |
| **Never versioned** state, with its date | `rating.planDetail.versions.emptyHistory` — *"Version history began on 21 August 2026 and is never filled in backwards…"* | `PlanDetail.tsx:1454` |
| `STATUS` shows the plan's pill on the current row and `superseded` on the rest | `RatingStatusPill` in both branches, never two `Published` pills | `PlanDetail.tsx:1435-1447` |
| the newest row first | the server orders descending; the screen does not re-sort | `PlanDetail.tsx:1310-` |
| no row actions | none rendered | `PlanDetail.tsx:1386-1450` |

### Findings

1. **⚠ THE `EFFECTIVE` COLUMN IS STILL THE DRAWN DEFECT, WORD FOR WORD.**
   `PlanDetail.tsx:1409-1412` renders, for every row that is not the current version:

   ```
   <Absent reason={t("rating.planDetail.versions.noVersionWindow")} />
   ```

   and that key is `'A plan version does not carry its own start date. When it does,
   this will say so.'` — **the exact sentence page 114 quotes as what was replaced.**
   No range is derived on any row; only the current version prints a date, and it
   prints the PLAN's `effective_from` (`PlanDetail.tsx:1413-1421`), not a version
   window. So the column is an absence on every row but one, which is the frame's
   `WHAT WAS WRONG` unchanged.
   ⚠ **BUT THE FIX IS NOT A LANE'S TO MAKE — see FOR THE PRODUCT OWNER.**
2. **THERE IS NO `BY` COLUMN.** The table declares FOUR headers —
   `version · effective · change · status` (`PlanDetail.tsx:1370-1384`). The submitter
   and the recorded-at date ride **under the version number** as a second line inside
   column 1 (`PlanDetail.tsx:1393-1408`), on the code's own reasoning: *"WHO and WHEN,
   under the number rather than in columns of their own — §10 gives `BY` to the rate
   schedule alone."* The frame draws five columns with `BY` as the fourth.
3. **THE PANEL IS STILL HEADED `Versions`.** `PlanDetail.tsx:1367` renders
   `rating.planDetail.panel.versions` = **`Versions`**. The rename landed on the TAB
   and not on the panel inside it, so the screen reads `Audit` in the tab strip and
   `Versions` one line below. This is the same half-landed-rename shape as
   `CR-087-p099` finding 1.
4. **THE HONEST FIRST ROW'S SENTENCE DIFFERS IN BOTH HALVES.**
   Drawn: *"This plan's **first** version predates the version history, so nothing was
   stored about who set it or why. **Every change since is recorded in full.**"*
   Code (`rating.planDetail.versions.currentUnrecorded`): *"This plan's **current**
   version predates the version history, so nothing was stored about who set it or
   why. **The next change to this plan will be recorded in full.**"* The code's second
   sentence is a promise about the future; the drawn one is a statement about the
   record, which is what an auditor needs.
5. **THE CLOSING CALLOUT CARRIES AN EXTRA CLAUSE AND HAS NO LABEL.**
   `PlanDetail.tsx:1458` renders `rating.planDetail.versions.inertNote` = *"This
   history is a record. Which version a bill is priced from is a separate question
   **that has not been decided**, and nothing here changes what an account is
   charged."* as a bare `<Note>`. The frame draws it under the label
   `WHAT THIS IS AND IS NOT`, and **without** the *"that has not been decided"*
   clause — which is `OQ-323`, an internal question, and B14 rule 32's fourth clause
   bans internal code in clerk-facing copy while rule 33 puts RATIONALE at zero words
   on screen.
6. **A `Dated` BANNER CLOSES THE TAB AND THE FRAME DRAWS NONE.**
   `PlanDetail.tsx:1462-1464` renders a `RuledNote` labelled
   `rating.planDetail.versions.datedLabel` = *"Dated"* with
   `datedBanner` = *"Composition changes save as a new plan version via the builder —
   accounts re-price from its effective date."* Two callouts where the frame draws
   one.
7. **THE TILES AND THE ABSENCE BAR DO NOT MATCH ON THIS TAB EITHER** — full evidence
   in `CR-087-p105`, finding 1.

### Divergences recorded under B14 rule 38 — the UI rules win, nothing is built

* **The frame draws no pagination footer.** B14 rule 16 exempts nothing but wizard
  summary tables; this table is unpaged in code too. Recorded as a shared gap rather
  than a divergence — the version count is small by construction, and **`NFR-3` says
  universal server pagination**, so an unpaged version list is a `T5` question the
  same as `GET /outstandings`. Named, not filed.

---

## FOR THE PRODUCT OWNER — the drawing asks for something a signed question has not settled

⚠ **HISTORY (2026-10-03): `OQ-324` is CLOSED as (B) by the PO-approved plans drawing (`CR-167-BRC10`), and `plan_versions` carries `effective_from`/`effective_to` from `rating/0062` — so the drawn range CAN now be served (`GET /plans/{id}` `versions[]`). The paragraphs below record what was true when this audit was written.**

**The frame's `EFFECTIVE` range is `OQ-324`, and `OQ-324` is OPEN.**

`12-governance/01-open-questions.md:412` — *"DOES A PLAN VERSION TAKE EFFECT THE MOMENT
IT IS SAVED, OR IS IT DRAFTED WITH AN EFFECTIVE DATE AND THEN ACTIVATED?"* — with two
options: **(A) IMMEDIATE, AS BUILT**, a version row records a change that has already
happened; **(B) EFFECTIVE-DATED PLAN VERSIONS**, `plan_versions` grows
`effective_from`/`effective_to`. The register records that `plan_versions` carries **no
`effective_from` column, deliberately** — *"adding one would make the dated reading
storable before it is ruled"*.

The drawing's own claim is that the range *"needed no new column"* because it is *"taken
from the next version's start"*. **On the data as stored, there is no next version's
start to take** — only the PLAN carries `effective_from`, and the drawn `01/01/2027` on
`v2` is the same date the page's `CHANGE ALREADY DATED` tile gives to a **rate
schedule's** dated change, which is a different object.

**So: the drawn column cannot be built from what is stored, and building it needs option
(B), which is a schema change `OQ-324` reserves for the PO.** Recorded; nothing built.
The three copy findings (3, 4, 5) and the missing `BY` column are independent of it and
need no ruling.
