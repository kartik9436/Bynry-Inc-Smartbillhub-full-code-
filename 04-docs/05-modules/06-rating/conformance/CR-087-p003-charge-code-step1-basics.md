# 01 · Charge code → Create · Step 1 · Basics — THE DRAWN SPEC

`S12 · CHG-02` · route `/:tenant/plans-rates/charge-codes/new` and
`…/:definitionId/edit` · **blueprint pages 3–6**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, section
`01 CHARGE CODES`, screen `01`. The section opens on **page 2**, the frame is
drawn across **pages 3–4** (the form panel on 3, the type table and the footer
on 4), and the specification runs **pages 4–6**. Read as RENDERED pages — the
five-row type table, the footer split and the help lines that sit ABOVE their
inputs are drawn, and text extraction alone prints them out of order.

**State chips on the screen head:** `NEW BUILD` · `COMMITMENT PRB-03`
**Screen question, verbatim:** *"What is this charge called, and what kind of
charge is it?"*

**What this file is.** Only the **bordered grey frame on pages 3–4** is the
specification. The amber *"What was wrong"* block above it is the problem
statement, never the target: *"Seven fields carried eight lines of help; the
type was five radio cards with prose on each; the customer class sat three
fields away from the size table that narrows the same amount; and nothing said
that the type decides what the next step asks for."*

⚠ **THE BLUEPRINT'S MASTHEAD (page 1) DISCLAIMS ITS OWN AS-BUILT LINES** —
*"Every as-built statement here was true at version 2.232.0, commit d2d493e4, on
8 September 2026, and must be re-verified"*. We are on **2.234.19**. Every
"the product currently does X" line below was re-checked against the code and is
cited with a file and a line. **One of this section's as-built claims is already
stale — see the p006 file, §1.**

⚠ **B14 rule 37** — every figure and value inked into the frame (`CONN`,
`Connection fee`, `One-time`, `Any service`) is an ILLUSTRATION. Nothing below
records a drawn value as a requirement, and no test may assert one.

---

## 1 · Header — drawn once, identical on all three steps

| slot | drawn |
|---|---|
| kicker | `NEW CHARGE CODE` |
| title (H1) | `Add a fee, deposit, or adjustment.` |
| sub-line | `Charge codes are the non-usage line items on a bill. Three steps · takes about 2 minutes.` |
| top-right, in order | `Cancel` *(bare accent text)* · `Save draft & exit` *(outlined button)* |
| back link | **none drawn inside the frame** |

## 2 · Step rail — three, `1 Basics` active

`1 Basics` | `2 Amount & behaviour` | `3 Review & save`

## 3 · Step body — a heading and NOTHING ELSE above the first field

| slot | drawn |
|---|---|
| heading (H2) | `Name the charge and pick its type.` |
| hint | **none drawn** |
| step kicker | **no `STEP 1 OF 3`** |

## 4 · The form panel — FIVE controls, in this order

| # | label, as drawn | required | help, as drawn | control | drawn value |
|---|---|---|---|---|---|
| 1 | `CODE` | `*` | `Uppercased on save. Unique for this utility.` — **ABOVE the input** | single-line text | `CONN` |
| 2 | `DESCRIPTION (SHOWN ON THE BILL)` | `*` | **none** | single-line text | `Connection fee` |
| 3 | `TYPE` | `*` | **none** | **a SELECT** (chevron at the right) | `One-time` |
| 4 | `APPLIES TO SERVICE` | — | **none** | **a SELECT** (chevron at the right) | `Any service` |
| 5 | `This is the base charge for its service` | — | `For the classes and sizes set on the next step.` — **BELOW the tick** | checkbox, unticked | — |

**No placeholder text is drawn in any box** — every box shows a value or is
empty.

## 5 · `What the type decides` — a second card inside the frame

| slot | drawn |
|---|---|
| heading (H3) | `What the type decides` |
| hint | `The type is not a label. It changes what the next step asks you for.` |

| `TYPE` | `WHAT IT IS` | `STEP 2 THEN ASKS` |
|---|---|---|
| `Recurring` | `A standing charge on every bill` | `How often it is charged · part-period charging` |
| `One-time` | `Connection, disconnection` | `Part-period charging` |
| `Refundable` | `A deposit, held and returned` | `Deposit terms` |
| `Penalty` | `Late payment, returned payment` | `What raises it` |
| `Adjustment` | `A credit or a correction` | `—` *and, under it,* `Nothing type-specific: an adjustment has no recurrence, no deposit and no trigger.` |

