# § 03 · Getting the readings in — the drawing against the running product

**Scope.** Blueprint entries **07, 08, 09, 10, 11, 12, 13** — PDF pages **21–38** (page 39
read too, because entry 13's field table runs onto it), read **AS IMAGES** at scale 2 per
**B14 rule 42**. Extracted text was used to find the pages and to check a spelling, and for
nothing else.

**Measured at** product version **`2.261.3`**, branch `claude/hi-0jmv62`, commit `c56e69b4`,
on **2026-09-13** — **24 versions after the blueprint was read** (`2.237.10`, 2026-09-12).
Every as-built sentence below was re-established this pass, in the browser or in the code.
Nothing is copied forward from the document.

**How.** Pages 21–39 rendered with `10-scripts/pdf/pdf_render.py`. Code read in
`07-frontend/src/features/metering/UploadReadsWizard.tsx`, `QuickReadModal.tsx`,
`ReadsBulkBar.tsx`, `readsImportRail.tsx`, `demandShared.tsx`,
`07-frontend/src/components/workflow/{WorkflowRunner,StageBar,kinds,workflowKit,
RollbackNotice,ReconcileStrip}.tsx`, `07-frontend/src/components/FormModal.tsx`,
`07-frontend/src/api/endpoints.ts`, all eleven `src/i18n/locales/*.json`,
`06-backend/apps/metering/{api,selectors,quick_read,read_import,models}.py`.
Walked in Chromium against the deployed join (SPA `:8080`, API `:8011`, tenant
`brazosbend`, signed in as Dana Whitfield) **at 1280 AND 1440** — both widths produced
identical structure and **nothing in this scope scrolls horizontally at either width**.
Four wizard stages were driven end to end with a real paste, a real stage, a real
validation run and a real refused commit; the quick-read dialog was opened and a real
multi-register meter resolved in it; the bulk bar and its dialog were opened from the reads
list. **Stage 5 was not rendered — §9 says why.**

**This file measures and routes. It builds nothing, edits no `.tsx`, and allocates no id.**

---

## 0 · THE HEADLINE

### What the drawings in this section ARE

This matters more here than anywhere else in the blueprint, and it is the first thing to
read. **Five of the eight drawings in entries 07–13 carry the caption `REDESIGN · published
2026-09-12/13 · NEVER BUILT`** — 07, 08 (both branches), 09, 10 and 12. Two carry
`AS-BUILT` (11, from source; 13, measured in Chromium).

So for most of this section the diff is not *"has the product drifted?"* but *"the drawing
is a proposal and none of it exists."* Under **B14 rule 41** — *"it is expected that Product
UI will match extactly the way it is given in Blueprint document"* — a NEVER BUILT drawing
is a **build list**, not a defect list, and that is how the counts below are routed.

### The document's own claims, re-checked

| The document's claim | State at `2.261.3` |
|---|---|
| Entry 07 · *"Two named doors … entry 02's primary `↑ Upload reads` and the Dashboard's `Import reads`"* | **CONFIRMED.** Both walked. The dashboard control is an `<a href="/brazosbend/reads/upload">`, enabled |
| Entry 07 · *"the wizard's own step ids are `["source","upload","validate","review","post"]` … stage 5 (Result) has no entry in `UPLOAD_STEP_IDS` at all"* | **CONFIRMED, and worse than stated.** The live `steps` array is `source · upload · validate · post · result` — the constant also still names a `review` step that no longer exists, **nothing in `src/` consumes the constant**, and its own test pins the stale list (`UploadReadsPage.test.tsx:258`). Defect **D07-3** |
| Entries 08, 09 · flow **`BREAKS AT PAGINATION`** | **CONFIRMED, STILL TRUE, and the fix the briefing pointed at is a different endpoint.** `DEF-766`'s `rejects_window {total, offset, limit}` and `?reject_offset/?reject_limit` are on **`GET /imports/{id}`**, the accounts/ETL runner. **`GET /read-batches/{id}` has no window of any kind** — `selectors.read_batch_rows` (`selectors.py:5767`) returns every row and the handler reads only `?severity` (`api.py:1236`). **Measured: 16,034 bytes for a 40-row batch.** Defect **D08-2** |
| Entry 10 · *"Primary action: **Commit N rows ✓** … **Not the danger tier, and that is right**"* | **WRONG on this branch.** Measured in Chromium at 1280 and 1440: `data-variant="danger"`, `background-color: rgba(0,0,0,0)`, `border-color: rgb(224,52,26)`, `color: rgb(168,22,0)` — the outlined-accent **danger tier**. `WorkflowRunner.tsx:211` renders `variant={current.writes ? "danger" : "primary"}`. Defect **D10-1** |
| Entry 10 · *"Pressed `Commit 1 rows ✓` with the certification unticked: the button was enabled, the click was accepted, and the screen answered 'Tick the certification before posting the batch.'"* | **CONFIRMED verbatim.** Reproduced at both widths |
| Entry 11 · *"the commit refuses until the certification is ticked, and **the tick could not be driven from the script**"* | **STALE.** The tick CAN be driven — clicking the `<label>` that wraps the input ticks it (measured, `checked === true` at both widths). Stage 5 was still not reached, for a **different** reason — §9 |
| Entry 12 · *"The context panel is fetched **on blur, not per keystroke**"* | **STALE.** `TextField` carries no `onBlur` and the file says so at `QuickReadModal.tsx:312`. The lookup is an explicit **`Check meter` button** (`:317–319`), which the drawing does not draw at all |
| Entry 12 · *"As built, a meter with more than one register renders **no value fields at all** and hands off to the five-stage wizard"* | **CONFIRMED.** Resolved `M-7210` at 1440: *"This meter has 2 registers."* + *"Use Upload reads to enter all of them."* and no value field |
| Entry 12 · *"this screen renders the register as the served **code** — `tou_on`, not *On-peak*"*, the modal's reason being *"no signed vocabulary maps a channel to a display word"* | **The REASON is false.** `metering.reads.channel.tou_on` = `"On-peak"` exists in **all eleven catalogues**, with `tou_mid`, `tou_off`, `total`, `demand`, `export`, `generation`. The modal's own exception line is stale. Build **B12-4** |
| Entry 13 · *"The bar renders **nothing** until something is selected"* | **CONFIRMED.** `ReadsBulkBar.tsx:137` returns `null`; measured `"NO BAR"` before any tick |
| Entry 09 · *"**1 rows will post**" is a plural bug"* | **CONFIRMED on screen**, and it is three strings, not one. Defect **D09-1** |

**Eleven of the document's own sentences re-checked: SEVEN confirmed, FOUR already
overtaken** — the danger tier, the tick that *"could not be driven"*, the *"on blur"*
lookup, and the *"no signed vocabulary"* reason.

### The count

| | build | defect | question | on screen, not drawn | could not see |
|---|---|---|---|---|---|
| 07 · stage 1 · Extract | 13 | 3 | 0 | 1 | 0 |
| 08 · stage 2 · Transform | 8 | 3 | 0 | 0 | 0 |
| 09 · stage 3 · Validate | 6 | 3 | 1 | 1 | 2 |
| 10 · stage 4 · Load | 12 | 3 | 0 | 1 | 0 |
| 11 · stage 5 · Result | 6 | 1 | 0 | 0 | 1 |
| 12 · Add a single reading | 9 | 0 | 0 | 1 | 0 |
| 13 · Accept flags in bulk | 0 | 1 | 0 | 0 | 2 |
| shared (the rail) | 0 | 1 | 1 | 0 | 0 |
| **Total** | **54** | **15** | **2** | **4** | **5** |

**The other direction — what the product does that the drawing does not show — is four
items, each listed under its own entry (§2, §4, §5, §7).** Not one of them is a surface the drawing forgot; each is a
control or a sentence the redesign deliberately removes or never had.

---

## 1 · THE RAIL — shared by all five stages, and the one thing B14 rule 3 names

**B14 rule 3, RATIFIED:** *"Any flow with 2+ stages uses the numbered step rail (clickable
when complete) + a wizard-actions footer. Single forms never fake a stepper."* The briefing
asked specifically whether the step count is hardcoded. **It is derived in three places out
of four, and hardcoded in the fourth — the one a clerk reads first.**

