# 17 · Runbooks — component inventory

**Two closed vocabularies, and closing them is the whole design.** A result is drawn from **twelve blocks**;
a parameter is one of **eleven types**. Thirty-four runbooks and seventy-five wireframes contain nothing
else. That is why `RBS-004` and `RBS-006` are renderers rather than pages, and it is why runbook 23 needs no
frontend change (`08-screen-layouts.md`).

**Compose the staff kit; do not fork it** (B14 rule 36, PO 2026-09-04). Every block below maps to a component
that already exists, or is named here as a thing the kit does not have — and where the kit lacks a piece, the
piece is **added to the kit**, one component and one visual decision, not hand-rolled per screen.

⚠ **B14 rule 21, and this one bites before any of the others.** A Tailwind utility is emitted **only** for a
file listed in `07-frontend/src/styles/route-b-migrated.txt`. **That file has 3,241 lines today and not one
of them is a runbooks path.** Write a utility in a file that is not on the list and it is a class no
stylesheet declares: it renders as **nothing at all**, and `tsc`, eslint and every `toContain("flex")`
assertion pass, because the class IS in the DOM. **The module's files join that list in their FIRST commit,
in the same commit that creates them** — that is what wave H did for `components/WarningBox.tsx` and what
`DEF-974` cost when it was not done.

---

# Part 1 · The twelve result blocks

A `report(run)` returns a list of blocks and nothing else. The renderer knows twelve names; a report naming a
thirteenth is refused at run close and never reaches the screen (`RB-016`).

| # | Block | What it draws | Used by runbook | Drawn region name(s) | Rendered by |
|---|---|---|---|---|---|
| 1 | **Verdict** | Go · no-go · warn: one bold word, a count line, a detail line | 2 · 3 · 9 · 12 · 13 | `Verdict band` (band · tone success / warning / danger) | **not in the kit** — a band; tones from `StatusPill` (FE-10)'s tokens. See *What the kit does not have*. |
| 2 | **KPIs** | Tiles: value, label, tone | every runbook except 6 and 13 | `KPI strip` | **`KPIStrip` (FE-09)** — built |
| 3 | **Chain** | Ordered steps: ok · bad · not reached; a red cell names the blocker | 1 · 2 · 6 · 13 | `Chain` (*N* cells in a row) | **not in the kit** |
| 4 | **Records** | The per-record table: declared columns, filters as chips, pagination; cell renderers pill · money · sparkline; a grid display mode | every runbook except 4, 13 and 19 — the coverage grid is its grid mode; runbook 5 uses the sparkline cell | `Toolbar` + `Table` + `Pagination footer` | **`DataTable` (FE-02)** + **`FilterBar` (FE-03)** + **`ListPager` (FE-22)**; cells **`StatusPill` (FE-10)**, **`MoneyCell` (FE-11)**, **`UnitCell` (FE-12)**, **`DateCell` (FE-13)** — all built. **The sparkline cell and the grid mode are not.** |
| 5 | **Breakdown** | Group-by with counts: by class, tier, source, channel, type | 8 · 10 · 16 · 19 · 20 · 22 | `Section heading` + `Table` | **`DataTable` (FE-02)** — built |
| 6 | **Reconciled** | Ours · theirs · difference, with a ties mark | 2 · 4 · 9 | `Section heading` + `Table` (side-by-side columns) | **`DataTable` (FE-02)** — built |
| 7 | **Ranked** | Label, thin bar, value — causes or a distribution | 4 · 16 | `Contribution bars` (*N* rows: label · bar · value) | **not in the kit.** `Chart` (FE-20) is ⬜ unbuilt and is the wrong instrument anyway — this is a row list with a bar, not a chart. |
| 8 | **Sentence** | One card: a stop, a find, *read this aloud*, what the customer receives | 4 · 6 · 11 | `Outcome box` (callout, success rail) · `Stop card` (danger callout) · `Notice` (muted box) | **not in the kit** in this shape. Nearest built: `WarningBox` (amber), `Panel` (`plain`/`info`/`warning`/`emergency`), `ConsequenceBox`. |
| 9 | **Facts** | Label · value list | 4 · 6 · 13 | `Key–value table` | **`PlainTable`** (`components/Surfaces.tsx`) — built |
| 10 | **Action** | One button with a tier and an enabling condition | 5 · 9 · 12 · 13 · 15 · 18 · 19 | page-head `action` Buttons · `Button row` | **`Button` / `buttonKit`** — built |
| 11 | **Row decisions** | Accept / keep on a records row, each mapping to a port or an engine act | 20 | a `Decide` column inside a `Records` table | **`RowActions`** — built, **but see the rule-15 divergence below** |
| 12 | **Downloads** | The two result files | every runbook except 4, 6 and 13 | page-head `action` Button `↓ …` | **`DownloadButton` (FE-14)** — built |

