# 03 · Charge code → Create · Step 3 · Review & save — THE DRAWN SPEC

`S12 · CHG-02` · route `/:tenant/plans-rates/charge-codes/new` and
`…/:definitionId/edit` · **blueprint pages 10–12**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, section
`01 CHARGE CODES`, screen `03`. The section head opens at the foot of **page 10**,
the frame is **drawn on page 11**, the specification runs on **page 12**. Read as
RENDERED pages — the three-column comparison table, the seven-cell plain grid and
the footer split are drawn, and text extraction alone prints them out of order.

**State chips on the screen head:** `NEW READ` · `NO COMMITMENT`
**Screen question, verbatim:** *"Is this what I just typed?"*

**What this file is.** Only the **bordered grey frame on page 11** is the
specification. The amber *"What was wrong"* block above it is the problem
statement, never the target: *"The review read back the amount already in force
instead of the one just typed, and nothing recorded why a fee moved."*

⚠ **THE BLUEPRINT'S MASTHEAD (page 1) DISCLAIMS ITS OWN AS-BUILT LINES** —
*"Every as-built statement here was true at version 2.232.0, commit d2d493e4, on
8 September 2026, and must be re-verified"*. We are on **2.234.19**. Every
"the product currently does X" line below was re-checked against the code and is
cited with a file and a line.

⚠ **B14 rule 37** — every figure inked into the frame (`$45.0000`, `$52.0000`,
`+$7.0000`, `CONN`, `4200-01`) is an ILLUSTRATION. Nothing below records a drawn
number as a requirement, and no test may assert one.

---

## 1 · Header — drawn once, identical on all three steps

| slot | drawn |
|---|---|
| kicker | `NEW CHARGE CODE` |
| title (H1) | `Add a fee, deposit, or adjustment.` |
| sub-line | `Charge codes are the non-usage line items on a bill. Three steps · takes about 2 minutes.` |
| top-right, in order | `Cancel` *(bare accent text)* · `Save draft & exit` *(outlined button)* |
| back link | **none drawn inside the frame** |

## 2 · Step rail — three, `3 Review & save` active

`1 Basics` | `2 Amount & behaviour` | `3 Review & save`

## 3 · Step body — heading and hint

| slot | drawn |
|---|---|
| heading (H2) | `Review and save.` |
| hint | `Everything that is changing, beside what it is changing from.` |

**No `STEP 3 OF 3` kicker is drawn above the heading.**

## 4 · The comparison table — FOUR columns, the first unheaded

| # | header | drawn cells |
|---|---|---|
| 1 | *(no header)* | `Amount` · `Applies to service` · `May be taxed` |
| 2 | `NOW` | `$45.0000` · `Any service` · `No` |
| 3 | `SAVING` | `$52.0000` · `Any service` · `Yes` |
| 4 | `CHANGE` | `+$7.0000` *(accent, monospace)* · *(blank)* · `changed` *(accent)* |

**The three drawn rows, in order:**

| | NOW | SAVING | CHANGE |
|---|---|---|---|
| `Amount` | `$45.0000` | `$52.0000` | `+$7.0000` |
| `Applies to service` | `Any service` | `Any service` | |
| `May be taxed` | `No` | `Yes` | `changed` |

⚠ The `Applies to service` row is drawn UNCHANGED and still present, which
contradicts §9's *"Only what is changing is in the comparison table"* — see §13.

## 5 · The plain grid below it — SEVEN cells, three across

| # | label, as drawn | value, as drawn |
|---|---|---|
| 1 | `CODE` | `CONN` |
| 2 | `DESCRIPTION (SHOWN ON THE BILL)` | `Connection fee` |
| 3 | `TYPE` | `One-time` |
| 4 | `THIS IS THE BASE CHARGE FOR ITS SERVICE` | `No` |
| 5 | `HOW THE AMOUNT IS WORKED OUT` | `A fixed amount` |
| 6 | `AMOUNT PER CONNECTION SIZE` | `One amount for every connection size.` |
| 7 | `GL ACCOUNT` | `4200-01 — Connection revenue` *(monospace)* |

## 6 · The reason box — REQUIRED, and new

| slot | drawn |
|---|---|
| label | `WHY THIS CHANGED` **with the asterisk** |
| help, drawn **ABOVE** the input | `Kept with the change. It is what the next person reads when they ask why this fee moved.` |
| control | a single-line bordered text box, full width, empty |

## 7 · The consequence note — accent-ruled, above the footer