**Derived, verified in code and on screen:**

* `WorkflowRunner.tsx:125` — `const total = WORKFLOW_STAGES.length`
* `WorkflowRunner.tsx:179` — `workflow.stageOf` = `"Stage {{n}} of {{total}} · {{name}}"`,
  rendering `Stage 1 of 5 · Extract` … `Stage 4 of 5 · Load` (measured)
* `StageBar.tsx:50` — `stages.map(...)`, one button per declared stage, `data-workflow-stage`
  = index + 1
* `UploadReadsWizard.tsx:3087` — `Math.min(step + 1, steps.length)`

**Hardcoded — `D-RAIL-1`:**

`StageBar.tsx:47` renders `workflow.promise`, and in English that string is:

> **"Five stages · nothing is written until you commit at stage four."**

Both numbers are literal, in **all eleven catalogues** (`Fünf Schritte … Schritt vier`,
`Cinco etapas … la etapa cuatro`, `5 つの段階 · 第 4 段階`, …). The count is
`WORKFLOW_STAGES.length` and the writing stage is the single entry carrying `writes: true`;
declare a sixth stage and the strip renumbers itself correctly while this sentence keeps
saying five, in eleven languages, above the strip that contradicts it. **Nothing checks it**
— `workflowStages.test.tsx` asserts the stage list's shape and never reads this string
against it. It is B14 rule 3's exact prohibition, in the one component the rule is about.

Two more rail facts, both measured:

* **The `Writes` chip is on stage 4** and on no other (`data-writes="true"`, rendered as the
  word `Writes`). The drawing draws it in the same place, uppercase. ✓
* **The forward fence works**: at stage 1 all five buttons are `disabled`; at stage 2, step 1
  is `data-state="done"` and clickable and steps 3–5 are disabled. That is BR-SHL-018 and it
  matches the document's *"Completed stages are clickable; stages ahead are disabled, which
  is right."* ✓

**`Q-RAIL-1` — the completed-step glyph. Both sides, verbatim, and I decide nothing.**

> **The drawing** (pages 24, 27, 29, 33) draws a completed step as a **boxed ✓ with no
> number**: `✓ Extract | ✓ Transform | 3 Validate | 4 Load [WRITES] | 5 Result`.

> **B14 rule 3, RATIFIED:** *"Any flow with 2+ stages uses the **numbered** step rail
> (clickable when complete)."* The code keeps the number and darkens the badge —
> `RAIL_BADGE_DONE = "bg-text text-bg"` (`workflowKit.ts:88`), measured as `1Extract` with
> `data-state="done"`.

This reaches the PO because it is a drawing against a signed rule (B14 rule 41), and because
`StageBar` is mounted by **seven import targets** — premises, units, three assets targets,
accounts and reads — so whichever way it goes, it moves every wizard in the product at once.

---

## 2 · ENTRY 07 · Upload reads · stage 1 · Extract · p22–24 · `/:tenant/reads/upload`

Chips: `EXISTS BEHIND` · `NEW BUILD` · `MR-06 · MR-31`. Caption: **REDESIGN · NEVER BUILT.**

**What the drawing specifies**, read off the image: header `← Reads`, kicker
`WORKFLOW · METER READS · CSV`, title **`Upload reads`**; stage kicker `STAGE 1 OF 5 ·
EXTRACT`, heading **`The source`**, no sub-line; two transport cards side by side (`CSV
upload` / *Route sheet, hand-held collector, or spreadsheet* · `Manual entry` / *Type a few
readings by hand*) and **no third card**; one line, *"AMI reads arrive as a file."*; then six
controls — `Reading month *` (*Any day in the month. We store the first.*) · `Cycle` (no
help) · `Route` (*Empty means the whole cycle.*) · `How were these read?` (*A row's own
method wins.*) · `Utility services` chips (*Which services this file covers.*) · **`Write
mode`** last (*Existing readings are not overwritten. Those rows are held back.*); footer
`Cancel` … `Transform →`.

**What the product does**, measured at 1280 and 1440.

**Matches — do not rebuild these.** The two transport cards and their sub-lines, byte for
byte, and the absence of a third. The AMI line's placement. The six controls **in the drawn
order**, write mode last. The asterisk on `Reading month` and on nothing else (rule 10). The
footer, `Cancel` … `Transform →`, primary tier, disabled until the reading month is set
(measured: `disabled: true` → `false` the moment `#period_month` is filled). The services
help, `"Which services this file covers."`, word for word.

### Build