## The rule that keeps this a vocabulary and not a language

> **A thirteenth block needs THREE runbooks that cannot be drawn without it.**

One runbook wanting a new shape is a runbook that should compose the existing twelve differently. **The moment
the block list grows per request, the result renderer becomes a UI language and every future runbook becomes a
support question about it.** The same rule governs a seventeenth category (`12-the-contract.md`), and both
exist for the same reason: a closed list is what makes a renderer possible at all.

⚠ **THE *USED BY RUNBOOK* COLUMN ABOVE IS TAKEN FROM THE SPECIFICATION'S PER-RUNBOOK COVERAGE TABLE, NOT FROM
ITS BLOCK TABLE, BECAUSE THE TWO DISAGREE IN SEVEN ROWS OF TWELVE AND THE DRAWINGS SETTLE IT.**
The block table's own *Used by* column says *Verdict: 2 · 9 · 12 · 13*, *KPIs: all 21*, *Records: all 21*,
*Breakdown: … 14 · 17 …*, *Reconciled: … 14*, *Sentence: … 13*, *Facts: 6 · 13 · 15*, *Downloads: all 21*.
Checked against the twenty-one result wireframes, the coverage table is right every time:

* **runbook 3** draws a `Verdict band` (`RBS-006-R3` region 2) — the block table omits it
* **runbooks 6 and 13** draw **no KPI strip** at all (`RBS-006-R6`, `RBS-006-R13`) — *"all 21"* is wrong
* **runbooks 4, 13 and 19** draw **no Records table** — `RBS-006-R19`'s one table is the Breakdown
* **runbooks 14 and 17** draw one table each and it is Records — no Breakdown, no Reconciled
* **runbook 13** draws Verdict · Chain · Facts · Action and no Sentence
* **runbook 15** draws no Facts list
* **runbooks 4, 6 and 13** carry no `↓` download button

**So: cite the coverage table for *which runbooks use a block*, and the block table only for *what a block
draws*.** One over-claim survives even the coverage table and is recorded rather than smoothed: **runbook 4
is listed as using both Reconciled and Facts and `RBS-006-R4` draws only one table** (`Line | Aug | Sep |
Change`), which is Reconciled. Runbook 4's Facts block is undrawn.

---

# Part 2 · The eleven parameter types

**Parameters are the knobs a utility can turn.** The setup renderer (`RBS-004`, Scope and Parameters panels)
draws a parameter from its type and from nothing else — that is `RB-021`, and it is why twenty-six setup
screens are one component.

| # | Type | Rule | Example on a card | Drawn as | Rendered by |
|---|---|---|---|---|---|
| 1 | **money** | **4 decimals stored, 2 shown** | *Past due more than* `$5.00` · *Overpayment over* | text input, right | **`MoneyCell` (FE-11)** for display (`MONEY_DISPLAY_DECIMALS = 2`); the input is a `FormField` |
| 2 | **integer** | Whole number | *Most per run* `400` · *Show biggest movers* | text input, right | `FormField` |
| 3 | **days** | A count of days | *Duplicate window* · *Once per meter every* | text input + the word *days* | `FormField` |
| 4 | **percent** | **6 decimals stored, 2 shown** | *Call it large above* | text input, right | **nothing** — there is no percent formatter in the front end at all. See below. |
| 5 | **enum** | **ONE value, SEVERAL, or *ALL*** of a **tenant-resolved** domain (`BR-RBS-042`, PO 2026-09-06), **searchable above five** (B14 rule 8). ⚠ *All* is stored as **the word** and resolved at run start — never expanded to a list at configure time | *Channel* · *Group by* · *Settle by* · **Services = `All`** · **Account types = All except Municipal** | single: dropdown `▾`, one chevron style · multi: **removable chips + an add control, never a wall of checkboxes** (B14 rule 9, row below) | `FormField` select; **the multi-value and *All* shapes are ⬜ UNBUILT**, and searchable half of rule 8 is **unenforced** |
| 6 | **toggle** | On or off | *Auto-apply exact matches* · *Fees need second approval* | switch | **`Switch`** — built |
| 7 | **text** | Short free text | *Last four of cheque or card* | text input | `FormField` |
| 8 | **window** | A period: last *N* days, a cycle, a date range | *Window* · *Against cycle* | dropdown or date range | **`DateCell` (FE-13)** for display; a range picker is **not in the kit** (B14 rule 7 requires the date input, never a bare text input) |
| 9 | **ref:setting** | **Read-only, dashed, links to Settings, NEVER duplicated here** | *Ladder tiers* · *Quiet hours* · *Interest* | dashed read-only box + **Open settings →** | **not in the kit** |
| 10 | **ref:object** | A picker for one account, meter, schedule, cycle, bank account | *Proposed schedule* · *one account* | picker | **not in the kit**; B14 rule 31 applies — the picker shows the NAME, never the id |
| 11 | **file** | An uploaded file the run reads once | *The legacy trial balance* | upload control | `ImportStager` (FE-15) is ⬜ unbuilt |

