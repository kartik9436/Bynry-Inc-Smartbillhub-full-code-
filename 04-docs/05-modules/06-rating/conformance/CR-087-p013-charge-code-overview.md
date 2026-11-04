# 04 · Charge code → View · Overview — THE DRAWN SPEC

`CHG-01 (charge)` · route `/:tenant/plans-rates/charge-codes/:id` ·
**blueprint pages 13–15**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, section
`01 CHARGE CODES`, screen `04`. The screen head and the first half of the frame
are on **page 13**, the frame continues on **page 14**, the specification runs to
**page 15**. Read as RENDERED pages — the class × size grid, the three-block
split and the tile strip are drawn and text extraction prints them out of order.

**State chips on the screen head:** `NEW BUILD` · `COMMITMENT PRB-04`
**Screen question, verbatim:** *"What is this charge, what does it cost, and when
does it apply?"*

**What this file is.** Only the **bordered grey frame on pages 13–14** is the
specification. The amber *"What was wrong"* block is the problem statement:
*"Three tabs answered one question between them; the amount was a figure on one
tab and a table on another; the classes that decide whether the code reaches
anybody were on no tab at all; and the count said accounts where a plan is
assigned to a unit."*

⚠ **B14 rule 37** — `$45.0000`, `218`, `6 plans`, `2"/4"/6"`, `4200-01` and every
other figure in the frame are ILLUSTRATIONS. Nothing below records one as a
requirement.

---

## 1 · Header

| slot | drawn |
|---|---|
| back link | `← Charge codes` *(accent)* |
| kicker | `CHARGE CODE · CONN · ONE-TIME` |
| title (H1) | `Connection fee` |
| status | `ACTIVE` *(pill, green outline, under the title)* |
| sub-line | `GL account 4200-01 — Connection revenue · Applying it creates a billable item that references the version in force, so an issued bill never changes.` |

## 2 · Header actions — in the drawn order, right-aligned

`Duplicate` *(secondary)* | `Edit` *(secondary)* | `Retire` *(**danger** — accent
outline)*

## 3 · Tabs — THREE, `Overview` active

`Overview` | `Plans` | `Audit`

## 4 · The tab description line — its own band under the tab strip

`What this charge is, what it costs, and when it applies.`

## 5 · Tiles — FOUR, with detail lines

| # | value | label | detail line |
|---|---|---|---|
| 1 | `$45.0000` | `AMOUNT` | `A fixed amount, one-time` |
| 2 | `218` | `UNITS REACHED` | `through 6 plans` |
| 3 | `Residential · Commercial` | `CLASSES` | *(none)* |
| 4 | `Active` | `STATUS` | *(none)* |

## 6 · The `NOT WORKED OUT YET` band — its own row under the tiles

| kicker | `NOT WORKED OUT YET` |
|---|---|
| row 1 | `Times applied last month` — `Nothing counts how many times one code was applied.` |
| row 2 | `Revenue` — `Nothing totals what one charge code has billed.` |

## 7 · Block 1 — `What it is`

*(no sub-line drawn)*

| # | label | value |
|---|---|---|
| 1 | `DESCRIPTION` | `Connection fee` |
| 2 | `TYPE` | `One-time` |
| 3 | `SERVICE` | `Any service` |
| 4 | `SHOWS ON THE BILL AS` | `Connection fee` |

## 8 · Block 2 — `What it costs`

**Sub-line:** `One grid: who is charged, and how big the connection is.`

**The grid — CUSTOMER CLASS down, connection sizes across:**

| `CUSTOMER CLASS` | `2"` | `4"` | `6"` |
|---|---|---|---|
| `Residential` | `$45.0000` | `$60.0000` | `—` *(under it, small: `Not served`)* |
| `Commercial` | `$85.0000` | `$110.0000` | `$140.0000` |

**Accent callout under the grid:**

| kicker | `HOW THE AMOUNT IS WORKED OUT` |
|---|---|
| body | `A fixed amount, narrowed by class and connection size. A blank cell is not served — a bill for it is refused, not charged $0.00.` |

## 9 · Block 3 — `When it applies`

**Sub-line:** `Five facts about how this charge behaves on a bill, and where the
money is posted.`