| # | The drawing says | The screen says | Where |
|---|---|---|---|
| **B07-1** | Title **`Upload reads`** | **`Extract, transform, validate, load.`** — measured, at `32px` (rule 40 ✓) | `workflow.title`, shared by 7 targets |
| **B07-2** | Stage heading **`The source`** | **`Where is the data coming from?`** | `workflow.extract.title`. The mechanism already exists: `WORKFLOW_KINDS.reads` overrides `loadTitle` and `transformBlurb` per kind (`kinds.ts:574` and `:565`) |
| **B07-3** | no sub-line | `Upload the reading file, or type the readings in. Nothing is written until you commit at stage four.` — 18 words | `workflow.reads.blurb` |
| **B07-4** | one heading | **two**: the stage head `Where is the data coming from?` and, directly under it, the panel's own `<h3>` `Where are these readings coming from?` | `metering.upload.source.title` |
| **B07-5** | `Cycle` carries **no help** | `The cycle's read window is what out-of-window compares against.` — 10 words | `…field.cycleHelp` |
| **B07-6** | `Any day in the month. We store the first.` (4 + 4) | `Any day in the month; the batch stores the first of it.` — 11 words, one sentence | `…field.periodMonthHelp` |
| **B07-7** | `Empty means the whole cycle.` (5) | `Leave empty when the file covers the whole cycle.` (9) | `…field.routeHelp` |
| **B07-8** | `A row's own method wins.` (5) | `A row naming its own method overrides this one.` (9) | `…field.readMethodHelp` |
| **B07-9** | Write-mode label **`Write mode`** (2) | `What does this file mean?` (5, a question) | `workflow.writeMode.label` |
| **B07-10** | `Existing readings are not overwritten. Those rows are held back.` (5 + 5) | `A reading already on file for that meter, date and register is not written over. Those rows are held back for you to look at before anything posts.` — 28 words | `metering.upload.writeMode.insertConsequence` |
| **B07-11** | nothing | `Asked here, before anything is read, because it decides what the checks at the next two steps are checking FOR. You can change it until you commit.` — **27 words of RATIONALE**, which B14 rule 33 caps at **ZERO on screen** | `workflow.writeMode.help`, rendered at `WriteModeChoice.tsx:138` |
| **B07-12** | `AMI reads arrive as a file.` (6) | `Reads collected by AMI arrive as a file. Tag the source below.` (12) | `metering.upload.source.amiTagged` |
| **B07-13** | `Cycle` and `Route` drawn with a **search affordance** (🔍) | plain `<select>` on both, and on `How were these read?` | `SelectField`, three call sites — see **D07-2** |

### Defect

**`D07-2` · B14 rule 8 — *"5+ options are searchable (type-to-filter)"* — is broken on all
three stage-1 pickers, and the kit's own threshold disagrees with the rule.**
Measured on the seeded tenant: **Cycle 7 options**, **Route 7**, **How were these read? 9**.
All three are plain `<select>`. The rule says five; `FormModal.tsx:690` declares
`LONG_LIST_THRESHOLD = 10`, and `SearchSelectField`'s own comment says *"BR-SHL-033 mandates
this control past `LONG_LIST_THRESHOLD`"*. **A ratified rule and the kit's constant are two
different numbers**, so a lane obeying the kit breaks the rule and believes it complied.
The drawing agrees with the rule, not with the kit.

**`D07-3` · `UPLOAD_STEP_IDS` names five steps that are no longer the steps.**
`UploadReadsWizard.tsx:221` exports `["source","upload","validate","review","post"]` and
calls it *"The prototype's five steps"*. The live array (`:2774`) is
`source · upload · validate · post · result` — `review` was folded into `validate` by
CR-038 W7 and `result` was added. **Nothing in `src/` reads the constant.** The only thing
that touches it is `UploadReadsPage.test.tsx:258`, which asserts the stale list and passes,
which is hard-won law 7's *looking at the wrong thing*.

**`D-RAIL-1`** (§1) lands on this entry too — the promise sentence sits directly under this
screen's title.

### On screen, not drawn

* **`Cancel` at stage 1 navigates to `/reads`** rather than closing anything, and
  `WorkflowRunner.tsx:208` picks the word by `stage === 1`. That is B14 rule 1 working
  (exit vs step-back) and the drawing agrees. Recorded so nobody "fixes" it.

### Recorded divergence — B14 rule 38, nothing is built

**`X07-1` · the two-column field grid.** The drawing pairs the six controls
(`Reading month | Cycle`, `Route | How were these read?`). The screen stacks all six.
B14 rule 38, RATIFIED verbatim: *"a drawing telling you that **two fields sit side by
side** … is not layout, it is FORM CONSTRUCTION, and B14 plus the component kit already
settle it. **So the drawing loses, the divergence is RECORDED in the conformance file, and
nothing is built for it.**"* Recorded here. The drawing is still right about **which** six
controls, in **what order** — and it is, and they match.

---

## 3 · ENTRY 08 · Upload reads · stage 2 · Transform · p24–27

Chips: `EXISTS BEHIND` · `NEW BUILD` · `BLOCKED` · `MR-08 · MR-24 · MR-31 · MR-40`.
Caption: **REDESIGN · NEVER BUILT** on both branches. Two screens behind one stage, chosen
on stage 1.

**Matches — do not rebuild these.** Measured after a real paste and a real stage:

* the four starter buttons, in the drawn order: `Flat or tiered` · `Time of use` · `Demand` ·
  `Net metering` — and **no fifth, seasonal button**, exactly as the redesign note requires
* **`↓ Reading sheet for CY-001 · 18 rows`** — the button names its own number, byte for
  byte as drawn, once a cycle is tagged; disabled with its reason
  (*"Pick a cycle on the previous step to get a pre-filled sheet."*) when it is not
* `↓ Drop the file here, or browse` · `…or paste the rows` · `Stage the batch`
* the **five-cell staged strip**: `Rows in batch · Meters · Services · Read date ·
  Total register` — the drawing's five figures, in the drawing's order
