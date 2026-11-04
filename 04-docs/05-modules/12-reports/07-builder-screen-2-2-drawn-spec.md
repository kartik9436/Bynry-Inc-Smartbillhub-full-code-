# 07 · Screen 2·2, the report builder — the drawn specification, and what diverges from it

**Lane REP-EDITOR-B · 2026-09-27 · build `2.380.6` · screen `RPT-02` / A1 `S47` ·
`/{tenant}/reports/{key}?edit=1`**

This file exists because a redesign of the report editor was dispatched on
2026-09-27 and **the builder turned out to be already drawn**. Under the skill's
§1 and B14 rules 41 and 42, a drawn screen is built to its drawing; under law 13,
a change that reverses a ruling goes to the Product Owner with the supersession
stated. Both apply here, and this file is the evidence for the second.

**Nothing in this file was read from the PDF's text layer as its specification.**
`05-prototype/09 Reports Build Brief.pdf` pages **31, 32 and 33** were rendered at
scale 3 through `10-scripts/pdf/pdf_render.py` and read as images, which is B14
rule 42. The text layer was used only to find the pages.

---

## 1 · The drawing exists, and it is stamped RULED

Page 31 carries the drawing under this heading, verbatim off the rendered page:

> **2·2 · REPORT — EDIT**  `TASK P5.3`  `RULED PANEL`
> END STATE · DESKTOP 1440 · **THE SAME TABLE, WITH A PANEL BESIDE IT**

The word `RULED` is not this lane's gloss. Page 3 of the same document:

> **The builder is a panel, not a wizard.** `RULED`
> Put to the Product Owner on **2026-09-26** and answered **"panel"**. This breaks
> a 42-file convention and was raised as such. `WizardFrame` gives a numbered
> rail, a forward fence and a single transactional commit at the end — the right
> shape for a linear task. A report builder is *iterative*: change a column, see
> the rows change, change it back. A forward fence fights that, and
> commit-at-the-end means you cannot see your report until you have finished
> describing it. **So 2·2 is an edit panel beside the live table — the preview
> *is* the viewer.**

It is in the decision log too (`12-governance/02-decision-log.md`, entry for
2026-09-26, section *"THE RULING THIS PHASE RESTS ON, CITED AND NOT RE-DERIVED"*),
and that entry records the panel **measured on the running product at 1440**: the
panel's left edge at `1160px`, the table's right edge at `1144px`, and horizontal
overflow at 1280 of **0px**.

**The ruling is one day older than the complaint that asks to reverse it.**

---

## 2 · What page 31 actually draws — the panel, section by section

The panel is a single narrow column on the **right**, running the full height of
the content area. The table keeps its own toolbar, its own pager and its own rows,
one column narrower. Row order below is the drawn order.

| § | Heading as drawn | Rows, in the drawn order |
|---|---|---|
| ① | `Report` | `Dataset` → *Payments* · `One row per` → *account* · `Calendar` → *Billing* |
| ② | `ATTRIBUTES · 4 OF 7` | `Account` · `Customer` · `Class` · `Route` each with ✓ and ✎; `Service` with an **empty box** |
| ③ | `MEASURES` | `61–90 days` *Sum* · `Over 90 days` *Sum* · `Total owed` *Sum* · `Accounts` *Count*, dimmed |
| ④ | `FILTERS · 13 AVAILABLE` | `Days overdue ≥` → *60* · `Consumer class` → *All* · **`+ Add filter`** · then the footer `Show on the bar` → *4 of 13* |
| ⑤ | `GROUP & SORT` | `Level 1` → *Area* · `Level 2` → *Route* · `Level 3` → *None* · `Subtotals` → *Every level* · `Sort` → *Total ↓* |
| ⑥ | *(no heading)* | the **unsaved marker**, in the rollup — drawn as `Unsaved · from AR Ageing` under the page title |
| ⑦ | `WHERE IT LIVES` | `Group` → *Receivables* · `Sub-group` → *Arrears* · `Services` → *All* · `Visible to` → *Only me* |

Above the panel, in the page head: `← Reports` · kicker `EDITING` · title
`Overdue 60+` · and two actions, **`Cancel`** (outline) and **`Save as`** (filled).