## Two rules the PO added to this table on 2026-09-06, and they change what a build owes

⚠ **THIS TABLE READ AS IF EVERY PARAMETER TOOK ONE VALUE FROM A FIXED LIST UNTIL 2026-09-06.**
It does not. A runbook is **one fixed process with declared inputs**, and the PO ruled two things
about those inputs (`BR-RBS-042`):

1. **A DOMAIN, RESOLVED PER TENANT.** *“every utility will not have all utility services or all
   combinations of Plans and rates, so we ahve to work in variables”*. A two-service utility's
   *Services* domain holds **two**; a utility with three plans sees **three**. **An empty domain
   says so** rather than drawing a dropdown with nothing in it, which reads as broken.
2. **ONE VALUE, SEVERAL, OR *ALL*, AND *ALL* IS A RULE RATHER THAN A VALUE.** Store the **word**;
   resolve it when the **run starts** (`BR-RBS-009` pins it there). A utility that sets *all
   services* with Water and Sewer and later adds Trash must get **three** on the next run.
   ⚠ **Expand it at configure time and adding a service silently drops it out of every runbook set
   to *all*** — no error, no screen change, nothing to see. That is the absence class this
   repository keeps paying for.

**The shape is already ruled and it is in the table below: chips, never a checkbox wall (rule 9).**
Nothing new is needed on screen — what is owed is the domain on each parameter and the multi-value
control.

⚠ **AND A TENANT NEVER SEES A STEP.** The step library — **173 step instances across 26 runbooks reduce to 137 distinct steps** (`14-step-library.md`, the hand count of 2026-09-06) — is **ours**, used from wave `C` onward to build runbooks, and no component in this
inventory draws it. PO verbatim: *“I dont think Utility admin will able to configure these using the 150 bricks that we give - you can keep all these bricks and buld ready to use runbooks - when we later change it will be small er changes for us”*.

## `ref:setting` is the one that carries a rule, not just a shape

A value that already lives in Settings is shown **dashed, read-only, with *Open settings →*** and **is never
duplicated** into the runbook's own parameters. `RBS-004-R8` draws five of them at once — *Ladder tiers ·
From Settings · 5 tiers*, *Grace days · From Settings · 3*, *Quiet hours · From Settings · 20:00–08:00*, and
in the Scope panel *Never include · Medical · Dispute · Sample*. **Duplicating one is how a utility ends up
with two ladders and no way to tell which one sent the notice.** The dashed border is the visible half of
that rule; the invisible half — that no runbook writes a Settings value — is enforced by the ports list.

## Money, percent and rate — three kinds, and the third is the one that gets lost

| Kind | Stored | Shown | Formatter |
|---|---|---|---|
| **money** | 4 decimals, `CHAR(3)` currency, never float | **2** | `formatMoney` / `MoneyCell` (FE-11), `MONEY_DISPLAY_DECIMALS = 2` |
| **percent** | 6 decimals | **2** | **none exists** |
| **rate** | 6 decimals (`NUMERIC(18,6)`, `RATE_PLACES = 6`) | **2 to 4** (up to 4, zeros past the 2nd dropped — PO 2026-10-02) | `formatRate` / `formatRateNumber`, `RATE_MIN_DISPLAY_DECIMALS = 2`, `RATE_DISPLAY_DECIMALS = 4` |

**A rate is a third kind beside money and a quantity, and it is not a rounding preference.** PO ruling on
`OQ-620`, closed 2026-08-27, verbatim: ***"What does a tariff rate show? Four ($0.1420). A rate is not money
and not a quantity - 4 decimal places"*** — worked there as `8.290000` per kgal → **`$8.2900`**, zeros KEPT.
Hard rule 2 was explicitly **not** changed by that ruling: money still displays 2 and a quantity at most 2
trimmed. **A rate is multiplied by a quantity before it becomes money, so its precision compounds** — round
it to 2 and `$0.0025 / kWh` prints `$0.00` beside a real charge. All three kinds live in
`06-backend/core/money_fields.py`.
⚠ **AMENDED 2026-10-02 — UP TO FOUR, ZEROS PAST THE SECOND DROPPED.** PO, verbatim: *"Show unit prices with up to 4 decimals and keep every total at 2."* (decision log *"THREE UI RULINGS FROM THE RATE-SCHEDULE SWEEP"* (1)). A unit price now reads `$0.0425`, `$0.10`, `$12.50` — `8.290000` reads **`$8.29`**, no longer `$8.2900`. The four-place ceiling and the reason for it stand; every amount stays at 2.