| # | label | value |
|---|---|---|
| 1 | `APPLIES TO` | `Any service` |
| 2 | `TAXABLE BY DEFAULT` | `Taxable` |
| 3 | `APPLY AUTOMATICALLY` | `Yes` |
| 4 | `STAFF MAY WAIVE IT` | `Yes` |
| 5 | `SHOW AS ITS OWN LINE ON THE BILL` | `Yes` |
| 6 | `GL ACCOUNT` | `4200-01 — Connection revenue` *(monospace)* |

⚠ Six fields under a sentence that says *five facts … and where the money is
posted* — read as five facts plus the GL account, which is the posting. Not a
contradiction.

## 10 · States — the blueprint's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **Never used** | *"`Units reached` reads 0, plainly. Zero here is a real zero."* |
| **Every class** | *"`Classes` reads `Every class` rather than listing all eight."* |
| **One amount for every size** | *"The grid collapses to a single row and says so, rather than repeating one figure across four columns."* |
| **Deactivated** | *"The status pill changes and the header says from when. Edit stays live — a deactivated code's wording may still need fixing."* |
| **Read-only role** | *"A role that may read but not change Plans & Rates sees every figure and no button. The refusal names the role, not the screen."* |

## 11 · Components named in the frame

`PageHeader` `KPIStrip` `AbsenceBar` `Panel` `FieldGrid` `AmountGrid`
`Callout accent`

## 12 · Rules it must obey, as stated (page 15)

*"Money shows two decimals and is stored to four; a percentage six. Colour is
never the only signal — every state carries its word. A code a clerk reads down
the phone is a printed reference, not a database id, so it is shown; a database id
never is. Built in the shared utility classes, adding nothing to a stylesheet. A
figure that does not exist is stated with its reason and never drawn at the weight
of one that does. A read screen shows a fact in the shape the edit screen sets
it."*

## 13 · FOR · HOW YOU GET HERE (page 14)

* **FOR** — *"Anyone who has been sent a code and needs to know what it is — a
  clerk on the phone, a supervisor checking a bill query."*
* **HOW YOU GET HERE** — *"`Charge codes` tab, clicking the name. Also from a
  plan's Charges tab, and from a rate schedule's base column, both of which name
  this code as the source of an amount."*
* **PRIMARY ACTION** — *"Edit."*

## 14 · The five WHAT CHANGED statements, verbatim (pages 14–15)

1. **THREE TABS BECAME ONE** — *"Overview, Amounts and Applicability answered one
   question between them. … They are one tab in three blocks, in the order a
   person arrives: **what it is**, **what it costs**, **when it applies**. Plans
   and Audit stay — they answer different questions and the PO said so."*
2. **UNITS, NOT ACCOUNTS** — *"The count said accounts. A charge reaches a
   customer through a plan, and a plan is assigned to a **unit** — so counting
   accounts undercuts by every vacant unit, and a vacant unit's base charge lands
   on a landlord's bill. Same ruling as the rate schedule."*
3. **THE AMOUNT IS A GRID HERE TOO** — *"It was a single figure with the per-size
   detail on another tab. The read screen shows the same grid the edit screen
   sets, so a clerk never has to hold two shapes for one fact."*
4. **THE CLASSES ARE A TILE** — *"Which classes a code applies to decides whether
   it reaches a customer at all, and it was on no tab. It is a headline figure,
   beside the amount."*
5. **TAXABLE READS TAXABLE, NOT YES** — *"A yes/no answers a question the label
   does not ask. Same correction as the tax screen's basis fields."*

## 15 · Absences — drawn as absent, do not fill them

* **No `Amounts` tab and no `Applicability` tab** — both are BLOCKS of Overview.
* **No `Minimum amount` or `Maximum amount` field** anywhere on the frame.
* **No `Priced separately for` field** — the classes are a TILE and the grid
  carries the per-class figures.
* **No version, no `V1` in the kicker.**
* **No `Bills last month` or `Monthly revenue` TILE** — both are rows of the
  `NOT WORKED OUT YET` band instead.

---

## THE DIFF — the drawn frame against the code at 2.234.19

The screen is `07-frontend/src/features/rating/DefinitionDetailPage.tsx` with
`kind="charge"` (`07-frontend/src/App.tsx:623–626`); every slot it fills comes
from `presentCharge` in `07-frontend/src/features/rating/definitionDetail.tsx`,
**lines 452–566**. `DefinitionDetailPage.tsx` is on `route-b-migrated.txt`
(line 77); `definitionDetail.tsx` is not and does not need to be — its own
docstring says *"This file holds no markup and no routing"*.