**Five types, in that order.** The hints that used to sit on five radio cards
are this table's middle column — the blueprint says so in its own words
(page 5): *"Five radio cards with a five-word hint each occupied a third of the
screen to ask one question with one answer. It is a select."*

## 6 · The `NOT DRIVEN BY TYPE` note — accent-ruled, inside the same card

`Two more sections appear regardless of type: an outside-city amount once a
service is chosen, and who may waive it once the charge is waivable.`

## 7 · Footer — one row, the advance alone at the right

`Continue` — drawn as the only control in the footer bar. **No `← Back` is
drawn.** It carries an accent outline with a grey label over an empty required
`CODE`; read that as the DISABLED state rather than as a tier (see the
last section).

## 8 · Cognitive load, as stated (page 5)

*"Five inputs, two lines of help, one table. Nothing is drawn twice and no
option carries prose."*

## 9 · States — the blueprint's own STATES block, verbatim (page 5)

| state | drawn behaviour |
|---|---|
| **Editing, unbilled** | *"Every field open."* |
| **Editing, already billed** | *"The code locks and says why: it is on issued bills and can no longer change. Everything else stays open."* |
| **Any service chosen** | *"The base-charge tick is disabled and says a base charge belongs to a service."* |
| **Read-only role** | *"A role that may read but not change Plans & Rates sees every figure and no button. The refusal names the role, not the screen."* |

## 10 · Components named in the frame (page 5)

`WizardFrame` `StepHead` `TextField` `SelectField` `CheckboxField` `ClassPicker`
`TypeEffectTable` `NamedAbsence`

## 11 · Rules it must obey, as stated (pages 5–6)

*"Money shows two decimals and is stored to four; a percentage six. Colour is
never the only signal — every state carries its word. A code a clerk reads down
the phone is a printed reference, not a database id, so it is shown; a database
id never is. Built in the shared utility classes, adding nothing to a
stylesheet. A control that changes a later screen says so before it is used."*

## 12 · FOR · HOW YOU GET HERE · PRIMARY ACTION (page 4)

* **FOR** — *"A clerk setting up what a utility charges beyond usage. In a new
  utility this is the **first** screen in Plans & Rates that can be finished — a
  rate schedule cannot show a base until a charge code owns one."*
