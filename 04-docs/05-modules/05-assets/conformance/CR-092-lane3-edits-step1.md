# CR-092 step 1 · lane 3 — Asset edits, what each pencil opens

**What this is:** the step-1 conformance read of the asset **edit surface** — blueprint
screens **14, 16, 17, 18, 19, 20, 21** — against the running product at
`claude/hi-0jmv62` @ `0a1a677d9`, version **2.237.0**.

**What this is not:** a fix. Step 1 identifies; step 2 fixes (`CR-092-BRC01` §6, PO ruling
2026-09-10). **Nothing in this lane changed a component, a catalogue, a route, a
stylesheet, a test, a rule, an epic, a question or the decision log.** It touched three
paths and every one of them is a finding: this document, the measurement that produced its
table (`10-scripts/render-checks/cr092-lane3-field-anatomy.mjs`, which reads and asserts
and writes nothing to the product), and **two appended rows** in the defect register —
appended through `10-scripts/file_defect.py`, and proved a pure append by
`diff <(head -c N 12-governance/10-defect-log.csv) <the tip's copy>` being empty.

**Specifications in scope:** `AST-B-12` · `AST-B-13` · `AST-B-25` · `AST-B-26`.
**Out of scope and never to be resurrected:** `AST-B-07`, `-08`, `-09`, `-17` (withdrawn)
and the Imports tab.

---

## 0 · How this was measured, so anyone can re-run it

```
# backend, against the existing seeded brazosbend database — READ ONLY,
# no form in this run was ever submitted
(cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
   python3 manage.py runserver 127.0.0.1:8471 --noreload &)
(cd 07-frontend && ./node_modules/.bin/vite build && \
   PORT=8472 API_PROXY_TARGET=http://127.0.0.1:8471 node server.mjs &)

SMOKE_BASE=http://127.0.0.1:8472 SMOKE_TENANT=brazosbend \
  PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
  node 10-scripts/render-checks/cr092-lane3-field-anatomy.mjs
```

* **Subject:** `M-7001` — an **active electric meter**, chosen by asking the server for a
  row whose action set carries `edit`, `retire` and `log_repair` **and that declares a
  service**, because `offersConnectionSize` gates the Connection-size field on exactly
  that and an asset without one would silently measure a shorter form.
* **Widths: 1280 and 1440.** Clerk and utility-admin are laptop and desktop, not mobile
  (PO 2026-09-10). **Every number below is identical at both** — the two generated tables
  differ in nothing but the width column.
* **Instrument:** `getComputedStyle` and `getBoundingClientRect` in Chromium, in the
  deployed join (`vite build` → `server.mjs` → `/api` pass-through), not the dev server.

**What would have made this measurement pass wrongly, and what was done about each.**
This is written out because the first run of the script produced **three wrong numbers**
and they looked exactly like findings:

| trap | what it did | the fix |
|---|---|---|
| a `.field` that renders `display:none` | measures 0 everywhere and reads as a perfect rhythm | hidden fields are excluded **and counted**, so an empty list cannot pass as a clean one |
| `querySelector("input")` inside a `SegmentedField` | the first `<input>` is a **radio inside a `.seg-opt` label**, inset by the seg's own padding — it reported **22.3px** for three fields, a number that is nobody's design decision | the control is the visible box: `.seg` when present, else the first `input`/`select`/`textarea`. **All three then measure 5px**, and the corrected figure is what this document carries |
| "the next field at the same left edge" | reported **53.69px** and **120.22px** — real distances across an intervening checkbox row and a nested grid, and not field-to-field gaps at all | field→field is measured **only between two `.field`s that are immediate siblings in one container and share a left edge**; everything else prints *why* it was not measured |
| reading DOM order from the source | would miss a CSS `order:` or `column-reverse` | the table carries the **painted** order (sorted by rendered `top`) beside the DOM order. They agree on all 29 fields |

Raw output: `fields.json` from the run above. The tables below are **generated** from it,
never typed.

**It was run three times.** The first produced the three wrong numbers above; the second
and third, after the corrections, produced a **byte-identical** 1280 table
(`diff` on the two logs is empty). A measurement quoted from one run is an anecdote.

---

## 1 · The measured table — 29 fields, 5 screens, identical at 1280 and 1440

