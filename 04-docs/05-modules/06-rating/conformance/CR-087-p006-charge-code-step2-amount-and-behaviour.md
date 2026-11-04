# 02 · Charge code → Create · Step 2 · Amount & behaviour — THE DRAWN SPEC

`S12 · CHG-02` · route `/:tenant/plans-rates/charge-codes/new` and
`…/:definitionId/edit` · **blueprint pages 6–10**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, section
`01 CHARGE CODES`, screen `02`. The screen head opens at the foot of **page 6**,
the frame runs **pages 6–8** (four stacked cards and the footer) and the
specification runs **pages 8–10**. Read as RENDERED pages — the four-by-five
price grid, the three-column cross-reference table and the one-row tick strip
are drawn, and text extraction alone prints the grid's cells in the wrong order
and loses which cell is a box and which is a dash.

**State chips on the screen head:** `NEW BUILD` · `COMMITMENT PRB-01` ·
`COMMITMENT PRB-02` · `COMMITMENT PRB-03`
**Screen question, verbatim:** *"What does it cost, and what makes it differ?"*

**What this file is.** Only the **bordered grey frame on pages 6–8** is the
specification. The amber *"What was wrong"* block above it is the problem
statement, never the target: *"A different deposit, connection fee or penalty
could not be set for a different class on one screen — the class was a list on
the code and the size a flat table, so the grid a utility actually prices in
could not be written. The cost and its behaviour were also two panels asking one
question, and three panels of dashes carried a heading and a paragraph each over
nothing a clerk could touch."*

⚠ **THE BLUEPRINT'S MASTHEAD (page 1) DISCLAIMS ITS OWN AS-BUILT LINES** —
*"Every as-built statement here was true at version 2.232.0, commit d2d493e4, on
8 September 2026, and must be re-verified"*. We are on **2.234.19**. **This
screen's central as-built claim is STALE, and building the frame from it would
undo work that has already shipped — see §1 of the diff.** Every other
"the product currently does X" line was re-checked and is cited with a file and
a line.

⚠ **B14 rule 37** — every figure inked into the frame (`45.0000`, `60.0000`,
`85.0000`, `110.0000`, `140.0000`, `150.0000`, `220.0000`, `340.0000`, and the
sizes `2"`–`8"`) is an ILLUSTRATION. Nothing below records a drawn number as a
requirement, and no test may assert one.

---

## 1 · Header and rail — identical to step 1, `2 Amount & behaviour` active

| slot | drawn |
|---|---|
| kicker | `NEW CHARGE CODE` |
| title (H1) | `Add a fee, deposit, or adjustment.` |
| sub-line | `Charge codes are the non-usage line items on a bill. Three steps · takes about 2 minutes.` |
| top-right, in order | `Cancel` · `Save draft & exit` |
| rail | `1 Basics` · **`2 Amount & behaviour`** · `3 Review & save` |
| step heading | **none drawn** — the first thing under the rail is a card |
| step kicker | **no `STEP 2 OF 3`** |

## 2 · Card A — `What it costs`

| slot | drawn |
|---|---|
| heading (H3) | `What it costs` |
| hint | `A charge code never multiplies by anything the meter measured — that is a rate schedule's job.` |

| # | label, as drawn | required | control | drawn value |
|---|---|---|---|---|
| 1 | `HOW THE AMOUNT IS WORKED OUT` | `*` | select (chevron) | `A fixed amount` |
| 2 | `AMOUNT` | `*` | single-line text | `45.0000` |
| 3 | `MAXIMUM AMOUNT` | — | single-line text | *(empty)* |

**Then, INSIDE the same card**, a kicker and a tick strip:

| slot | drawn |
|---|---|
| kicker | `HOW IT BEHAVES` |
| ticks — **all four on ONE ROW, all ticked** | `May be taxed` · `Apply automatically` · `Staff may waive it` · `Show as its own line on the bill` |
| help under the row | `May be taxed is permission, not an attachment.` |