### What matches, exactly

| drawn | code |
|---|---|
| kicker `CHARGE CODE · CONN · ONE-TIME` | `definitionDetail.tsx:470–474` — kind · code · type, joined with ` · ` |
| title = the code's name | `:469` |
| `ACTIVE` pill under the title | `DefinitionDetailPage.tsx:485–494`; `PageHeader.tsx:273` puts state with the identity, not in the action row |
| `Duplicate` · `Edit` · `Retire`, that order | `DefinitionDetailPage.tsx:170–174` |
| `Retire` in the danger tier | `:560` — `variant={key.endsWith("retire") ? "danger" : "secondary"}` |
| `Edit` is the live primary action | `:161` `EDITABLE_KINDS` includes `"charge"`; `:552–553` + `:562–566` navigate to the wizard |
| the policy half of the sub-line | `:477`, key `rating.definition.charge.policy` |
| tiles are exactly four, above the tab body | `:605` `<KPIStrip …>` |

### 1 · THERE ARE FIVE TABS, NOT THREE — the merge has not reached the charge

`definitionDetail.tsx:67`:

```
charge: ["overview", "amounts", "applicability", "plans", "versions"],
```

The frame draws `Overview | Plans | Audit`. **Both merges the frame asks for have
already been done for the other two kinds and not for this one:**
`discount: ["overview", "plans", "audit"]` (`:85`) and
`tax: ["overview", "plans", "audit"]` (`:104`), both on the PO ruling of
2026-09-08 recorded in the comments at `:68–103`. The charge is named in those
comments as the one left: *"the CHARGE is the last one left, and until it moves
`isHistoryTab` stays the one place that knows"* (`:97–99`).

`07-frontend/src/features/rating/DefinitionDetail.test.tsx:405` pins it —
`expect(DEFINITION_TABS.charge).toHaveLength(5)` — so the merge lands with a test
that already names itself.

### 2 · THE FOUR TILES ARE FOUR DIFFERENT TILES

`definitionDetail.tsx:255–260` and `:483–497`:

| # | drawn | built | served? |
|---|---|---|---|
| 1 | `AMOUNT` `$45.0000` · `A fixed amount, one-time` | `Plans carrying it` = `row.used_by_plans` | yes |
| 2 | `UNITS REACHED` `218` · `through 6 plans` | `Bills last month` = `—` | **no read** |
| 3 | `CLASSES` `Residential · Commercial` | `Monthly revenue` = `—` | **no read** |
| 4 | `STATUS` `Active` | `Basis` = the amount RULE (`A fixed amount`) | yes |

**Two of the drawn four are already served and simply not rendered here:**

* `AMOUNT` — `chargeAmountDisplay(row)` is already computed at `:460–461` and
  used in the panels; it is not given to a tile.
* `CLASSES` — `charges.applies_to_customer_classes` is served
  (`06-backend/apps/rating/selectors.py:2586`) and typed
  (`07-frontend/src/api/endpoints.ts:4092`), and **`presentCharge` reads it
  nowhere**. The blueprint's *"the classes … were on no tab at all"* is TRUE at
  2.234.19 — verified by reading all three panels at `:501–563`.
  ⚠ Do not confuse it with `rating.definition.charge.perClass` at `:545–556`:
  that reads `size_amounts[].customer_class`, which is what each class PAYS. The
  tile wants who the code REACHES. The file states the distinction itself at
  `:438–441`.
* `STATUS` — `row.status` is already the header pill (`:479–481`). Drawing it a
  second time as a tile is a duplication the PO should confirm; recorded under
  "for the Product Owner" below.

**One of the drawn four has no read:** `UNITS REACHED`. Nothing counts units for
a charge code. ⚠ **The exact query shape exists one function away, for the
discount** — `discount_offered_unit_count`
(`06-backend/apps/rating/selectors.py:3255–3300`), which counts units on a
current plan assignment whose plan carries the object, and whose docstring
carries the ruling the frame's *"units, not accounts"* statement is quoting:
*"`schedule_applied_to_accounts` next door counts exactly this shape and is called
`accounts`, and that mislabelling reached four screens (DEF-RAT-4664). A plan is
assigned to a UNIT — `unit_plan_assignments` — so units is what this query can
honestly answer for."*

### 3 · THE `NOT WORKED OUT YET` BAND DOES NOT EXIST, AND ITS PATTERN DOES