Page 32's own facts table for the screen:

* **FOR** — a clerk or analyst answering a question we did not write a report for
* **DOORS** — **one: the Edit button on 2·1.** Nothing else reaches it,
  deliberately — you always edit a report you are already looking at
* **PRIMARY ACTION** — **`Save as`, not `Save`**: editing a built-in never
  overwrites it, and that wording is the safety
* **FIELDS** — dataset · columns · filters · group by · sort · name · group ·
  sub-group · services · visibility
* **TABLE CONTROLS** — unchanged from 2·1; the table below **is** 2·1, running live

---

## 3 · The PO has already looked at this panel once, and page 32 records it

Page 32 carries a red box, verbatim:

> **"The user cannot add columns" — the PO, looking at this panel. Three parts,
> and two are mine to fix.**
>
> **Fixed here.** You could not *reorder* a column and you could not *rename* its
> heading. Both are definition data, both are cheap, and a report you cannot
> reorder is half a builder — `P5.11`. And an unticked column was drawn *greyed*,
> which reads as *you cannot* when the truth is *you have not*. It is an empty box
> now.
>
> **Not fixed, and stated rather than hidden.** You cannot invent a column the
> dataset does not produce. **That is the architecture, not an oversight:**
> datasets are code and definitions are data, which is the whole reason a utility
> can author reports at all without us shipping them a fork. The panel says how
> many columns the dataset has — *7 available* — so a clerk can see the list is
> complete rather than wondering what is hidden.
>
> `OPEN` **A computed column** — *Total = 61–90 plus 90+* — is genuinely
> definition data and would not need a dataset change. It is **not in this plan**,
> because it is an expression editor: a grammar, a validator, a type system and a
> set of error messages. **If a utility asks for it, that is a change request with
> a named requester and a figure.**

**This matters for the 2026-09-27 complaint.** *"no edit no adds"* is the same
sentence the drawing already answers. Rename and reorder are drawn, and — §4 below
— they are also **built**. The part that is genuinely refused is inventing a column
the dataset does not produce, and the drawing refuses it on the record rather than
quietly.

---

## 4 · Drawing vs. the code at `2.380.6` — verified by reading the file

`07-frontend/src/features/reports/ReportEditPanel.tsx`, 636 lines, on
`route-b-migrated.txt`, mounted by `ReportViewerPage.tsx:1350` behind
`searchParams.get("edit") === "1"`, with the `Edit` door at
`ReportViewerPage.tsx:1143`. **The panel is wired** — law 2 checked in both
directions: the door exists, it is a `Button`, and it sets the parameter the panel
reads.

| Drawn | Built? | Where |
|---|---|---|
| Panel on the right, table live beneath | **Yes** | mounted beside the table; measured 0px overflow at 1280 (decision log, 2026-09-26) |
| ① Report — dataset, grain, calendar | **Yes** | `ReportEditPanel.tsx:296–334` |
| ② Attributes — tick, reorder, rename | **Yes** | `:335–412`; reorder is **two buttons, not a drag** — a declared divergence, keyboard reachability |
| ② header `4 OF 7` | **Wrong arithmetic** | `:339–341` — see §5 |
| ③ Measures, each with its own aggregation | **Yes** | `:413–460` |
| ④ Filters, header `13 AVAILABLE` | **Yes** | `:462–465` |
| ④ **`+ Add filter`** | **NO — absent** | `:466–482` renders *every* declared filter as a stacked row. **`DEF-REP-7080`** |
| ④ footer `Show on the bar · 4 of 13` | **Yes** | `:483–488` |
| ⑤ Group & sort, three levels | **Yes** | `:493–521` |
| ⑦ Where it lives | **Yes** | `:523–580` |
| `Cancel` + `Save as` | **Yes** | `:584–596` |

### 4.1 The one drawn control that is missing

Page 31 §4 draws **two** filter rows — the ones carrying a value — then
`+ Add filter`, then the `Show on the bar` footer. The code maps the dataset's
**whole** filter list:

```tsx
{filterNames.map((name) => (          // ReportEditPanel.tsx:466
  <Row key={name}> … </Row>
))}
```