**Where this lands in Runbooks:** there is **no `rate` parameter type** — a rate never appears as a knob. It
appears as a **result cell**, on runbook 16's *Rate change preview* above all, where a draft tariff is
compared against a real cycle. A Records or Reconciled cell holding a tariff rate uses `formatRate`, not
`formatMoney`, and a cell holding the resulting money uses `formatMoney`. **A screen that formats both with
one helper is wrong in one of the two directions on every row.**

**Hard rule 3 holds on every quantity:** always an explicit unit, never assumed. The pack does this —
`~11,000 gal`, `7,240 gal vs 5,250 gal`, `1,140` under a `Gal / day` header, `1,802 meter-days`. Use
`UnitCell` (FE-12), which makes the unit compile-required.

---

# Part 3 · The grammar — which B14 rule governs each element

| Element on a runbook screen | B14 rule | Status of that rule |
|---|---|---|
| The page head's `←` names where the page EXITS to; a wizard footer's `← Back` means previous step only | **1** | RATIFIED, unenforced |
| One page head everywhere: kicker · title · optional subtitle · right-aligned actions | **2** | RATIFIED · `BR-SHL-044` · kicker gate ENFORCED, 0 |
| The six-step run rail; numbered, clickable when complete | **3** | RATIFIED, unenforced |
| Button grammar: `+ Noun` creates · `Verb →` advances · `Verb ✓` commits · `↓` download · `↑` import | **4** | RATIFIED, unenforced |
| Two button sizes only — default (14px) and small (12px) | **5** | RATIFIED · CR-016 gate ENFORCED, register `["12px","14px"]` |
| **Approve and queue ✓** is the danger tier, not the standard primary | **6** | RATIFIED · ENFORCED on rendered output for the wizard commit (`DEF-712`) |
| Every date field is the date input, never a bare text input | **7** | RATIFIED, unenforced |
| One chevron style on every dropdown; 5+ options searchable | **8** | chevron half ENFORCED (`nativeSelects: 0`); searchable half unchecked |
| A multi-value parameter is removable chips + an add control, never a wall of checkboxes | **9** | RATIFIED, unenforced |
| A required parameter carries the asterisk on its label | **10** | RATIFIED, unenforced |
| The *What this will do* box before **Approve and queue ✓** | **11** | RATIFIED, unenforced |
| Toolbar order `[Search…] [All \| chips ×] [+ Filter ▾] … [▦ Columns]` | **12** | RATIFIED, unenforced |
| Sortable headers show `⇅`; click cycles asc → desc → clear | **13** | RATIFIED, unenforced |
| `▦` opens show/hide with reorder and Reset | **14** | RATIFIED, unenforced |
| **Row actions are ICONS with tooltips, never text links. Max 2 visible + `…`** | **15** | RATIFIED · **G37 ENFORCED** + a browser spec |
| Pagination footer on every list table; page size remembered per table | **16** | RATIFIED · rides the shared `DataTable` |
| Empty state on every list: what is missing and the action that fills it | **17** | RATIFIED, unenforced |
| Descriptions cap at **80%** of content width (amended from r10's 66%) | **18** | RATIFIED · `--desc-measure` · G43(b) RATCHETED at 50 |
| Search placeholder reads *Search {entities}…* | **19** | RATIFIED · **G43(a) ENFORCED, baseline 0** |
| Table type is one size — 13.5px body under a 12px header | **20** | RATIFIED · CR-016 gate ENFORCED |
| **New UI is Tailwind and adds NO class to a stylesheet** | **21** | RATIFIED · **G31 — declared-class count is a CEILING** |
| **No database id, rule number, path or route is ever the visible value of a field** | **31** | RATIFIED · **G28 ENFORCED in three parts**; a uuid-shaped VALUE is enforced on `S30` and `S15` only |
| **Description budget: one sentence per section; a stated absence is a `<details>` CLOSED by default; no rule id or internal code in clerk-facing copy** | **32** | RATIFIED, clauses 1/3/4 unenforced |
| **On-screen text capped by what it is for**: LABEL ≤ 3 words · FACT ≤ 6 · INSTRUCTION ≤ 6 per sentence · CONSEQUENCE ≤ 6 per sentence, at most two · **RATIONALE = zero words on screen** | **33** | RATIFIED · `G33` enforces the REFUSAL half at six words; the other four kinds are unenforced |
| **Recorded** and **In the books** are the one pair of words for *held here* and *in the books*, in all eleven catalogues | **34** | RATIFIED, unenforced |
| A catalogue is written in its own language, not translated from English | **35** | RATIFIED, unenforced |
| **The pack gives layout and detail; `r10` gives the VISUAL STYLE; the shared kit is how you comply. Nothing dashed, monospaced or labelled like a diagram ships to a utility user** | **36** | RATIFIED, unenforced |

⚠ **A note on the count, because it will be quoted.** `CLAUDE.md` calls these *the thirty-six binding UI
rules*, and **36 is the highest rule NUMBER, not the number of rules.** B14 declares rows **1–21 and 31–36**
— twenty-seven rules. Numbers 22–29 were never issued and **30 was declined** on 2026-08-30 in the same
sentence that ratified 31. Cite a rule **by its number**; do not derive a count from the pointer.

---

# Part 4 · Where the seventy-five wireframes DIVERGE from B14

**These are findings, not problems to smooth over.** Each is measured. None is a reason to stop building; all
of them are cheaper to settle once, here, than screen by screen.

### 1 · Rule 33 — twenty-eight Outcome boxes, every one over the cap

Rule 33 caps a **FACT** at six words and an **INSTRUCTION** or **CONSEQUENCE** at six words *per sentence*.
The `Outcome box` — the *Produces: …* callout at the foot of every setup renderer — runs **14 to 88 words,
median 25.5**, and **all 28 exceed six words in at least one sentence**. The longest is `RBS-004-R5` at 88
words; `RBS-004-R8`, `RBS-006-R4`, `RBS-004-R9` and `RBS-006-R11` follow at 43, 40, 39 and 33.

This is a real divergence and it needs a decision, not a trim: the Outcome box is a *description of what a run
produces*, which is closest to rule 33's **RATIONALE** kind — and rationale is **zero words on screen**. The
honest readings are (a) it is a FACT list and must be cut to six-word sentences, or (b) it is not
clerk-facing copy at all but a **template-library** description, in which case it belongs on `RBS-002`'s card
and not on the setup screen. **The decision belongs in the module's `02-business-rules.md`**, and it is ours
to make under hard-won law 13, not the PO's to be asked.

Two callouts are already compliant or nearly so and are the shape to copy: `RBS-005.1`'s consequence
preview (*This step sends nothing.* / *You will see everything first.* — 4 and 5 words) and `RBS-005.4`'s
(*Queue 400 notices now.* / *Charge no fees. None are due.* / *Leave 412 for next run.* / *Leave 95 accounts
for you.* — four facts of ≤ 6 words each). ⚠ Note that **`RBS-005.4` draws four consequence lines and rule 33
caps a consequence at *at most two* sentences.** The design note calls them *four facts*, which puts them
under the FACT cap rather than the CONSEQUENCE cap — a reading, and worth stating in the rules rather than
leaving to a reviewer.

Two more overrun outright: `RBS-005.7`'s refusal card ends *Narrow the scope, or raise the limit.* (7 words),
and `RBS-006-R6`'s stop card is three sentences with a 14-word opener.

### 2 · Rule 15 — three icons outside the ratified vocabulary, two with no glyph in the kit

Rule 15's list is closed: **👁 view · ✎ edit/note · ⟲ roll back · 🔧 fix · 🖨 print · ✉ send · ⚡ raise work ·
✓ assign · − remove**. The pack draws:

| Icon | Meaning in the pack | Sheets | In rule 15? | In `components/icons.tsx`? |
|---|---|---|---|---|
| `👁` | view a run | 18 | ✅ | ✅ `EyeIcon` |
| `✎` | edit / note a work item | 7 | ✅ | ✅ `PencilIcon` |
| `🗑` | delete a Draft run | 1 | as `−` remove | ✅ `TrashIcon` (the divergence between the prose `−` and the shipped trash can is already recorded in that file) |
| **`▶`** | **run the runbook** | **12** | ❌ | ❌ |
| **`→`** | **open the run / the work item** | **10** | ❌ | ❌ |

**So Runbooks needs two new verbs and two new glyphs.** *Run* and *open* are the two most-pressed controls on
the whole surface and neither exists. `icons.tsx` is the one place they go — that file exists precisely
because rule 15 listed its glyphs in prose and prose is not importable, and the pencil ended up drawn four
times. Add `PlayIcon` and `ArrowRightIcon` there, in the same commit as the first screen that uses them, and
extend rule 15's vocabulary in B14 with the ruling recorded.

⚠ **Row-action counts are all compliant** — every drawn set is at most two icons plus `…`.

### 3 · Rule 15 vs the Row decisions block — `RBS-006-R20`'s `Decide` column

Runbook 20's queue draws two **text buttons** in a table cell: *Accept theirs →* · *Keep ours*. Rule 15 says
row actions are icons with tooltips, **never text links**.

**Both readings are defensible and the product has already chosen one.** *Accept theirs* and *Keep ours* are
not any of rule 15's nine verbs, and an icon cannot carry which of two values is being kept — an icon here
would be unreadable. **The precedent is Integrations**, whose `MappingRow` draws **Change** / **Map it** and
whose `DecisionCard` draws **Accept the change · Keep ours · Ask the City**, both as text buttons, both
shipped. **So the answer is that a DECISION is not a row action**, and the rule to write is that a Records
table may carry one decision column of text buttons where the choice is between named values. Write it in
`02-business-rules.md` and stamp the divergence in B14; do not let two screens quietly answer it differently.

### 4 · Rule 36 — monospace and dashed borders on production screens

Rule 36, ratified 2026-09-04 on the PO seeing four shipped screens: **nothing dashed, monospaced or labelled
like a diagram ships to a utility user.** The sheets specify both:

* **Monospace, by name.** `Progress list` regions specify *"right text mono 11.5px"* — the `read` / `writes`
  / `Never reached` markers on `RBS-004.2`, `RBS-004-Rn` and `RBS-005.2/.5/.8`. `Contribution bars` specify
  *"value mono 12.5px right"* (`RBS-006-R4`, `RBS-006-R16`). The rendered PNGs confirm it: `RBS-004-R8`'s
  *6 · four read, two write* caption and its `read`/`writes` column are monospaced, as are `RBS-006-R4`'s
  `+$46.40` and `$0.00`.
* **Dashed, by name.** Every `ref:setting` parameter is *"dashed, read-only"*.

**Neither is automatically a breach and the distinction matters.** Rule 36's own breach list names *"an
annotation style in a screen"* — `border-dashed` with `font-mono uppercase tracking-wider` legends, so that
*"a customer-facing form looked like a sketch of itself"*. A dashed box also already carries a **legitimate**
meaning in this product: B14 rule 17's empty state is *"dashed n400 box, centred"*, and Integrations ships
`border-dashed` for a coming-soon control. And monospace has a legitimate meaning too — Integrations'
inventory reserves it for *"every value a machine gave us"*.

**The rule to apply, and it is one sentence:** a dashed border means *this is not yours to edit here*, and
monospace means *a machine produced this exact value* — and **nothing else on any runbook screen is dashed or
monospaced.** By that test `ref:setting`'s dashed box passes, the mono `$46.40` passes (it is a computed
figure in a column that must align), and **`RBS-004-R8`'s *6 · four read, two write* caption fails** — it is a
panel subtitle in a diagram font. Put it in the panel title's own type.