| slot | drawn |
|---|---|
| kicker | `WHAT SAVING DOES` |
| body | `Saving changes what this code charges from now on. A bill already issued is never re-priced.` |

## 8 · Footer — one row, the commit alone at the right

`Save charge code` — drawn as the only control in the footer bar. **No `← Back`
is drawn.** The button is drawn with an accent outline and grey label; with the
required reason box empty above it, read that as the DISABLED state rather than
as a tier (see §14).

## 9 · Cognitive load, as stated (page 12)

*"Only what is changing is in the comparison table. Everything unchanged drops to
the plain grid below it, so a three-field change does not read as a nineteen-field
one."*

## 10 · States — the blueprint's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **Creating** | *"No comparison table — there is nothing to compare against. The grid alone, and no reason box."* |
| **Editing, nothing changed** | *"The comparison table is absent rather than showing three unchanged rows. The Save button stays live: a clerk may have come only to add the reason."* |

## 11 · Components named in the frame

`WizardFrame` `OldNewTable` `FieldGrid` `TextArea` `ConsequenceNote`

## 12 · Rules it must obey, as stated (page 12)

*"Money shows two decimals and is stored to four; a percentage six. Colour is
never the only signal — every state carries its word. A code a clerk reads down
the phone is a printed reference, not a database id, so it is shown; a database id
never is. Built in the shared utility classes, adding nothing to a stylesheet. A
review screen states what saving does before the button, never after."*

## 13 · FOR · HOW YOU GET HERE (page 12)

* **FOR** — *"A clerk about to commit a price change that reaches every plan
  carrying this code."*
* **HOW YOU GET HERE** — *"Continue from step 2, or the rail."*
* **PRIMARY ACTION** — *"Save charge code."*

## 14 · Absences — drawn as absent, do not fill them

* **No `STEP 3 OF 3` kicker** above the step heading.
* **No `← Back`** in the footer.
* **No sample bill line** anywhere on the frame.
* **No `Amount`, `Applies to service` or `May be taxed` row in the plain grid** —
  all three are in the comparison table, and the grid holds the other seven facts.
* **No back link** inside the frame's header.

---

## THE DIFF — the drawn frame against the code at 2.234.19

The screen is `07-frontend/src/features/rating/ChargeCodeWizard.tsx`;
step 3 is `ReviewStep`, **lines 1333–1425**. It is on
`07-frontend/src/styles/route-b-migrated.txt` (line 166), so Tailwind utilities
are lawful in it (B14 rule 21).

### What matches, exactly

| drawn | code |
|---|---|
| kicker `New charge code` | `ChargeCodeWizard.tsx:601`, key `rating.chargeWizard.kicker` |
| title `Add a fee, deposit, or adjustment.` | `:605`, key `rating.chargeWizard.title` |
| sub-line, word for word | `:610`, key `rating.chargeWizard.sub` |
| `Cancel` · `Save draft & exit`, in that order | `:612–632`, keys `rating.plan.cancel` (`:614`) · `rating.rate.saveDraft` (`:630`) |
| rail `Basics` · `Amount & behaviour` · `Review & save` | `:557 · :575 · :588` |
| heading `Review and save.` | `:1401`, key `rating.chargeWizard.review.heading` |
| commit `Save charge code` | `:643–645`, key `rating.charges.form.addSubmit` |
| grid labels 1–7 | all present as the row list at `:1348–1394` — see below |

### 1 · THE COMPARISON TABLE DOES NOT EXIST — the whole point of the screen

`ReviewStep` builds ONE flat list of ten facts (`ChargeCodeWizard.tsx:1348–1394`)
and renders it in one `<dl className="grid grid-cols-2 …">` at `:1405`. There is
no NOW column, no SAVING column, no CHANGE column and no per-field diff anywhere
in the file. **No old/new comparison component exists in the kit at all** —
`grep -rn "OldNew\|beforeAfter" 07-frontend/src` returns nothing outside tests.

⚠ **The read-back defect the frame was drawn to fix is STILL LIVE, and the code
says so in its own words.** `ChargeCodeWizard.tsx:1346–1348`:

```
const amountLine =
  charge === null ? null : t(chargeAmountDisplay(charge).key, chargeAmountDisplay(charge).params);
```

`charge` is the SERVER'S row — the amount already in force. On an edit the
`Amount` cell (`:1387–1390`) therefore reads back **the stored amount, never the
typed one**, which is the blueprint's *"A clerk retyped 45 → 52, reached this
screen and read back 45"* reproduced exactly. Only when `charge === null`
(creating) does it fall through to `rating.chargeWizard.amountAsTyped` =
*"As typed above"*.