So a dataset declaring thirteen filters draws **thirteen stacked rows** in a narrow
column, where the drawing draws **three**. Filed as **`DEF-REP-7080`**
(design-divergence, medium).

**This is the same complaint as the dispatch's task 9** — *"ten filters and three
grouping levels legibly"* — and **the drawing already solves it**, by progressive
disclosure rather than by widening the column. It needs no ruling and no reversal.

---

## 5 · The `7 of 5` count — mechanism, confirmed

Section ② asks for `t("reports.edit.shownOfTotal", …)` with:

```tsx
shown: draft.columns.length,   // ReportEditPanel.tsx:340 — attributes AND measures
total: attributes.length,      // :341 — attributes ONLY, measures removed at :223-227
```

`attributes` is built by *removing* every measure from `dataset.columns`
(`:223–227`), while `draft.columns` is the full column list and carries measures —
`displayOrder` at `:251–256` appends them on purpose, because dropping them once
cost *Usage* and *Amount* off a billing register.

**So the heading over-counts by exactly the number of ticked measures, always.**
Five attributes and three ticked measures read **"8 of 5"**. The drawing's form is
`4 OF 7`, where shown ≤ total by construction.

**This is lane REP-EDITOR-A's item and is deliberately not touched here.** It is
recorded because a finding that lives only in one lane's report is a finding nobody
can count.

---

## 6 · The dispatch's four asks, against the drawing

| Ask | Status against the drawing |
|---|---|
| **6 · a page, not a rail** | **Reverses the `panel` ruling of 2026-09-26.** Needs the PO |
| **7 · rename / move / remove on the preview itself** | The acts are **already built**, in the panel. Moving them onto the column headings is a second door to one thing, which page 30 callout ① warns against by name: *"two ways to change one thing is how they diverge"*. Needs the PO |
| **8 · a `+` at the end of the header row** | The drawing's `+` is **`+ Add filter`, inside the panel**. A `+` on the header row that adds a *column* can only offer the dataset's own columns — the tick-list, relocated. Needs the PO |
| **9 · filters and grouping with room to read** | **Buildable now, to the drawing** — `DEF-REP-7080`. No ruling needed |

---

## 7 · What is NOT built at all, from the 2026-09-26 entry

Named here because a redesign conversation should not rediscover them:

* `P5.5` — screen `E·2`, the Reports section of Settings. ⚠ **AMENDED 2026-09-27,
  HOURS AFTER THIS FILE WAS WRITTEN:** a sibling landed the section's fourth card in
  `2.381.0` (`a3591ed74`, `BR-REP-044`), so *"untouched"* — the 2026-09-26 entry's
  word, quoted here — is no longer true. **The claim that matters is still true and
  was re-checked against `7fa5b6552`: `report_categories` appears nowhere in
  `07-frontend/src/features/tenancy/referenceDataConfig.ts`**, whose `reports` group
  holds four cards and none of them that one. **A tenant can still add no catalogue
  category of its own**; a saved report files under one of the six shipped
* `P5.8` — the `J-REP-04` journey markdown (the journey *is* walked, in
  `10-scripts/rep_p5_builder_walkthrough.mjs`)
* `P5.9` — role gating on a definition. `BR-REP-023` restricts the access-review
  report to System Admin and Executive and **nothing enforces it**
* `P5.12` — the History retention link into `E·2`, which `P5.5` did not build
* **Building a report from scratch** — `+ Build your own` opens the **Custom** list
  instead, because `GET /reports/{key}` resolves a definition first and there is no
  read path for a report that has never been saved

---

## 8 · Status

**This lane STOPPED before building tasks 6, 7 and 8**, and did not silently choose
between the drawing and the dispatch. The question put to the Product Owner is in
the lane's report and in `12-governance/02-decision-log.md` for 2026-09-27.

Task 9 is buildable to the drawing and is filed as `DEF-REP-7080`. It was not built
in this lane because lane **REP-EDITOR-A** is live and unpushed in the same file and
the same section, and racing it would revert its work (law 11).

---

## 9 · 2026-09-28 — THE PANEL IS SUPERSEDED. THE BUILDER IS ITS OWN PAGE

**Lane REP-EDITOR-PAGE · build `2.386.0` · `/{tenant}/reports/{key}/edit`**