### 5 · Rule 31 / 32 — one screen id in clerk-facing copy

`RBS-007` region 5 is an `h5` reading **`S153.2 · all clear`**. It is the drawing labelling its own second
state on a single sheet; the rendered PNG shows it as a live section heading above the empty state.
**Rule 31 forbids an internal code as visible text and rule 32 forbids one in clerk-facing copy.** The built
screen shows the table **or** the empty state, never both, and never that heading. Same for `RBS-005.7`'s and
`RBS-005.8`'s route lines (*S151.7 · cap refused*), which are the sheet's own captions and not screen copy.

### 6 · Hard rule 2 — five money values drawn without two decimals

| Sheet | Region | Drawn | Should show |
|---|---|---|---|
| `RBS-006-R16` | KPI tile | `+$5,310 — Revenue · +4.7%` | `+$5,310.00` |
| `RBS-006-R5` | KPI tile | `$9,840 — Revenue at risk` | `$9,840.00` |
| `RBS-006-R18` | KPI tile + page-head subtitle | `~$1,940 — Unbilled per month` · *About $1,940 a month.* | see below |
| `RBS-004-R18` | Outcome box | *about $1,940 a month unbilled* | see below |
| `RBS-006-R12` | KPI tile | `2 — Under $50` | a threshold in a LABEL — not a money value, no change |