Ratified figures (B14 **rule 39**, the PO's `R12`): **label → input 5px · input → helper
6px · field → field 20px**, a ratio of ≈ 1 : 1 : 4, and the order is
**label → input → helper**.

| screen | field | control | DOM order | painted order | label→input | input→helper | field→field | helper words |
|---|---|---|---|---|---|---|---|---|
| 14 Edit one asset (`AssetFormModal`) | Asset # | `input` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **28.59px** | n/a — the helper is **above** | **14px** | 12 |
| 14 Edit one asset | Device ID / serial # | `input` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **47.19px** | n/a — the helper is **above** | **14px** | 17 |
| 14 Edit one asset | Asset type | `select` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **28.59px** | n/a — the helper is **above** | **14px** | 9 |
| 14 Edit one asset | Meter type | `select` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **28.59px** | n/a — the helper is **above** | **14px** | 12 |
| 14 Edit one asset | Connection size | `select` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **47.19px** | n/a — the helper is **above** | **14px** | 36 |
| 14 Edit one asset | Read method | `select` | LABEL > INPUT | LABEL > INPUT | **5px** | — | **14px** | — |
| 14 Edit one asset | Unit of measure | `input` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **28.59px** | n/a — the helper is **above** | **14px** | 15 |
| 14 Edit one asset | Multiplier | `input` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **47.19px** | n/a — the helper is **above** | **14px** | 17 |
| 14 Edit one asset | Manufacturer / model | `input` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **28.59px** | n/a — the helper is **above** | _last field_ | 9 |
| 22 Reassign | Move to | `seg` | LABEL > INPUT | LABEL > INPUT | **5px** | — | **16px** | — |
| 22 Reassign | Unit | `input` | LABEL > INPUT | LABEL > INPUT | **5px** | — | **16px** | — |
| 22 Reassign | Effective date | `input` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **28.59px** | n/a — the helper is **above** | _not adjacent_ | 12 |
| 22 Reassign | Final register reading (kWh) | `input` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **47.19px** | n/a — the helper is **above** | _side by side_ | 19 |
| 22 Reassign | Read date | `input` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **47.19px** | n/a — the helper is **above** | _not adjacent_ | 12 |
| 23 Log repair | Type | `seg` | LABEL > INPUT | LABEL > INPUT | **5px** | — | _not adjacent_ | — |
| 23 Log repair | Date | `input` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **28.59px** | n/a — the helper is **above** | _side by side_ | 5 |
| 23 Log repair | Assign tech | `input` | LABEL > INPUT | LABEL > INPUT | **5px** | — | _not adjacent_ | — |
| 23 Log repair | Detail | `textarea` | LABEL > INPUT | LABEL > INPUT | **5px** | — | _not adjacent_ | — |
| 23 Log repair | Set status | `select` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **28.59px** | n/a — the helper is **above** | _side by side_ | 12 |
| 23 Log repair | Estimated cost | `input` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **47.19px** | n/a — the helper is **above** | _not adjacent_ | 16 |
| 24 Retire · 1 | Reason | `select` | LABEL > INPUT | LABEL > INPUT | **5px** | — | _side by side_ | — |
| 24 Retire · 1 | Retire date | `input` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **28.59px** | n/a — the helper is **above** | _not adjacent_ | 7 |
| 24 Retire · 1 | Final read (kWh) | `input` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **47.19px** | n/a — the helper is **above** | _side by side_ | 19 |
| 24 Retire · 1 | Read date | `input` | LABEL > INPUT | LABEL > INPUT | **5px** | — | _not adjacent_ | — |
| 28-31 Add an asset · 1 | Asset class | `seg` | LABEL > INPUT | LABEL > INPUT | **5px** | — | **16px** | — |
| 28-31 Add an asset · 1 | Asset # | `input` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **28.59px** | n/a — the helper is **above** | _not adjacent_ | 10 |
| 28-31 Add an asset · 1 | Asset type | `select` | LABEL > INPUT | LABEL > INPUT | **5px** | — | _side by side_ | — |
| 28-31 Add an asset · 1 | Read method | `select` | LABEL > INPUT | LABEL > INPUT | **5px** | — | _not adjacent_ | — |
| 28-31 Add an asset · 1 | Service | `input` | LABEL > HELP > INPUT | LABEL > HELP > INPUT | **28.59px** | n/a — the helper is **above** | _not adjacent_ | 14 |

**The totals, and they are the finding:**

* **18 of 18 helper fields paint `LABEL → HELP → INPUT`.** Not ten of eighteen — **every
  single field that has a helper**, on all five screens, including the edit dialog the
  blueprint never opened.
* **label → input is 28.59px** where the helper is one line and **47.19px** where it wraps
  to two. The arithmetic is exact and comes straight out of the stylesheet:
  `.field > label { margin-bottom: 5px }` (`FormModal.css:93`) + one helper line (18.59px) + `.field-help { margin: 0 0 5px }` (`:105`) = **28.59**; two lines (37.19px) = **47.19**.
* **label → input is 5px on 11 of 11 helperless fields.** Exactly right, on every one.
* **input → helper does not exist to measure.** Rule 39's 6px governs a gap that is not in
  the product: the helper is above the input on every field that has one.
* **field → field is 14px inside the dialog and 16px on the four full-page forms.
  Zero of the eleven adjacent pairs hit the ratified 20px.**

---

## 2 · `AST-B-13` / R12 — the blueprint's most checkable claim, checked

**The claim:** *"Ten of eighteen fields render label → helper → input. Measured
2026-09-11: on those, label-to-input is 29px or 47px, not 5 … The eight fields with no
helper are exactly 5px and correct — so the rhythm holds only where there is nothing to
get wrong."*

**VERDICT: the direction is right, the figures are right, and the scope is understated.**

| the blueprint | measured here | agree? |
|---|---|---|
| ten fields render label → helper → input | **eighteen** — and it is **18 of 18** fields that have a helper | **understated** |
| label-to-input is **29px or 47px** | **28.59px or 47.19px** | **yes**, to rounding |
| the helperless fields are **exactly 5px** | **5px on 11 of 11** | **yes**, and on three more fields than it counted |
| eighteen fields on those screens | **twenty** on the four full-page screens, plus nine in the dialog | the ten with helpers match **exactly**, field for field |

The ten fields the blueprint names — Add wizard: *Asset #*, *Service* · Reassign:
*Effective date*, *Final register reading*, *Read date* · Log repair: *Date*, *Set
status*, *Estimated cost* · Retire: *Retire date*, *Final read* — are **exactly** the ten
helper fields I measured on those four screens. Its count of helperless fields is two
short of the ten I find, and its "eight at 5px" is seven at 5px plus three `SegmentedField`s
it appears not to have counted, which also measure 5px.

**Where it understates:** the blueprint measured four full-page screens and did not open
the **edit dialog** — it says so honestly (*"The dialog it replaces was also not opened: it
needs a click on a row action and the walk drove by address"*). The dialog is screen 14's
as-built, it carries **eight more helper fields**, and every one of them is in the wrong
order too. The real figure for the asset edit surface is **eighteen**.

**This is not an assets defect and it is already filed.** The cause is one shared file:
`07-frontend/src/components/FormModal.tsx` renders `<label>` then `<p class="field-help">`
then the control in **all five field variants that accept a `help` prop** —
`TextField` (241) · `PasswordField` (311) · `SelectField` (363) · `DatePickerField` (624) ·
`SearchSelectField` (786) — and `field-help` is referenced by **24 non-test files**. It is
**`DEF-SHL-4921`** (open, `platform-shell`, filed 2026-09-11 by `CR-085` step 1 lane 1),
and B14 rule 39's own status cell already names it. **`AST-B-13` should be mapped onto
that row rather than given a new one**; a second row for the same fault in one module is
a duplicate, and the register already carries two thousand five hundred rows.

What `DEF-SHL-4921` does **not** carry is the asset-module consequence, which is §4 below.

**Escape reason, for the record:** the order of two elements inside a field wrapper is a
layout fact **no assertion in this repository looks at**. No gate reads `field-help` —
`grep -rl "field-help" 10-scripts/gates/*.py` returns nothing — `G105` compares screens
against drawings for the **portal only**, and `tsc`, eslint and every `toContain` case pass
whatever sequence the three elements are in.

---

## 3 · `AST-B-26` — the count, and where I disagree with the causal claim

### 3a · The count

Counted from `07-frontend/src/i18n/locales/en.json` against every `help={t("…")}` in the
fourteen non-test asset feature files:

* **34 occurrences · 29 distinct keys.**
* **Over ten words: 19 of 29 distinct** (24 of 34 occurrences).
* **Over eight words: 23 of 29 distinct** (28 of 34 occurrences).
* **The worst is 36 words** — `assets.form.sizeClassHelp`, which the blueprint also names,
  and which renders on **two** screens (the Add wizard and the edit dialog).
* Of the **18 helper fields actually rendered** in this run, **16 run over eight words** and
  **13 over ten**.

The blueprint says *"27 of 37 helper strings run over ten words, worst at 36"*. **The
worst matches exactly.** The 37 and the 27 do not reproduce from the catalogue at this tip
— I find 34 occurrences / 29 distinct, and 24 / 19 over ten. The gap is a counting
boundary, not a disagreement about the copy: whatever set it counted, the copy is long and
the worst string is the same one.

⚠ **The blueprint contradicts itself on the threshold.** Its register row states *"A helper
line is **eight** words or fewer"*; its own specification block states the work as
*"27 of 37 helper strings … rewritten to **ten** words or fewer"*. On today's rendered set
the two differ by three fields.

⚠ **AND NEITHER IS A RULE THIS REPOSITORY HOLDS.** *"Six to eight words"* appears nowhere
in `04-docs` or `12-governance`. **The citable cap is B14 rule 33** (RATIFIED 2026-08-30),
and it is a better rule than either number because **its unit is the SENTENCE, not the
string**: a field's helper is an INSTRUCTION — *"what to type, what to do next"* —
capped at **six words per sentence**, with the rule's own clause that *"two sentences of
six beat one sentence of twelve"*. Rule 18's 80% is a WIDTH cap on a screen description
and does not reach a helper; rule 32's budget is one sentence per SECTION.

**Counted against the rule that exists** (`re.split` on sentence ends, worst sentence per
helper):

| | rendered on these five screens | distinct keys in the module |
|---|---|---|
| helper fields | **18** | **29** |
| with a sentence **over six words** — rule 33 breached | **16** | **26** |
| over eight words as a whole string | 16 | 23 |
| over ten words as a whole string | 13 | 19 |
| worst single **sentence** | **19 words** — `assets.reassign.finalReadHelp` | same |
| worst whole **string** | **36 words** — `assets.form.sizeClassHelp` | same |

**The two ways of counting disagree in both directions, which is why the rule matters.**
The Add wizard's *Asset #* helper is **ten words in two sentences of five** — lawful under
rule 33, over the blueprint's ten-word budget. Retire's *Retire date* helper is **seven
words in one sentence** — under both of the blueprint's budgets and **a breach of rule
33**. Step 2 should count sentences, cite rule 33, and stop quoting a word budget that was
never ratified.

### 3b · The causal claim, and it is backwards

**The claim:** *"it is the cause of the field misalignment rather than a separate
defect"*, and *"the alignment defect and the copy defect are the same defect, and
shortening the sentence fixes both."*

**I disagree, and the measurement settles it.** Here is every side-by-side row in the
module, at both widths:

| screen | the row | left (helper words · label→input) | right | same baseline? |
|---|---|---|---|---|
| 22 Reassign | Final register reading + Read date | 19w · 47.19px | 12w · 47.19px | **yes** |
| 23 Log repair | Date + Assign tech | 5w · 28.59px | 0w · 5px | **NO** — 23.59px apart |
| 23 Log repair | Set status + Estimated cost | 12w · 28.59px | 16w · 47.19px | **NO** — 18.6px apart |
| 24 Retire · 1 | Reason + Retire date | 0w · 5px | 7w · 28.59px | **NO** — 23.59px apart |
| 24 Retire · 1 | Final read + Read date | 19w · 47.19px | 0w · 5px | **NO** — 42.19px apart |
| 28-31 Add · 1 | Asset type + Read method | 0w · 5px | 0w · 5px | **yes** |

Three things follow, and each is measured rather than argued.

**(1) The blueprint's own worked example does not reproduce.** `AST-B-26` says *"On
Reassign, Final register reading and Read date sit side by side … Today the left helper
runs to two lines and the left input sits a line lower than the right one."* **They are on
the same baseline** — identical `top` (530.03), identical `bottom` (631.81), identical
label→input (47.19px), at 1280 **and** at 1440. Both helpers wrap to two lines in a 390px
column, so they wrap *equally* and the row lines up. The misalignment is real at some
width; it is not real at either of the two widths this audience uses.

**(2) Shortening the copy would BREAK that row.** Cut the 19-word *Final register reading*
helper to eight words and it stops wrapping; the 12-word *Read date* helper still wraps at
390px; the row that lines up today comes apart. A word budget applied to one field of a
pair is a new misalignment, not a fix.

**(3) Three of the four misaligned rows cannot be fixed by any word budget at all**,
because the break is one field having a helper and its neighbour having none — *Date* (5
words) against *Assign tech* (none); *Reason* (none) against *Retire date* (7 words);
*Final read* (19 words) against *Read date* (none). **Five words and seven words already
break a row.** Only *Set status + Estimated cost* would be fixed by an eight-word cap.
**Shortening the copy fixes one of the four misaligned rows in the module. Moving the
helper below the input fixes all four, at every width, for every future string.**

**The repository already recorded the correct causal direction, a week earlier and on a
different screen.** `DEF-2376` (fixed, audit, 2026-09-02) — *"S61 audit log: the filter row
is out of line — a three-line helper pushes the Action code box off the baseline"* — states
its escape reason as: *"the field kit puts help text **BETWEEN** the label and the input,
**so** a long helper moves only its own box down."* The order is the cause; the length is
the trigger.

**So `AST-B-26` is a real and worthwhile copy defect on its own merits** — **16 of 18
rendered helpers breach B14 rule 33**, one carries a 19-word sentence and one a 36-word
string holding three separate facts. **It is not the cause of the alignment defect
and must not be scheduled as the fix for it.** If step 2 ships the copy alone, four
misaligned rows become three, one aligned row becomes misaligned, and `AST-B-13` is still
open — at the price of eleven catalogues of translation.

---

## 4 · Field → field: the ratified 20px appears nowhere, and rule 39 disagrees with itself

Measured on the eleven pairs where two `.field`s are immediate siblings sharing a left edge:

| container | measured | source |
|---|---|---|
| the edit dialog | **14px** | `.modal-body { gap: 14px }`, `FormModal.css:78-83` |
| Reassign · Log repair · Retire · Add wizard | **16px** | `flex flex-col gap-4` on each form body |
| anywhere | **20px** | **zero pairs** |

The 14px half is already in `DEF-SHL-4921`, which notes that 14 is one of the four numbers
rule 39 forbids by name (*"NO AD-HOC 3 / 7 / 9 / 14 ANYWHERE"*).

⚠ **The 16px half is NOT a defect on the rule as written, because B14 rule 39 states both
figures.** Its ratified scale reads *"`--sp-4` **16px between fields**, between blocks"*
and its field anatomy reads *"field → field **20px**, a ratio of ≈ 1 : 1 : 4"*. **Those
are the same measurement with two values, inside one rule.** The four asset full-page
forms are compliant with one half and not the other, and no lane can tell which without a
ruling — which is exactly the shape the PO already had to settle once inside this rule,
when the KPI gap was ratified at 6 and 6 is not a step of the scale (*"One off-scale value
invites the next one. 8 is the nearest step and nobody will see 2px."*).

**No defect is filed for the 16px.** This is a question for the PO and a question is a
register row, which step 1 may not write. **Step 2 should mint it** and put it in plain
English with the figure: *between two fields, is the gap 16px or 20px? Rule 39 says both.*

---

## 5 · `AST-B-12` — an asset can be corrected from the asset, at an address

**Everything the specification asserts about today is true. Verified four ways.**

| the claim | evidence |
|---|---|
| there is no `/assets/{id}/edit` route | `App.tsx` declares **six** `/edit` routes — two routes-and-cycles, plan, rate schedule, charge code, discount — and **none under `assets`**. `grep -rn "assetId}/edit" 07-frontend/src` returns nothing |
| there is no Edit control in the header | `AssetDetailPage.tsx` contains **three** occurrences of the string `edit`, **all three in comments**. In the browser the header offers `← Assets · Reassign · Log repair · Retire` and nothing else, and **0 controls anywhere on the page have an accessible name containing "edit"** |
| `PATCH /assets/{id}` already validates a partial payload | `apps/assets/services.py:1203` `update_asset` → `_validate_asset(data, partial=True, current=asset)`; the view accepts `GET, PATCH, DELETE` and **no `PUT`** (`apps/assets/api.py:138`) |
| a retired asset must show no pencil | `selectors.row_actions` returns `["view"]` for `TERMINAL`, and `update_asset` tests `STAGE_TERMINAL` and raises `BIZ_IMMUTABLE` **before it validates anything**. The two halves agree |

**Two things the blueprint does not say, and step 2 should have both.**

**(a) The asset detail page is the odd one out in its own module.** `PremisesDetailPage.tsx`
(`:956`) and `UnitDetailPage.tsx` (`:506`) both carry `metering.action.edit` in their
header's `secondaryActions`. Premises, unit and asset are three detail screens of one
module; two of the three can be corrected from where you are standing. That makes the
missing header control a **consistency defect**, whatever one calls the new route.
`CR-092-BRC01` §1 classifies `AST-B-12` as a CHANGE, which is right about the route; the
header control is the half that is already promised by its neighbours.

**(b) The one edit door in the product is reached from a table row and nowhere else.**
`AssetFormModal` in `AssetRegistryPage.tsx:1165` is the **only caller of `updateAsset` in
the whole front end** — the file's own comment says so and `grep` confirms it. A clerk
reading a wrong multiplier on the detail page must leave the asset, find its row in a
paginated registry, and press a pencil.

**Also true, and not a defect:** `row_actions` omits `edit` for `out_of_service`, so an
asset marked needs-repair cannot be corrected from any screen even though the server would
accept the PATCH. BR-AST-006 sources those sets from the prototype, so this is reported,
not filed.

---

## 6 · `AST-B-25` — each Overview pencil opens a dialog that edits only its own panel

**What each pencil does today: there are no pencils.** Measured in the browser on
`M-7001`: **0 controls on the detail page have an accessible name containing "edit"**, and
the Overview draws **four** panels — `Specifications`, `Assignment`, `Warranty & supplier`,
`Lifecycle` (a fifth, `Test & certification`, renders only on a device with a test
cadence). None of them carries an edit affordance. The only controls inside the panels are
`Reassign →` on Assignment and `Log test` on Test & certification, and both **navigate to a
full page**.

**The server side of the specification is confirmed exactly as written.** `_validate_asset`
accepts **39** field names on a partial payload — including `external_ref`, `purchase_date`,
`purchase_cost`, `supplier`, `depreciation_method`, `expected_life_years`, `location_note`,
`test_interval_months`, `certification_due`, `register_digits`, `allocation_share_pct`,
`allocation_rule`, `loss_tolerance_pct`, `install_date`, `firmware_version`, `seal_no`,
`form_class`, `warranty_end` and `last_test_date`. **The one edit door in the product sends
seven:** `serial_no`, `read_method`, `manufacturer_model`, and conditionally `meter_type`,
`unit`, `multiplier`, `size_class`. Nothing on the server has to change for six dialogs.

**⚠ AST-B-25 is not buildable against today's panels.** The blueprint's six pencils sit on
*What's due*, *Measurement*, *Device*, *Cost & value*, *Lifecycle* and *Assignment* — a
panel set that **does not exist**. Today's four panels cut the same facts differently and
there is no Cost & value panel at all; the money facts live inside `Warranty & supplier`.
The re-cut is blueprint **screen 08**, which is a different lane's scope. **Step 2 must
sequence screen 08 before screens 16–21**, or the six dialogs will be hung on panels that
are not there.

### The two fields the specification says become typable for the first time

**`external reference` — the claim holds, with one correction.** `selectors.asset_dict`
serves `external_ref` on every asset (`selectors.py:274`); the front-end `AssetRow` type
does not declare it; no asset screen writes it and no asset screen shows it. **The
correction: the ASSET IMPORT writes it** — `BR-AST-049(e)` puts the utility's own legacy
number there and `import_rules.py` maps it. So the honest sentence is *"no **screen**
writes it, and none shows it back"*, not *"no surface writes it"*. A utility that migrated
by file has the value stored and invisible; a utility that adds an asset by hand can never
record it at all.

**`purchase date` — the claim is wrong, and what is actually true is worse.**
`purchase_date` **is typable today**, in the Add wizard's step 4, as an enabled
`DatePickerField` (`AssetAddWizard.tsx:1060`). What it is not is **visible** or
**correctable**: the `Warranty & supplier` panel draws supplier, purchase cost, present
value, warranty term and cover ends and **not the purchase date**, and no edit surface
sends the field. So a clerk types a date once, at create, and can never see it again or
fix it — while `age_months`, `accumulated_depreciation` and `present_value` are all
computed from it and **are** shown. **That is a defect, and it is filed below.**

---

## 7 · What this lane found that the blueprint does not carry

### 7a · The edit dialog's **Asset type** control changes nothing — filed

`AssetFormModal` renders `Asset type` as a **required, fully interactive** `SelectField`
with the help *"Changing the type moves this asset to another tab."*
(`AssetRegistryPage.tsx:1291-1299`). Its `submit()` builds the payload in one place and
**`type` is never put in it** (`:1216-1253`). `FormModal` validates `values` against
`assetSchema` — which marks `type` required — and then calls the consumer's `onSubmit`,
so the value is validated and discarded. A clerk changes the type, presses **Save**, gets
the success toast, and the asset's type is unchanged. Worse: selecting a non-measuring
type flips `measuring` to false, which **also drops `meter_type`, `unit` and `multiplier`
from the payload**, so the save silently writes three fields instead of seven.

**Nothing could have caught it.** The only test that mounts `AssetFormModal`
(`AssetSizeDoors.dom.test.tsx:401`) never submits it — `grep` for a save assertion in the
asset test files returns nothing — so the payload has no assertion anywhere in the repo.

### 7b · Purchase date is write-once, invisible and uncorrectable — filed

See §6. Typed on the Add wizard, accepted by `PATCH`, drawn by no screen, sent by no edit
surface, and the input to three figures that **are** drawn.

### 7c · The blueprint's screen-14 field list is wrong on three of nine

Its card says the field set *"is read from `AssetRegistryPage.tsx`'s `AssetFormModal`"*.
The count matches — nine controls render on a meter that declares a service — but the
membership does not:

| the blueprint's screen 14 | the as-built `AssetFormModal` |
|---|---|
| `Location note` | **absent.** `location_note` appears in this file **zero** times |
| — | `Manufacturer / model` — **present**, and not on the blueprint's list |
| `Asset # *`, editable, with *"a duplicate asset number is a hard block under the field"* | **`readOnly`**, helped by *"The asset number identifies this record everywhere and is not edited here."* The refusal the blueprint lists as a state **cannot be reached from this screen** — the server implements it (`BR-AST-033`, `update_asset:1232`), nothing can trigger it |

This matters for step 2 because the blueprint's carry-over table reconciles
*"as-built 11 → remedy 11"* on a field set that is not the as-built one.

### 7d · `AssetLifecycleModals.tsx` contains no modals

The brief warned not to trust the filename and it was right. The file holds schemas,
stage-transition logic, option builders and mutation hooks — **zero JSX components**. The
modals it was named for were retired by `CR-028 AST-W4`. The edit dialog is
`AssetRegistryPage.tsx:1165`; `AssetFlowPages.tsx` holds Reassign and Log-repair as
**full pages**, not dialogs.

### 7e · B14 rule 7 is unmet at the component, not at the screen

`DatePickerField` declares no `min`, no `max` and no Today shortcut — the prop does not
exist on the component, so no asset screen could pass one. Five date fields render across
the four full-page screens — Reassign's *Effective date* and *Read date*, Log repair's
*Date*, Retire's *Retire date* and *Read date*; the dialog has none — and not one has a
bound or a Today shortcut, including *Retire
date*, whose own helper promises one (*"Any current assignment closes on this date."*, and
the blueprint quotes *"Cannot be before the install date"* from the drawing). Reported
here because the fix is in the shared kit, alongside `DEF-SHL-4921`, and not in this
module.

---

## 8 · Where I disagree with the blueprint, in one list

| # | the blueprint | this lane |
|---|---|---|
| 1 | `AST-B-13`: *"ten of eighteen fields"* | **eighteen of eighteen** helper fields, across five screens. Ten is the count on the four screens it walked; it did not open the edit dialog and says so |
| 2 | `AST-B-13`: *"the eight fields with no helper are exactly 5px"* | **eleven of eleven** are exactly 5px, `SegmentedField`s included |
| 3 | §09 exemption: *"Field-to-field spacing is correct … takes its 20px from the form grid's gap"* | **zero of eleven** adjacent pairs measure 20px. 14px in the dialog, 16px on the full-page forms. `margin-bottom: 0` is true; the 20px is not |
| 4 | `AST-B-26`: the long copy *is the cause* of the misalignment | **backwards.** The cause is the helper's position; the length is the trigger. `DEF-2376` recorded the same direction on 2026-09-02 |
| 5 | `AST-B-26`'s worked example: Reassign's two inputs sit a line apart today | **they sit on the same baseline** at 1280 and 1440 — identical `top`, `bottom` and label→input. Shortening one helper would break the row |
| 6 | `AST-B-26`: *"27 of 37 helper strings over ten words"* | **24 of 34 occurrences / 19 of 29 distinct keys** from the catalogue at this tip. **The worst, 36 words, matches exactly** |
| 7 | `AST-B-26`: **eight** words (register) vs **ten** words (spec block) | the document states both, and **neither is ratified anywhere**. *"Six to eight words"* is in no repo file. **B14 rule 33** is the citable cap and counts **sentences**: **16 of 18** rendered helpers breach it, worst sentence **19 words** |
| 8 | `AST-B-25`: *"external reference and purchase date … typable for the first time"* | **purchase date is typable today** on the Add wizard. It is **invisible and uncorrectable**, which is a different and worse fault. `external_ref` is written by the **import** |
| 9 | screen 14's field list *"read from `AssetFormModal`"* | wrong on three of nine — see §7c |
| 10 | closing paragraph: *"Twelve live specifications"* | **24**, counted from the document's own markup: 24 `spec-AST-B-##` blocks, 24 register rows linking to one, 4 struck. `CR-092-BRC01` §4 already says so; confirmed independently |
| 11 | §09 R11: the KPI anchor *"16×20 gap 6 ✓"* is counted as conforming | **measuring against a superseded figure.** Rule 39's KPI anchor was amended from **6 to 8** on the day it was ratified (PO: *"One off-scale value invites the next one. 8 is the nearest step and nobody will see 2px."*). Not measured by this lane — the edit surface has no KPI strip — and **already filed by `CR-092` lane 6 as `DEF-SHL-4949`**, so no second row. Recorded here because it means the blueprint's list of anchors it judges CORRECT is **one shorter than it says** |

**Where it is right and it is worth saying so:** the R12 direction, the 29/47 figures, the
5px on helperless fields, the worst helper at 36 words, the absent route, the absent header
control, the partial-payload endpoint, the terminal-state refusal, the *"no pencil at all"*
on a retired asset, and all fourteen asset feature files being on `route-b-migrated.txt`.
**Every as-built statement in §3 of the CR held.**

---

## 9 · Defect rows this lane filed

| id | `AST-B-##` | what |
|---|---|---|
| `DEF-MET-4971` | context for `AST-B-25` | the edit dialog's **Asset type** select is validated and never sent — a live control over a dead write |
| `DEF-MET-4972` | context for `AST-B-25` | **purchase date** is typed once on the Add wizard and can never be seen or corrected, while three figures computed from it are drawn |

⚠ **BOTH IDS WERE RENUMBERED TWICE, AND BOTH TIMES THE CHECK IS WHAT FOUND IT.**

**First:** allocated as `DEF-MET-4946` / `-4947` against a worktree pinned at `0a1a677d9`.
While this lane worked, siblings pushed **`DEF-SHL-4946` through `DEF-MET-4964`**, so
`10-scripts/allocate.py defect --verify 4946` answered **TAKEN — a sibling pushed it**.
The register was rebuilt byte-for-byte from the live tip and the rows re-filed as
`DEF-MET-4965` / `-4966`.

**Then it happened again, and this is the race `allocate.py` says in its own docstring it
cannot prevent:** *"nothing writes to the remote, so two lanes calling it in the same
second still collide."* `CR-092` **lane 2** filed `DEF-MET-4965` and `-4966` minutes later
against the same maximum. Both lanes' arithmetic was right; the register published **four
rows under two numbers** and every gate except `G17` read it as a register. Found by
re-reading the pushed register after the push — `grep -c '^"DEF-MET-496[56]"'` returned
**4** where **2** was expected. Lane 2 keeps its contiguous block `4965`–`4970`; **this
lane moved to `DEF-MET-4971` and `DEF-MET-4972`** by splicing the id column of its own two
lines, byte-for-byte, with the line count and the file length asserted unchanged.

**The lesson is the one law 11 already states and it is worth one more line:** a verify at
push time removes the STALE read, which is the common case, and catches the simultaneous
one only if somebody looks at the register **after** the push. `grep -c` on your own ids,
once, is the whole check.

**Filed nowhere, deliberately, and each with its reason:**

* **`AST-B-13`** → **`DEF-SHL-4921`**, open, already covers the cause and is broader. A
  second row for one module would be a duplicate.
* **field → field 16px** → **B14 rule 39 states 16 and 20 for the same measurement.** A
  question for the PO, and a question is a register row step 1 may not write.
* **`AST-B-12`, `AST-B-25`, `AST-B-26`** → classified as work under this CR by
  `CR-092-BRC01` §1. Their evidence is above; their rows or stories belong to step 2.
* **rule 7's missing date bounds** → the shared kit, beside `DEF-SHL-4921`.
* **the KPI anchor's superseded `gap: 6`** → `DEF-SHL-4949`, filed by `CR-092` lane 6. Not
  this lane's surface and not this lane's row.

---

## 10 · What step 2 needs from this lane, in order

1. **Fix the order in `FormModal.tsx`, not the copy.** Five variants, one file, and it
   repairs all eighteen fields and four of the four misaligned rows at once.
2. **Sequence screen 08 before screens 16–21.** The six pencils need panels that do not
   exist yet.
3. **Count sentences against B14 rule 33, not words against a budget nobody ratified**,
   and apply the result to *all* fields of a side-by-side row or to none of them.
4. **Ask the PO whether field-to-field is 16 or 20**, in plain English with the figure.
5. **The two filed defects are independent of all of the above** and can land first.

---

## Trace

* **Source:** artifact `2f979496-886a-47a2-a125-69035d1b3bff`, *The Assets menu, screen by
  screen* — §04 *Asset edits* (screens 14, 16–21), §09 rows R12 / rule 7 / R11, and the
  `AST-B-12`/`-13`/`-25`/`-26` specification blocks.
* **Measured against:** `claude/hi-0jmv62` @ `0a1a677d9`, version `2.237.0`, Chromium at
  `/opt/pw-browsers`, tenant `brazosbend`, subject `M-7001`, widths 1280 and 1440.
* **Instrument:** `10-scripts/render-checks/cr092-lane3-field-anatomy.mjs` (added by this
  lane; it reads and asserts, and writes nothing to the product).
* **Reproducibility:** three runs; runs 2 and 3 produced byte-identical tables.
* **Rules:** B14 **rule 39** (the PO's `R12`) · B14 **rule 33** (the citable text cap) ·
  B14 rule 7 · B14 rule 32 · `BR-AST-006` ·
  `BR-AST-012` · `BR-AST-033` · `BR-AST-044` · `BR-AST-047` · `BR-AST-049` · `BR-AST-500`.
* **Related rows:** `DEF-SHL-4921` · `DEF-2376` · `DEF-CWP-4856` · `DEF-CWP-4872` ·
  `DEF-SHL-4949` · `DEF-515` (the mirror shape `_validate_asset`'s own comment records).
* **Process:** `CR-092-BRC01` §6 · `12-governance/13-change-process.md` ·
  `04-docs/02-decisions/12-engineering-plan.md` Addendum r11 · CLAUDE.md hard-won laws
  2, 6, 7, 11, 12, 13.