* **HOW YOU GET HERE** — *"`Charge codes` tab → `+ New charge code`. Also from
  the plan builder's Charges step, which offers `Not listed? Define it in Charge
  codes →` and returns you here."*
* **PRIMARY ACTION** — *"Continue. One filled button. There is deliberately no
  Save-draft: a charge code has no draft state — it is active or deactivated —
  and the button says so rather than sitting greyed."*

## 13 · Absences — drawn as absent, do not fill them

* **No `STEP 1 OF 3` kicker** above the step heading.
* **No helper paragraph** under the step heading.
* **No `← Back`** in the footer (correct — it is step one).
* **No internal/staff description field.** It is named on step 2's
  *Not stored on a charge code* line instead.
* **No customer-class control on this step** — moved to step 2 deliberately
  (page 5: *"Customer class narrows the AMOUNT, so it belongs beside the
  amount… They are one box on the next step now. This step is identity only"*).
* **No GL account field** anywhere on this step.
* **No help under `DESCRIPTION (SHOWN ON THE BILL)`, `TYPE` or `APPLIES TO
  SERVICE`.**

---

## THE DIFF — the drawn frame against the code at 2.234.19

The screen is `07-frontend/src/features/rating/ChargeCodeWizard.tsx`; step 1 is
`BasicsStep`, **lines 679–789**, and the type control is `ChargeTypePicker`,
**lines 805–851**. The file is on
`07-frontend/src/styles/route-b-migrated.txt` (line 166), so Tailwind utilities
are lawful in it (B14 rule 21).

### What matches, exactly

| drawn | code |
|---|---|
| kicker `New charge code` / `Edit charge code` | `:598–601`, keys `rating.chargeWizard.kicker` · `.kickerEdit` |
| title `Add a fee, deposit, or adjustment.` | `:602–607`, key `rating.chargeWizard.title` |
| sub-line, word for word | `:610`, key `rating.chargeWizard.sub` |
| `Cancel` · `Save draft & exit`, in that order | `:612–632`, keys `rating.plan.cancel` (`:614`) · `rating.rate.saveDraft` (`:630`) |
| rail `Basics` · `Amount & behaviour` · `Review & save` | `:557 · :575 · :588` |
| heading `Name the charge and pick its type.` | `:695`, key `rating.chargeWizard.basics.heading` |
| field 1 `Code`, required, read-only once billed | `:699–708`; `chargeCodeIsFrozen` at `:380–382` |
| field 2 `Description (shown on the bill)`, required | `:714–722`, key `rating.chargeWizard.billLabel` |
| field 4 `Applies to service`, not required, `Any service` as the empty option | `:736–747`, keys `rating.chargeWizard.serviceLabel` · `rating.charges.anyService` |
| field 5 `This is the base charge for its service` | `:754–759`, key `rating.chargeWizard.isBaseLabel` |
| the five TYPES and their order | `CHARGE_TYPES` at `src/api/endpoints.ts:4019–4025` — `recurring · one_time · refundable · penalty · adjustment`, the drawn order exactly |
| footer holds `Continue` alone on step 1 | `components/WizardFrame.tsx:856–885` — `← Back` renders only when `nav.step > 1` |

⚠ **The `ChargeTypePicker` docstring at `:797–803` still says *"FOUR CELLS, AND
CR-013 ASKS FOR FIVE"* and cites `OQ-286` as open.** The fifth type was ruled in
on 2026-08-21 (`OQ-287`, quoted at `endpoints.ts:4008–4017`) and is served. The
comment is stale; the code is right and matches the drawing.

### 1 · THE TYPE IS A SELECT IN THE DRAWING AND A GRID OF RADIO CARDS IN THE CODE

This is the change screen 01 exists for, and it is the one thing not done.

* **drawn:** one `SELECT` showing `One-time`, with the five options and their
  descriptions moved into the `What the type decides` table below.
* **built:** `ChargeTypePicker` (`:805–851`) renders
  `<div className="grid grid-cols-4 …" role="radiogroup">` (`:814–817`) with one
  bordered `<label>` per type, **each carrying its own hint** —
  `rating.chargeWizard.typeHint.*` at `:842`.

Two consequences, both visible only in a browser:

* the hints the drawing moved into a table are still on the cards
  (`typeHint.recurring` = *"Every bill — standing charges"*, and four more);
* **the grid is `grid-cols-4` and there are now FIVE types**, so `Adjustment`
  wraps onto a second row on its own. `tsc` and every test pass on that.

### 2 · `What the type decides` DOES NOT EXIST, AND NEITHER DOES `TypeEffectTable`

`grep -rn "TypeEffectTable" 07-frontend/src` returns nothing. What the product
renders in its place is a `MoreAbout` disclosure (`:846–848`) holding one
sentence, `rating.chargeWizard.typeSetPending` = *"These are the types a charge
code can be."*

The mapping the table publishes IS in the code and is correct —
`stepTwoSections` (`:348–373`) returns `recurrence · proration` for recurring,
`proration` for one-time, `deposit` for refundable, `event` for penalty and
nothing for adjustment, which is the drawn table row for row. **It is simply
never shown to a clerk before they choose**, which is exactly the blueprint's
complaint (page 5: *"a clerk met that for the first time after pressing
Continue"*).

⚠ **AND THE DRAWN TABLE PROMISES SOMETHING THE PRODUCT REFUSES.** Its `STEP 2
THEN ASKS` column reads as a list of questions; in the product every one of
those ids renders as a NAMED ABSENCE — `ArrivesWithField` at `:1035–1041`,
messages `rating.chargeWizard.section.recurrence.pending`, `…deposit.pending`,
`…event.pending`, `…proration.pending`, each of which says the column does not
exist. See the p006 file for the same contradiction from step 2's side.

### 3 · TWO CONTROLS ARE DRAWN ABSENT AND ARE BUILT AS STATED ABSENCES

Both sit between the drawn fields, so the built panel has **eight** children
where the drawing has five.

| built control | line | what it renders | drawn? |
|---|---|---|---|
| `Internal description` | `:724–727`, `ArrivesWithField`, message `rating.chargeWizard.internalPending` = *"There is one description column today, so a staff-only one is not offered."* | a bordered note between fields 2 and 3 | **not on this step** — the drawing names it once, on step 2 |
| `Customer class` | `:772–777`, `ArrivesWithField`, `tracks="DEF-471"` | a bordered note after the base tick | **not on this step** — the drawing moves the class to step 2 |
| `GL account` | `:780–785`, `GlManagedElsewhereField` | the mapped account, read-only, linking to Settings | **not drawn at all** |

### 4 · ⚠ THE `Customer class` ABSENCE SENTENCE IS FALSE AT 2.234.19

`rating.chargeWizard.customerClassPending` reads *"A charge code carries no
customer-class column, so it cannot be limited to one."*

**The column exists, is served, is accepted, and the engine narrows by it:**

* `charges.applies_to_customer_classes` — `06-backend/apps/rating/models.py:833`,
  with its ruling at `:815–832` (BR-RAT-108, PO 2026-08-21);
* it is in the writable field set — `apps/rating/services.py:4463–4466`
  (`CHARGE_FIELDS`), validated by `_customer_class_list` at `:4478`;
* it is served on every row — `apps/rating/selectors.py:2586`;
* the front end already types it — `src/api/endpoints.ts:4092`,
  `applies_to_customer_classes?: string[]` on `ChargeRow`.

What is missing is the **wizard's own draft**: `ChargeDraft`
(`ChargeCodeWizard.tsx:176–194`) has no such key, `emptyChargeDraft` (`:198–216`)
sets none and `chargePayload` (`:267–…`) posts none. So a code's class scope can
be read by the API and set by nothing a clerk can reach, while the screen tells
them the capability does not exist. **That is hard-won law 2's mirror — a live
capability behind a dead refusal** — and it is the same sentence both drawn
screens assume is working: the drawing's own card on page 8 says class variation
for a connection fee is set *"Here — the class list on this code"*.

### 5 · THE HELP LINES — THREE DIFFER, AND ONE IS DRAWN ABSENT

| # | drawn | built | key |
|---|---|---|---|
| 1 `CODE` | `Uppercased on save. Unique for this utility.` | `Letters and numbers, up to 20. Uppercased on save, unique for this utility.` | `rating.chargeWizard.codeHelp` (`:709`) |
| 2 `DESCRIPTION (SHOWN ON THE BILL)` | **none** | `This is the line the customer reads. Write it for them, not for the catalogue.` | `rating.chargeWizard.billLabelHelp` (`:720`) |
| 4 `APPLIES TO SERVICE` | **none** | `Leave this on Any service unless the charge only makes sense for one. A late fee or a returned payment belongs to the account, not to a service.` | `rating.chargeWizard.serviceHelp` (`:745`) |
| 5 base tick | `For the classes and sizes set on the next step.` | `Tick this only for the standing charge every connection on this service pays. It is what a bill and a rate schedule read the base from, and only one code per service may carry it.` | `rating.chargeWizard.isBaseHelp` (`:761–767`) |

The drawn count is the blueprint's stated budget — *"Five inputs, **two lines of
help**, one table"* — against **four** help lines built, one of them 46 words.
B14 rule 33 caps an instruction at six words per sentence; the built lines 2, 4
and 5 are what that cap is about, and rule 32's *one sentence per section* is
the same finding one level up.

⚠ **The drawn help for the base tick says something different rather than
shorter.** *"For the classes and sizes set on the next step"* points at step 2's
grid; the built sentence explains what a base charge is. Both are true; only one
is the drawing's.

### 6 · THE STATES — THREE OF FOUR ARE BUILT, ONE COULD NOT BE VERIFIED

| drawn state | built |
|---|---|
| Editing, unbilled — every field open | ✓ default |
| Editing, already billed — the code locks and says why | ✓ `readOnly={props.frozenCode}` (`:707`) with `rating.chargeWizard.codeFrozen` = *"This code is already on issued bills, so it can no longer be changed. Everything else on this screen still can."* |
| Any service chosen — the tick is **disabled** and says why | **partly.** The tick is NOT disabled: `CheckboxField` at `:754–759` takes no disabled prop and the code instead *forces* `is_base` false when the service is cleared (`:741–743`), and the `Note` at `:760–768` swaps to `isBaseNeedsService` = *"A base charge belongs to a service, so pick one above before declaring this the base."* The sentence is drawn; the disabled state is not built |
| Read-only role — every figure, no button, the refusal names the role | **not verifiable from source.** No role gate appears in this file; whatever a read-only role sees is the shell's, and this pass booted no stack |

### 7 · `HOW YOU GET HERE` — the first door works, the second is one-way

* `Charge codes` tab → `+ New charge code` — ✓, and pinned by a test
  (`ChargeCodeWizard.test.tsx:575`).
* The plan builder's `Not listed? Define it in Charge codes →` — the door
  exists: `PlanWizard.tsx:220` declares `NEW_CHARGE_ROUTE` and `:1911`
  navigates to it. **`and returns you here` is not built.** Every exit from this
  wizard goes to the charge-codes list and nowhere else —
  `ChargeCodeWizard.tsx:613` (Cancel), `:648` (`onCommitted`), `:598` (the back
  link) — and `PlanWizard` holds its draft in React state alone (no `exit`
  park/resume prop is passed, no storage), so a clerk who steps out to define a
  code returns to a list, not to their plan.

### 8 · THE REQUIRED MARKER IS MISSING FROM `TYPE`

The frame draws `TYPE*`. `ChargeTypePicker` renders its label as a bare
`<span>` (`:813`) rather than through the kit's `FieldLabel`, so no asterisk is
emitted and nothing carries `aria-required`. B14 rule 10 — *"Required fields
carry the asterisk on the label"* — is unmet here. Fields 1 and 2 pass
`required` correctly (`:705`, `:719`); field 4 is drawn without an asterisk and
is built without one, which agrees.

---

## DIVERGENCES — B14 rule 38 (the UI rules win, nothing is built for these)

Rule 38, PO 2026-09-10: *"if you are doing a form - go as per our UI rules"*.
Each of these is FORM CONSTRUCTION, so the drawing loses and the divergence is
recorded rather than acted on.

1. **The frame draws no back link in its header.** The screen renders one above
   the frame (`:598`). A page header's `←` is B14 rules 1–2. UI rules win.
   ⚠ **What it SAYS is a separate matter and is already recorded** — it reads
   `← Plans & Rates` while it exits to the charge-codes list; the p013 file
   §"the back link names the wrong place" carries it, and `:598` is a second
   instance of the same `rating.kicker` label on a charge-codes route.
2. **`Cancel` is drawn as bare accent text.** The kit renders it as
   `Button variant="ghost"` (`:613`). UI rules win.
3. **No `STEP 1 OF 3` is drawn.** `StepHead` (`:661–675`) prints it on every
   step of five wizards. B14 rule 3's numbered rail plus the shared frame settle
   this; removing it is a five-wizard change on one screen's drawing. UI rules
   win — and it is the same call the p011 file made.
4. **Help is drawn ABOVE the input.** This one is NOT a divergence: the kit
   already puts help between the label and the input (`components/FormModal.tsx`
   `TextField` at `:240–244`, `SelectField` at `:362–366`). Drawing and kit
   agree.

---

## THE BLUEPRINT AGAINST ITSELF — recorded, not resolved

1. **`Save draft & exit` is drawn LIVE and declared ABSENT on the same page.**
   The frame draws it as an ordinary outlined button; the specification on
   page 4 says *"There is deliberately no Save-draft: a charge code has no draft
   state — it is active or deactivated — and the button says so rather than
   sitting greyed."* The product follows the SPEC (`:623–631`, `GuardedButton
   readOnly` with `rating.chargeWizard.saveDraftPending`). Recorded in the p011
   file too; nothing is resolved here.
2. **Step 1 promises questions step 2 says it cannot record.** The drawn type
   table's `STEP 2 THEN ASKS` column names *part-period charging* for two types,
   while the step-2 frame's own `Not stored on a charge code` line says
   part-period charging *"has no column"*. Both are the same document. The
   product treats them as absences.
3. **`ClassPicker` is named in this screen's COMPONENTS list** (page 5) while
   this screen's own specification moves the customer class to step 2 (*"This
   step is identity only"*). The component list and the frame disagree about
   which step owns the class.

---

## FOR THE PRODUCT OWNER

1. ⚠ **A LIVE CAPABILITY SITS BEHIND A REFUSAL THAT IS NO LONGER TRUE.** A
   charge code CAN be limited to named customer classes today — the column, the
   validator, the API and the engine all exist — and this screen tells a clerk
   it cannot (§4 above). Both drawn charge-code screens assume the control is
   there. Whether the class list belongs on step 1 (where the product's dead
   note sits) or on step 2 (where the drawing puts it, beside the amount) is a
   design call, not a lane's.
2. ⚠ **FOUR-DECIMAL MONEY IS DRAWN THROUGHOUT THIS SECTION** — nothing on step 1
   itself, but the frame's sibling steps draw `45.0000`, `60.0000`, `110.0000`.
   `CLAUDE.md` hard rule 2, PO re-sign 2026-08-22, verbatim: *"We already
   confirmed this - MOney 4 decimal, percentage 6 decimal , display both 2
   decimal"*, and the server implements it
   (`06-backend/apps/rating/selectors.py:_display_money`). The blueprint's own
   RULES row on page 5 says *"Money shows two decimals and is stored to four"* —
   so the document contradicts its own frames. **Both are recorded; neither is
   followed.**
3. **The type control's shape is a real choice, not a construction detail.** The
   drawing asks for a select plus a comparison table; the product ships five
   cards each carrying prose. B14 rule 8 governs a select's chevron and
   type-to-filter, and settles nothing about which control this field should be,
   so this one is the drawing's to win — but it deletes five hint strings from
   the screen and adds a table nothing in the kit draws.

---

## WHAT COULD NOT BE VERIFIED WITHOUT THE APP RUNNING

* Whether the drawn footer `Continue` is the **disabled primary** or a tier. The
  frame shows an accent outline with a grey label over an empty required field;
  both readings fit the picture. No stack was booted.
* The **read-only role** state (§6). Nothing in this file gates on a role.
* Whether five type cards in a four-column grid wrap where the screenshot
  suggests, and how the two-line cards sit beside the one-line ones. Layout,
  alignment and spacing rhythm are hard-won law 6's gap: this pass read a PDF
  and a source tree, not a browser.

## THE ELEVEN CATALOGUES

Every key this step renders is **present in all eleven locales** — 0 missing, 0
empty, checked over the 47 keys `BasicsStep`, `ChargeTypePicker`, `StepHead`,
`PageHeader` and `WizardFrame` resolve on this screen.

⚠ **26 of those 47 are ENGLISH VERBATIM in five of them** — `es-MX`, `hi`,
`id-ID`, `ja-JP`, `ko-KR` — including `rating.chargeWizard.basics.heading`,
`.billLabel`, `.serviceLabel`, `.isBaseLabel` and four of the five
`rating.chargeWizard.typeHint.*` (`adjustment` is translated). `de`, `es`, `fr-FR`, `it-IT` and `pt-BR` are
translated. That is B14 rule 35's subject — a catalogue written in its own
language — and it is present-but-untranslated rather than missing, so nothing
renders as silence. (`rating.charges.col.code` is identical in `de` because the
German word is `Code`; that one is a false positive.)

---

## ⚠ AMENDED 2026-09-10 — WHAT THIS FILE'S DIFF NO LONGER DESCRIBES

**Built this day under `CR-087` maintenance (decision log, *THE CHARGE CODES TAB
AGAINST ITS DRAWN BLUEPRINT*). Read the diff above as the record of what was
found, not as the state of the code.**

| §  | finding | now |
|---|---|---|
| §1 | the type is five radio cards in a `grid-cols-4`, so `Adjustment` wraps alone | **FIXED** — one `SelectField`, five options, `DEF-RAT-4831` |
| §2 | `What the type decides` does not exist; the mapping is never shown before the choice | **BUILT** — `TypeEffectTable`, its rows `CHARGE_TYPES` and its third column `sectionsForType`, extracted from `stepTwoSections` so the promise and the behaviour are ONE mapping. The frame's `NOT DRIVEN BY TYPE` note is built too, shortened to rule 33's cap |
| §3 | the `Customer class` stated absence sits between the drawn fields | **DELETED** — see §4 |
| §4 | the `Customer class` refusal sentence is FALSE at 2.234.19 | **FIXED** — the sentence and its label are RETIRED from all eleven catalogues, `ChargeDraft` gained `applies_to_customer_classes`, and the real control (`ChipMultiSelect`, B14 rule 9) is on **step 2** beside the amount, which is this file's own §13 placement. `DEF-RAT-4830` |
| §8 | `TYPE` carries no asterisk and no `aria-required` | **FIXED** — `SelectField` draws both through the kit's `FieldLabel`. `DEF-RAT-4831` |
| §5 | the four help lines against the drawn two | **NOT CHANGED.** A copy cut is its own change with its own reading; nothing here was re-worded except the two sentences item 4 required |
| §6 | the base tick is not DISABLED when a service is cleared | **NOT CHANGED** — recorded, not built |
| §7 | the plan builder's door is one-way | **NOT CHANGED** — parking a plan draft is a `PlanWizard` change |

⚠ **THE `ChargeTypePicker` DOCSTRING THIS FILE QUOTES IS GONE.** It said *"FOUR
CELLS, AND CR-013 ASKS FOR FIVE"* and cited `OQ-286` as open, over an enum the PO
closed on 2026-08-21. Hard-won law 1: the code was right and its own comment was
the thing that was wrong.