**PO ruling, verbatim:** *"the report editor — panel or its own page - own page"*
(`12-governance/02-decision-log.md`, 2026-09-28, commit `d8c4bc1cb`).

⚠ **§1 OF THIS FILE IS NOW HISTORY AND IS DELIBERATELY NOT DELETED.** It records
that p031 is stamped `RULED PANEL`, that the ruling was one day older than the
complaint, and that lane REP-EDITOR-B stopped rather than guess. That is the
evidence the supersession rests on, and law 13 asks for the supersession to be
*stated* rather than assumed. **It is stated here: the 2026-09-26 `panel` ruling
is SUPERSEDED as of 2026-09-28, and nobody may re-open it by citing p031's
stamp.** The PO was shown the cost — *a page cannot show the rows changing as a
column is ticked* — and chose the page with that cost in front of them.

### 9.1 What the ruling changed, and it is ONE sentence of the drawing

Exactly one line of p031 is reversed: *"END STATE · DESKTOP 1440 · **THE SAME
TABLE, WITH A PANEL BESIDE IT**"*, and callout ⑨ which argues for it. **Every
other thing on p031–p033 still binds and is still built to**: the seven
sections, their contents, their order, `4 OF 7`'s form, `13 AVAILABLE`,
`Show on the bar · 4 of 13`, the unsaved marker in the rollup, `Cancel` then
`Save as` at the top right, and `Save as` NEVER `Save`.

### 9.2 The departures, each one deliberate and each one recorded

| # | The drawing | What was built | Why |
|---|---|---|---|
| 1 | the live table beneath the panel | **a five-row preview of the report's own rows**, in `ReportSamplePreview` | the ruling costs the live table. §9.3 is the answer this lane owed |
| 2 | table left, panel right | **sections left, preview right** | on a page the choosing IS the screen; DOM order is reading order, so a keyboard meets the controls first |
| 3 | a narrow fixed right column | **`lg:w-96` — 384px, one step up our scale from the panel's `lg:w-60`** | the extra 144px is the physical half of *"I don't know how fields are shown"*. A token on our scale, not a measurement off the page (B14 rules 44 and 37) |
| 4 | `← Reports` | **`←` the report's own name** | on the drawing that arrow belonged to 2·1, which had the only address. A clerk sent to the library has lost the report |
| 5 | a drag handle to reorder | **two keyboard-reachable buttons** | unchanged from the panel, and recorded there for the same reason |
| 6 | ⑤ `Level 1 · Level 2 · Level 3 · Subtotals · Sort` | **three levels only** | `Subtotals` and `Sort` are `DEF-REP-7200`, FILED NOT BUILT — honouring them is the runner's half (`P2.17`), and a control the server ignores is a dead control |

### 9.3 *What does the clerk see while they are choosing* — the answer

The decision log handed this lane one thing to decide. **The answer: the
report's OWN first five rows, run with the draft's columns, re-running on every
tick — and the SHAPE where those rows do not exist.**

* **The furniture goes, the answer stays.** The panel bought a live table:
  toolbar, search, sort, pager, KPI band, export, fifty rows. One thing in that
  list is a decision being made on this screen — *which columns, in what order,
  reading which way, over rows that are really mine*. The rest belongs to 2·1
  and is one click away. The space that buys goes to the controls.
* **It is STICKY, which the panel never was.** On the panel, scrolling to
  *Group & sort* scrolled the table out of sight — the rows were beside section
  ① and nowhere near section ⑤. The preview holds its position while the
  sections scroll under it. **That is the one respect in which the page is
  better than what it replaces**, and it is worth writing down because the rest
  of this trade is a cost.
* **No invented figure, ever.** Where the run returns nothing,
  `ReportShapePreview` draws headings over grey bars and not one character a
  clerk could read as a value. The page picks on `rows.length`, so there is
  always a shape and never a made-up number on a money screen.

### 9.4 `DEF-REP-7080` — CLOSED, to the drawing

§4.1 of this file said the code mapped the dataset's whole filter list, so a
dataset declaring thirteen filters drew thirteen stacked rows where the drawing
draws three. **It now draws the filters that are ON THE BAR, then `+ Add
filter`, then `Show on the bar · N of 13`** — the drawing's own shape, which
needed no ruling.