**No help line is drawn under any of the three money fields.**

## 3 · Card B — `What makes it differ`

| slot | drawn |
|---|---|
| heading (H3) | `What makes it differ` |
| hint | `A connection is not one price. The same fee differs by class and by capacity, and both are decided here.` |
| field kicker | `AMOUNT BY CUSTOMER CLASS AND CONNECTION SIZE` |
| help under the kicker | `Leave a cell blank and that class is not served at that size — a bill for it is refused, not charged $0.00.` |

**The grid — classes DOWN, sizes ACROSS:**

| `CUSTOMER CLASS` | `2"` | `4"` | `6"` | `8"` |
|---|---|---|---|---|
| `Residential` | `45.0000` | `60.0000` | `—` `Not served` | `—` `Not served` |
| `Commercial` | `85.0000` | `110.0000` | `140.0000` | `—` `Not served` |
| `Industrial` | `—` `Not served` | `150.0000` | `220.0000` | `340.0000` |
| `Every other class` | `45.0000` | `60.0000` | `—` `Not served` | `—` `Not served` |

* a priced cell is a **bordered input box** holding the figure;
* an unpriced cell is a **bare em-dash over the words `Not served`** — no box,
  no control;
* `Every other class` is the **LAST row**, not the first.

**Two controls under the grid, side by side, outlined:**
`+ Add a class row` · `+ Add a size column`

**Two accent-ruled notes, in this order:**

| kicker | body |
|---|---|
| `WHY A GRID AND NOT A NUMBER` | `A connection fee, a disconnection fee, a deposit and a penalty all differ by who is being charged and how big the connection is. One grid answers both, on the code that owns the fee.` |
| `WHAT THIS COSTS` | `This needs ONE COLUMN the amount table does not have. It is keyed by charge and size today, so a class cannot be a row. Until that column exists a utility declares one code per class — CONN-RES, CONN-IND — each with its own size amounts, which prices correctly and reads as a workaround.` |

## 4 · Card C — `Where class already varies a charge, today`

| slot | drawn |
|---|---|
| heading (H3) | `Where class already varies a charge, today` |
| hint | `Read this before deciding a fee cannot be set: it may already be set somewhere else.` |

| `WHAT` | `HOW IT VARIES BY CLASS` | `WHERE YOU SET IT` |
|---|---|---|
| `Deposit` | `Already a grid — one amount per customer category` | `The plan`, `on its Discounts & billing step` |
| `Late fee` | `Its percentage, minimum and grace` | `The plan`, `on its Discounts & billing step` |
| `Connection · disconnection · other fees` | `One charge code per class` | `Here — the class list on this code` |
| `Base charge` | `One charge code per class, then per size` | `Here — the class list, then the grid above` |

**Accent note under it:** `TWO PLACES, ONE QUESTION` — *"The same question — what
does this cost for this class — is answered in two places, and no screen said
which. A deposit is not on a charge code at all; it is a plan rule keyed by
customer category, and it has been all along."*

## 5 · Card D — `Not stored on a charge code`

| slot | drawn |
|---|---|
| heading (H3) | `Not stored on a charge code` |
| hint | `Said once, so the screen is not three panels of dashes.` |
| rule | a bare `—` |
| body, one line | `Three things this screen cannot record. Part-period charging, who may approve a waiver, and a staff-only description have no column, so the full amount is charged, anyone who may change Plans & Rates can waive it, and there is one description.` |

## 6 · Footer — one row, the advance alone at the right

`Continue` — the only control drawn, accent outline with a grey label. **No
`← Back` is drawn**, on a step that has one.

## 7 · Cognitive load, as stated (page 9)

*"Three boxes: what it costs, what makes it differ, and what cannot be recorded.
The amount fields appear and disappear with the rule above them, so a clerk never
sees a box that cannot apply."*

## 8 · States — the blueprint's own STATES block, verbatim (pages 9–10)

