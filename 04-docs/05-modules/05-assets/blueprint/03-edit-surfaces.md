# Assets blueprint § 04 — the edit surfaces (screens 14–21) measured against the code

**What this file is.** One section per screen, saying what the blueprint DRAWS, what the
product DOES today, and every difference between them with a class and a verdict on
whether it is already fixed. It measures and routes. **It builds nothing and it changes
no product code.**

**Read at** product version `2.261.3`, branch tip `11307c79`, 2026-09-13.
The blueprint was read at `2.234.17` / `79c659d7` on 2026-09-10–11, so **every as-built
sentence in it is a hypothesis** (its own page 2 says so) and every one below has been
re-checked against the code on this branch.

---

## How the drawing was read — B14 rule 42, and one correction from the coordinator

Every drawn fact below comes from **the PDF page image**, rendered with
`10-scripts/pdf/pdf_render.py` from `05-prototype/01 Assets Menu Blueprint.pdf` and
opened with the Read tool:

```
python3 10-scripts/pdf/pdf_render.py "05-prototype/01 Assets Menu Blueprint.pdf" /tmp/laneC 2 66,...,84
```

Pages opened as images: **66, 67, 68, 69, 70, 71, 72, 73, 74, 75 (also at scale 4), 76,
77, 78, 79, 80, 81, 82, 83, 84**, plus **139, 158, 159, 160, 161, 209, 210** for the
remedy rule, the commitment cards and appendix K. That is 26 page images.