* the mapping table's five columns: **`Source column | Sample value | Maps to | Transform |
  Status`**, with `Matched` on each row
* `Not in your file: row_key, service, read_method, notes, demand_reset.` — byte for byte
* **no search, filter, column picker, sort or pager** on either table, which is right:
  B14 rule 16 exempts wizard summary tables and the document says so

### Build

| # | The drawing says | The screen says |
|---|---|---|
| **B08-1** | Stage heading **`Columns`** | `Map their shape onto ours.` (`workflow.transform.title`) |
| **B08-2** | `Nothing is remembered between files.` (5) | `Columns are matched to the published template on every upload. Nothing is remembered between files.` (14) |
| **B08-3** | the drop target states `reads.csv · **2 rows** · 1 KB` and, under it, `File hash (SHA-256) · 808e48f7…` | `reads.csv · 1 KB`. **No row count and no hash at stage 2.** The hash IS computed and IS served — it renders at stage 4 (`b89a9817e071…`, measured) — so this is a placement gap, not a data gap |
| **B08-4** | `Batch RB-2609-0005 · 2 rows staged.` (5 words) | `Batch RB-2609-0015 is staged with 40 row(s). Nothing has been posted.` (`metering.upload.file.staged`) |
| **B08-5** | `Only stage 4 creates readings.` (5) | `Nothing has entered Reads yet. Only the final step creates readings.` (11) |
| **B08-6** | the manual grid **drawn to the kit** | two of its five cells are hand-rolled: a raw `<input type="date" className="input">` and a raw `<select className="input">` (`UploadReadsWizard.tsx` ~1478 and ~1498), where stage 1 three panels earlier uses `DatePickerField` and `SelectField` for the same kinds of choice. B14 rule 36 |
| **B08-7** | `+ Add a row` as an accent link | `+ Add row` as a ghost `Button` (`metering.upload.manual.addRow`) |
| **B08-8** | manual heading `Enter the readings` + `One row per register per date.` | `Type in the readings.` + `Each row inherits the batch tags. Pick the register each reading came from.` (12 words, 2 sentences) |

### Defect

**`D08-1` · `row(s)`.** `metering.upload.file.staged` = *"Batch {{batch}} is staged with
{{rows}} row(s). Nothing has been posted."* — an `(s)` construction in clerk-facing copy, in
eleven catalogues, on a stack where i18next plurals are available and used elsewhere.
Measured on screen at one row: *"staged with 1 row(s)"*.

**`D08-2` · NFR-3 — `GET /read-batches/{id}` is an unbounded list, and this is the
`BREAKS AT PAGINATION` the document names.**

* `api.py:1236` reads exactly one query parameter, `?severity`. There is no `offset`,
  `limit`, `page` or window of any kind.
* `selectors.read_batch_rows` (`selectors.py:5767`) returns
  `[read_row_dict(row) for row in qs.order_by("row_no")]` — no slice.
* `read_import.CSV_ROW_CAP = 50_000`.
* **Measured this pass: a 40-row staged batch answers `200` with `16,034` bytes** on
  `/api/brazosbend/read-batches/<id>` — ≈ 400 bytes a row, and the payload grows linearly
  with the batch to **≈ 20 MB at the cap**. The screen re-fetches it after every per-row
  `PATCH`.

⚠ **The `rejects_window` fix is on a different endpoint.** `DEF-766` gave
`GET /imports/{id}` a window — `rejects_window {total, offset, limit}` plus
`?reject_offset/?reject_limit` — and it is the **accounts/ETL** runner
(`ImportWorkflowPage.tsx`). It never reached read-batches. Anyone reading *"the reject list
travels as a window"* and assuming reads are covered will conclude this is fixed; it is not.

**`D08-3` · the manual grid's register list is a literal array in the front end.**
`READ_CHANNELS` at `api/endpoints.ts:12189` — `total`, `tou_on`, `tou_mid`, `tou_off`,
`export`, `generation`, `demand`. Every other list on stage 1 (cycles, routes, read methods,
services) is the tenant's own. The document grades this field **HARDCODED** and it is right.

---

## 4 · ENTRY 09 · Upload reads · stage 3 · Validate · p27–29

Chips: `EXISTS BEHIND` · `NEW READ` · `NEW BUILD` · `MR-08 · MR-20 · MR-31 · MR-40 · MR-49`.
Caption: **REDESIGN · NEVER BUILT.** Two of the code's five steps share this one rail stage.

**Matches — do not rebuild these.** Measured after a real `Run the rules`:

* **`Run the rules`**, byte for byte
* the **five-tile strip**: `Rows in batch · Passed · Warnings · Errors · Missing records` —
  the drawing's five figures, in the drawing's order, with `Errors` and `Missing records`
  carrying `data-flagged="true"`
* the rules table's four columns: **`Rule | Severity | Hits | Action`**
* the **segmented control**, all five segments in the drawn order and with counts:
  `All flagged (n)` · `Errors (n)` · `Warnings (n)` · `Accept all warnings` ·
  `Note demand reset (n)` — and the document is right that these are segments, not tabs,
  and not in the URL
* `Load →` in the **primary** tier, correctly (it navigates; B14 rules 4 and 6)

### Build

| # | The drawing says | The screen says |
|---|---|---|
| **B09-1** | Stage heading **`The rules`** | `Test it before you trust it.` (`workflow.validate.title`) |
| **B09-2** | `Errors block the load. Warnings do not.` (4 + 3) | `Errors block the load. Warnings don't — but you should look at them.` (13) |
| **B09-3** | two sub-labels, `What the rules found` and `Flagged rows` | two `<h3>`s that say something else: `Validation results.` and `Review and fix the flagged rows.` — so the screen carries **three** headings where the drawing carries one heading and two labels |
| **B09-4** | `Give each row a decision. An undecided error will not post.` (5 + 6) | `Give each row a decision. A row you leave undecided with an error on it will not post — it comes back in the rejects file.` (24 words) |
| **B09-5** | `This batch has no demand rows. **1 row will post. 1 will not.**` | `0 rows will post. 1 will not, and you can download them.` — plus a second sentence the drawing drops, `1 of them carry an error nobody has decided. Deciding them here is cheaper than correcting the file later.` |
| **B09-6** | `Discard this batch` sits **inside the footer**, between `← Back` and the primary | it renders **below the wizard**, outside `[data-workflow="footer"]` (`UploadReadsWizard.tsx:3160`, a sibling of `<WorkflowRunner>`). Measured: `.met-page > button` = `["Discard this batch"]` at stages 2, 3 and 4 |

### Defect

**`D09-1` · the plural bug, and it is three strings.** Measured on screen:

| key | English |
|---|---|
| `metering.upload.split.line` | `{{post}} rows will post. {{hold}} will not, and you can download them.` |
| `metering.upload.split.all` | `All {{post}} rows will post.` |
| `metering.upload.split.unresolved` | `{{count}} of them carry an error nobody has decided. …` |

None has a plural form. At one row the screen reads *"1 rows will post"* and *"1 of them
**carry** an error"*. Eleven catalogues. The document calls this *"a plural bug"* and files
it as its own row 7-09; it is confirmed, and it is wider than one string.