⚠ **The reason the code gives for it is sound and is the reason the fix belongs
on the SERVER.** The comment at `:1341–1345` says a created code *"has no server
row yet and therefore no display string — so the read-back says 'as typed' rather
than formatting the typed value here, which would be client-side money arithmetic
on a value the server owns"* (BR-RAT-087 / DEF-364). A `SAVING` column has the
same constraint: the typed string cannot be formatted in the browser. **Drawing
it needs a served preview or the typed string shown verbatim and labelled as
such — not a client-side format.** Open, and named for the PO below.

### 2 · THE TEN FACTS ARE ALL THERE — the SHAPE is what is missing

The drawn 3 comparison rows + 7 grid cells are the same ten facts the code
already lists, in the same order:

| # | drawn | code row (`ChargeCodeWizard.tsx`) | label key | renders |
|---|---|---|---|---|
| 1 | `CODE` | `:1349` | `rating.charges.col.code` | `Code` ✓ |
| 2 | `DESCRIPTION (SHOWN ON THE BILL)` | `:1350` | `rating.chargeWizard.billLabel` | `Description (shown on the bill)` ✓ |
| 3 | `TYPE` | `:1351` | `rating.charges.col.type` | `Type` ✓ |
| 4 | *(comparison)* `Applies to service` | `:1355` | `rating.filter.service` | **`Service`** ✗ |
| 5 | `THIS IS THE BASE CHARGE FOR ITS SERVICE` | `:1356` | `rating.chargeWizard.isBaseLabel` | ✓ |
| 6 | `HOW THE AMOUNT IS WORKED OUT` | `:1360` | `rating.charges.amountRuleLabel` | ✓ |
| 7 | *(comparison)* `Amount` | `:1366` | `rating.charges.col.amount` | `Amount` ✓ |
| 8 | `AMOUNT PER CONNECTION SIZE` | `:1375` | `rating.chargeWizard.section.perSize` | ✓ |
| 9 | `GL ACCOUNT` | `:1386` | `rating.charges.col.gl` | `GL account` ✓ |
| 10 | *(comparison)* `May be taxed` | `:1391` | `rating.chargeWizard.taxableLabel` | `May be taxed` ✓ |

**One label differs:** row 4 renders `Service`, the frame says
`Applies to service`. The correct key already exists —
`rating.chargeWizard.serviceLabel` = *"Applies to service"*, used by step 1 at
`:738`. This is one key swap, not new copy.

### 3 · THE HINT UNDER THE HEADING IS A DIFFERENT SENTENCE

* **drawn:** `Everything that is changing, beside what it is changing from.`
* **built:** `rating.chargeWizard.review.hint` = *"Once saved, this charge code
  can be attached to any plan. Changing it later never changes a bill that has
  already been issued."*

The built sentence is the CONSEQUENCE the frame moves into §7's
`WHAT SAVING DOES` box. The frame therefore asks for the sentence to MOVE and be
replaced, not for a second one to be added — one sentence per section, B14 rule 32.

### 4 · THE REASON BOX DOES NOT EXIST ANYWHERE IN THIS WIZARD

No `WHY THIS CHANGED` field, no `TextArea`, and no key for either. `grep -n
"reason" ChargeCodeWizard.tsx` returns nothing. The blueprint's *"WHY THIS
CHANGED · New"* is accurate at 2.234.19.

⚠ **The pattern already exists one screen over**, which is what the frame means
by *"the shape you signed off for the rate wizard"*: `rating.rate.reasonLabel` =
*"Reason for this change"* with `rating.rate.reasonHelp` = *"Required: a change to
a live schedule creates a new version, and the reason goes into the compliance
record."* A charge code has **no version table** to file it against (see the p018
file, §"no ChargeVersion model"), so where the reason is STORED is an open
question rather than a copy job.

### 5 · THE CONSEQUENCE NOTE IS NOT BUILT, AND B14 RULE 11 ASKS FOR ONE ANYWAY

`ChargeCodeWizard.tsx:1422–1425` renders an **`ArrivesWith`** panel instead:

* title `rating.chargeWizard.sample` = *"How it reads on the bill"*
* body `rating.chargeWizard.samplePending` = *"The customer will see the line
  "{{label}}". The amount beside it is worked out and formatted by the server when
  the charge is saved, so it is shown on the charge code's own page rather than
  guessed here."*