Hard rule 2 is unambiguous: money **displays 2**. The two clean breaches are `+$5,310` and `$9,840`, both
exact-looking figures with no hedge. The `~$1,940` and *about $1,940* cases are deliberately approximate and
are the ones worth a rule: **either an approximation is still money and shows two decimals, or a KPI tile may
carry a rounded estimate and must mark it** — the tilde and the word *about* are already doing that. Decide
it once in `02-business-rules.md`; `MoneyCell` (FE-11) has no rounded-estimate mode today, so whichever way it
goes, the kit needs the affordance or the fixtures need the cents.

### 7 · Hard rule 2 — no percentage anywhere is drawn at two decimals

Across all seventy-five sheets, percentages are drawn at **zero or one decimal**: `+38%`, `+4.7%`, `+30.4%`,
`15%`, `2.0%`, `0.05%`, `61%`, `92%`. Hard rule 2 says percentages **display 2**.

**Not all of these are hard-rule-2 percentages** — `61%` is a progress bar, `300%` is a threshold in a
parameter label. But `+4.7%` (a revenue change) and `+30.4%` (a bill change) are derived from money and are
squarely inside the rule. **And there is no percent formatter in the front end at all** — `MoneyCell.tsx`
exports `formatMoney` and `formatRate` and nothing for a percent. The module needs `formatPercent` / a
`PercentCell` in the kit before the first percentage is drawn, or twelve screens will each choose their own.

### 8 · Two sheets carry pager arithmetic that does not foot