| state | drawn behaviour |
|---|---|
| **Fixed amount** | *"One amount box, and the size table."* |
| **Percentage** | *"A percentage box and a minimum; no size table, because a percentage of a size makes no sense."* |
| **Prices by size** | *"The single Amount box goes read-only and says the amount is set per size below."* |
| **Formula** | *"Offered and permanently disabled — the type is agreed and nothing prices it, so choosing it would be refused on save."* |
| **Any service** | *"No size table: a connection size is a property of a service, and an account-level code like a late fee has none. The class picker stays — a late fee can still differ by class."* |
| **Recurring or Refundable** | *"The middle box is unchanged; only the third line differs, naming how-often or deposit terms among the gaps."* |

## 9 · Components named in the frame (page 10)

`WizardFrame` `SelectField` `MoneyTextField` `CheckboxRow` `ClassPicker`
`SizeAmountTable` `NamedAbsence`

## 10 · Rules it must obey, as stated (page 10)

*"Money shows two decimals and is stored to four; a percentage six. Colour is
never the only signal — every state carries its word. A code a clerk reads down
the phone is a printed reference, not a database id, so it is shown; a database
id never is. Built in the shared utility classes, adding nothing to a
stylesheet. A panel a clerk cannot act on is a line, not a panel."*

## 11 · FOR · HOW YOU GET HERE · PRIMARY ACTION (page 8)

* **FOR** — *"The same clerk, one step on. This is the only screen in the
  product where what a fee costs is decided."*
* **HOW YOU GET HERE** — *"Continue from Basics, or the rail. On an edit the
  rail opens with every step reachable — a clerk correcting a price should not
  walk three screens to reach it."*
* **PRIMARY ACTION** — *"Continue."*

## 12 · Absences — drawn as absent, do not fill them

* **No `STEP 2 OF 3` kicker and no step heading** — the first thing under the
  rail is card A.
* **No `← Back`** in the footer.
* **No per-field help** under the amount, maximum or rule fields.
* **No `Minimum amount` field is drawn** — it exists only in the STATES block,
  for the percentage case.
* **No percentage or minimum box on the drawn frame**, which draws the fixed-
  amount state.
* **No panel of dashes** — every gap is one line inside card D.

---

## THE DIFF — the drawn frame against the code at 2.234.19

The screen is `07-frontend/src/features/rating/ChargeCodeWizard.tsx`; step 2 is
`AmountStep`, **lines 855–1046**, and the price grid is `PerSizeAmounts`,
**lines 1088–1329**. The file is on
`07-frontend/src/styles/route-b-migrated.txt` (line 166), so Tailwind utilities
are lawful in it (B14 rule 21).

### 1 · ⚠ THE CENTRAL AS-BUILT CLAIM IS STALE — THE COLUMN LANDED ON 2026-09-08

The frame's `WHAT THIS COSTS` note, its `WHAT THE SERVER NEEDS` paragraph
(page 10) and figure 1 on page 2 all say the same thing: *"`charge_code_amounts`
is unique on `(tenant_id, charge_id, size_class)` and carries **no customer-class
column at all**, so the class × size grid drawn here cannot be stored today"*,
with the workaround *"a utility declares one code per class — CONN-RES,
CONN-IND"*.

**All of that was true when the blueprint was read and is false now:**

* the column exists — `06-backend/apps/rating/models.py:514`
  (`customer_class = models.TextField(null=True, blank=True)`), with the ruling
  written out at `:495–513`;
* it is INSIDE the unique key, as two partial constraints because Postgres
  treats NULLs as distinct — `models.py:528–538`;
* the migration is
  `06-backend/apps/rating/migrations/0029_cr087_a1_amount_by_customer_class.py`,
  committed 2026-09-08 as *"CR-087 A1 — one charge code can price a house at
  $45.00 and a shop at $85.00"*, and its own trace line names **PRB-01**;
* the screen writes it — `ChargeCodeWizard.tsx:1113–1116` builds the class
  columns, `:1233–1266` writes a cell, and `SizeAmountDraft.customer_class`
  (`:165–173`) survives the round trip as `null` rather than `""`;