**The text extractor was not used as a specification anywhere in this file**, per B14
rule 42 (PO 2026-09-13: *"When you use images to create screens your accuracy is higher;
hence dont create screens using only Text"*).

⚠ **Two repo files that are DERIVED copies of these wireframes were NOT used as the
specification** — `04-docs/05-modules/05-assets/wireframes/CR-092-assets-screens.html`
(an HTML re-drawing) and `04-docs/05-modules/05-assets/08-screen-layouts.md` (a prose
index). Hard-won law 5: one source, never a second copy.
**Nothing in this file was corrected after that instruction arrived, because nothing had
been taken from either file.** `08-screen-layouts.md` was read once, afterwards, for
**build history only** — the two facts quoted in the summary below (screen 14 shipped in
`2.239.9`; `DEF-AST-5107` is open against its field table). No layout, field, label,
column or ordering came from it.

---

## The two halves of the document, and which one is the target

* A **grey-rail description** states what the code did on 2026-09-10. It commits nobody.
* A **red accent card** (`AST-B-nn`) is a commitment. That is the target.
* Where a screen carries an as-built AND a redrawn figure, the redrawn one is the target.

Screens 14 and 16–21 carry **NEW BUILD** and are drawn to the rules rather than read off
the code, so **their figures ARE the specification**. Screen 15 is EXISTS BEHIND with
**NO COMMITMENT**, so its figure is a description and nothing here proposes to change it.

Commitments in scope, quoted from the cards on pages 69–70, 84 and 158–161:

| id | what it promises | screens |
|---|---|---|
| `AST-B-12` | *"An asset can be corrected from the asset, at an address."* | 08, 14 |
| `AST-B-13` | *"Every hint says which input it belongs to."* | 14, 16–21, 23 |
| `AST-B-25` | *"Each Overview pencil opens a dialog that edits only its own panel."* | 16–21 |
| `AST-B-26` | *"A helper line is eight words or fewer."* | 14, 16–21, 22–27, 28–32 |

---

## Screen 14 · Edit one asset — pages 66–69, figure 21

Route drawn: `/:tenant/assets/{assetId}/edit` — *"a full page, replacing today's dialog"*.
Chips: **NEW BUILD · COMMITMENT 12 · 13 · 26**.

### What the image shows

Page head: back link **← Asset**, kicker **ASSETS · METER**, title **Edit E-5000**.
No actions on the right of the head. One lead line: *"Correct what was recorded when this
meter went in."*

Nine fields in a **two-to-a-row grid**, in this drawn order, left column first:

| row | left | right |
|---|---|---|
| 1 | **Asset #** `*` — value `E-5000`, no helper | **Serial #** — `81-44120`, helper *"A duplicate is allowed, and warned about."* |
| 2 | **Asset type** `*` (select, `Meter`) | **Meter type** (select, `Walk-by`) |
| 3 | **Read method** (select, `Manual`), no helper | **Connection size** (select, `5/8"`), helper *"What a rate ladder that prices by size charges off."* |
| 4 | **Multiplier** `*` (`1`), no helper | **Unit of measure** `*` (`kgal`), helper *"Always explicit. Never assumed."* |
| 5 | **Location note** — FULL WIDTH, placeholder *"Where a crew will find it"*, helper *"Up to 280 characters. A note, not an address — the address lives on the premises."* | |

Then a **red-bordered consequence box** headed `FORWARD ONLY`, below the fields and above
the buttons: *"Multiplier, unit of measure, net metering and service apply from now on
once this asset has reads. Nothing already billed changes."*

Footer, **right-aligned**: **Cancel** then **Save ✓** (Save is the primary).

Four helpers are drawn and only four. Asset #, Asset type, Meter type, Read method and
Multiplier carry none.

⚠ **The orange `SET ▸ ASSET_TYPES`, `SET ▸ METER_TYPES`, `SET ▸ READ_METHODS`,
`SET ▸ SERVICE_SIZE_CLASSES` badges beside four labels, and the small numerals 1–4 in the
left margin, are DOCUMENT ANNOTATIONS, not screen chrome.** They are appendix L's
"where do this drop-down's options come from" apparatus. Building them would put a
database table name on a clerk's screen, which **B14 rule 31 forbids by name**. The code
correctly renders neither.

### What the code does today

`07-frontend/src/features/assets/AssetEditPage.tsx` — 574 lines, on the migration ledger
(`07-frontend/src/styles/route-b-migrated.txt:3544`).

* Route registered: `07-frontend/src/App.tsx:1105` — `assets/:assetId/edit` → `AssetEditPage`.
* Door 1, the registry pencil: `AssetRegistryPage.tsx:681` navigates (it opens no dialog).
* Door 2, the asset's own header: `AssetDetailPage.tsx:554–559`, a `GuardedButton`
  labelled `assets.action.edit` = **"Edit"**, shown only when the server's action set
  carries `edit`.
* Shell: `AssetFlowPages.tsx:137–207` — `PageHeader` with `backTo` = **"Asset"**,
  kicker = `assets.kicker` + `type_name` = **"Assets · Meter"**, title 32px via
  `[&_h1]:text-h2` (B14 rule 40), body `flex max-w-3xl flex-col gap-5`.
* Form: `AssetEditPage.tsx:318` — `grid grid-cols-2 gap-5 max-md:grid-cols-1`, i.e. two
  to a row at 20px both ways (B14 rule 39).
* Fields in code order: `asset_no` (**readOnly**, 323) · `serial_no` (334) ·
  `type` required (344) · `meter_type` *measuring only* (356) · `size_class`
  *on-the-connection only* (388) · `read_method` (399) · `unit` required (412) ·
  `multiplier` required (424) · `manufacturer_model` **full width** (436–446).
* Consequence: `<Note>{assets.form.forwardOnlyNote}</Note>` at line 450.
* Footer: line 454 — `mt-2 flex gap-2 border-t-2 border-divider pt-4`, then
  **Cancel** (ghost) and **Save asset** (`WorkingButton`).
* Write: `updateAsset(asset.id, payload)` → `PATCH /assets/{id}`.
  **Verified on the server:** `06-backend/apps/assets/api.py:158` declares
  `@api_view(["GET","PATCH","DELETE"])` — there is no PUT — and
  `06-backend/apps/assets/services.py:1321` calls
  `_validate_asset(data, partial=True, current=asset)`. **The blueprint's claim that the
  endpoint already takes a partial payload is TRUE today.**
  Role gate `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` at `services.py:1294`.

### Gaps

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| the screen itself | a full page at `/assets/{id}/edit`, two doors | exists, routed, both doors wired | — | **YES — shipped `2.239.9`.** `AST-B-12` is discharged |
| tenth field | **Location note**, full width, last | **Manufacturer / model**, full width, last | CONTENT | No — open as `DEF-AST-5107`. A SWAP, so the carry-over arithmetic on p69 (`11 = 11 − 1 + 1`) cannot see it |
| Asset # editability | editable, required `*` | `readOnly` (line 325) | CONTENT | No |
| duplicate-number refusal | *"a duplicate asset number is a hard block under the field"* (p68) | unreachable from this form — the field cannot be typed | WIRING | No. The server still enforces it (`services.py:1324–1332`); the screen state the drawing names cannot occur |
| Serial # label | **Serial #** | **Device ID / serial #** (`assets.form.serial`) | CONTENT | No |
| field order rows 3–4 | Read method \| Connection size, then Multiplier \| Unit of measure | Connection size before Read method; Unit of measure before Multiplier | LAYOUT | No |
| helper count | 4 helpers drawn | **8 helpers rendered** | CONTENT | No — four fields gained a helper the drawing does not give them |
| the 36-word helper | *"What a rate ladder that prices by size charges off."* (10 words) | `assets.form.sizeClassHelp` — **36 words, three sentences** | CONTENT | **No. This is AST-B-26's named worst case and it is still 36 words in the product** |
| forward-only box | a red-bordered **consequence box** headed `FORWARD ONLY` | a plain `<Note>` paragraph (line 450) | LAYOUT | No. `ConsequenceBox` is in the kit (`components/ConsequenceBox.tsx`) and B14 rule 11 asks for one here |
| footer alignment | right-aligned | left-aligned (`flex gap-2`, no `justify-end`) | LAYOUT | No — see the rule-38 section |
| commit label | **Save ✓** | **Save asset**, no glyph | CONTENT | No. B14 rule 4 wants `Verb ✓`; `WorkingButton` appends nothing, the label must carry it |
| lead line | *"Correct what was recorded when this meter went in."* (9 words) | *"Correct what was recorded."* (4 words) | CONTENT | Deliberate — rule 33 beat the drawing. See the rule-38/41 section |
| content width | the form spans ≈875px of a 1440 frame | `max-w-3xl` = 768px | LAYOUT | Unverified — measured off a scaled image, needs a browser. **Do not act on this without measuring** |

**Three biggest:** the field swap (`DEF-AST-5107`), the 36-word helper still live, and
the read-only Asset # that makes a drawn refusal state unreachable.

---

## Screen 15 · Delete this asset? — pages 70–71, figure 22

No address of its own — a confirm on `/:tenant/assets` and `/:tenant/assets/{id}`.
Chips: **EXISTS BEHIND · NO COMMITMENT**. **This is a description. Nothing here is a
target and nothing below should be built without a new ruling.**

### What the image shows

A small centred dialog. Title **Delete AST-04412?** Body, two sentences: *"This removes
the asset completely. Only an asset that has never been installed and has no history
against it can be deleted; anything else is retired instead."* Footer right-aligned:
**Cancel** then **Delete** in the danger tier. No fields, no kicker, no close glyph drawn.

### What the code does today

Two call sites, identical props:
`AssetRegistryPage.tsx:1135–1147` (the trash row action) and
`AssetDetailPage.tsx:650–658` (the header **Delete** button). Both use the shared
`ConfirmDialog` with `confirmVariant="danger"` — B14 rule 6, which is one of the few
rules **enforced on rendered output** (DEF-718).
Server: `DELETE /assets/{id}` → `services.delete_asset`, `@require_role(SYSTEM_ADMIN)` at
`services.py:1389`, which re-probes every referencing table before deleting
(`services.py:1405–1412`).

### Gaps

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| title | **Delete AST-04412?** | **Delete asset AST-04412?** | CONTENT | n/a — no commitment. The code's form satisfies BR-SHL-032 more fully |
| confirm label | **Delete** | **Delete asset** | CONTENT | n/a |
| body length | 2 sentences, 32 words (12 + 20) | 3 sentences, **38 words** (6 + 26 + 6) | CONTENT | No. **Both break B14 rule 33** (a consequence: ≤6 words per sentence, at most two). The code is the worse of the two |
| rationale on screen | — | *"the server checks all of those again before deleting"* | CONTENT | No. Rule 33: rationale is **zero words on screen** |

**Three biggest:** the 26-word middle sentence, the rationale clause, and the label
drift — all three are copy, none is a capability.

---

## Screen 16 · Edit · What's due — page 73, figure 23

Modal over `/:tenant/assets/{id}` · `PATCH /assets/{id}`.
Chips: **NEW BUILD · COMMITMENT 13 · 25 · 26**.

### What the image shows

A dialog. Kicker **M-4022 · METER · AMR**. Title **Edit · What's due**. Two fields, each
FULL WIDTH, one per row, label → input → helper:

1. **Test interval** — `96` — *"In months. The next due is computed."*
2. **Certification due** — a date input (calendar affordance drawn) — *"Empty where no certificate applies."*

Then a divider and a small block: *"Not on this form, because nothing types them:"* with
four bullets — Next due · Age vs expected life · Replacement forecast · Warranty state,
each followed by an em-dash and the reason it is computed.

Footer right-aligned: **Cancel** then **Save changes**.

### What the code does today

`AssetPanelEdits.tsx:206–282` (`EditWhatsDue`), reached from the What's-due panel's
pencil (`AssetDetailPage.tsx:898–901` → `634` → `AssetPanelEdits.tsx:161` dispatch).
Fields: `test_interval_months` (250) and `certification_due` as a `DatePickerField` (258)
— B14 rule 7. Absence block: `NotOnThisForm` at line 266 with keys
`nextDue · age · forecast · warrantyState`. Footer is `FormModal`'s own
(`components/FormModal.tsx:1364`, `.modal-foot` is `justify-content: flex-end`).

### Gaps

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| the screen itself | a per-panel dialog, two fields, one PATCH | exists and is wired | — | **YES — shipped `2.237.9`.** `AST-B-25` is discharged for this panel |
| labels, order, helpers | as drawn | **character-for-character identical**, same order | — | YES |
| kicker | `M-4022 · METER · AMR` — three segments | `M-4022 · Meter` — two (line 170) | CONTENT | No — the meter type is dropped |
| absence block reasons | each bullet carries its reason (*"— computed from the last test and the interval"*) | label only, four bullets | CONTENT | Deliberate — rule 33 says rationale is zero words on screen. Recorded at `AssetPanelEdits.tsx:140–147` |

**Three biggest:** none are capability gaps. The kicker's missing third segment, the
stripped reasons (a defensible rule-33 call), and nothing else.

---

## Screen 17 · Edit · Measurement — pages 74–75, figure 24

Modal over `/:tenant/assets/{id}` · `PATCH /assets/{id}`. **NEW BUILD · 13 · 25 · 26**.

### What the image shows

Kicker **M-4022 · METER · AMR**, title **Edit · Measurement**. **Eight fields, every one
FULL WIDTH and one to a row** — the figure draws no two-column run anywhere:

| # | label | badges drawn beside the label | value | helper |
|---|---|---|---|---|
| 1 | Read method | `SET ▸ READ_METHODS` | `AMR` | *"How a reading reaches us."* |
| 2 | Connection size | **`affects billing`** + `SET ▸ SERVICE_SIZE_CLASSES` | `—` | *"A rate ladder prices by this."* |
| 3 | Multiplier | **`affects billing`** | `1` | *"Multiplied into every reading before billing."* |
| 4 | Unit of measure | **`affects billing`** + `SET ▸ SERVICES · UOM` | `kgal` | *"The unit every quantity carries."* |
| 5 | Register digits | — | `9` | *"Digits before the dial rolls over."* |
| 6 | Allocation share | — | `—` | *"Its share of the master. Empty means unallocated."* |
| 7 | Allocation rule | — | `—` | *"How the share is worked out."* |
| 8 | Loss tolerance | — | `—` | *"How far the subs may fall short."* |

Below the last field, an amber line: *"⚠ Three of these change what a reading means.
Continue shows what that does before anything saves."*

⚠ **The figure is CLIPPED at that line — no footer is drawn for screen 17.** The
footer is only described in the table (p75): *"**Continue**, never Save — this is the one
edit on the screen that goes through a second step."* Anyone building this must not
invent a drawn footer; there isn't one.

Per-kind variation, from the table on p84: a meter gets 5 of these fields and the three
allocation rows render **read-only**; a sub-meter gets all 8 and they are editable; a BTM
device gets **no panel and no pencil**; a BTM inverter gets **export capacity only**.

### What the code does today

`AssetPanelEdits.tsx:284–528` (`EditMeasurement`). Field order in code:
`read_method` (424) · `size_class` (437) · `multiplier` (451) · `unit` (460) ·
`register_digits` (467) · `allocation_share_pct` (482) · `allocation_rule` (490) ·
`loss_tolerance_pct` (502) · `export_capacity_kw` read-only (513).
**That is the drawn order exactly.** Every label and every helper string matches the
drawing character for character.

The `affects billing` pill is a `StatusPill tone="warning"` rendered by
`AffectsBilling` (529–536), on the same three fields the drawing marks.
Billing-affecting set verified on the server:
`06-backend/apps/assets/services.py:271` —
`{"multiplier","unit","net_metering","service","size_class"}`, five, of which three are
on this form. The button flips to **Continue** only when one of those three actually
changed (line 413).

### Gaps

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| the screen itself | dialog, eight fields, the two-step | exists and is wired | — | **YES — `2.237.9`** |
| field order / labels / helpers | as drawn | identical, all eight | — | YES |
| `affects billing` placement | a pill **beside the label, on the label's line** | a separate `<p>` **above the whole field**, pulled up with `-mb-2` (529–536) | LAYOUT | No — see the rule-38 section |
| pill association | reads as belonging to the field below it | not programmatically tied to any input | WIRING | No — a screen reader gets a loose "Affects billing" with no owner |
| the amber warning line | *"Three of these change what a reading means. Continue shows what that does before anything saves."* | **absent** — nothing sits below Loss tolerance | CONTENT | No. The count is a live fact, not an illustration: three of the five billing-affecting fields are on this form |
| allocation rows on a meter | drawn **read-only on a meter**, editable on a sub-meter | rendered **only on a sub-meter** (`{sub && …}`, line 477) | CONTENT | No — absent where the drawing wants present-but-locked |
| the drawing's own spacing note | *"R12, two to a row"* (p76 table) | one field per row | — | **The table contradicts its own figure.** Rule 42: the image governs, and the image is one to a row. The code agrees with the image |

**Three biggest:** the missing amber warning line, the allocation rows being absent
rather than read-only on a meter, and the pill's placement.

---

## Screen 18 · Edit · Measurement · confirm — pages 76–77, figure 25

*The second step of the same modal — no second address.* **NEW BUILD · 13 · 25 · 26**.

### What the image shows

Same kicker and a title **Edit · Measurement · confirm**. Then, top to bottom:

1. A sentence: *"You are changing the **multiplier** from **×1** to **×10** on a meter
   that already has readings."*
2. An accent-bordered block: *"**This meter has 1,460 recorded reads.** The change applies
   **from today forward**. No stored read and no issued invoice is restated — a bill that
   has already gone out keeps the quantity it was calculated on."*
3. A **three-row** label/value list:
   * **What changes** → *"Every reading taken from today."*
   * **What does not** → *"1,460 stored reads · 34 issued invoices · the consumption strip above the reads."*
   * **Recorded as** → *"An audit row with the before and the after, and a `forward_only_change` warning on the response."*
4. Footer right-aligned: **Back** then **Save changes**.

⚠ **`1,460` and `34` are ILLUSTRATIONS under B14 rule 37** — *"Treat every number drawn
in a wireframe as an illustration, never a fact to build to."* Neither may be asserted in
a test or seeded into a fixture. The document grades this screen **DERIVED** for exactly
that reason (p78): the read count is obtainable from an endpoint the page already calls,
the invoice count is **not served by anything today**.

⚠ **`forward_only_change` is an internal code and B14 rule 31 forbids it on screen.**
Whatever else is built from this figure, that token is not.

### What the code does today

`AssetPanelEdits.tsx:355–402` — the `step === 2` branch of the SAME `FormModal`, so
**Back returns the typed values**, which is the whole reason it is one modal in two steps.

* `ConsequenceBox tone="check"` (373) — title *"Every reading taken from today."*,
  tag *"Affects billing"*, body *"No stored read is restated."*
* A `<dl>` (380–387) with **two** rows: **What changes** → the changed field names joined
  with `·`; **What does not** → *"Stored reads and issued invoices"*.
* **Back** is a ghost `Button` **inside the modal body** (line 397), not in the footer;
  the footer holds Cancel and **Save changes**.

### Gaps

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| the second step itself | one modal, two steps, Back preserves typing | exists, wired, and tested (`AssetOverviewPanels.dom.test.tsx` TC-M1/M2/M3) | — | **YES — `2.237.9`** |
| the opening sentence | *"You are changing the multiplier from ×1 to ×10…"* — names the field and both values | **absent** | CONTENT | No. The `<dl>` names the field but never the before/after values |
| third list row | **Recorded as** → an audit row with before and after | **absent** — only two rows | CONTENT | No. The audit row IS written (`services.py` `_audit` before/after), so this is a screen gap, not a capability gap |
| read count | *"This meter has 1,460 recorded reads."* | no count shown | MISSING PLUMBING (partial) | No. The read count is reachable; the invoice count is not served by any endpoint today — the document's own DERIVED grade |
| Back's position | in the **footer**, left of Save changes | in the **body**, above the footer | LAYOUT | No — see the rule-38 section. `FormModal` declares no secondary-footer-action slot |
| Back's neighbour | footer is **Back · Save changes** | footer is **Cancel · Save changes**, with Back separately in the body | LAYOUT | No — the drawn footer has no Cancel |

**Three biggest:** the missing before/after sentence, the missing **Recorded as** row, and
Back sitting in the body rather than the footer.

### ⚠ The "one removal" claim about this screen is wrong, and it is wrong in two places

The blueprint index (`00-index.md:206–208`) and this lane's own brief both say: *"Across
all six remedies in this document, exactly one thing is removed — the dialog frame on
**screen 18**. Appendix K carries that one row and nothing else."*

**Read off the page images, appendix K (p209–210) says something different:**

* It carries **TWO** rows, not one. p210 opens: *"**Two rows, and both carry a quoted
  ruling.** Rows with no quoted ruling: 0."*
* Row one is *"The dialog frame around the edit form"*, REMOVED, under *"Instruction,
  2026-09-11: **this should be form and not modal**"* — and its cost column reads
  *"every one of the **nine fields**, the forward-only note and both buttons carry over …
  what they gain is an address they can return to and a **second door from the asset
  itself**."* **That is screen 14, word for word.** Screen 14's own carry-over table on
  p69 says the same thing: *"The dialog frame itself — REMOVED."*
* Row two is screen **05c**'s Asset value panel, REMOVED, under *"remove this - Asset
  value"*.
* Appendix K numbers that first row **"07"**, and p210 lists the change set as
  *"05a, 05b, 05c, **07** and R1–R6"* — so appendix J/K use their own walked-screen
  numbering, not § 04's. It is not screen 18 under either numbering.

**Screen 18 removes nothing.** It is a new second step, drawn from scratch.
Routing: this is a documentation defect in `00-index.md`, not a product defect. I have
not edited that file — one file only, per my brief.

---

## Screen 19 · Edit · Device — pages 78–79, figure 26

Modal over `/:tenant/assets/{id}` · `PATCH /assets/{id}`. **NEW BUILD · 13 · 25 · 26**.

### What the image shows

Kicker **M-4022 · METER · AMR**, title **Edit · Device**. **Nine fields, every one full
width, one to a row:**

| # | label | value drawn | helper |
|---|---|---|---|
| 1 | **Asset type** `*` (+ `SET ▸ ASSET_TYPES`) | `Meter` | *"Changing this changes the tabs."* |
| 2 | **Meter type** (+ `SET ▸ METER_TYPES`) | `AMR` | *"Classifies the device. No rate uses it."* |
| 3 | **Manufacturer** | `Badger Meter` | none |
| 4 | **Model** | `M25` | none |
| 5 | **Device ID / serial** | `41-8827301` | *"The manufacturer's number, not ours."* |
| 6 | **External reference** | empty | *"Your own or a third party's number."* |
| 7 | **Form / class** | empty | none |
| 8 | **Firmware** | `3.2.1` | none |
| 9 | **Seal #** | `SL-88214` | none |

No `affects billing` pill anywhere and no confirmation step — which the page calls
information in itself: *"a person learns that this panel is the safe one."* Footer is
clipped off the figure; the table gives the primary as **Save changes**.

### What the code does today

`AssetPanelEdits.tsx:543–689` (`EditDevice`). Order: `type` (608) · `meter_type` (618,
measuring only) · `manufacturer` (628) · `model` (634) · `serial_no` (640) ·
`external_ref` (649) · `form_class` (656) · `firmware_version` (662) · `seal_no` (668).
**Nine fields, the drawn order, the drawn labels and the drawn helpers exactly** — the
five with a helper have one, the four without have none.
`external_ref` becomes typable here for the first time in the product; the server has
accepted it on update all along (`services.py:646`, BR-AST-049) and re-refuses a
duplicate (`services.py:1333–1336`).

### Gaps

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| the screen itself | nine fields, one PATCH, no confirmation | exists, wired, asserted by `AssetOverviewPanels.dom.test.tsx` TC-E3 | — | **YES — `2.237.9`** |
| external reference writable | typable | typable and sent | MISSING PLUMBING (was) | **YES — the column had a reader and no writer; it has one now** |
| Asset type asterisk | `*` on the label | no `required` passed (609) | CONTENT | No. Minor; the type is never empty on a served asset |
| the drawing's own spacing note | *"R12, two to a row, nine fields"* (p79) | one field per row | — | **The table contradicts its own figure again.** Rule 42: the image governs; the code agrees with the image |

**Three biggest:** there is essentially nothing here. The missing asterisk, and that is
the list. **This is the closest match in § 04.**

---

## Screen 20 · Edit · Cost & value — page 80, figure 27

Modal over `/:tenant/assets/{id}` · `PATCH /assets/{id}`. **NEW BUILD · 13 · 25 · 26**.

### What the image shows

Kicker, title **Edit · Cost & value**. **Six fields, full width, one to a row:**

1. **Supplier** — `Badger Meter` — no helper
2. **Purchase cost** — `182.0000` — *"Stored to four decimals, shown to two."*
3. **Purchase date** — `04/02/2021`, a date input — *"Age counts from here when never installed."*
4. **Depreciation method** (+ a red `NONE ▸ NO LIST EXISTS` annotation) — `Straight line` — *"How the present value is worked out."*
5. **Expected life** — `10` — *"In years."*
6. **Warranty term** — `60` — *"In months, from the purchase date."*

Then a divider and *"Not on this form, because nothing types them:"* with **three**
bullets — Present value · Cover ends · Book value and treatment.
Footer clipped; primary is **Save changes**.

⚠ `182.0000` is drawn at four decimals **inside an input**, which is how the value is
stored (hard rule 2). The helper says so. That is the storage form, not a display-2
violation.

### What the code does today

`AssetPanelEdits.tsx:690–793` (`EditCostValue`). Fields: `supplier` (734) ·
`purchase_cost` (740) · `purchase_date` as `DatePickerField` (748) ·
`depreciation_method` (756) · `expected_life_years` (768). **Five.**
`NotOnThisForm` at 782 with **two** keys: `presentValue · bookValue`.
Money travels as a raw string; the server stores at 4 dp.

### Gaps

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| the screen itself | six fields, one PATCH | exists and is wired | — | **YES — `2.237.9`** |
| **Warranty term** | field 6, *"In months, from the purchase date."* | **absent** | MISSING PLUMBING | No. `assets` holds `warranty_end` (a date) and **no term column**. Filed as `DEF-MET-5002` and correctly not invented — the prime directive |
| absence bullets | three — Present value · **Cover ends** · Book value | two — Present value · Book value | CONTENT | No, and it follows from the row above: *Cover ends* is computed from the term that does not exist |
| purchase date typable | drawn as an editable date | editable and sent | MISSING PLUMBING (was) | **YES — the date appeared nowhere in the product before and is now typed here** |
| the drawing's spacing note | *"R12, two to a row"* (p81) | one field per row | — | Figure governs; code agrees with the figure |

**Three biggest:** Warranty term has no column (the only genuine plumbing gap in § 04),
the third absence bullet that depends on it, and nothing else.

---

## Screen 21 · Edit · Lifecycle — pages 81–84, figure 28

Modal over `/:tenant/assets/{id}` · `PATCH /assets/{id}`. **NEW BUILD · 13 · 25 · 26**.

### What the image shows

Kicker, title **Edit · Lifecycle**. **Two fields, full width:**

1. **Installed** — `02/2024`, a date input — *"The date it went into service."*
2. **Location note** — `Pit at the kerb, north side` — *"Where a technician will find it."*

Then *"Not on this form, because nothing types them:"* with **three** bullets — Status
(*moves by action: assign, log a repair, retire*) · Age (*computed from the install date*) ·
Retired on · Reason · Replaced by (*written by the retire flow*).
Footer right-aligned: **Cancel** then **Save changes**.

**And the state in which there are none** (p83, figure 29): a **retired** asset shows
**no pencil at all**, on any panel, and the header carries no action but the overflow.
The page calls this hard-won law 2's mirror: a control that cannot work is worse than an
absent one, because `update_asset` raises `BIZ_IMMUTABLE` before it validates anything.

### What the code does today

`AssetPanelEdits.tsx:795–849` (`EditLifecycle`): `install_date` as a `DatePickerField`
(826) and `location_note` as a **multiline** `TextField` (838), then `NotOnThisForm` at
846 with keys `status · age · retirement`.
The retired state is real: `AssetDetailPage.tsx:897` — `const editable = hasAction(asset,
"edit")`, and `pencilFor` returns `undefined` when it is false, so **no pencil renders on
any of the five panels**. The screen and the server read the same action set, so they
cannot drift.

### Gaps

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| the screen itself | two fields, one PATCH with two keys | exists, wired, asserted by TC-E5 | — | **YES — `2.237.9`** |
| labels, helpers, absence bullets | as drawn | identical, three bullets | — | YES |
| the retired state | no pencil anywhere | no pencil anywhere, from the server's own action set | — | **YES**, and it is the strongest match in § 04 |
| location note width | *"runs full width because it is a sentence rather than a value"* (p82) | full width and `multiline` | — | YES |
| kicker third segment | `M-4022 · METER · AMR` | `M-4022 · Meter` | CONTENT | No — the same one-line gap as screens 16–20 |

**Three biggest:** the kicker segment, and nothing else. This screen matches.

---

## Rule 38 — where the drawing's FORM CONSTRUCTION disagrees with our UI rules

B14 rule 38, PO verbatim 2026-09-10: *"if youa re doing a form - go as per our UI
rules"*. Its own text names the cases: *"a drawing telling you that two fields sit side
by side, that help text sits under its input, that the footer puts Cancel on the left,
that the header carries a sub-line, what the kicker says, or that the close control is a
labelled button rather than `✕` — is not layout, it is FORM CONSTRUCTION, and B14 plus
the component kit already settle it."* And its last clause: *"the drawing is still right
about WHAT THE FORM CONTAINS."*

Six live conflicts in § 04:

| # | what the drawing draws | what B14 / the kit say | which wins | what to do |
|---|---|---|---|---|
| 1 | **"R12, two to a row"** in the prose of screens 17, 19, 20 — while every figure draws **one** field per row | **B14 has NO rule about field columns.** Grep of `14-ui-conventions.md` for *two to a row*, *side by side*, *grid*: zero hits in any rule. `R13` is the blueprint's own numbering, not B14's | **The IMAGE** (rule 42), and the kit is silent so nothing overrides it | Nothing. The code already draws one to a row inside the dialogs and two to a row on the page, which is what the figures show |
| 2 | Footer **right-aligned** on screen 14's page | B14 has no page-footer alignment rule. The kit's convention: `FormModal`'s `.modal-foot` is `justify-content: flex-end`, but the three asset **page** footers (`AssetFlowPages.tsx:507`, `:802`, `AssetEditPage.tsx:454`) are all `flex gap-2` — **left** | **The kit convention**, by rule 38 — but it is a convention, not a ratified rule | Decide it ONCE for all page footers and write it down. Three screens left-align and every dialog right-aligns; that is two answers to one question, which is how a figure drifts |
| 3 | **Back in the footer** beside Save changes (screen 18); no Cancel drawn | `FormModal` declares one footer shape: Cancel (ghost) + submit. There is no secondary-action slot | **The kit** | Rule 36's remedy applies: if the kit genuinely lacks the piece, **add it to the kit as an opt-in** so nothing existing moves. Do not hand-roll a second footer in one screen file |
| 4 | The **`affects billing` pill beside the label**, on the label's line (screen 17) | The kit's five help-bearing field variants take `label`, `help`, `error` — **no label adornment** | **The kit**, so today it is a floating `<p>` above the field | Same remedy as #3 — an opt-in `labelTag` on the kit's `FieldLabel`. The current floating paragraph is neither the drawing nor the kit, and it is not associated with its input for a screen reader |
| 5 | **Numbered fields 1, 2, 3 …** on every figure | No kit affordance, and it would change every dialog in the product on one screen's authority | **The kit.** Already decided and recorded at `AssetPanelEdits.tsx:48–55` | Nothing. These are document callouts, not screen chrome |
| 6 | `SET ▸ READ_METHODS` etc. beside four labels; `NONE ▸ NO LIST EXISTS` on screen 20 | **B14 rule 31** forbids a database table name on a clerk's screen | **Rule 31, absolutely** | Nothing. These are appendix-L provenance annotations. If anyone ever mistakes them for chrome, this row is why they must not build them |

### And two rule-41 escalations that were never escalated

B14 rule 41, ratified 2026-09-13: *"only exception to the rule can be in case any rule or
BR is not matching or contradicting - in such case you can ask us."* A drawn element that
contradicts a signed rule goes **to the PO with both sides quoted**. Two were decided in
code instead:

* **Screen 16/20/21's absence reasons.** The drawing writes *"Next due — computed from
  the last test and the interval."* Rule 33 says rationale is **zero words on screen**.
  The code kept the label and dropped the reason (`AssetPanelEdits.tsx:140–147`) and
  filed the divergence. Right answer; wrong route — rule 41 wants it put to the PO.
* **Screen 14's lead line.** Drawn at 9 words, built at 4, because rule 33 caps an
  instruction at 6 words per sentence. Same shape, same verdict.

Both are correct calls. Both should reach the PO as one question with both sides quoted,
rather than being settled by a lane — that is what rule 41 changed on 2026-09-13.

---

## `AST-B-26` — eight words or ten, and what actually governs

⚠ **The document contradicts itself inside one commitment card, and my brief inherited
the wrong half.** Read off p161: the card's TITLE is **"A helper line is eight words or
fewer."** Its measurement sentence uses a different threshold: *"measured across the
module, **27 of 37 helper strings run over ten words** and the worst is 36."*

So the specification is **eight**; **ten** is only the yardstick the census was counted
against. Neither is the binding number.

**B14 rule 33 governs and it is stricter than both, and it is stricter in a different
SHAPE.** A helper under an input is an **INSTRUCTION** — *what to type* — so the cap is
**6 words PER SENTENCE**, not 8 or 10 in total, and *"two sentences of six beat one
sentence of twelve."* A rule counting whole strings would mark
*"In months. The next due is computed."* (7 words) as a failure when it is exactly the
shape rule 33 asks for.

**So: build to rule 33's per-sentence cap. Treat `AST-B-26`'s eight as a useful proxy,
never as the rule.**

### Measured on this branch, `07-frontend/src/i18n/locales/en.json`

| surface | strings | over 8 words (`AST-B-26`) | with a sentence over 6 words (B14 rule 33) |
|---|---|---|---|
| **Screens 16–21** (`assets.panel.help.*`) | 21 | **0** | **5** — all exactly 7, one word over |
| **Screen 14 + 15** (`assets.form.*Help`, the notes, the delete body) | 12 | **11** | **11** |

The five at seven words: `depreciationMethod` · `externalRef` · `lossTolerance` ·
`purchaseCost` · `purchaseDate`.

**`AST-B-26`'s named worst case is still live and it is on screen 14.**
`assets.form.sizeClassHelp` = *"The size of the service connection this meter sits on. A
rate ladder that prices by size uses it, so a wrong one changes the bill. Leave it blank
if you do not know it yet."* — **36 words, three sentences of 10, 16 and 10.**
Screen 14's own drawing gives that field a 10-word helper, so **the 36-worder is a code
fault and not a drawing one.** Screen 17's version of the same helper is already
*"A rate ladder prices by this."* — six words. **One field, two helpers, 30 words apart.**

All 92 keys behind screens 14–21 are present in **all eleven catalogues** — checked, zero
missing in de, es, es-MX, fr-FR, hi, id-ID, it-IT, ja-JP, ko-KR, pt-BR.

---

## Other things worth writing down before the next lane reads them

* **`AssetLifecycleModals.tsx` contains no modals and nothing for screens 14–21.** It
  holds the transition law, the catalogue constants, the schemas and one mutation hook.
  Its own header says the modals left in CR-028 AST-W4. A lane opening it looking for
  screen 21 finds nothing; **screen 21 is `AssetPanelEdits.tsx:795`.** The name is a trap.
* **"Twenty-three fields" appears three times in the document about screen 14** — p72
  (*"Page — twenty-three fields"*), p78 (*"without opening a twenty-three field form"*)
  and `AST-B-25`'s own headline. **Nothing drawn anywhere has 23 fields.** Screen 14
  draws nine. The CHANGELOG entry for `2.237.9` gives the origin: the asset **Overview**
  *"used to open with one list of twenty-three rows"* before it was cut into six panels.
  A row count became a field count. Rule 42 again: read the picture.
* **`AST-B-17` is a FOURTH withdrawn commitment** (p159, struck through, *"withdrawn
  2026-09-11, the day it was drawn"*), alongside `-07`, `-08`, `-09`. 28 − 4 = 24 live,
  which is the cover's own figure. `00-index.md` now says this; it did not when this lane
  started.
* **p161's closing line reads "Twelve live specifications."** while the cover and the
  index both say 24. One of the two is stale. Low cost, worth a look by whoever owns § 12.
* **The document's own as-built claims that I re-verified and that still hold:**
  `PATCH /assets/{id}` takes a partial payload · PUT does not exist · `update_asset` is
  gated to System Admin and Billing Clerk · `delete_asset` to System Admin only ·
  `BILLING_AFFECTING_FIELDS` holds exactly five. Only the line numbers have moved
  (`api.py:138` is now `:158`).

---

## Summary — the counts

**Build status. Seven of my eight screens carried a NEW BUILD chip. Six of those seven
are already built and wired, both after the read this blueprint was made at.**

| screen | chip in the blueprint | status today |
|---|---|---|
| 14 Edit one asset | NEW BUILD | **built `2.239.9`**, routed, both doors live |
| 15 Delete this asset? | EXISTS BEHIND, no commitment | unchanged, as described |
| 16 Edit · What's due | NEW BUILD | **built `2.237.9`** |
| 17 Edit · Measurement | NEW BUILD | **built `2.237.9`** |
| 18 Edit · Measurement · confirm | NEW BUILD | **built `2.237.9`** |
| 19 Edit · Device | NEW BUILD | **built `2.237.9`** |
| 20 Edit · Cost & value | NEW BUILD | **built `2.237.9`** |
| 21 Edit · Lifecycle | NEW BUILD | **built `2.237.9`** |

`AST-B-12`, `AST-B-25` and `AST-B-27` are **discharged**. `AST-B-13` (every hint under
its input) is discharged for screens 16–21 and holds on screen 14 too — the kit renders
label → input → helper in all five variants. **`AST-B-26` is the only one of the four
still genuinely outstanding, and it is outstanding on screen 14 alone.**

**Gaps found: 38 across eight screens.** By class:

| class | count | where the weight is |
|---|---|---|
| CONTENT — a label, a sentence, a value, a missing line | **21** | 12 of them on screen 14 and the delete confirm |
| LAYOUT — placement, alignment, order | **9** | 5 are rule-38 cases the kit wins |
| WIRING — a control that cannot reach its state | **2** | screen 14's unreachable duplicate-number refusal; screen 17's unassociated pill |
| MISSING PLUMBING — no column, no endpoint | **3** | Warranty term (no column, `DEF-MET-5002`) · screen 18's invoice count (unserved) · screen 17's read-only allocation rows |
| **already fixed since `2.234.17`** | **3** of the above were the blueprint's own findings and are now closed | external reference typable · purchase date typable · the whole per-panel dialog set |

**By screen, worst first:**

| screen | gaps | headline |
|---|---|---|
| **14** | **12** | the field swap, the 36-word helper, the read-only Asset # |
| **18** | 6 | no before/after sentence, no *Recorded as* row, Back in the body |
| **17** | 6 | no amber warning line, allocation rows absent not read-only, pill placement |
| **15** | 4 | a 26-word sentence and a rationale clause in a destructive confirm |
| **20** | 4 | Warranty term has no column |
| **16** | 3 | kicker segment |
| **21** | 2 | kicker segment |
| **19** | 1 | a missing asterisk |

**The single clearest finding: screen 14 carries 12 of the 38 gaps — nearly a third —
while the five panel dialogs built four weeks later carry 22 between them and screen 19
carries one.** The dialogs were built to the drawing; screen 14 was a container change to
a form that already existed, and the form's content came with it unreviewed. That is
where a remediation wave should start.

**Two claims in the packet that are wrong and should not be carried forward:**

1. The one removal in appendix K belongs to **the edit form (screen 14)**, not screen 18,
   and appendix K carries **two** rows, not one. `00-index.md:206–208` still says
   otherwise. Verified off p209 and p210 as images.
2. `AST-B-26` is **eight** words in its title, not ten; ten is the census yardstick; and
   **B14 rule 33's six-words-per-sentence cap governs both**, in a different shape.

**What I did not do:** I did not run the front-end suite or `tsc`, so I am making no
claim about red lines I did not cause. I did not open the product in a browser, so every
pixel statement here is from a page image and from source, and the one measurement that
needs a browser — screen 14's content width against the drawn ≈875px — is marked
unverified above and must not be acted on until somebody measures it.