`RBS-001.1` reads *Showing 1–5 of 34 · Rows per page 50 · Page 1 of 1*; `RBS-007` reads *Showing 1–7 of 14 ·
Rows per page 50 · Page 1 of 1*. At fifty per page those are *1–34 of 34* and *1–14 of 14*. The drawings show
five and seven rows because that is what fitted. **The pager copy comes from `table.pager.range` and is
computed, so the built screen cannot reproduce this — but a FIXTURE copied from the sheet can**, and a test
asserting the sheet's string would pin the wrong number.

### 9 · Two build sheets are wrong about their own component

* **`RBS-006-R13` region 4** declares a `DataTable` whose first column is `(row actions) [icons only]`, and
  its rows are label-and-value. It is the **Facts** block: `PlainTable`.
* **`RBS-006.2` region 4** declares a `Key–value table` and its right-hand side is a control (*Add an address
  →*). It is a failure list with fix routes: build it as `RBS-005.6` region 4 already draws.

The sheets' own preamble is the standard to apply: *"A sheet and its frame cannot disagree — one is derived
from the other. If one is wrong, both are, and the frame is the thing to fix."*

---

# Part 5 · What the staff kit does not have — six things

Everything else on these seventy-five wireframes is composition. These six are new components, and each is
**one component added to the kit**, not a shape hand-rolled per screen (rule 36).

1. **`VerdictBand`** — one bold word, a count line, a detail line, toned success / warning / danger from the
   run outcome. Five runbooks. A commit button placed on the band is the danger tier when it closes or sends
   (rule 6).
2. **`Chain`** — *N* cells in a row, each `ok` / `bad` / `not reached`; a red cell **names the blocker** and a
   *Never reached* cell says so rather than sitting blank. Four runbooks, and it is also `RBS-005.8`'s shape.
3. **`ContributionBars`** — rows of label · thin bar · value, largest first, with a 12px second line under the
   label. Two runbooks. **Not a chart** — `Chart` (FE-20) is unbuilt and is the wrong instrument.
4. **`OutcomeCard`** — the Sentence block in its three tones: success rail (*What the customer receives*),
   danger (*Stop card*), muted (*Notice*). `WarningBox`, `Panel` and `ConsequenceBox` each cover part of this
   and none covers the shape. Whatever it is called, **its word budget is rule 33's and Part 4 §1 above is the
   decision it waits on.**
5. **`SettingsOwnedField`** — the `ref:setting` parameter: dashed, read-only, its value from Settings, with
   **Open settings →**. Used five times on one screen (`RBS-004-R8`) and on nearly every setup renderer.
   **The rule it enforces is that the value is never duplicated**, so the component reads Settings and takes
   no value prop — a component with a value prop here is the bug.
6. **`PercentCell` / `formatPercent`** — hard rule 2's percentage half, which has no code anywhere in the
   front end. See Part 4 §7.

**And two glyphs in `components/icons.tsx`:** `PlayIcon` (▶ run) and `ArrowRightIcon` (→ open). See Part 4 §2.

**And one line per file in `07-frontend/src/styles/route-b-migrated.txt`, in the first commit that creates
the file.** Without it every Tailwind utility in that file is a class no stylesheet declares, the screen
renders as unstyled text, and `tsc`, eslint and every assertion still pass.

---

# Part 6 · What CR-075 wave C actually built (2026-09-06) — and the one thing it did not

**Read this before writing a line of `RBS-006` or `RBS-004`.** Part 5 above names six things the kit does not
have; five of them and three more now exist. This section is the CURRENT state, and it is written here rather
than in a commit message because the next lane reads the repo, not the history.

## The kit — all eight built, all eight on the ledger

Every one is in `07-frontend/src/components/` (the **shared kit**, B14 rule 36 — not a runbooks folder), and
every one has its own line in `07-frontend/src/styles/route-b-migrated.txt`, added in the commit that created
it. `components/` is listed PER FILE, so a new kit component is covered by nothing until its line exists.

| Component | Draws | Notes |
|---|---|---|
| `VerdictBand` | Verdict block | Three tones. The WORD is the runbook's, never derived from the tone — six words for three tones across the five sheets. |
| `Chain` | Chain block | A grid, not `flex flex-wrap`: flex stretched the last wrapped row and *Reads* drew 372px beside a 155px *Services*. |
| `ContributionBars` | Ranked block | Bar is proportional to the LARGEST ROW, not the total. Order is the runbook's; it never re-sorts. |
| `OutcomeCard` | Sentence block | Three tones. **Counts and truncates nothing** — see the stated absence below. |
| `SettingsOwnedField` | `ref:setting` parameter | **No `value` prop, ever** — a test reads the source and fails if one appears. Three visible states: loaded · not loaded · not set. |
| `PercentCell` | every percentage | `formatPercent` + `PERCENT_DISPLAY_DECIMALS = 2`. The convention (`fraction` \| `points`) is a REQUIRED argument. |
| `Sparkline` | the Records block's sparkline cell | Inline SVG, no library. `label` carries the unit — hard rule 3 reaches a picture too. |
| `RecordGrid` | the Records block's GRID MODE | Every cell is a real link; the component cannot express a dead one. **No build sheet exists** — see `08-screen-layouts.md`. |