* there is a rendered-output test for it —
  `07-frontend/src/features/rating/cr087ClassSizeGrid.dom.test.tsx`.

**So PRB-01 is delivered.** A lane building this frame literally would re-file a
shipped capability as missing and would print a `WHAT THIS COSTS` note telling a
utility to create `CONN-RES` and `CONN-IND` — the workaround the product no
longer needs.

### 2 · THE GRID IS TRANSPOSED, AND THE EVERY-CLASS LINE MOVES

| | drawn | built |
|---|---|---|
| rows | **customer classes** (`Residential`, `Commercial`, `Industrial`, `Every other class`) | **connection sizes**, from the tenant's own `service_size_classes` (`:1187–1196`) |
| columns | **connection sizes** (`2"`, `4"`, `6"`, `8"`) | **customer classes** (`:1116`, `columns = [null, ...pricedClasses]`) |
| first header cell | `CUSTOMER CLASS` | `Size` — `rating.rateDetail.matrix.col.size` (`:1157`) |
| the fallback line | `Every other class`, drawn **LAST** | `Every customer type` — `rating.chargeWizard.perSize.everyClass` — always **FIRST** and not removable (`:1104–1112`, `:1121–1125`) |

The code states its reason at `:1104–1112`: the every-class column *"is the price
a code states when it says nothing about the customer's type, and every row a
tenant wrote before 2026-09-08 lives in it… so the general price is read before
the exceptions to it."* **Drawing and code disagree about order and about
wording; only the wording is settled by anything** — `Every other class` is not
a phrase the catalogue holds.

### 3 · THE TWO ADD CONTROLS DIFFER, AND ONE OF THEM IS DELIBERATELY ABSENT

| drawn | built |
|---|---|
| `+ Add a class row` | a `SelectField` labelled `Price a customer type` with the placeholder `Choose a customer type` (`:1291–1314`), plus a per-column `Remove` (`:1160–1184`, the label at `:1178`) |
| `+ Add a size column` | **nothing.** Sizes are not created here at all |

The absence is a documented product rule rather than a gap:
`PerSizeAmounts`'s docstring at `:1165–1178` — *"THE SIZES ARE CHOSEN, NEVER
TYPED… A typed size would store a string nothing ever looks up: the meter
resolves `W-58`, R4 finds no amount for `W58`, and the bill refuses for a base
the utility believes it set."* — and the empty state points at Settings
(`rating.rate.sizes.noSizeClasses`, rendered at `:1147`). **The drawing offers a
control that would move where a utility creates a size class**; see the PO
section.

### 4 · A CELL'S THREE STATES ARE BUILT AND THE DRAWING SHOWS TWO

| state | drawn | built |
|---|---|---|
| priced | a box holding the figure | `MoneyTextField` (`:1233–1266`) |
| a row with a blank box — **NOT SERVED** | *(collapsed into the dash)* | a box left empty; posts as `null`, never `"0"` (`:157–160`) |
| no row at all | `—` over `Not served` | `No row — this code does not price this size.` + an `Add row` button (`:1212`, `:1227`) |

The drawn cell reads `Not served`; the built cell reads `No row — this code does
not price this size.` and offers a control. The words `Not served` appear in the
product only inside the help line
`rating.chargeWizard.perSize.blankIsNotServed` (`:1142`).