One thing the drawing implies and the old code contradicted: **presence puts a
filter on the bar and VALUE narrows the report.** p031's second row is
`Consumer class → All` — on the bar, narrowing nothing. So clearing an input no
longer deletes the row (it used to, and the row vanished under the clerk
mid-edit); a trash control removes it, and `draftToWire` drops an empty value so
the SAVE never carries `{"consumer_class": ""}`.

Measured on the statement, whose dataset declares thirteen: **13 stacked rows
before, 0 rows and one `+ Add filter` control after.**

### 9.5 `DEF-REP-7073` — CLOSED STRUCTURALLY, not patched

The editor was `?edit=1`, and `searchFrom` rebuilds the whole query string from
the report's own parameters — so a parameter it does not know about is DELETED
by any update, and every control on the screen reaches `update()`. The fix at
the time was one line re-setting the flag, which every future caller has to
remember. **The builder's address is a PATH SEGMENT now and `searchFrom` cannot
touch a path.** The fault class is removed rather than patched, and
`reportEditorPage.dom.test.tsx` presses a control and then asserts
`router.state.location.pathname`, which is the thing that actually moved.

### 9.6 The address, and why it needs no new reserved word

`/reports/{key}/edit` is a CHILD segment. The signed reserved list stays at
four: a report key is `[a-z0-9_]` and never holds a slash, so `/reports/edit` is
still a report a utility may call *Edit* and `/reports/edit/edit` is that
report's builder. `?edit=1` was reached for in the first place to avoid widening
that list, and the child segment does not widen it either.

`?edit=1` **still answers** and redirects here carrying the rest of the query —
it was the builder's address for two days and is in bookmarks, two walkthrough
scripts and the Product Owner's own screenshots.


### 9.7 Two things the browser found that no suite could

Both were measured at 1440 on the running product, per hard-won law 6.

* **`DEF-REP-7201` — FIXED HERE.** `index.css` carries a global
  `.view label:has(> select) { flex-direction: column }`. Its specificity is
  (0,1,2); a Tailwind utility is (0,1,0). So section ①'s *Dataset* row drew its
  word **centred above** its own select while the two rows under it — plain
  `<div>`s — drew label-left value-right as the drawing shows. Measured:
  `flexDirection` computed `column`, the label's box 350×68, the word at x=446
  in a 384px column. **`tsc`, eslint, `toHaveClass`, `G31` and
  `routeBUtilities.test.ts` all passed over it**, because every one of them
  reads the class LIST and none reads a COMPUTED style. Fixed by making the
  label a sibling so the selector stops matching — `flex-row` would lose on
  specificity and a stylesheet class is what rule 21 forbids. After: the label
  sits at x=297, the panel's left edge. **The general case is open**: any label
  wrapping a select anywhere under `.view` is still stacked.
* **`DEF-REP-7202` — FILED.** The attributes list offers a column called
  **`teller`** on every report built on the `payments` dataset. `reportWord`
  falls through to the stored name where no catalogue entry exists, which is
  right — a blank option is a silence a clerk cannot report — and it means a
  key that exists in **no** language is invisible to a parity check.

### 9.8 Walked, at 1440 and 1280

`10-scripts/rep_editor_page_walkthrough.mjs`, shots in
`scratchpad/po-shots/rep-editor-page/`. Measured on the running product:

| | 1440 | 1280 |
|---|---|---|
| `Edit` on 2·1 lands on | `/brazosbend/reports/billing-register/edit` | same |
| `?edit=1` lands on | `/brazosbend/reports/billing-register/edit` | same |
| tick a column → address | unchanged | unchanged |
| filter rows drawn, 8 declared | **0**, plus one `+ Add filter` offering 8 | same |
| after adding one | **1**, `Show on the bar 1 of 8` | same |
| AR Ageing preview | **5 live rows of 26 served · 8 headings** | same |
| statement | `7 of 7`, no Measures section, 7 shape headings | same |
| horizontal page overflow | **0px** | **0px** |
| preview after scrolling 900px | `top=433` in an 1100px viewport — still in view | — |