Today the two absent figures are **permanently blank tiles**:
`definitionDetail.tsx:483–497` passes `NO_FIGURE` (`"—"`, `:294`) for tiles 2 and
3, with TODO comments saying no read exists. The frame moves both out of the
strip and into a named band, which is exactly what CR-087 C2 already did for the
discount — `definitionDetail.tsx:264–270` records it: *"`…discount.cost` STOOD
HERE AND WAS AN EM-DASH ON EVERY DISCOUNT THAT HAS EVER EXISTED … a permanently
blank quarter of the strip — furniture, not a stated absence."*
The discount's replacement is a `noteKey` on a block (`:1010`,
`rating.definition.discount.notWorkedOut`). **There is no `AbsenceBar` component
in the kit** — `ls 07-frontend/src/components/` has 45 files and none is one.

### 4 · THE OVERVIEW IS ONE FLAT FOUR-FIELD LIST, NOT THREE BLOCKS

`definitionDetail.tsx:501–508` — `overview` is
`Description · Type · Service · Amount`, rendered by `FieldList` through the
`props.fields` fallback branch at `DefinitionDetailPage.tsx:756–763`. The
`blocks` mechanism the frame needs **already exists and already works** — the
tax and the discount both declare `blocks` and the renderer prefers them
(`DefinitionDetailPage.tsx:733–751`). The charge declares none.

**Where the drawn blocks' fields live today:**

| drawn block | drawn field | today |
|---|---|---|
| What it is | `DESCRIPTION` | `overview` `:502`, key `rating.charges.col.description` = `Description` ✓ |
| What it is | `TYPE` | `overview` `:503` ✓ |
| What it is | `SERVICE` | `overview` `:506`, key `rating.filter.service` = `Service` ✓ |
| What it is | `SHOWS ON THE BILL AS` | **nowhere** — and it cannot be distinct, see the contradiction below |
| What it costs | the grid | **nowhere** — `amounts` `:510–558` is a flat six-field list |
| What it costs | the callout | **nowhere** |
| When it applies | `APPLIES TO` | `applicability` `:560`, key `rating.charges.appliesTo` = `Applies to` ✓ |
| When it applies | `TAXABLE BY DEFAULT` | `applicability` `:561` ✓ label, ✗ value — see 6 |
| When it applies | `APPLY AUTOMATICALLY` | `applicability` `:562` ✓ |
| When it applies | `STAFF MAY WAIVE IT` | `applicability` `:563` ✓ |
| When it applies | `SHOW AS ITS OWN LINE ON THE BILL` | `applicability` `:564` ✓ |
| When it applies | `GL ACCOUNT` | on the SUB-LINE (`:476`), not in a block |

**Fields the frame does NOT draw and the code renders:** `Minimum amount` and
`Maximum amount` (`:513–514`), the `Amount per connection size` count sentence
(`:522–544`) and `Priced separately for` (`:545–556`). §15 says the frame omits
them deliberately; the last two are the flat rendering of the grid the frame
replaces.

### 5 · THE CLASS × SIZE GRID IS NOT ON THE READ SCREEN — AND THE EDIT GRID IS
TRANSPOSED

The data is there. `charge_code_amounts.customer_class` shipped on 2026-09-08
(`06-backend/apps/rating/models.py:514`, migration
`06-backend/apps/rating/migrations/0029_cr087_a1_amount_by_customer_class.py`),
with the two partial unique constraints at `models.py:519–537`, and it is served
as `size_amounts[]` with `customer_class` and `amount_display` per row
(`selectors.py:2630–2649`).

⚠ **THE ORIENTATIONS DO NOT AGREE, WHICH MATTERS BECAUSE THE FRAME'S OWN
JUSTIFICATION IS THAT THEY SHOULD.** §14.3 says *"The read screen shows the same
grid the edit screen sets, so a clerk never has to hold two shapes for one fact."*
The built edit grid — `PerSizeAmounts`,
`07-frontend/src/features/rating/ChargeCodeWizard.tsx:1090–1329` — puts
**SIZES down the rows and CLASSES across the columns**, with the every-class
column always first and not removable (`:1101–1122`). The frame puts **CLASSES
down and SIZES across**. Transposed. A PO question, below.

Everything else about the drawn grid matches the built semantics: a blank cell is
*not served* and refuses the bill rather than charging `$0.00` — DEF-277,
`models.py:481–484`, and the wizard's own help line
`rating.chargeWizard.perSize.blankIsNotServed`.

