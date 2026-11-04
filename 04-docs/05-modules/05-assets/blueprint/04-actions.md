# Section 05 · Actions — moving it, fixing it, retiring it (screens 22–27)

**What this file is.** A measurement, not a plan. It puts the blueprint's six action
screens beside the code that runs today and says, for each difference, which side is
right and what class of work it is. **It builds nothing and changes no product code.**

**Scope.** Blueprint pages **85–107**, screens **22 Reassign · 23 Log repair /
maintenance · 24 Retire 1 · 25 Retire 2 · 26 Retire 3 · 27 Raise work order**, and
figures **30–42**.

---

## 0 · HOW THIS WAS READ, AND THE TWO FILES IT WAS *NOT* READ FROM

Every layout fact below — field order, two-to-a-row versus full width, helper position
and wording, the step strip, the consequence boxes, footer button order and labels —
comes from the **rendered PDF page image**, opened and looked at, per B14 rule 42
(PO 2026-09-13: *"When you use images to create screens your accuracy is higher; hence
dont create screens using only Text"*). Pages 85–108 and 209–210 were rendered with
`10-scripts/pdf/pdf_render.py` at scale 2, and eight dense regions were re-rendered at
scale 4 to settle a footer, a header block and an annotation chip.

**Neither `wireframes/CR-092-assets-screens.html` nor `08-screen-layouts.md` was used as
a specification, and nothing was corrected out of either** — no layout detail was ever
taken from them, so there is nothing to restate. `08-screen-layouts.md` was opened once,
for build history only, and that single read immediately paid for the rule:

> ⚠ **DRIFT, MEASURED.** `08-screen-layouts.md` line 97 lists screen 27's commitments as
> `AST-B-02, AST-B-05, AST-B-10, AST-B-14, AST-B-26, AST-B-27`. **The PDF page image
> (p104) draws four chips: `COMMITMENT 02 · 05 · 10 · 26`.** The derived index carries
> two commitments the drawing does not. Screens 22–26 agree on both sides; screen 27
> does not. Hard-won law 5, on a document.

The extracted text layer was used only to find a page and to check a spelling.

### And the map's own figure numbers are wrong for this section

`blueprint/00-index.md` says screen 22 is *"Fig 29–31"* and that *"screens 22–27 each
carry a REDRAWN figure beside the as-built one (figs 30, 32, 34, 36, 38, 40, 42)"*.
**Read off the page images, both halves are wrong:**

| what the page actually says | where |
|---|---|
| `FIGURE 30 · DESKTOP · 1440` over the **as-built** Reassign (title *Reassign E-5000*, helpers above inputs, footer `Cancel · Reassign ✓`, stamped `v2.234.17`) | p87 |
| `FIGURE 31 · FIGURE 32 · 1 REDRAWN…` over the **redrawn** Reassign, panel 1 of 2 | p88 |
| panel **2** of that pair — a whole new **confirm step** | p89 |

So section 05 holds **thirteen figures, 30–42**: as-built **30, 33, 35, 37, 39, 41** and
redrawn **31+32, 34, 36, 38, 40, 42**. Screen 22 is the only screen in the section whose
remedy is **two panels**, and the index's list omits 31 entirely while naming 30 as a
remedy. Figure 29 is not in this page range at all.

---

## 1 · THE SECTION HEAD (p85), AND WHAT OF IT IS ALREADY FIXED

The section's own opening claim is that **the data capture is not the problem**: *"Four
assumptions were made about missing fields while auditing them and **three were wrong**
— reassign offers Inventory (unassign) and a work-order checkbox, log repair captures
cost, and retire takes every key its service accepts. What they break is **layout,
escape and consequence**."* That holds against today's code, field for field.

p85 then names **three faults every screen in the section shares**. Two of the three are
already gone:

| p85's shared fault | today | verdict |
|---|---|---|
| **R12** — *"ten of eighteen fields render label → helper → input; label-to-input measures 29px or 47px instead of 5"* | `FormModal.tsx` renders the helper **after** the control in all five help-bearing variants — `:300`, `:386`, `:428`, `:785`, `:1017`, each `<p className="field-help mt-1.5 mb-0">` | **FIXED** (B14 rule 39's 2026-09-12 amendment; measured 5 / 6 / 20 px on 29 fields across five asset screens) |
| **B14 rule 7** — *"five date inputs, **zero** Today shortcuts and **zero** with `min` or `max`"* | **three of five now bounded**: reassign `effective_date` `min=` the current assignment's start (`AssetFlowPages.tsx:415`), log repair `date` `max=` today (`:726`), retire `retire_date` `min=` install date (`AssetRetireWizard.tsx:304`). Both `final_read_date` fields deliberately unbounded, with the reason in the code | **HALF FIXED** — the **Today shortcut does not exist anywhere in the product**; `DatePickerField` renders a bare `<input type="date">` with `min`/`max` and a prefill and no shortcut control |
| **The header** — *"not one of the six carries screen 08's five-slot header or its attention strip, so a person acting on an asset whose test is overdue sees no sign of it while they act"* | `AssetFlowShell` (`AssetFlowPages.tsx:197`) passes `backTo`, `kicker`, `title` and **nothing else**; `RaiseWorkOrderPage.tsx:159` the same | **STILL TRUE ON ALL SIX** |

That last one is the section's single largest gap and it repeats six times. It is
sized once, in §8.

---

## 2 · SCREEN 22 · REASSIGN

`/:tenant/assets/{assetId}/reassign` · `?unit={id}` preselects · **EXISTS BEHIND ·
COMMITMENT 26** · figures **30** (as-built), **31 + 32** (redrawn)

### What the as-built drawing shows (fig 30, p87)

`← Asset` · kicker `ASSIGNMENT` · title **`Reassign E-5000`** · then, full width down one
column: `Where is it going?` over a two-segment control **`To a unit` | `Back to
inventory`** · `Unit *` over `Search units…` with no helper · `Effective date`, helper
**above** the input (*"The date the move takes effect."*), date input · checkbox `Record
the final read` · then **two fields side by side** — `Final register reading (kgal)` with
a **two-line helper above** and `Read date` with a one-line helper above · checkbox
`Move the 2 sub-meters under this master as well` · checkbox `Raise a field work order
for the physical move` · footer, right-aligned: **`Cancel` · `Reassign ✓`**.

### What the REDRAWN drawing changes (figs 31 + 32, p88–89)

The caption is the carry-over rule in its inline form: *"REDRAWN. THE FIVE-SLOT HEADER
FROM SCREEN 08 WITH ITS ATTENTION STRIP, R12'S FIELD ORDER, AND DATES WITH A TODAY
SHORTCUT AND BOUNDS. **EVERYTHING MARKED NEW IS A CHANGE; EVERYTHING ELSE IS THE
AS-BUILT.**"*

**Panel 1 (fig 31)** keeps every field, in order, and adds:

1. the **five-slot header** — kicker `METER · AMI · REASSIGN`, title **`W-5001`** (the
   asset number, not a sentence), a green `Installed` chip, the **attention strip**
   `⚠ Annual test overdue 11 days · due 06/15/2026` carrying `Raise work order →`, and a
   context line `118 Bayou Bend Dr · Unit 1 · ACC-20194 Ruth Alvarez · Water · Installed
   Jan 2026`;
2. a `…` **overflow button**, top right;
3. every helper **below** its input;
4. a **new** helper on `Unit`: *"Only units without a live meter."*;
5. shortened helpers — effective date *"Not before the install date."*, final read
   *"Taken before the move. Both commit together."*, read date *"The effective date when
   left blank."*;
6. the footer becomes **`Cancel` · `Continue`**, `Continue` marked **NEW**.

**Panel 2 (fig 32) is a whole new CONFIRM STEP**, and its caption says exactly why:
*"NEW. EVERY SENTENCE HERE ALREADY EXISTS IN THE CATALOGUE AND RENDERS **BESIDE THE
FORM** TODAY, WHERE A PERSON READS IT BEFORE THEY HAVE DECIDED ANYTHING. THIS SHOWS IT
AFTER THEY HAVE, AND BEFORE IT COMMITS."* It holds: the same header with kicker
`METER · AMI · REASSIGN · CONFIRM` and **no attention strip** · one sentence,
*"W-5001 leaves Unit 1 on 09/11/2026 and joins Unit 3."* · an accent-ruled consequence
box titled **`Three things commit as one transaction.`** whose body ends *"If the read
cannot be taken, the asset does not move."* · three fact rows **`What moves` / `What
stays` / `Also raised`** · footer **`← Back` · `Reassign ✓`**.

### What the code does today

One page, one step, no confirm. `AssetReassignPage` → `AssetFlowShell` →
`ReassignForm`, all in `07-frontend/src/features/assets/AssetFlowPages.tsx`
(`:218`, `:137`, `:232`). Route mounted at `App.tsx:1080`.

* Header: `PageHeader` with `backTo` / `kicker` / `title` only (`:197`–`:203`). Kicker
  `Assignment`; title `Reassign {asset}`.
* Segmented control `:380`, labelled **`Move to`**, options **`A unit`** and
  **`Inventory (unassign)`**.
* `Unit` picker `:392`, helper **only on failure** (`unitsQuery.isError`).
* `Effective date` `:405`, `min` = the current assignment's `from_date`, helper composed
  from two catalogue sentences.
* `Record the final read before moving` checkbox `:434`, default **on**.
* Final read value + `Read date` **side by side** in `grid grid-cols-2` at `:440`. ✔
* `Move its sub-meters too` `:485`; `Raise a field work order for the physical move`
  `:498`.
* **The two consequence sentences render as two 11 px grey captions** — `<Note>` at
  `:504` and `:505`. `Note` is `text-xs` at 60 % ink (`TextBits.tsx:76`): a caption, not
  a consequence box.
* Footer `:507`–`:513`: `Cancel` (ghost) then `Reassign ✓` (`WorkingButton`, **primary
  tier**).

### Carry-over arithmetic

**Reconciles.** Eleven element groups on the as-built; eleven on redrawn panel 1, plus
six additions, plus a new panel 2. **Nothing is dropped.** ✔

### Gaps

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| five-slot header | kicker · asset-no title · status chip · attention strip · context line · `…` | `backTo` + kicker + title, nothing else | **MISSING PLUMBING** + LAYOUT | no |
| confirm step | a second panel before the commit | commits from the form | LAYOUT + WIRING | no |
| consequence box | accent box titled *Three things commit as one transaction.* | two 11 px grey `<Note>` captions beside the form | LAYOUT (**B14 rule 11**) | no |
| segmented label | `Where is it going?` | `Move to` | CONTENT | no |
| segment options | `To a unit` · `Back to inventory` | `A unit` · `Inventory (unassign)` | CONTENT | no |
| checkbox labels | `Record the final read` · `Move the 2 sub-meters under this master as well` | `Record the final read before moving` · `Move its sub-meters too` | CONTENT | no |
| unit helper | *Only units without a live meter.* | none in the happy path | CONTENT + **MISSING PLUMBING** (see below) | no |
| helper position | label → input → helper | label → input → helper | — | **FIXED** |
| `min` on effective date | bounded | `min` = assignment start | — | **FIXED** |
| Today shortcut | present | absent | MISSING PLUMBING (kit-wide) | no |
| footer order | `Cancel` left, commit right | same | — | already right |

> ⚠ **THE NEW UNIT HELPER IS NOT DELIVERABLE AS DRAWN, AND SAYING IT WOULD BE A LIE.**
> `unitPickerOptions` (`AssetLifecycleModals.tsx:145`) maps **every** row the server
> returns and filters nothing, and `GET /units` has no such filter to ask for:
> `UNIT_FILTERS = ("occupancy", "premises_id", "service", "sub_metered", "plan")`
> (`06-backend/apps/metering/api.py:158`). Adding the sentence without a filter is
> hard-won law 1 — a comment claiming a guarantee. **Backend work, and it is a
> metering-module change, not an assets one.**

> ⓘ **ONE THING TO PUT TO THE PO RATHER THAN DECIDE.** Both figures draw `Reassign ✓` in
> the **danger tier** (red outline). B14 rule 6 names four destructive commits —
> disconnect, **retire**, reverse, write-off — and a reassign is not one of them. The
> code uses the primary tier. Rule 41's one legitimate question is a drawing that
> disagrees with a signed rule; this is one.

> ⓘ **`Where is it going?` is a four-word question.** B14 rule 33 caps a LABEL at three
> words and says *no sentence*. Same shape: `Move the 2 sub-meters under this master as
> well` is nine words and embeds a figure (rule 37 — the `2` is an illustration, so any
> build must interpolate a count). Both are rule-41 questions, not lane decisions.

---

## 3 · SCREEN 23 · LOG REPAIR / MAINTENANCE

`/:tenant/assets/{assetId}/maintenance/new` — titled *Log test* on a device with a
cadence · **EXISTS BEHIND · NEW BUILD · COMMITMENT 04 · 13 · 26** · figures **33**
(as-built), **34** (redrawn)

### p92's headline, and the correction it already carries

The page's own callout is titled **"The worst single defect in the module, and the data
capture is not it."** It then corrects itself in the open: *"⚠ This document nearly filed
**'repair cost is never captured'** as a finding — it is captured, and the first read of
the component missed it."* The real fault it names is `AST-B-04`:

> *"For a Billing Clerk the picker degrades to a bare text box holding a **UUID**, under
> the sentence 'Your role can't list users, so enter the technician's ID.' That breaks
> **B14 rule 31** … and `BR-AST-038` explicitly permits a Billing Clerk to log a repair,
> so the role that is allowed to use this screen is the role the screen cannot serve."*

### ⚠ AST-B-04 IS BUILT. THE DOCUMENT'S CLAIM IS STALE, AND ITS LINE CITATION IS DEAD.

p91 cites `AssetFlowPages.tsx:604-612` for the uuid text box. **There is no text box
there and there is no degrade branch anywhere in the file.** What is there today:

* the picker reads **`GET /work/crew-directory`**, not `GET /users` —
  `listCrewDirectory` at `AssetFlowPages.tsx:88` and `:625`;
* it is **one control, always** — a `SearchSelectField` at `:584`, disabled with its
  reason when the read fails, never swapped for a `TextField`;
* the option label is `name · email`, the id travels only as the `value`.

**And the half the document was right to worry about is still true and must stay true.**
`GET /users` is **still `SystemAdminOnly`** — `06-backend/apps/identity/api.py:194` — so
AST-B-04's specification was satisfied the way it asked for (*"a read a clerk is allowed
to make … It is a new endpoint, so this one is genuinely back-end work"*), by minting
`crew_directory` (`06-backend/apps/work/api.py:687`, route `:1627`,
`WorkOrdersReadAnyWriteAdminOrClerk`) rather than by widening the admin route.
**AST-B-04's own done-test — *"shows ASSIGN TECH as a searchable picker … and no UUID
appears anywhere on the screen"* — is met.**

### What the as-built drawing shows (fig 33, p91–92)

`← Asset` · kicker `LIFECYCLE` · title `Log repair / maintenance · E-5000` · row 1
**`Kind *` segmented [Repair | Inspection | Test] | `Date`** (helper above) · row 2
**`Set status`** (helper above, small select `No change ▾`) **| `Assign tech`**
(`Search users…`) · `What was done *` full width · `Estimated cost` half width with
helper above · an **accent-ruled consequence box `RECORDED, NOT POSTED`** carrying two
sentences · checkbox `Raise a work order from the repair template` · footer
**`Cancel` · `Log it ✓`**.

### What the REDRAWN drawing changes (fig 34, p92–93)

* the **five-slot header** (kicker `METER · AMI · LOG REPAIR / MAINTENANCE`, title
  `W-5001`, `Installed` chip, context line, `…`);
* `Kind *` gets **its own full-width row**;
* **the pairing changes**: row 2 is `Date | Set status`, row 3 is `Technician | Cost`;
* **`What was done *` moves down**, below both rows;
* two **relabels** — `Assign tech` → **`Technician`**, `Estimated cost` → **`Cost`**;
* `Technician` is a **select showing `Sam Reyes`**, helper *"Anyone on the crew list."*
  marked **NEW** — caption 2 states it in full: *"TECHNICIAN IS A PICKER ON EVERY ROLE"*;
* helpers move below; `Date` reads *"Not in the future."*, `Set status` reads *"Only
  legal transitions are offered."*;
* the consequence box, the checkbox and the footer are **unchanged**.

### What the code does today

`AssetLogMaintenancePage` / `MaintenanceForm`, `AssetFlowPages.tsx:531` / `:554`.
Route `App.tsx:1081`.

Order rendered: `Kind` segmented full width (`:681`) → **`Date | Technician`**
(`grid grid-cols-2` at `:691`) → `What was done` full width (`:747`) → **`Set status` |
`Estimated cost`** (`:757`) → work-order checkbox (`:793`) → `<Note>` (`:800`) → footer
`Cancel` · `Save entry` (`:802`–`:808`).

### Carry-over arithmetic

**Reconciles.** Eight groups in, eight groups out plus the header; two labels shortened,
one field re-ordered, **nothing dropped**. ✔

### Gaps

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| technician picker / uuid | a picker on every role | `SearchSelectField` over `GET /work/crew-directory` | — | **FIXED** (`AST-B-04`) |
| five-slot header | present | `backTo` + kicker + title | MISSING PLUMBING + LAYOUT | no |
| row pairing | `Date \| Set status`, then `Technician \| Cost` | `Date \| Technician`, then `Set status \| Estimated cost` | **LAYOUT** | no |
| `What was done` position | after both paired rows | between them | **LAYOUT** | no |
| `Assign tech` → `Technician` | `Technician` | `Technician` | — | **FIXED** (catalogue `assets.maintenance.tech`) |
| `Estimated cost` → `Cost` | `Cost` | `Estimated cost` | CONTENT | no |
| technician helper | *Anyone on the crew list.* | none when the read succeeds | CONTENT | no |
| `Set status` helper | *Only legal transitions are offered.* | *Only the moves that are legal from where this asset is now.* (12 words) | CONTENT (**B14 rule 33**) | no |
| the `RECORDED, NOT POSTED` box | an accent-ruled box with a small-caps title, two sentences | a single 11 px grey `<Note>` at `:800` carrying **one** sentence; the second lives as the Cost field's helper | **LAYOUT** (B14 rule 11 + 36) | no |
| commit label | `Log it ✓` | `Save entry` — no verb match, **no `✓`** | CONTENT (**B14 rule 4**) | no |
| date `max` | bounded | `max` = today | — | **FIXED** |
| Today shortcut | present | absent | MISSING PLUMBING (kit-wide) | no |

> ⓘ **THE REDRAWN DRAWS COST AS `84.0000`.** Hard rule 2 is *display 2 decimals*, and the
> as-built figure draws `84.00`. Rule 37 makes the number an illustration; the **number
> of decimal places is not**. The drawing loses here and the code is right; recorded so
> nobody builds to it.

---

## 4 · SCREEN 24 · RETIRE · 1 REASON & FINAL READ

`/:tenant/assets/{assetId}/retire` step 1 · **EXISTS BEHIND · COMMITMENT 26 · 28** ·
figures **35** (as-built), **36** (redrawn)

### What the as-built drawing shows (fig 35, p95–96)

`← Asset` · kicker `LIFECYCLE` · title `Retire E-5000` · **step rail
`1 Reason & final read › 2 Replacement › 3 Book value`** · an accent-ruled notice
**`RETIRING, NOT DELETING`** with two lines, the second bold (*"This cannot be undone.
Retired is the end state — there is no un-retire."*) · row **`Reason *` (small select
`End of life ▾`) | `Retire date *`** with helper **above** (*"Cannot be before the install
date."*) · row **`Final read`** (two-line helper above) **| `Read date`** (no helper) ·
footer **`Cancel` · `Continue`**.

### What the REDRAWN drawing changes (fig 36, p96)

Five-slot header · `Reason` becomes a **full-width select with the house chevron** (the
caption adds *"and every choice list drawn as a select"*) · helpers move below and
shorten (*"Not before the install date."*, *"Optional. Without it the last cycle cannot
bill."*) · `Read date` gains a helper, **NEW** (*"The retire date when left blank."*) ·
**footer becomes `Save as draft` (NEW) · `Continue` — and `Cancel` is gone.**

### ⚠ THE CARRY-OVER ARITHMETIC DOES NOT RECONCILE HERE

`Cancel` is on the as-built figure and absent from the remedy, and **no ruling is
quoted**. p139's rule is *"a remedy never loses anything … unless somebody has ruled that
it goes and the ruling is quoted"*, and **Appendix K (p209–210) carries exactly two rows
— screen 07's dialog frame and screen 05c's Asset value panel — and then states its own
scope: *"Everything else carries over, across six remedies … 05a, 05b, 05c, 07 and R1–R6
between them touch every screen this document proposes to change."*** Section 05's six
redrawn figures are **none of those**, so the carry-over audit was never run over this
section at all. Appendix K's own standard is *"Rows with no quoted ruling: 0 — any such
row would be a defect in this document rather than a design decision."* By that
standard this is a defect in the document. §7 counts all three.

**And the as-built half is wrong too, which is the more useful half.** `CR-092` lane 4
step 2 measured this footer in Chromium at 1280 and 1440 on 2026-09-12 and got
**`["Continue"]`** — one button. So figure 35 drew a `Cancel` the product never had, and
figure 36 then removed it. *(The blueprint itself corrects this on p96, in a callout
headed "This document first recorded 'the retire wizard has no Cancel'. **That was
wrong**" — but the correction is about the escape hatch existing in the kit, not about
the figure.)*

### What the code does today

`AssetRetireWizard.tsx`, route `App.tsx:1096`. It wraps `AssetFlowShell` (`:165`), so it
inherits the three-slot header, and drives `WizardFrame`.

* notice box `:255`–`:268`: **hand-rolled**, not `ConsequenceBox` — a `<div>` with
  `border-l-[3px] border-accent-500`, a small-caps title from
  `assets.retire.noticeTitle`, and **three** paragraphs (the drawing shows two): the
  notice, the bold terminal sentence, and `assets.retire.correctionPath`.
* row `Reason | Retire date` at `:269`; `Reason` is the kit's `SelectField`, half width.
* row `Final read | Read date` at `:316`, rendered only for a measuring asset.
* `retire_date` carries `min={asset.install_date}` (`:304`) and appends
  `assets.retire.dateFloorHelp` = *"Not before the install date."* — **the drawing's own
  sentence, already built.**
* `final_read_date` has **no helper at all** and no bound, deliberately, with the reason
  written out at `:317`–`:336`.

### ⚠ AST-B-28 — THE ESCAPE HATCH — IS BUILT

`AssetRetireWizard.tsx:438`–`:449` passes `WizardExit`. `WizardFrame` renders
`[Save & exit][Park] [← Back] [Continue/commit]`, right-aligned
(`WizardFrame.tsx:316`–`:341`, `:849`–`:883`). `Park` is **disabled carrying its reason**
— *"Drafts are not kept yet."* — because `wizard_parks.flow` admits no `retire_asset` and
there is no Drafts home to list one on. Four cases in
`AssetWizardExit.dom.test.tsx` hold it, including *"the RETIRE wizard draws it too — its
footer was one button"*.

**So the drawing's `Save as draft` exists as `Save & exit`, in the drawn position.** The
label differs and the built footer carries a second control (`Park`) the drawing does not
show. Under **B14 rule 38** footer construction is the kit's, so the kit wins and the
divergence is recorded rather than built.

### Gaps

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| escape hatch | `Save as draft` beside `Continue` | `Save & exit` + a disabled `Park`, same slot | CONTENT (label only) | **FIXED** (`AST-B-28`) |
| `Cancel` on step 1 | as-built has one, remedy drops it | **never had one** | *document defect, both ways* | n/a |
| five-slot header | present | `backTo` + kicker + title | MISSING PLUMBING + LAYOUT | no |
| `Reason` width | full width | half width, paired with the date | LAYOUT | no |
| retire-date helper | *Not before the install date.* | that exact sentence, appended to *Any current assignment closes on this date.* | — | **FIXED** |
| `retire_date` `min` | bounded | `min` = install date | — | **FIXED** |
| final-read helper | *Optional. Without it the last cycle cannot bill.* (8 words) | *The read that closes the meter's billing life. Optional — but without it the last cycle cannot be billed.* (19 words) | CONTENT (**rule 33**) | no |
| `Read date` helper | *The retire date when left blank.* | none | CONTENT | no |
| notice box | two paragraphs, drawn as an accent box | **three** paragraphs, **hand-rolled** rather than `ConsequenceBox` | LAYOUT (**rule 36**) + CONTENT | no |
| Today shortcut | present | absent | MISSING PLUMBING (kit-wide) | no |

---

## 5 · SCREEN 25 · RETIRE · 2 REPLACEMENT

`/:tenant/assets/{assetId}/retire` step 2 · **EXISTS BEHIND · COMMITMENT 26 · 28** ·
figures **37** (as-built), **38** (redrawn)

### What the two drawings show (p98–100)

As-built: header · step rail with **2** active · a lede sentence *"A unit with no meter
cannot be billed. Assign the replacement now or the account goes to estimated reads."* ·
`Replaced by` over `Search inventory…` with the helper **already below**, reading *"Only
assets in inventory are offered. **A retired asset is refused.**"* · checkbox `Raise a
meter-exchange work order for the swap` · footer **`← Back` · `Continue`**.

Redrawn: the five-slot header is added, `Save as draft` joins the footer (**NEW**), and
**the helper is cut to *"Only assets in inventory are offered."***

### ⚠ SECOND CARRY-OVER MISS, AND THIS ONE COSTS A REFUSAL

*"A retired asset is refused."* is dropped with no ruling quoted. It is defensible under
`AST-B-26` (helpers to ten words or fewer) — but `AST-B-26` is a **copy** commitment, and
the half deleted is the half that states a **server refusal**. A refusal sentence
quietly disappearing is hard-won law 2's mirror clause in copy form. The screen's own
`States` row (p100) lists that refusal as live: *"The replacement is itself retired. Pick
a living asset."*

### What the code does today

`AssetRetireWizard.tsx:352`–`:390`. Lede `:357` from `assets.retire.replacementLede`,
verbatim the drawn sentence. `SearchSelectField` `:358` with
`help={t("assets.retire.replacedByHelp")}` = **"Optional. The asset number of a living
asset in this utility."** — **neither** the as-built helper nor the redrawn one.
`RaiseWorkOrderCheckbox` `:375`. An extra unmetered-warning band `:381`–`:390` renders
when a measuring, assigned asset gets no replacement — **on neither figure**, and it is
hand-rolled rather than `ConsequenceBox`.

### Carry-over arithmetic

**Does not reconcile** — one helper sentence dropped, unruled. And the as-built figure's
helper does not match the shipped string either, so both figures describe copy the
product does not have.

### Gaps

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| five-slot header | present | `backTo` + kicker + title | MISSING PLUMBING + LAYOUT | no |
| escape hatch | `Save as draft` | `Save & exit` + disabled `Park` | CONTENT (label) | **FIXED** (`AST-B-28`) |
| `Replaced by` helper | as-built 2 sentences, remedy 1 | *Optional. The asset number of a living asset in this utility.* — a third wording | CONTENT | no |
| unmetered warning | not drawn on either figure | hand-rolled warning band at `:381` | LAYOUT (**rule 36**) — and a drawing gap | no |
| step rail, lede, checkbox, `← Back`/`Continue` | as drawn | as drawn | — | already right |

---

## 6 · SCREEN 26 · RETIRE · 3 BOOK VALUE

`/:tenant/assets/{assetId}/retire` step 3 · **EXISTS BEHIND · COMMITMENT 26 · 28** ·
figures **39** (as-built), **40** (redrawn)

### What the two drawings show (p101–102)

As-built: header · step rail with **3** active · a box titled **`Book value at
retirement`** with **three** rows — `Purchase cost $182.00` · `Accumulated depreciation
$182.00` · `Book value $0.00` (bold) · `Treatment` over a **two-segment control
`Write off` | `Carry forward`** · an accent box **`RECORDED, NOT POSTED`** reading *"The
amount and your choice are recorded on the asset. Nothing is posted to the ledger."* ·
footer **`← Back` · `Retire E-5000 ✓`** in the danger tier.

Redrawn: identical, **plus the five-slot header and `Save as draft` in the footer**.
Nothing else moves. **Carry-over reconciles.** ✔

### What the code does today — and where the drawing is simply wrong

`BookValueStep`, `AssetRetireWizard.tsx:479`–`:588`.

| the drawing | the code |
|---|---|
| box titled `Book value at retirement` | titled **`Asset value`** (`assets.retire.assetValue`, `:504`) |
| **3** rows | **4**, plus a conditional fifth: `Purchase cost` · **`Age at retirement`** · `Accumulated depreciation` · **`Remaining book value`** · `Cover ends` when a warranty end exists (`:506`–`:560`) |
| `Treatment`, a **segmented** control, **2** options | `Write-off treatment`, a **radio `<fieldset>`** (`:565`–`:578`), **3** options |
| options `Write off` \| `Carry forward` | `Write off the remaining book value` · `Claim under warranty first` · `Hold pending supplier credit` |
| an accent-ruled `RECORDED, NOT POSTED` box | a single 11 px grey `<Note>` at `:584` |
| commit in the danger tier | **danger tier, and asserted on rendered output** (`commitVariant="danger"`, `:463`; DEF-718) |

> ⚠ **THE DRAWING'S TREATMENT ENUM DOES NOT EXIST AND NEVER DID.** p104's field table
> states the source as *"`assets.book_value_treatment` — `write_off` · `carry_forward`"*.
> The ratified set is **three values** and is enforced in two places:
> `06-backend/apps/assets/services.py:241`
> `BOOK_VALUE_TREATMENTS = ("write_off", "warranty_claim", "hold")`, re-checked at
> `:1682` with a `VAL_REQUIRED` refusal naming the allowed list, mirrored at
> `07-frontend/src/api/endpoints.ts:8402`, and commented on the column itself
> (`apps/assets/models.py:392`). The set was ratified under `BR-AST-047` / §10-D4 in the
> CR-028 AST-W4 lane. **`carry_forward` is not a value the server accepts.**
> Rule 41's narrow exception applies: the drawing contradicts a signed rule, so it goes
> to the PO with both sides quoted — it is not a lane's to build or to ignore.

### Gaps

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| treatment options | 2 — `Write off` \| `Carry forward` | 3 — write off / warranty claim / hold, server-enforced | **CONTENT — drawing is wrong**, PO question | no |
| treatment control | segmented, 2 choices | radio fieldset, 3 choices | LAYOUT (follows from the above) | no |
| value box title | `Book value at retirement` | `Asset value` | CONTENT | no |
| value box rows | 3 | 4 (+1 conditional) | LAYOUT — **the code has more**, so a build to the drawing would *lose* `Age at retirement` | no |
| `RECORDED, NOT POSTED` box | accent box, small-caps title | 11 px grey `<Note>` | LAYOUT (**rule 11 + 36**) | no |
| five-slot header | present | `backTo` + kicker + title | MISSING PLUMBING + LAYOUT | no |
| escape hatch | `Save as draft` | `Save & exit` + disabled `Park` | CONTENT (label) | **FIXED** (`AST-B-28`) |
| danger tier on the commit | danger | danger, asserted on rendered output | — | already right |

---

## 7 · SCREEN 27 · RAISE WORK ORDER

`/:tenant/assets/{assetId}/work-orders/new` · **EXISTS BEHIND · NEW BUILD ·
COMMITMENT 02 · 05 · 10 · 26** · figures **41** (as-built), **42** (redrawn)

### What the as-built drawing shows (fig 41, p104–105)

`← Asset` · kicker **`AST-04412`** (the asset number) · title **`Raise work order`**,
drawn at 40 px · an accent box **`WHAT THIS DOES`** reading *"One work order, **not tied
to a new connection**, for this asset; the maintenance history gains a work-order
reference."* · `Template` over a full-width `Choose a template ▾` · footer, **left
aligned**, **`Raise work order`** (solid) then **`Cancel`** as a text link.

### What the REDRAWN drawing changes (fig 42, p105–106)

Five-slot header (kicker `METER · AMI · RAISE WORK ORDER`, title `W-5001`, chip,
attention strip, context line, `…`) · title at **32 px** — caption 2 says so in as many
words · the box body cut to *"One work order for this asset; the maintenance history
gains a work-order reference."* · `Template` becomes **required** with a chevron select
showing `Annual backflow test` and a **NEW** helper *"Only templates for this kind of
asset."* · a **NEW** field **`Note for the crew`** with helper *"What the technician
needs before arriving."* · a **NEW** second box **`WHAT HAPPENS NEXT`** — *"Scheduling,
priority and who goes are set by dispatch in Work. This raises the job and hands it
over."* · footer **`Cancel` · `Raise work order ✓`**, order reversed.

p106's callout gives the reasoning and the four already-filed faults: the 40 px title,
the retired `WRK-19` badge, *"there is no door — the screen is reached by URL only"*,
and the dead-ended *"No template applies to this kind of asset."*

### ⚠ THIRD CARRY-OVER MISS

*"not tied to a new connection"* is dropped from the `WHAT THIS DOES` body with no ruling
quoted. It is the clause that distinguishes this raise from the connection-anchored one,
so it is the load-bearing half of the sentence.

### What the code does today

`RaiseWorkOrderPage.tsx`, route `App.tsx:1095` via `RAISE_WORK_ORDER_ROUTE.slice(1)`.
11 cases in `RaiseWorkOrder.test.tsx`.

* `PageHeader` `:159` — kicker = `asset.asset_no`, title, `backTo`. Title size comes from
  `PageHeader` itself since B14 rule 40 (2026-09-12, `DEF-SHL-4947`, enforced by
  `PageHeader.test.tsx` **and** `cr093-page-title-size.mjs` reading computed style):
  **the 40 px fault is fixed.**
* `ConsequenceBox tone="check"` `:171` — the shared kit piece, title *What this does*,
  body carrying **the full as-built sentence including "not tied to a new connection"**.
* **`:183` is a raw `<select className="border border-neutral-300 px-2 py-1">` inside a
  hand-rolled `<label><span>`** — not the kit's `SelectField`. No `*`, no helper slot,
  no house chevron.
* Refusal `:222`–`:227`: *"No template applies to this kind of asset. Ask an admin to add
  one."*, carrying the `id` the disabled picker and the disabled submit both point at.
* Footer `:228`–`:253`: **commit first** (`Raise work order`, **no `✓`**), then `Cancel`
  (ghost).
* Badge: no local constant — `screenIds.ts` is the authority, `WRK-24`. **Fixed.**

### ⚠ TWO CORRECTIONS TO THE DOCUMENT'S BACKEND CLAIMS

**1 · `create_work_order` DOES take a priority and a due date.** p86 and p106 both say
*"`create_work_order` accepts sixteen keys and **none** is priority, due date, window or
assignee. Scheduling happens in Work, **after** the raise. That is the architecture, not
an oversight."* Measured: `06-backend/apps/metering/connections.py:2332` resolves
`priority` through `_resolve_priority(tenant_id, data, type_ref)`, which reads
**`data["priority_id"]`** (`:2275`), and `due_at` through `_resolve_due_at(data, …)`,
whose first line is `if data.get("due_at"):` (`:2325`) — its docstring says outright
*"A caller may override it (a dispatcher promising a specific day)"*. Both are stamped
onto the row at `:2483`–`:2484`. **Window and assignee are correctly absent.** So the
architectural argument holds for two of the four and not for the other two, and a lane
sizing `AST-B-05` off that sentence would size it wrongly.

**2 · `technician_notes` has a write path, just not this one.** The column exists
(`connections.py:1180`) and is written by the work-order **edit** form
(`apps/work/edit.py:232`–`:236`, audited at `:430`). `create_work_order` does not set it
(`:2454`–`:2492`). So the drawn `Note for the crew` is deliverable, and it is a
**Work-module change** — widening `POST /work-orders` and `create_work_order` — never an
`apps/assets` write.

### ⚠ WHAT SCREEN 27 NEEDS FROM THE `work` MODULE, AND WHAT MUST NOT BE DESIGNED HERE

CLAUDE.md forbids cross-module writes. **Today's screen already complies and says so in
its own header comment** (`RaiseWorkOrderPage.tsx:29`): *"`apps/assets` WRITES NOTHING.
The form posts `POST /work-orders` with `asset_id`, which is Work's own door; the assets
module gains no line of code for this feature and a test asserts that by name."* The
front end calls `raiseWorkOrderForAsset` / `listTemplatesForAsset` from
`features/work/workEndpoints.ts`; the server route is `apps/work/api.py:1644`, which
hands to `services.raise_work_order` → `metering_seam.raise_work_order`.

**What the redrawn figure needs, stated as a request on `work` and designed no further:**

| need | who owns it | why it is not ours |
|---|---|---|
| accept `technician_notes` on the raise | `apps/work` + `apps/metering.create_work_order` | a foreign write; `G78` fails an assets-side write from its first commit |
| a helper that is TRUE about template filtering | `apps/work` — `listTemplatesForAsset` already filters by *applies to asset types*; the sentence just needs to match | the filter is Work's, the sentence is ours |
| a destination for the `No template applies` dead end (`AST-B-10`) | **unruled** | both candidates fail: the Work templates screen is admin-only, and a template-less order has no `type` to send |

### Gaps

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| title size | 32 px | 32 px, enforced by two checks | — | **FIXED** (rule 40) |
| screen badge | `WRK-24` | `WRK-24`, no local constant | — | **FIXED** (`DEF-MET-4978`) |
| refusal names a next step | — | *Ask an admin to add one.*, tied by `aria-describedby` | — | **FIXED** (`DEF-MET-4973`) |
| template control | kit select, `*`, house chevron, helper below | **raw `<select>` + hand-rolled `<label>`**, no `*`, no helper slot | **LAYOUT (rule 8, 36, 39)** | no |
| template helper | *Only templates for this kind of asset.* | none | CONTENT | no |
| `Note for the crew` | a field with a helper | absent | **MISSING PLUMBING** (Work) | no |
| `WHAT HAPPENS NEXT` box | present | absent | CONTENT + LAYOUT | no |
| `WHAT THIS DOES` body | remedy drops *not tied to a new connection* | keeps it | *document defect* | n/a |
| five-slot header | present | kicker + title + `backTo` | MISSING PLUMBING + LAYOUT | no |
| commit label | `Raise work order ✓` | `Raise work order` — **no `✓`** | CONTENT (**rule 4**) | no |
| footer order | `Cancel` left, commit right | **commit left, `Cancel` right** | LAYOUT — see below | no |
| a door to this screen (`AST-B-02`) | — | reached by URL and by four post-commit ticks; **no action-bar or Maintenance-panel entry**, both named by `BR-WRK-056` | WIRING | no |

> ⓘ **THE FOOTER ORDER IS A RULE-38 CASE AND THE DRAWING LOSES — BUT THE PRODUCT IS
> INCONSISTENT WITH ITSELF, WHICH IS A SEPARATE FINDING.** B14 rule 38 names *"that the
> footer puts Cancel on the left"* as **form construction**, so the kit decides. The kit
> decides one way everywhere else in this section — reassign (`AssetFlowPages.tsx:507`)
> and log repair (`:802`) both put `Cancel` first, and `WizardFrame` puts its exits and
> `← Back` before the commit. **Screen 27 is the only one of the six that reverses it.**
> So the drawing and five of six built screens agree, and the sixth is the outlier: this
> is worth fixing on the product's own authority without needing the drawing at all.

> ⚠ **AND THE ONE CHECK THAT WOULD CATCH THE RAW `<select>` CANNOT SEE THIS SCREEN.**
> `CR-016`'s conformance walk enforces B14 rule 8 by reading computed `appearance` and
> holds `nativeSelects` at an **exact** 0 (`07-frontend/e2e/ui-conformance-baseline.json`).
> Its own README says it measures *"every sidebar destination plus two settings
> sub-tabs"* — and `/assets/{id}/work-orders/new` is not a sidebar destination. The same
> is true of `foreignControls`, held at 0, which compares a control's border and
> background against a real `.input`. **Both report zero truthfully over a scope that
> excludes this screen** — hard-won law 7's fifth shape, *reporting zero over a scope it
> silently excludes*. The number is not wrong; it is not about this screen.

---

## 8 · THE ONE GAP THAT IS SIX GAPS — THE FIVE-SLOT HEADER

All six redrawn figures carry the same caption clause: *"THE FIVE-SLOT HEADER FROM SCREEN
08 WITH ITS ATTENTION STRIP"*. It is the section's largest single piece of work and it is
**one piece**, not six.

**What exists today.** Screen 08 builds it inline in `AssetDetailPage.tsx:463`–`:500`:
`PageHeader` with `kicker` (type · asset-no · meter-type), `title` (asset_no), `status`
(`AssetStatusCell`), and a `rollup` holding `<AttentionStrip>` above a `·`-joined place
line. `assetAttention()` is **exported** (`:749`); **`AttentionStrip` is not**
(`:762`) — it is a module-private function.

**What the six screens have.** `AssetFlowShell` (`AssetFlowPages.tsx:137`–`:207`) serves
screens 22, 23, 24, 25 and 26 and passes `backTo` + `kicker` + `title` only.
`RaiseWorkOrderPage.tsx:159` does the same by hand for screen 27.

**So the gap is exactly this:** the strip is built, correct, and unreachable from five
sixths of this section. `PageHeader` already has the `status` and `rollup` slots it
needs. Nothing here is a new design; it is an export, a shared context-line builder, and
one change to `AssetFlowShell` that six screens inherit. Class: **MISSING PLUMBING**, and
it is the cheapest large item in the section.

The section head states the cost in a sentence worth keeping: *"a person reassigning a
meter whose test is eleven days overdue sees no sign of it while they act."*

---

## 9 · WHERE THE DRAWING LOSES, AND WHY — THE RULE-38 AND RULE-41 SPLIT

**B14 rule 41 is the default: the drawing IS the scope**, and the only thing that reaches
the PO is a drawn element that contradicts a signed rule. **B14 rule 38 carves out form
CONSTRUCTION** — side-by-side fields, help under an input, footer button order — where
the UI rules and the kit win and the divergence is recorded rather than built.

| the drawing | disposition | authority |
|---|---|---|
| screen 27's footer puts `Cancel` left | **drawing wins on the merits anyway** — five of the six built screens already do it, so this is the product's own inconsistency, not a kit change | rule 38 names it as construction; no kit change needed |
| `Save as draft` as the exit label | **kit wins**: `Save & exit` + `Park`, in the drawn slot | rule 38; `WizardFrame` is shared by 29 files |
| `Treatment` = `Write off` \| `Carry forward` | **drawing is factually wrong** — the ratified enum is three values, server-enforced | **rule 41's exception → PO**, `BR-AST-047` / §10-D4 |
| `Reassign ✓` in the danger tier | **PO question** — rule 6 names four destructive commits and reassign is not one | rule 41's exception |
| `Where is it going?` (4 words); `Move the 2 sub-meters under this master as well` (9 words, and a drawn figure) | **PO question** — rule 33 caps a label at 3 words with no sentence; rule 37 makes the `2` an illustration | rule 41's exception |
| cost drawn as `84.0000` | **code wins** — hard rule 2 is display 2 | rule 41's exception, resolved without asking |
| screen 26's value box drawn with 3 rows | **do not build to it** — the code's 4 rows include `Age at retirement`, which the drawing would remove | *"a remedy never loses anything"* cuts both ways |
| *"Only units without a live meter."* | **not deliverable as copy alone** — no such filter exists on `GET /units` | hard-won law 1 |
| everything else — headers, field order, pairing, helper wording, the confirm step, the two new boxes, `Note for the crew` | **the drawing wins and is the scope** | rule 41 |

---

## 10 · SUMMARY — CONCRETE COUNTS

**Screens measured: 6. Figures read as images: 13 (30–42), plus pages 85, 86, 90, 91,
93, 94, 97, 100, 103, 104, 106, 107, 108, 209, 210.**

### Gaps by class

| class | count | what it means |
|---|---|---|
| **LAYOUT** | **17** | the elements exist, in the wrong place, shape or container |
| **CONTENT** | **19** | a label, helper or sentence differs from the drawing |
| **WIRING** | **2** | screen 22's confirm step; screen 27's missing doors (`AST-B-02`) |
| **MISSING PLUMBING** | **9** | five-slot header ×6, the Today shortcut (kit-wide), a unit filter on `GET /units`, `technician_notes` on the raise |
| **TOTAL OPEN** | **47** | |
| **ALREADY FIXED since 2.234.17** | **11** | see below |

### The eleven already fixed — do not re-file any of these

1. **`AST-B-04`** — the technician picker. A Billing Clerk gets a searchable
   name-and-email picker over `GET /work/crew-directory`; no uuid on screen; `GET /users`
   is **still** `SystemAdminOnly` and was not widened. *(The document's
   `AssetFlowPages.tsx:604-612` citation points at code that no longer exists.)*
2. **`AST-B-28`** — the escape hatch, on both asset wizards, with `Park` disabled
   carrying its reason, and four DOM cases holding it.
3. **R12 / field order** — label → input → helper in all five kit variants.
4. **`effective_date` `min`** on reassign.
5. **`date` `max`** on log repair.
6. **`retire_date` `min`** on retire step 1, with the drawing's own sentence.
7. **The 40 px title** on screen 27 — now 32 px, enforced by two checks including one
   that reads computed style.
8. **The retired `WRK-19` badge** — the dead constant is deleted; `screenIds.ts` is the
   authority and the screen renders `WRK-24`.
9. **The greyed submit with no reason** on screen 27 — disabled *because of* the refusal,
   carrying it via `title` and `aria-describedby`.
10. **The refusal with no next step** — *"Ask an admin to add one."*
11. **Three screens proposing no date at all** — `todayInZone(timeZone)`, with a test that
    mounts the page the way the router does.

### Document faults found — six

1. **Carry-over arithmetic does not reconcile for this section, in three places**, and
   the reason is structural: **Appendix K's scope sentence (p210) names `05a, 05b, 05c,
   07 and R1–R6` and omits section 05's six redrawn figures entirely**, so the audit was
   never run here. The three: screen 24's `Cancel`, screen 25's *"A retired asset is
   refused."*, screen 27's *"not tied to a new connection"*. By Appendix K's own
   standard — *"Rows with no quoted ruling: 0"* — all three are defects in the document.
2. **`create_work_order` does take `priority_id` and `due_at`**, contradicting p86 and
   p106's *"none is priority, due date, window or assignee"*. Window and assignee are
   correctly absent.
3. **The book-value treatment enum is wrong** — p104 says `write_off · carry_forward`;
   the ratified, server-enforced set is `write_off · warranty_claim · hold`.
4. **Figure 35 draws a `Cancel` on retire step 1 that the product never had** — measured
   `["Continue"]` on 2026-09-12.
5. **The blueprint map's figure numbers for this section are wrong** — figure 30 is
   screen 22's *as-built*, and its remedy is figures **31 + 32**, a pair.
6. **`08-screen-layouts.md` gives screen 27 two commitments the PDF page does not**
   (`AST-B-14`, `AST-B-27` against the drawn `02 · 05 · 10 · 26`) — a derived copy
   drifting from its source, which is why the PDF is the only specification.

### The three biggest gaps, per screen

| screen | 1 | 2 | 3 |
|---|---|---|---|
| **22 Reassign** | no confirm step — the two consequence sentences render as 11 px grey captions beside the form, where a person reads them before deciding anything | no five-slot header / attention strip | segmented label and both options differ from the drawing (`Move to` · `A unit` · `Inventory (unassign)`) |
| **23 Log repair** | the row pairing and `What was done`'s position are both wrong — the drawing pairs `Date \| Set status` and `Technician \| Cost` | `RECORDED, NOT POSTED` is a grey `<Note>` carrying one of its two sentences, not a consequence box | commit reads `Save entry`, not `Log it ✓` (rule 4) |
| **24 Retire 1** | no five-slot header | the notice box is hand-rolled rather than `ConsequenceBox`, and carries three paragraphs where the drawing has two | the final-read helper is 19 words against the drawing's 8 (rule 33) |
| **25 Retire 2** | the `Replaced by` helper is a **third** wording, matching neither figure | no five-slot header | an unmetered-warning band renders that neither figure draws, hand-rolled |
| **26 Retire 3** | the treatment control is a 3-option radio group against a drawn 2-option segmented control — **and the drawing's enum is the wrong one** | `RECORDED, NOT POSTED` is a grey `<Note>`, not a box | the value box has four rows titled `Asset value`, not three titled `Book value at retirement` — building to the drawing would *lose* `Age at retirement` |
| **27 Raise work order** | a raw `<select>` and hand-rolled `<label>` instead of the kit's `SelectField` — invisible to the one check that enforces rule 8, because that walk only visits sidebar destinations | `Note for the crew` and the `WHAT HAPPENS NEXT` box are both absent, and the note needs a **Work-module** change to `POST /work-orders` | no door — `BR-WRK-056` names the action bar and the Maintenance history panel and neither is built (`AST-B-02`) |

---

*Measured 2026-09-13 against `11307c79`, product version `2.261.3`. Blueprint read at
`2.234.17` / `79c659d7`. Every layout statement above was read from a rendered PDF page
image (B14 rule 42); every code statement carries a file and line. Nothing was built,
no register was edited, and no id was allocated.*