## The twelve blocks — **eleven built, one not**

In `07-frontend/src/features/runbooks/blocks/`, one file each, composed from the kit above. The feature root
is a DIRECTORY entry on the ledger, so a file born under it is Tailwind-owned from birth.

| # | Block | Component | Built |
|---|---|---|---|
| 1 | Verdict | `VerdictBlock` | ✅ |
| 2 | KPIs | `KpisBlock` | ✅ |
| 3 | Chain | `ChainBlock` | ✅ |
| 4 | **Records** | — | ❌ **not built — see below** |
| 5 | Breakdown | `BreakdownBlock` | ✅ |
| 6 | Reconciled | `ReconciledBlock` | ✅ |
| 7 | Ranked | `RankedBlock` | ✅ |
| 8 | Sentence | `SentenceBlock` | ✅ |
| 9 | Facts | `FactsBlock` | ✅ |
| 10 | Action | `ActionBlock` | ✅ |
| 11 | Row decisions | `RowDecisionsBlock` | ✅ |
| 12 | Downloads | `DownloadsBlock` | ✅ |

Plus two shapes three blocks share: `ReportTable` (Breakdown · Reconciled · Row decisions) and
`ReportValueCell` (the eight-kind cell vocabulary).

### ⚠ Why `Records` is NOT built, and who owns it

**It is the only block that PAGES.** `NFR-3` makes every list server-paged with `per` clamped
50/100/200/500/1000, so it owns a request state, a toolbar, filters and a pager — and every one of those is a
question about a QUERY that the RENDERER holds and a block does not. Building it here with a state nothing
drives would be a component with props nothing passes: **dead UI that renders nothing while every test
passes**, which is hard-won law 2 and four defects in one day.

**It belongs to `C2`, which owns that state**, and `C2` starts from something rather than from nothing: the
payload shape (`RecordsPayload`, including its `display: "table" | "grid"` and its chips) is declared in
`blocks/types.ts`, and both of its unusual cells — `Sparkline` and `RecordGrid` — are built and in the kit.

**The absence has a TEST, not a comment.** `blocks/index.ts` exports `BLOCKS_BUILT`, and
`blocks/blocks.test.tsx` asserts it holds **eleven** and that the one name missing from `BLOCK_TYPES` is
exactly `records`. So the day `C2` lands it, that test goes red and names it — a stated absence with nothing
asserting it is a comment claiming a guarantee (hard-won law 1).

### The payload shapes are the front end's, by the backend's own decision

`06-backend/apps/runbooks/contract.py`'s `Block` says so: *"`payload` is whatever that block draws and is
deliberately untyped here: the twelve shapes are the renderer's (wave C) … What is typed is the NAME."*
`blocks/types.ts` is the other half, and `blocks.test.tsx` **reads `contract.py` and asserts the twelve names
match in order** — two declarations of one thing that can disagree, kept from disagreeing by a test, because
no tuple can be shared across Python and TypeScript.

### Three rulings this wave made, recorded rather than left to be re-derived

1. **A percentage's convention is a required argument.** The product stores percentages BOTH ways and `0.5`
   is ordinary under each reading (50.00% and 0.50%), so no heuristic decides it and getting it wrong is a
   factor of 100 on a money path. Decision log, 2026-09-06.
2. **A DECISION is not a row action.** B14 rule 15 says row actions are icons; `RBS-006-R20` draws *Accept
   theirs →* / *Keep ours* as text, because an icon cannot carry WHICH of two values is kept. A Records table
   may carry ONE decision column of text buttons where the choice is between named values — the precedent is
   Integrations' shipped `MappingRow` and `DecisionCard`. (Part 4 §3 asked for this to be written down; this
   is it.)
3. **A disabled action must say why, and the TYPE enforces it.** `ActionPayload` is a union where
   `enabled: false` requires `reason`, so `tsc` refuses a disabled control with no explanation.

### Still owed by a later wave

* **The Outcome box's word budget** (Part 4 §1: 28 boxes, 14–88 words, median 25.5, all over rule 33's cap).
  Owed by `C3`, which draws `RBS-004`'s Outcome box. `OutcomeCard` counts and truncates nothing on purpose.
* **`PlayIcon` (▶ run) and `ArrowRightIcon` (→ open)** (Part 4 §2) — two verbs outside rule 15's closed
  vocabulary, drawn 12 and 10 times, with no glyph in `icons.tsx`. They land with the first screen that
  presses them, not with the kit.
* **The coverage grid's RESULT frame**, which is undrawn — `RecordGrid` is built from `RBS-004-R24`'s one
  sentence and wave `F1` draws the frames.