### 6 · `TAXABLE BY DEFAULT` STILL READS `Yes`, AND THE FILE DECLINES THE FIX BY
NAME

`definitionDetail.tsx:561` renders `yesNo(t, row.taxable_default)` → `Yes` / `No`.
The frame wants `Taxable`. **The helper the frame asks for already exists in the
same file** — `taxedOrNot` at `:402–418`, built for `DEF-RAT-4662` with the
reasoning the frame is repeating: *"`Usage charges: Yes` ANSWERS A QUESTION THE
LABEL DOES NOT ASK. The label is a NOUN, so the reader has to already know that
the unwritten question is 'is this in the tax base'."* Its docstring then says:
*"`yesNo` above is deliberately left alone: on the charge kind the labels ARE
questions ('Waivable', 'Auto-apply') and Yes is the right word there."*
That is true of `Staff may waive it` and `Apply automatically`. It is **not** true
of `Taxable by default`, which is a noun phrase — the same shape the correction
was made for. Keys exist: `rating.taxes.baseTaxed` = `Taxed`,
`rating.taxes.baseNotTaxed` = `Not taxed`; the frame's word is `Taxable`, a third
spelling.

### 7 · THE BACK LINK NAMES THE WRONG PLACE — B14 RULE 1

Drawn: `← Charge codes`. Built: `← Plans & Rates`.
`DefinitionDetailPage.tsx:465` passes `label: t(route.backLabelKey)` and
`definitionDetail.tsx:172` sets `backLabelKey: "rating.kicker"` = `Plans & Rates`,
while the same config's `listRoute` (`:171`) is
`/plans-rates/charge-codes`. **The link goes to the charge-codes tab and is
labelled with the module.** B14 rule 1: *"A page header's `←` names where it EXITS
to."* All three kinds share the defect — the tax and the discount configs use the
same key.

### 8 · THE SUB-LINE HAS AN EXTRA SENTENCE AND A COLON

* drawn: `GL account 4200-01 — Connection revenue · Applying it creates a
  billable item that references the version in force, so an issued bill never
  changes.`
* built: `GL account: 4200-01 — Connection revenue` (`:476`, a literal `": "`) ·
  `A charge code is a definition. Applying it creates a billable item that
  references the version in force, so an issued bill never changes.`
  (`rating.definition.charge.policy`)

Two edits: drop the colon, drop the leading *"A charge code is a definition."*
The frame also moves `GL ACCOUNT` off the sub-line into block 3 (§9 row 6), which
would leave the sub-line as the policy sentence alone.

### 9 · THE TAB DESCRIPTION LINE DOES NOT EXIST