**The frame draws no sample bill line at all** (§14). B14 rule 11 —
*"Any form writing money … shows a 'what this will do' box before its commit
button"* — is unmet on this screen: `ConsequenceBox` exists at
`07-frontend/src/components/ConsequenceBox.tsx` and is used by 20 other screens;
this wizard does not import it (`ChargeCodeWizard.tsx:66–122`).

### 6 · THE `STEP 3 OF 3` KICKER IS BUILT AND IS NOT DRAWN

`StepHead` (`:661–673`) renders `rating.chargeWizard.stepOf` = *"Step {{step}} of
{{total}}"* above every step heading. The frame draws the heading directly under
the rail. **Recorded, not actioned** — the rail already says which step this is,
and removing it changes all three steps of a five-wizard shell.

### 7 · `Save draft & exit` IS DISABLED WITH ITS REASON, AND THE BLUEPRINT
CONTRADICTS ITSELF ABOUT IT

Code: `GuardedButton readOnly` at `:623–631`, reason
`rating.chargeWizard.saveDraftPending` = *"A charge code has no draft state to
save into. It is active or deactivated, nothing in between, so there is nowhere to
keep a half-finished one. Cancel leaves without saving."* (DEF-375).

The frame **draws the button live**. The blueprint's own screen-01 specification,
**page 4**, says the opposite of its own frame: *"There is deliberately no
Save-draft: a charge code has no draft state — it is active or deactivated — and
the button says so rather than sitting greyed."* **Frame and spec disagree inside
one document; nothing is resolved here.** The code follows the SPEC text and not
the frame, and B14 rule 37 says a drawn control's appearance is not a fact.

---

## DIVERGENCES — B14 rule 38 (the UI rules win, nothing is built for these)

Rule 38, PO 2026-09-10: *"if you are doing a form - go as per our UI rules"*.
Each of these is FORM CONSTRUCTION, so the drawing loses and the divergence is
recorded rather than filed.

1. **Help text is drawn ABOVE the reason input.** The kit puts help under its
   input. UI rules win.
2. **`Cancel` is drawn as a bare accent text link.** The kit renders it as
   `Button variant="ghost"` (`:612`). A control a person presses is a `<button>`
   — the skill's *"a clickable `<div>` is a defect"*, one step along. UI rules win.
3. **The footer draws the commit alone.** `WizardFrame`'s footer carries
   `← Back` beside the commit (`components/WizardFrame.tsx:854–862`), which is
   B14 rules 1 and 3. UI rules win.
4. **The frame draws no back link in the header.** The screen renders
   `← Plans & Rates` (`:598`). A page header's `←` is B14 rule 1 and is not the
   frame's to remove — though **what it says is wrong**, see the p013 file §"the
   back link names the wrong place".

---

## THE BLUEPRINT AGAINST ITSELF — recorded, not resolved

1. **THE FRAME DRAWS AN EDIT INSIDE THE NEW-CHARGE-CODE HEADER.** The comparison
   table can only exist when editing (§10: *"Creating → No comparison table"*),
   and the reason box is drawn filled-in-required — yet the kicker reads
   `NEW CHARGE CODE`, the title reads `Add a fee, deposit, or adjustment.` and the
   commit reads `Save charge code`. In the product the edit head is
   `rating.chargeWizard.kickerEdit` = *"Edit charge code"* /
   `rating.chargeWizard.editTitle` = *"Change what {{code}} charges."* and the
   commit is `rating.charges.form.editSubmit` = *"Save changes"*
   (`ChargeCodeWizard.tsx:601–606`, `:643–645`). **One of the two halves of the
   frame is drawn in the wrong mode and the document does not say which.**
2. **`Applies to service` IS DRAWN IN THE COMPARISON TABLE UNCHANGED** while §9
   says the comparison table holds *only what is changing*. Its `CHANGE` cell is
   blank, which is the tell.
3. **`Save draft & exit` — drawn live, declared absent on page 4.** See §7 above.
4. **MONEY IS DRAWN TO FOUR DECIMALS THROUGHOUT** — `$45.0000`, `$52.0000`,
   `+$7.0000` — on the same page whose own RULES row reads *"Money shows two
   decimals and is stored to four"*. See the next section.

---

## FOR THE PRODUCT OWNER — the drawing against a signed rule