⚠ **The blueprint uses one phrase for both states and contradicts itself on
which one it means:** the grid's own help says *"Leave a cell blank and that
class is not served at that size"*, while `BLANK IS NOT ZERO` on page 9 says
*"a size with **no row** is not served"*. The product distinguishes the two
deliberately (`DEF-277`, the docstring at `:1114–1125` of `PerSizeAmounts`' own header comment).

### 5 · ONE CARD DOES NOT EXIST AT ALL — `Where class already varies a charge, today`

Nothing in `ChargeCodeWizard.tsx` renders a deposit/late-fee cross-reference,
and no catalogue key holds any of its four rows.

**Its four as-built claims are TRUE at 2.234.19** and were re-checked:

* deposits are a plan rule keyed by customer category —
  `06-backend/apps/rating/models.py:1448–1465` (`PlanDepositRule`, unique on
  `rate_plan × account_type_id`);
* the late fee's percentage and minimum are plan-level —
  `models.py:1503–1504` (`late_fee_min`, `late_fee_pct`), and the plan points at
  the charge it raises (`models.py:166–172`, `late_fee_charge`);
* fees and base charges narrow by class **on the code** —
  `charges.applies_to_customer_classes` (`models.py:833`), which is the same
  field §7 below shows the wizard cannot set.

So the card is accurate, absent, and would answer a real question — the
blueprint's own reason for it is *"a clerk stops hunting for them here"*.

### 6 · CARD D IS BUILT, BUT AS A CLOSED DISCLOSURE AND WITH A DIFFERENT LIST

| | drawn | built |
|---|---|---|
| shape | a card with a heading and ONE line | a `MoreAbout` `<details>` (`:1034–1043`, `ratingShared.tsx:789–804`) holding one `ArrivesWithField` per gap |
| summary | — | `rating.rate.moreAbout` = *"More about this step"* |
| the gaps named | part-period charging · who may approve a waiver · a staff-only description | `proration` · `waiver` (only when the code is waivable, `:369–371`) · `outsideCity` (only when a service is chosen, `:365–368`) · plus the type-specific `recurrence` / `deposit` / `event` (`:349–354`) — and the **staff-only description is on step 1**, not here (`:724–727`) |

`MoreAbout` closed-by-default is B14 rule 32 (*a stated absence is a `<details>`
CLOSED by default*), so the shape is the UI rules' and not the drawing's.
**What is a real difference is the LIST**: the drawing names three gaps and the
product names up to six, four of which the drawing's own step-1 table presents
as questions step 2 will ask (see the p003 file, §2).

### 7 · THE CLASS PICKER THE DRAWING RELIES ON IS NOT ON THIS SCREEN EITHER

The drawn STATES block says of `Any service`: *"The class picker stays — a late
fee can still differ by class."* Card C says a connection fee's class variation
is set *"Here — the class list on this code"*. `ClassPicker` is named in this
screen's COMPONENTS list.

**There is no class picker anywhere in the wizard.** `grep -rn "ClassPicker"
07-frontend/src` returns nothing; `ChargeDraft` (`:176–194`) carries no
`applies_to_customer_classes`; and step 1 renders an `ArrivesWithField` saying
the column does not exist (`:772–777`) — which is false, as the p003 file §4
sets out with the model, service, selector and endpoint lines. **The grid's
class COLUMNS are a different field**: they say what each class PAYS, and the
code says so itself at `:1285–1289` and in `perSize.classIsNotReach` (`:1313`) = *"This
sets what a customer type pays. Who the charge reaches is set on the previous
step."* — a sentence that points at a control the previous step does not have.

### 8 · THE COST AND THE BEHAVIOUR ARE STILL TWO PANELS

The frame's whole `WHAT CHANGED · ONE BOX FOR THE COST` argument (page 8) is
that *"The amount and how it behaves were two panels asking one question… One
box."* The code still renders two `Panel`s — the money fields (`:874–948`) and
then a separate panel opening with the `How it behaves` kicker (`:950–999`).

### 9 · THE FOUR TICKS ARE A COLUMN, NOT A ROW — AND THAT IS A PO FIX

Drawn: four ticks on one row. Built: `<div className="flex flex-col
items-start gap-2">` (`:966`), one tick per line.

⚠ **The column is deliberate and was made on the PO's own report.** The comment
at `:953–965` records it: walking this step the Product Owner said *"in this
section tick boxes alignment s are not correct"* (`DEF-2356`), because four
inline `CheckboxField`s wrapped and each tick sat jammed against the end of the
previous label. **The drawing asks for the layout the PO rejected**, so this one
goes to the PO rather than into either column of this file.

The four labels themselves match the drawing exactly —
`rating.chargeWizard.taxableLabel` = `May be taxed` (`:973`),
`rating.charges.autoApplyLabel` = `Apply automatically` (`:982`),
`rating.charges.waivableLabel` = `Staff may waive it` (`:988`),
`rating.charges.separateLineLabel` = `Show as its own line on the bill`
(`:994`) — and in the drawn order.

### 10 · THE TAXABLE SENTENCE IS BEHIND A DISCLOSURE AND IS FOUR TIMES LONGER

* **drawn**, as a plain line under the tick strip: `May be taxed is permission,
  not an attachment.` (7 words)
* **built**: inside a `MoreAbout` (`:977–979`),
  `rating.chargeWizard.taxableHelp` = *"This is permission, not an attachment:
  it says the charge can be taxed, and the tax codes decide which tax attaches
  in which jurisdiction. Fees and late charges are never part of the tax base
  whatever this is set to."* (44 words)

The disclosure is rule 32's; the LENGTH is rule 33's (*a fact ≤ 6 words*), and
the drawn sentence is what that cap looks like.

### 11 · THE REQUIRED MARKERS ARE DRAWN AND NOT BUILT

The frame marks `HOW THE AMOUNT IS WORKED OUT *` and `AMOUNT *`.

* the rule select passes no `required` — `:876–885`, though `SelectField`
  accepts one (`components/FormModal.tsx:352`);
* the amount field cannot carry one at all — `MoneyTextField`
  (`ratingShared.tsx:908–934`) declares **no `required` prop** and never passes
  one to the `TextField` underneath.

B14 rule 10 is unmet on both. The second is rule 36's *"where the kit lacks a
piece, ADD IT TO THE KIT"* rather than a screen-level fix — `MoneyTextField` is
used by the rate, plan and discount wizards too.

### 12 · THE STATES — FIVE OF SIX ARE BUILT AS DRAWN

| drawn state | built |
|---|---|
| **Fixed amount** — one amount box and the size table | ✓ `amountFieldsFor` (`ChargeCodesTab.tsx:115–125`) gives `amount` only to `flat`; the grid is offered on `fields.amount` and a chosen service (`:1019`) |
| **Percentage** — a percentage box **and a minimum** | **partly.** `percent` gives the percentage box alone; the minimum arrives only under the separate rule `percent_with_minimum` (`ChargeCodesTab.tsx:120–124`, fields at `:905–920` (percent) and `:921–935` (minimum)). The product has FOUR rules where the drawing describes three states |
| **Prices by size** — the Amount box goes read-only and says why | ✓ `readOnly={pricesBySize}` (`:896`) with `rating.chargeWizard.perSize.amountOwned` = *"This code prices by connection size, so the amount is set per size in the table below."* (`:898`) |
| **Formula** — offered and permanently disabled | ✓ `amountRuleOptions` appends it `disabled: true` (`ChargeCodesTab.tsx:106–110`), and the help line `rating.charges.formulaDisabled` says so (`:883`) |
| **Any service** — no size table; **the class picker stays** | **half.** No size table ✓ (`:1019` requires `draft.service !== ""`). No class picker exists — §7 |
| **Recurring or Refundable** — only the third line differs | ✓ `stepTwoSections` (`:348–373`) |

### 13 · `HOW YOU GET HERE` — THE RAIL DOES NOT OPEN ON AN EDIT

Drawn: *"On an edit the rail opens with every step reachable — a clerk
correcting a price should not walk three screens to reach it."*

Built: `WizardFrame` computes `const done = number < nav.step`
(`components/WizardFrame.tsx:798`) and renders `disabled={!done}`
(`:807`), so on an edit the rail opens at step 1 with steps 2 and 3 dead.
`ChargeCodeWizard` passes no `nav` (`:641–650`), and the frame exposes no
"all steps reachable" prop. A clerk correcting a price does walk the three
screens.

---

## DIVERGENCES — B14 rule 38 (the UI rules win, nothing is built for these)

Rule 38, PO 2026-09-10: *"if you are doing a form - go as per our UI rules"*.
Each of these is FORM CONSTRUCTION, so the drawing loses and the divergence is
recorded rather than acted on.

1. **The footer draws `Continue` alone on a middle step.** `WizardFrame` puts
   `← Back` beside it (`WizardFrame.tsx:856–864`), which is B14 rules 1 and 3.
   UI rules win.
2. **No `STEP 2 OF 3` and no step heading are drawn.** `StepHead` prints both on
   every step of five wizards (`:661–675`). UI rules win — the same call the
   p003 and p011 files made.
3. **Card D is drawn as an open card.** B14 rule 32 makes a stated absence a
   `<details>` **closed** by default, which is what `MoreAbout` is. UI rules
   win.
4. **`Cancel` is drawn as bare accent text**; the kit renders a ghost `Button`
   (`:613`). UI rules win.

---

## THE BLUEPRINT AGAINST ITSELF — recorded, not resolved

1. **MONEY IS DRAWN TO FOUR DECIMALS ON EVERY ONE OF THE ELEVEN FIGURES** —
   `45.0000` through `340.0000` — on a screen whose own RULES row reads *"Money
   shows two decimals and is stored to four"*, and beside a help line that
   writes the same money as `$0.00`. See the PO section.
2. **`Not served` vs `blank`** — the grid help and the `BLANK IS NOT ZERO`
   paragraph name two different states with one phrase (§4).
3. **Step 1 promises what step 2 says it cannot record.** The step-1 type table
   lists *part-period charging* under `STEP 2 THEN ASKS` for two of the five
   types; card D says it *"has no column"*.
4. **`ClassPicker` is named in the COMPONENTS lists of BOTH step 1 and step 2**
   while step 1's own specification says the class moved to step 2 and step 2
   draws no picker — only the grid's class rows.
5. **`Save draft & exit` is drawn live** here as on every charge-code frame,
   while page 4 declares it deliberately absent (carried in the p003 and p011
   files).

---

## FOR THE PRODUCT OWNER

1. ⚠ **A DRAWN NOTE WOULD RE-PUBLISH A SOLVED PROBLEM.** `WHAT THIS COSTS` tells
   a utility to keep `CONN-RES` and `CONN-IND` as a workaround. The column
   landed on 2026-09-08 (`CR-087` A1 / PRB-01) and the grid writes it. **The
   note should go, not be built.**
2. ⚠ **THE TICK STRIP IS THE LAYOUT THE PO ALREADY REJECTED.** The frame draws
   four ticks on one row; the product stacks them because the PO reported the
   one-row version as broken alignment on this very screen (`DEF-2356`). The
   drawing and the ruling cannot both be followed.
3. ⚠ **`+ Add a size column` WOULD MOVE WHERE A SIZE CLASS IS CREATED.** Today
   sizes come from Configure → Reference data and the screen says so; the
   drawing puts a create control on the pricing screen. That is a decision about
   where reference data is owned, not a component choice.
4. ⚠ **FOUR-DECIMAL MONEY CONTRADICTS A PO RE-SIGN.** `CLAUDE.md` hard rule 2,
   PO re-sign 2026-08-22, verbatim: *"We already confirmed this - MOney 4
   decimal, percentage 6 decimal , display both 2 decimal"*. The server
   implements it (`06-backend/apps/rating/selectors.py`, `_display_money`
   quantizes every `*_display` string to two places) and the screens render only
   those strings. **Every figure on this frame is drawn at four.** B14 rule 37
   makes the drawn NUMBERS illustrations; it does not obviously settle the drawn
   FORMAT. **Both are recorded; neither is followed.** ⚠ And note the frame's
   money INPUTS are a separate question: `moneyIn` (`ratingShared.tsx`) strips
   trailing zeros beyond two places for an editable box precisely so a clerk
   does not meet `0.000000` (`DEF-2361`), so a four-decimal box is not what the
   product types into either.
5. **The class list on a code has no control** (§7, and the p003 file §4). Where
   it belongs — step 1 with identity, or step 2 beside the amount as this
   drawing has it — is the PO's call.

---

## WHAT COULD NOT BE VERIFIED WITHOUT THE APP RUNNING

* Whether the drawn `Continue` is a **disabled primary** or a tier. Step 2
  declares no `validate` (`:562–583`), so `Continue` is live in the product;
  the drawn grey label reads as disabled. No stack was booted.
* How the built grid behaves at width — sizes down and classes across puts the
  removable-column control in a `<th>`, and the drawn orientation would put four
  boxes on a row. `overflow-x-auto` is set (`:1152`); nothing beyond that can be
  read from source.
* Alignment, spacing rhythm and where the accent-ruled notes sit relative to the
  grid. Hard-won law 6 — nothing in this repo reads rendered output, and this
  pass read a PDF and a source tree, not a browser.

## THE ELEVEN CATALOGUES

Every key this step renders is **present in all eleven locales** — 0 missing, 0
empty, checked over the 51 keys `AmountStep` and `PerSizeAmounts` resolve, plus
the eight `rating.customerClass.*` labels the grid's columns use.

⚠ **22 of those 51 are ENGLISH VERBATIM in five of them** — `es-MX`, `hi`,
`id-ID`, `ja-JP`, `ko-KR` — including `rating.chargeWizard.amount.heading`,
`.behaviour`, `.taxableLabel`, `.taxableHelp`, `rating.rate.sizes.addRow` /
`.removeRow` and **all twelve `rating.chargeWizard.section.*` keys and their
`.pending` sentences**. `de`, `es`, `fr-FR`, `it-IT` and `pt-BR` are translated.
That is B14 rule 35's subject, and it is present-but-untranslated rather than
missing, so nothing renders as silence.

---

## ⚠ AMENDED 2026-09-10 — WHAT THIS FILE'S DIFF NO LONGER DESCRIBES

**Built this day under `CR-087` maintenance (decision log, *THE CHARGE CODES TAB
AGAINST ITS DRAWN BLUEPRINT*).**

| §  | finding | now |
|---|---|---|
| §7 | there is no class picker anywhere in the wizard, and `perSize.classIsNotReach` points at a control the previous step does not have | **BUILT** — a `ChipMultiSelect` (B14 rule 9) in its own `Who it reaches` panel on THIS step, directly above the price grid, offered whatever the service is (this file's own `Any service` state: *"the class picker stays"*). The grid's help line now reads *"…is set above"* and is true. `DEF-RAT-4830` |
| §11 | the rule select and the amount box carry no `required`, and `MoneyTextField` declares no such prop | **FIXED IN THE KIT** — `MoneyTextField` gains an OPTIONAL `required`, so nothing existing moves; both step-2 controls now set it, and the amount DROPS it when the per-size table owns the figure. `DEF-RAT-4831` |
| §1 | the `WHAT THIS COSTS` note would re-publish a solved problem | **NOT BUILT, DELIBERATELY.** The column landed 2026-09-08; building the note would instruct a utility to keep `CONN-RES`/`CONN-IND` for a workaround it no longer needs |
| §9 | the four ticks are a column and the drawing wants a row | **NOT CHANGED — RULED.** PO 2026-09-10: *"Stacks them down the page"*. The drawing is asking `DEF-2356` back |
| §2 | the grid is transposed from the drawing | **NOT CHANGED** — a PO question (which orientation moves), recorded in this file and in p013 |
| §3 · §5 · §8 · §13 | `+ Add a size column`, the `Where class already varies` card, the two panels, the rail on an edit | **NOT CHANGED** — each is recorded above and none is a lane's call |

⚠ **AND ONE NEW DIVERGENCE, RECORDED RATHER THAN BUILT.** This file's §6 lists
the gaps card D names. The customer class was never one of them and must not be
added back: it is a live column with a live control now.