`What this charge is, what it costs, and when it applies.` has no key and no
render. The panel heading today is `rating.definition.panel.overview` =
`What this is`, drawn as a `Kicker` INSIDE the panel
(`DefinitionDetailPage.tsx:690`, `:757–762`). The frame puts a description under
the TAB STRIP and gives each block its own heading. Three new keys are needed for
the three block headings — `rating.definition.panel.identity` = `What it is`
already exists (`:998`, used by the discount's merged Overview) and is the drawn word exactly.

---

## DIVERGENCES — B14 rule 38 (the UI rules win, nothing is built for these)

1. **The status is drawn BOTH as a header pill and as tile 4.** The kit draws
   state once, with the identity (`PageHeader.tsx:167–172`, DEF-966: *"state is
   not an action"*). Which of the two the frame means is a PO question rather
   than a construction one — recorded below rather than here.
2. **The frame draws the tab strip with a small ▲▼ control at its right end.**
   Nothing in the kit has one and it reads as a wireframe scroll affordance. Not
   built, not recorded as a requirement.

---

## THE BLUEPRINT AGAINST ITSELF — recorded, not resolved

1. **`DESCRIPTION` AND `SHOWS ON THE BILL AS` ARE DRAWN AS TWO FIELDS HOLDING THE
   SAME STRING** (`Connection fee`, twice). There is ONE description column on
   `charges` today — the wizard says so in
   `rating.chargeWizard.internalPending`: *"There is one description column today,
   so a staff-only one is not offered."* Splitting the two is **PRB-03**, whose
   own card on **page 21** says it *"Waits on: A column on `charges`"* and is
   `UNVERIFIED`. **So the frame draws a field its own register says does not
   exist**, and draws it holding the same value as the field it is supposed to be
   distinct from.
2. **THE GRID IS DRAWN TRANSPOSED FROM THE EDIT GRID** while §14.3 justifies the
   grid by saying it is *"the same grid the edit screen sets"*. See §5.
3. **MONEY IS DRAWN TO FOUR DECIMALS** — `$45.0000`, `$60.0000`, `$85.0000`,
   `$110.0000`, `$140.0000` — on pages whose own RULES row reads *"Money shows two
   decimals and is stored to four"*.

---

## FOR THE PRODUCT OWNER

1. ⚠ **FOUR-DECIMAL MONEY CONTRADICTS A PO RE-SIGN.** `CLAUDE.md` hard rule 2,
   PO 2026-08-22, verbatim: *"MOney 4 decimal, percentage 6 decimal , display both
   2 decimal"*. The server implements it —
   `06-backend/apps/rating/selectors.py:208–227` quantizes every `*_display`
   string to two places — and the screens render only those strings. **Both the
   drawing and the rule are recorded; neither is followed by this pass.**
2. **PRB-01 IS BUILT AND THE REGISTER STILL SAYS `UNVERIFIED`.** Its card (page
   20) says *"Nothing else on this list can be drawn until it lands."* It landed
   on 2026-09-08 as `charge_code_amounts.customer_class`
   (`models.py:492–537`, migration `0029`), as a CODE rather than the
   `account_type_id` the card names, for the reason at `models.py:498–505`. The
   register asks engineering to fill the status column in from the code; this is
   that answer for PRB-01.
3. **`STATUS` AS A TILE beside the header's `ACTIVE` pill** is the same fact
   twice. One sentence to the PO: *should the fourth tile be the status, or
   something else?*
4. **THE GRID ORIENTATION** — classes down and sizes across (the drawing), or
   sizes down and classes across (the built edit screen)? One of the two moves.

---

## WHAT COULD NOT BE VERIFIED WITHOUT THE APP RUNNING

* The **read-only role** state (§10) — the code passes `readOnly` into every
  `GuardedButton` (`DefinitionDetailPage.tsx:556–557`), but whether the refusal
  *"names the role, not the screen"* is a rendered-output question. Not booted.
* The **deactivated** state's *"the header says from when"* — nothing in
  `presentCharge` carries a deactivation date and `charges` has only
  `deleted_at`; whether the header can say *from when* was not tested live.
* Tile widths, grid alignment and the `NOT WORKED OUT YET` band's exact placement.
  Hard-won law 6: nothing in this repo reads rendered output.

## THE ELEVEN CATALOGUES

All keys this screen renders are present in all eleven locales (0 missing, 0
empty). **50 of the 91 `rating.definition.*` keys are English verbatim in
`es-MX`, `hi`, `id-ID`, `ja-JP` and `ko-KR`** — including every tile label on this
screen (`rating.definition.kpi.charge.plans` reads `Plans carrying it` in
`ja-JP.json`). B14 rule 35.

---

## ⚠ AMENDED 2026-09-10 — ONE THING MOVED, AND IT IS NOT ON THIS TAB

**`CR-087` maintenance (decision log, *THE CHARGE CODES TAB AGAINST ITS DRAWN
BLUEPRINT*).** The Overview itself is **unchanged**: the tab merge (§1), the four
tiles (§2), the `NOT WORKED OUT YET` band (§3), the three blocks (§4), the read
grid (§5), `TAXABLE BY DEFAULT` (§6), the back link (§7) and the sub-line (§8)
are all still exactly as this file's diff describes them.

**What changed is the ADDRESS of the tab this page's strip ends on.** `?tab=audit`
used to fall back to THIS screen, silently — the charge's tab has read `Audit` in
all eleven catalogues since the rename while its id is `versions`, and
`definitionTabFrom` cannot tell a mistyped tab from a synonym. It resolves now, in
both directions, and the address a clerk copies out of the bar is still the
kind's own (PO 2026-09-10: *"Change the label, keep the address"*).
`DEF-RAT-4832`.

⚠ **AND ONE FINDING IN THIS FILE IS NOW HALF ANSWERED.** §2 says the `CLASSES`
tile's data *"is served and `presentCharge` reads it nowhere"*. That is still true
of the TILE — nothing here was changed — but the field is no longer unreachable
from the product: the charge wizard's step 2 sets it (`DEF-RAT-4830`). A lane
building the tile has a control to point at.