⚠ **FOUR-DECIMAL MONEY ON SCREEN CONTRADICTS A PO RE-SIGN.** `CLAUDE.md` hard
rule 2, PO re-sign 2026-08-22, verbatim: *"We already confirmed this - MOney 4
decimal, percentage 6 decimal , display both 2 decimal"*. The server implements
it: `06-backend/apps/rating/selectors.py:208–227` (`_display_money`) quantizes
every served `*_display` string to `TWO_PLACES`, and the screens render only those
strings (BR-RAT-087 / DEF-364). **Every money figure on this frame is drawn at
four decimals.** B14 rule 37 makes the drawn NUMBERS illustrations; it does not
obviously settle the drawn FORMAT. **Both are recorded; neither is followed.**
The blueprint's own PRB-01 card (page 20) contradicts its own frames here too —
it instructs *"types 45.0000 against Residential"* and then says *"a commercial
move-in is quoted $85.00 while a residential one is quoted $45.00"*, two decimals,
in the same paragraph.

**Second item for the PO, and it is a real design question rather than a
divergence:** the drawn `SAVING` column has to render a money value the browser
has NOT been given a display string for — the row is not saved yet. Either the
server previews it or the typed string is shown verbatim and labelled as typed.
Choosing in a component would be client-side money arithmetic on a value the
server owns, which is what DEF-364 was.

---

## WHAT COULD NOT BE VERIFIED WITHOUT THE APP RUNNING

* Whether the drawn footer commit is the **disabled primary** or a **tier**.
  The frame shows an accent outline with a grey label over an empty required
  field; both readings are consistent with the picture. No stack was booted.
* Alignment, spacing rhythm and the exact column widths of the drawn comparison
  table. Hard-won law 6 — nothing in this repo reads rendered output, and this
  pass read a PDF and a source tree, not a browser.

## THE ELEVEN CATALOGUES

Every key this screen renders is **present in all eleven locales** — 0 missing,
0 empty, checked over `rating.chargeWizard.*`, `rating.charges.*` and
`rating.definition.*` (225 keys × 11 files).

⚠ **BUT 50 OF THE 70 `rating.chargeWizard.*` KEYS ARE ENGLISH VERBATIM IN FIVE
OF THEM** — `es-MX`, `hi`, `id-ID`, `ja-JP`, `ko-KR`. `rating.chargeWizard.review.heading`
reads `Review and save.` in `ja-JP.json` and `ko-KR.json`. `de`, `es`, `fr-FR`,
`it-IT` and `pt-BR` are translated. That is B14 rule 35's subject — a catalogue
written in its own language — and it is present-but-untranslated rather than
missing, so nothing renders as silence.

---

## ⚠ AMENDED 2026-09-10 — WHAT MOVED, AND WHAT DELIBERATELY DID NOT

**`CR-087` maintenance (decision log, *THE CHARGE CODES TAB AGAINST ITS DRAWN
BLUEPRINT*).**

| §  | finding | now |
|---|---|---|
| §2 | row 4 renders `Service`, the frame says `Applies to service`, and the right key already exists | **FIXED** — one key swap, no new copy. `rating.chargeWizard.serviceLabel`, the same sentence step 1 uses |
| — | the review read back nothing about the customer class | **ADDED** — the reach reads back beside the service, `[]` rendering as *Every customer type* and never as a blank. It is not a drawn row, and it is here because a wizard that lets you SET a field and never reads it back is a half-built control (`DEF-RAT-4830`) |
| §1 | no NOW / SAVING / CHANGE comparison table | **NOT BUILT, AND NOT STUBBED.** The `SAVING` column has to render a money value the browser has been given no display string for — the row is not saved yet — so drawing it needs a served preview or the typed string shown verbatim and labelled as typed. Choosing in a component is client-side money arithmetic on a value the server owns, which is what `DEF-364` was. Named for the PO |
| §1 | the `Amount` cell reads back the STORED amount on an edit, not the typed one | **NOT FIXED** — it is the same server-side question as the row above, and half-fixing it in the browser is the defect it is trying to cure |
| §4 | no `WHY THIS CHANGED` box | **NOT BUILT, AND NOT STUBBED.** There is nowhere to store a reason: a charge code has no version table. The blueprint says the box and the Audit tab *"only work together"*, and the sizing is in the decision log of 2026-09-10 §7 |
| §3 | the hint under the heading is the CONSEQUENCE sentence the frame moves into `WHAT SAVING DOES` | **NOT CHANGED** — it moves with the consequence box, which moves with the reason box |
| §5 | B14 rule 11's `ConsequenceBox` is unmet on this screen | **NOT CHANGED** — recorded, and it is the same block of work |