**`D09-2` · two words for one thing, on one screen.** The stage-2 manual grid's column
header is **`Register`** (`metering.upload.manual.col.channel` = `"Register"`, and the
entry's own *Words* row says *"Register, not channel, on the clerk-facing grid"*). The
stage-3 flagged-rows grid's header is **`Channel`** — measured:
`Row | Meter | Read date | **Channel** | Reading | What the rules said | Decision`. One
wizard, two nouns for the same column, three panels apart. This is B14 rule 34's shape
(*one pair of words, everywhere, in all eleven catalogues*) applied to a different pair.

**`D09-3` · the segment filter is client-side over the whole batch.** The four segments
filter rows already fetched, and the rows already fetched are **every** staged row
(**D08-2**). Correct at two rows; at the 50,000-row cap the segments are filtering a 20 MB
payload in the browser.

### Question

**`Q09-1` · what precision does a meter reading display at?** Both sides, and I decide
nothing.

> **The drawing** (pages 25, 28, 35) prints readings as **`8700`**, **`45910`**,
> **`12,480`**, **`51,710`** — whole numbers, thousands-separated.

> **The product** prints **`45910.000000`** — measured on the stage-3 flagged-rows grid at
> 1280 and 1440. The chain is honest end to end: `ReadImportRow.value` is
> `NUMERIC(18,6)` (`models.py:1768`), `read_row_dict` serialises it with `str()`
> (`selectors.py:5587`), and `StagedRegisterValue` (`demandShared.tsx:165`) renders
> `props.value` verbatim beside its unit.

**This is routed as a question and not as a defect on purpose**, because it is a figure on a
metering surface. **Hard rule 2's "DISPLAY 2" governs money and percentages, and a meter
reading is neither**; **hard rule 3 is already satisfied** — the unit is on screen beside
the number, or its absence is stated (`unit not on file`, measured, with
`metering.reads.unitUnknownWhy` on hover). **No signed rule anywhere states a reading's
display precision**, so choosing one is not ours to make: it changes what a clerk reads at
the one moment before a reading becomes a billing input, and B4/B5 are ❄️ FROZEN.

### On screen, not drawn

* `Download the 1 rows that will not post` and its 36-word explanation
  (*"It comes back on the standard template's columns — …"*). The drawing offers the rejects
  file at stage 5 only. Note the plural again.

### Could not see

* **The `Meter factor — cannot run` row** — the drawing's best detail, a rule declaring it
  did not fire and why (*"No signed threshold exists for this rule, so it reports instead of
  firing."*). The seeded batch produced one rule (`Unknown meter`, Error), so no
  could-not-run outcome appeared. `metering.read.unevaluatedTitle` = *"Rules that could not
  run"* exists, on the **detail** screen. **Not proved either way on stage 3.**
* **The `Registers expected` shortfall table** — `Plan | Meters | Expects | Arrived | Short |
  Decision` with `Estimate all` and `Send someone out`. The component exists
  (`RegisterCompleteness`, `readsImportRail.tsx:332`) and the two actions are described
  there as ordinary dispositions. It did not render on the seeded batch. **Not proved.**

---

## 5 · ENTRY 10 · Upload reads · stage 4 · Load · p29–33

Chips: `EXISTS BEHIND` · `NEW READ` · `NEW BUILD` · `BLOCKED` ·
`MR-09 · MR-17 · MR-20 · MR-31 · MR-49`. Caption: **REDESIGN · NEVER BUILT.** The only stage
that writes.

**Matches — do not rebuild these.** Measured:

* the stage heading **`Certify it. Then post.`** — byte for byte, because `WORKFLOW_KINDS.reads`
  already overrides it per kind (`kinds.ts:574`)
* the Evidence rows and their labels, in the drawn order: `Batch` · `Source` ·
  `File hash (SHA-256)` · `Uploaded by` · `Uploaded at` · `Session · IP`
* the certification's own words: **`I certify these readings are accurate to the best of my
  knowledge`** — byte for byte
* `Co-sign this batch`
* coverage's first line: **`3 of 5 meters covered. 2 meters still unread.`** — byte for byte
* the refusal's words: **`Tick the certification before posting the batch.`**

### Build

| # | The drawing says | The screen says |
|---|---|---|
| **B10-1** | seven numbered group labels — `1 EVIDENCE`, `3 COMPOSITION`, `4 COVERAGE`, `6 CO-SIGN`, `7 CERTIFY` | one `<h3>`, `Compliance and posting.`, and then a bare `<dl>` and loose blocks. No group labels |
| **B10-2** | `Session · IP` reads **`Not captured`** in the refusal colour, never blank | **`— · —`** (measured). The redesign's reason: *"An em dash reads as nothing to say; the audit row's whole job is to say whether there is"* |
| **B10-3** | composition is **four tiles** — `Will post` · `Held back` · `No decision` (red) · `Rejected` — labels **cut to two words** | **seven rows** under the caption `What this batch will do`: `Rows that will post` · `Rows held back` · `Error rows with no decision` · `Rows marked for estimation` · `Rows rejected` · `Rows sent for a site visit` · `Rows skipped this cycle`. **All seven exceed B14 rule 33's 3-word label cap**, one of them at six |
| **B10-4** | `Held rows come back as a file.` (7) + `A warning still posts.` (4) | the 32-word original: `A row that cannot be filed is held back with its reason and comes back as a file you can correct and upload again. A reading with a warning on it is still filed.` (`…post.compositionNote`) |
| **B10-5** | no stage sub-line | `The batch is stamped with everything below. A row that cannot be filed is held back with its reason; the rest post.` (19 words). The redesign REMOVES it — the group heading `Evidence` is the label |
| **B10-6** | `Optional. It does not hold the post.` (7) | `Optional. A co-sign records a second review; it does not hold the post.` (13) |
| **B10-7** | a **NEW READ**: `Short registers · tou_mid on MTR-0471 · demand on MTR-0488`, off the `plan_registers` outcome the batch already stores | absent. *"A TOU meter short of one window is invisible today until stage 3 is re-read"* |
| **B10-8** | coverage closes on `Unread meters join the chase list.` | the screen adds `You can post anyway.` first |
| **B10-9** | a **NEW READ** under the tick: **`This creates 1 reading.`** (4) + **`A posted reading cannot be un-created.`** (6) — exactly B14 rules 11 and 33's consequence-before-an-irreversible-act | absent. There is no consequence sentence on this screen at all |
| **B10-10** | the commit is **`Post readings`** — two words, no count — and the count is a separate fact on the line beside it (`1 reading will post`) | `Commit {{count}} rows ✓` — measured `Commit 0 rows ✓`. The redesign's reason: *"A label is ≤ 3 words and carries no sentence; the count was what broke the grammar"* |
| **B10-11** | the commit is **disabled until the tick**, with its reason underneath and its consequence above — *"so the refusal arrives **before** the click rather than after it"* | **enabled with the tick empty.** Measured at 1280 and 1440: the click is accepted, nothing posts, and an `[role="alert"]` appears saying `Tick the certification before posting the batch.` |
| **B10-12** | `Discard this batch` inside the footer | outside it — same as **B09-6** |

### Defect

**`D10-1` · B14 rule 6 — the commit renders in the DANGER tier, and posting readings is
additive.**

Measured in Chromium at 1280 **and** 1440, on the footer's primary at stage 4:

```
data-variant = "danger"
background-color = rgba(0, 0, 0, 0)      ← transparent
border-color     = rgb(224, 52, 26)      ← accent outline
color            = rgb(168, 22, 0)
```

That is B14 rule 6's danger tier — *"outlined accent, filled on hover"* — and rule 6,
RATIFIED, reserves it for **destructive** commits: *"disconnect, retire, reverse,
write-off"*. Posting a read batch **creates rows and destroys nothing**; the product itself
says so twice on the same screen (*"A posted reading is superseded, never un-created"*,
`workflow.reads.rollback`). The source is `WorkflowRunner.tsx:211` —
`variant={current.writes ? "danger" : "primary"}` — which keys the tier off *does this stage
write* rather than off *is this destructive*, **so all seven import targets' commits are
danger.** The blueprint records the opposite (*"Not the danger tier, and that is right"*);
that sentence is wrong at `2.261.3`.

⚠ **The blast radius is why this is filed and not fixed here.** Rule 6 is one of the very few
B14 rules **ENFORCED on rendered output** — `WizardFrame` / `WorkflowRunner` / `ConfirmDialog`
suites read the button's own `class` in both directions — so moving it will turn those
suites red by design, and it moves premises, units, three assets targets and accounts with
it. It is one line and six suites.

**`D10-2` · the commit offers to commit nothing.** Measured: with one unknown-meter error
row, the button reads **`Commit 0 rows ✓`** and is **enabled**. The consequence preview
directly above it says `Rows that will post: 0`. B14 rule 11 asks for a consequence preview
before a money/state write; the preview is correct and the control ignores it.

**`D10-3` · `Commit {{count}} rows ✓` has no plural form.** Same family as **D09-1**, on a
commit button. At one row it reads `Commit 1 rows ✓` — which is the exact string the
blueprint quotes from its own walk.

### On screen, not drawn

* **`Change it`** — a button beside the stated write mode that jumps back to stage 1
  (`DEF-770`'s fix, `workflow.writeMode.change`). The drawing does not show it. It is
  `WriteModeStated` doing the right thing; recorded so nobody removes it to match the
  drawing.

---

## 6 · ENTRY 11 · Upload reads · stage 5 · Result · p33–34

Chips: `EXISTS BEHIND` · `NEW BUILD` · `MR-41`. Caption: **AS-BUILT, FROM CODE — composed
from the source, not walked.** The blueprint says plainly that this is the one drawing in
the whole document that is a picture of the source rather than of the product.

**It is still unwalked, and by me too — but not for the document's reason.** See §9. The
comparison below is therefore **code against drawing**, and that limit is on the finding,
not hidden under it.

### Build

| # | The drawing says | `ResultPanel` (`UploadReadsWizard.tsx:2249`) does |
|---|---|---|
| **B11-1** | stage heading **`Posted`** | the stage head renders `workflow.result.title` = `Loaded. Here's the receipt.` and the panel adds its own `<h3>` `The batch is posted.` — two sentences where the drawing has one word |
| **B11-2** | **`COMPOSITION`**, four tiles: `Posted` (green) · `Superseded` · `Held back` · `Refused` | a three-row `<dl class="met-facts">` — created · failed · batch — with `SupersededSummary` and `RefusedBilledRows` rendered as separate blocks further down. There is no four-tile strip |
| **B11-3** | three group labels: `COMPOSITION` · `HELD BACK` · `BATCH` | none |
| **B11-4** | `1 row could not be filed.` + `↓ Download the rejects file` + `Correct it and upload again.` | `RejectsDownload`, rendered only when `failed > 0`, with a longer sentence |
| **B11-5** | the `BATCH` block's fourth row: **`Rollback` → `Not available`**, and under it `A posted reading is superseded, never un-created.` | **nothing.** See **D11-1** |
| **B11-6** | a footer: `↓ Rejects file` on the left, **`Back to Reads`** on the right | `WORKFLOW_STAGES[4].advanceKey === null`, so `WorkflowRunner` draws **no footer at all** on stage 5 (`:201`). The panel's own last control reads `See the readings` (`metering.upload.result.viewReads`) |

### Defect

**`D11-1` · the reads rollback sentence is written, translated, and rendered nowhere —
hard-won law 2.**

`WORKFLOW_KINDS.reads.rollbackBody` (`kinds.ts:591`) is 45 words written deliberately for
`DEF-623`, in all eleven catalogues:

> *"A posted read batch cannot be rolled back. Every reading it committed is permanent, and a
> wrong one is corrected by uploading the right one — which supersedes it and keeps both on
> the record. Cancel before you post to discard the batch instead."*

The component that renders it is `components/workflow/RollbackNotice.tsx`. **Its only mount
in `src/` is `ImportWorkflowPage.tsx:2987`** — the accounts/ETL runner — plus
`workflowStages.test.tsx`. `UploadReadsWizard.tsx` never imports it. So a kind field exists,
is required by the type, carries carefully-argued copy in eleven languages, and **no clerk on
this target will ever read it.** Every check passes: `tsc` is happy because the field is
supplied, the catalogues are complete, and `CR054KindCopy.test.tsx` asserts the string
exists. The drawing draws exactly the missing fact.

### Could not see

**The receipt itself.** §9.

---

## 7 · ENTRY 12 · Add a single reading · p34–37 · a dialog on entry 02

Chips: `EXISTS BEHIND` · `NEW BUILD` · `MR-25 · MR-31`. Caption: **REDESIGN · NEVER BUILT,
with MR-25 drawn in.**

**Matches — do not rebuild these.** Measured at 1280 and 1440, dialog 560px wide, top
inset 32px, no horizontal scroll:

* the door — `+ Add reading` in the Reads page head, **unconditionally enabled**, as the
  document says
* kicker **`One meter, one date, one value`** and title **`Add a single reading`**, byte for
  byte
* `Meter number *` and its help `Type the number on the meter, then check it.`
* the value fields **stay hidden until a meter resolves** — the `simple` gate working
* the out-of-window warning fires and does not disable the commit
  (`This date is outside the cycle's reading window.`) — `BR-MET-140`, `OQ-422` closed
  *"(b) Accept and warn"*
* `Cancel` on the left of the commit

### Build

| # | The drawing says | The screen says |
|---|---|---|
| **B12-1** | context reads **`MTR-0451 · 1408 Elm · 4B · Total register · ×1`** | **`M-7210 · readings in kWh`** (measured). The address, the unit label, the register name and the multiplier are all absent — and **the address is not in the payload at all**: `quick_read.quick_entry_context` (`quick_read.py:306`) serves `meter{id, asset_no, unit, multiplier, service}`, `registers`, `cycle`, `pipeline` and nothing else. The multiplier IS served and not shown; the address is neither. Under hard rule 8 the address is derived by walking to the premises. **Backend + frontend** |
| **B12-2** | `Cycle CY-002 · **period August 2026**` | `Cycle CY-004 · period **2026-09-01**` — a raw ISO date in clerk copy (`metering.quickRead.cycleLine`), on a screen whose sibling list formats dates `08/01/2026` |
| **B12-3** | on a multi-register meter, labelled number boxes per register under `ON A MULTI-REGISTER METER`, closing on `Its plan expects four. All four post together.` | **no value fields at all**: `This meter has 2 registers.` + `Use Upload reads to enter all of them.` (measured on `M-7210`). This is **`MR-25`** — *"let the modal grow the rows it already knows about … It has already fetched `channels` — the exact list, by name"* — and the hand-off stays only for `channel_count === null` |
| **B12-4** | the register named as a **word** | the modal's own exception line says *"no signed vocabulary maps a channel to a display word"*. **It does.** `metering.reads.channel.tou_on` = `On-peak`, `tou_mid` = `Mid-peak`, `tou_off` = `Off-peak`, `total` = `Total register`, plus `demand`, `export`, `generation` — all eleven catalogues, and the reads list already uses them |
| **B12-5** | `Reading · kWh *` | `Reading (kWh) *` (`metering.quickRead.valueLabel`). Same fact; the drawing uses the product's house `·` |
| **B12-6** | **`Post reading ✓`** | **`Post reading`** — measured, `data-variant="primary"`, no `✓`. **B14 rule 4, RATIFIED: `Verb ✓` commits/writes.** This dialog writes through three endpoints |
| **B12-7** | the commit is drawn **disabled** until the form is fillable | enabled from the first render with only an empty meter box on screen (measured `disabled: false`) |
| **B12-8** | `Note` | `Note (optional)` — B14 rule 10 puts the marker on required fields; this is the inverse convention on the one optional field |
| **B12-9** | the redesign proposes `Upload reads takes all three.` (5) | `Use Upload reads to enter all of them.` — 7 words against B14 rule 33's 6 |

### On screen, not drawn

* **A `Check meter` button.** The drawing shows no lookup control and the blueprint's own
  prose says the context is fetched *"on blur"*. Neither is what the product does:
  `TextField` carries no `onBlur` — the file says so at `QuickReadModal.tsx:312` — and the
  lookup is an explicit `Check meter` button at `:317`. **Recorded, not routed**: the
  drawing is silent on how the lookup fires, so there is nothing to diverge from, and the
  blueprint's *"on blur"* sentence is simply stale.

---

## 8 · ENTRY 13 · Accept flags in bulk · p37–39 · a bar and a dialog on entry 02

Chips: `EXISTS BEHIND` · `BLOCKED` · `MR-10`. Caption: **AS-BUILT · measured in Chromium on
2026-09-12 at `3706b459`.**

**This is the one entry in the section that matches its drawing.** Walked at 1280 and 1440
from `/:tenant/reads?tab=all`, 24 selectable rows in the seed:

| Drawn | Measured | |
|---|---|---|
| the bar renders **nothing** until a row is ticked | `"NO BAR"` before, bar after | ✓ |
| `6 selected` · `Accept flags` · `Clear selection` | `1 selected` · `Accept flags` (secondary) · `Clear selection` (ghost) | ✓ |
| `Accept only — a correction is done one reading at a time.` | byte for byte | ✓ |
| dialog kicker `ONE REASON, RECORDED ON EVERY ROW` | `One reason, recorded on every row` | ✓ |
| dialog title `Accept flags on 6 readings` | `Accept flags on {{count}} readings` | ✓ |
| `Reason *` + `Say what you checked. It is stored on each reading.` | byte for byte | ✓ |
| `These readings are already posted. This records your review of their flags.` | byte for byte | ✓ |
| `Your name is recorded against every reading this touches.` | byte for byte | ✓ |
| footer `Cancel` · `Accept 6 readings` | `Cancel` (ghost) · `Accept {{count}} readings` (primary) | ✓ |

**Zero build items.** The drawing is the product.

### Defect

**`D13-1` · `Accept {{count}} readings` has no plural form.** Measured with one row
selected: the dialog title reads `Accept flags on 1 readings` and its commit reads
`Accept 1 readings`. Two strings, eleven catalogues, same family as **D09-1** and **D10-3**.
The drawing cannot show it because it is drawn at six.

### Could not see

* **A row that cannot be selected.** The drawing's caption is emphatic — *"A row that cannot
  be accepted keeps its checkbox and has it **disabled with the reason on hover**, so a
  clerk learns why rather than wondering where the control went"* — and the three reasons
  exist in the catalogue (`notSelectable.derived` / `.notFlagged` / `.unavailable`). **All
  six checkboxes I sampled were enabled**, so the disabled state was never rendered. The
  `bulkSelectable(row)` predicate is exported and unit-tested; the RENDERED refusal is not
  proved.
* **A selection larger than 500.** `POST /reads/bulk-fix` caps at 500 server-side and
  `metering.reads.bulk.too_many` exists. The seed holds 24 rows. Not proved.

### One thing for whoever owns the register

The bar's own trace names **`DEF-046` finding 2** — *"fix_disposition/fix_reason/fixed_by
exist with no writer and no route"*, open since 2026-08-11. Those three columns **do** have
a writer today: `POST /reads/bulk-fix` (`api.py:2112`) → `services._stamp_fix` (`services.py:9698`). Whether that
closes the finding is a register question, not mine; flagged so it is not left stale by
default.

---

## 9 · WHAT I COULD NOT SEE, AND WHY

**A stage I could not reach is not a stage that passed.** Five items, each with its reason.

1. **Stage 5 · the receipt.** Reached in the rail and named; **never rendered.** The
   document's reason — *"the tick could not be driven from the script"* — is **stale**: the
   tick works (click the wrapping `<label>`; measured `checked === true` at both widths).
   What refused me is the **idempotency guard**, working correctly: after my earlier walks
   had posted the same paste under the same batch tags, the screen answered

   > *"This exact file and batch tags have already been posted. Open the original batch
   > instead."*

   — `_idempotency_block(batch)` (`services.py:6908`, called at `:7519` — guard 2), which is `BR-MET-018` / `OQ-044`
   doing its job. Entry 11's whole comparison in §6 is therefore **code against drawing**,
   and `Screen health: UNGRADED — not walked` still stands. **The fix is the one the
   document already names**: a test that can tick the certification and post a batch whose
   file hash and tags are new, after which this becomes a walked drawing like the rest.

2. **The `Meter factor — cannot run` rules row** (entry 09). The seeded batch produced one
   rule outcome. Not proved either way.

3. **The `Registers expected` plan-shortfall table and its two actions** (entry 09). The
   component exists; it did not render on the seeded batch. Not proved.

4. **A bulk row that cannot be selected** (entry 13). All sampled checkboxes were enabled.

5. **A bulk selection over the server's 500 cap** (entry 13). The seed holds 24 reads.

**What I did NOT fail to see:** the manual-entry branch of stage 2 was read in code but not
driven in the browser — I drove the CSV branch. The two hand-rolled cells (**B08-6**) are a
source reading with line numbers, not a rendered one.

---

## 10 · ROUTING

**Nothing below is filed. This is what should be filed, and by whom.**

### To the PO — two, and only two

Both are B14 rule 41's single exception: *"the only exception to that is if you find that
Blueprint is contradicting to the rules that we have defined."*

* **`Q-RAIL-1`** · the completed-step glyph — the drawing draws a **✓**, B14 rule 3 says a
  **numbered** rail. Seven wizards move either way. §1 quotes both sides.
* **`Q09-1`** · a meter reading's display precision — the drawing prints `45910`, the product
  prints `45910.000000`, and **no signed rule states one.** It is a figure on a metering
  surface, so it is put rather than chosen. §4 quotes both sides.

### Defects — 15, none of which needs the PO

| id | one line | where |
|---|---|---|
| `D-RAIL-1` | `workflow.promise` hardcodes *"Five stages … stage four"* under a rail that derives everything else — B14 rule 3, eleven catalogues | `StageBar.tsx:47` |
| `D07-2` | B14 rule 8 broken on three stage-1 pickers (7 / 7 / 9 options); the kit's `LONG_LIST_THRESHOLD = 10` contradicts the rule's "5+" | `UploadReadsWizard.tsx` · `FormModal.tsx:690` |
| `D07-3` | `UPLOAD_STEP_IDS` names steps that no longer exist; nothing reads it; its own test pins the stale list | `:221` · `UploadReadsPage.test.tsx:258` |
| `D08-1` | `row(s)` in clerk copy | `metering.upload.file.staged` |
| `D08-2` | **NFR-3** — `GET /read-batches/{id}` serves every row, no window, cap 50,000; **16,034 B measured for 40 rows** ≈ 20 MB at the cap. `DEF-766`'s window is on `/imports/{id}`, not here | `api.py:1236` · `selectors.py:5767` |
| `D08-3` | the register list is a literal array in the front end | `endpoints.ts:12189` |
| `D09-1` | three split strings with no plural form — *"1 rows will post"*, *"1 of them carry"* | `metering.upload.split.*` |
| `D09-2` | `Register` on stage 2 and `Channel` on stage 3, same column, one wizard | two catalogue keys |
| `D09-3` | the segment filter is client-side over the whole unbounded batch | `ReviewStep` |
| `D10-1` | **B14 rule 6** — the reads commit renders in the **danger** tier and posting is additive; measured; one line, seven targets, six rendered-output suites | `WorkflowRunner.tsx:211` |
| `D10-2` | the commit reads `Commit 0 rows ✓` and is enabled | `UploadReadsWizard.tsx:3141` |
| `D10-3` | `Commit {{count}} rows ✓` has no plural form | `…post.commitRows` |
| `D11-1` | the reads rollback sentence exists in eleven catalogues and **no screen on this target renders it** — hard-won law 2 | `kinds.ts:591` · `RollbackNotice.tsx` |
| `D13-1` | `Accept {{count}} readings` and `Accept flags on {{count}} readings` have no plural form | `metering.reads.bulk.*` |
| — | *(the blueprint's own entry-10 sentence, "Not the danger tier", is wrong at `2.261.3`)* | this file, §0 |

⚠ **Three of these fifteen are the SAME fault** — `D08-1`, `D09-1`, `D10-3`, `D13-1` are
six catalogue keys' worth of missing i18next plurals across four screens. **File them as one**, with
all six keys named, rather than as four rows that four lanes fix four ways.

### Build — 54, and they group into five waves, not fifty-four tickets

1. **The five stage headings and the page title** (`B07-1`, `B07-2`, `B08-1`, `B09-1`,
   `B11-1`). The mechanism already exists and reads already uses it twice
   (`loadTitle`, `transformBlurb`): add per-kind title overrides and give reads
   `Upload reads` · `The source` · `Columns` · `The rules` · `Posted`. **One change, five
   strings, no other target touched.**
2. **The copy budget** (`B07-3`, `B07-5`–`B07-12`, `B08-2`, `B08-4`, `B08-5`, `B08-8`,
   `B09-2`, `B09-3`, `B09-4`, `B10-3`–`B10-6`, `B10-8`, `B12-9`). Twenty-two strings, every
   one of them the drawing's shorter version, most of them B14 rule 33 as well. Eleven
   catalogues each — this is the biggest single piece of work in the section and it is
   entirely copy.
3. **Stage 4's shape** (`B10-1`, `B10-2`, `B10-7`, `B10-9`, `B10-10`, `B10-11`): group
   labels, `Not captured`, short registers by name, the consequence sentence, `Post
   readings`, and the commit disabled-with-its-reason. This is the wave that changes what a
   clerk can get wrong.
4. **The quick-read dialog** (`B12-1`–`B12-8`), whose centre is **`MR-25`** — let the modal
   grow the register rows it has already fetched — plus the address the payload does not yet
   carry (`B12-1`, backend).
5. **Stage 5** (`B11-2`–`B11-6`) and the footer placement shared with `B09-6` / `B10-12`.
   **Do not start this wave until stage 5 has been rendered once** (§9).

### Recorded divergence — B14 rule 38, nothing is built

* **`X07-1`** · the drawing's two-column field grid on stage 1. The drawing loses; the order
  and the six controls it specifies are already right.

---

## 11 · WHAT THIS FILE IS NOT

It is not a specification, not a change request, and not permission to build. It allocates
no id, edits no `.tsx` and files no register row — **the ids above are labels local to this
document** so the report and the follow-up can name the same thing.

Every figure in it is a reading: rendered from the PDF as an image, read out of a named file
at a named line, or measured in Chromium at 1280 and 1440 on 2026-09-13 against
`2.261.3` / `c56e69b4`. Where something could not be measured, §9 says so and says why, and
it is counted as unproved rather than as a pass.
