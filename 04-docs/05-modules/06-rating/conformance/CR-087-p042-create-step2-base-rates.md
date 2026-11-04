# 14 · Rate schedule → Create · Step 2 · Base rates — THE DRAWN SPEC

`S11 · RAT-03` · route `/:tenant/plans-rates/rates/:id/edit` · **blueprint pages 42–45**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, section opening
on page 42, **frame drawn across pages 42–43**, specified on 43–45. Read as
RENDERED pages — the four-column matrix, the two stacked cells in the base column
and the ORDER of the link and the two callouts under the table are only visible
as a picture; text extraction prints `Add row` before the link and both callouts
out of sequence.

**State chip:** `NEW BUILD`
**Commitment:** `PRB-08` — *"A rate schedule's minimum reaches the engine"*, waiting
on `DEF-2446`. Screens `14` · `18`.

**Masthead warning, applied.** Every *"as-built"* line was true at **2.232.0**; we
are on **2.234.19** and each was re-checked below.

---

## 1 · Header, step rail, footer — the wizard frame, unchanged from step 1

Kicker `PLANS & RATES` · title `New version of Sample — Residential water` ·
sub-line *"One pricing formula for one service. The name is internal: customers
see the plan name, not this one."* · actions `Cancel` and `Save draft & exit`
top-right · rail `1 Basics | 2 Base rates | 3 Rates | 4 Effective & approval |
5 Review & activate` with **`2 Base rates` active** · footer `Continue`,
right-aligned.

## 2 · The panel — `Base rates`

**Heading:** `Base rates`
**Hint, verbatim:** `The base belongs to charge code BASE-W and is read-only here. Change it there and every schedule and plan carrying it follows.`

## 3 · `WHICH BASE APPLIES` — an accent callout ABOVE the table

> `This schedule prices the Residential class, so its base comes from BASE-W-RES.`
> `An industrial schedule for the same service reads BASE-W-IND — one service,`
> `two bases, one per class.`

Drawn as an accent-ruled callout (left rule, small caps legend), the same
treatment as the two callouts below the table.

## 4 · The matrix — FOUR columns, in this order

| # | header | alignment | content |
|---|---|---|---|
| 1 | `SIZE` | left, **bold value** | `2"` · `4"` · `6"` |
| 2 | `BASE CHARGE` | left, two stacked lines | amount `$8.0000`, then quiet `BASE-W-RES · Residential` |
| 3 | `MINIMUM RATE` | left, an **input box** | `18.50` · `24.00` · em-dash + `No row — this size uses the schedule's single minimum rate.` |
| 4 | `PER-SIZE ROW` | left, one button | `Remove row` where a row exists · `Add row` where none does |

**The three drawn rows:**

| SIZE | BASE CHARGE | MINIMUM RATE | PER-SIZE ROW |
|---|---|---|---|
| `2"` | `$8.0000` / `BASE-W-RES · Residential` | `18.50` (input) | `Remove row` |
| `4"` | `$8.0000` / `BASE-W-RES · Residential` | `24.00` (input) | `Remove row` |
| `6"` | `$8.0000` / `BASE-W-RES · Residential` | `—` / `No row — this size uses the schedule's single minimum rate.` | `Add row` |

⚠ **B14 rule 37 — `$8.0000`, `18.50`, `24.00` and the three diameters are
ILLUSTRATIONS.** The shape is: a base attributed to a code AND a class, an
editable minimum, and an empty cell that says what an empty cell means.

⚠ **THE BASE CELL CARRIES TWO FACTS, NOT ONE.** Page 43: *"This screen now names
the code **and** the class it resolved from, so a clerk can see at a glance that a
residential schedule is reading the residential base."*

## 5 · `Open BASE-W-RES to change the base` — a link, immediately under the table

Drawn as an accent-coloured inline link, left-aligned, directly beneath the last
row and above the two callouts. Page 44: *"The cell said `change it there` and gave
no way to get there. A link opens the right charge code — the one for this
schedule's class — and comes back."*

## 6 · Two callouts under the link, in this order

**(a) `NOT READ BY BILLING YET` — accent-ruled, loud**

> `A minimum typed here is saved and no bill reads it. Billing takes the minimum`
> `from the plan, not from this schedule — so until that is wired, these boxes`
> `change nothing a customer pays.`

**(b) an unlabelled quiet callout — grey rule**

> `Blank is not zero: a blank minimum rate means none on that size. A size the`
> `charge code has no amount for is not served, and a bill for it is refused`
> `rather than charged $0.00.`

Page 44 on (b): *"Stated once, plainly, under the table — the same sentence as the
charge code screen, deliberately word-for-word. Two screens, one fact, one
wording."*

## 7 · States — the blueprint's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **No base charge code** | *"The base column says no code is marked as this service's base and that the schedule cannot be activated until one is. It is a refusal stated three steps before it would otherwise fire."* |
| **A size the code does not price** | *"Says the size is not served and a bill for it is refused."* |
| **No size classes set up** | *"Says where to add them rather than showing an empty table."* |

## 8 · Components named in the frame

`WizardFrame` `SizeMatrix` `ReadOnlyCell` `BulkSetField` `Callout accent`

## 9 · FOR · HOW YOU GET HERE · PRIMARY ACTION · COGNITIVE LOAD

* **FOR** — *"A clerk who has already set the base on a charge code and is now saying what each size pays as a floor."*
* **HOW YOU GET HERE** — *"Continue from Basics."*
* **PRIMARY ACTION** — `Continue.`
* **COGNITIVE LOAD** — *"Add a row only where a size differs. A size with no row is priced by the schedule's single minimum on the next step, and the empty cell says exactly that instead of looking unfinished."*

## 10 · The two rules this step exists to keep, stated on page 44

* **WHERE TWO WOULD BOTH APPLY** — *"The engine refuses and names both rather than choosing. Two codes surviving the narrowing is a configuration fault, not a precedence question, and it stops one account rather than mispricing every one of them."*
* **WHAT BILLING ACTUALLY READS** — *"**Base charge:** the charge code, first and normally only. **Minimum:** the plan — **never** this schedule. Both answers are read off the engine's own code, not inferred from the screen."*

---

# THE DIFF — drawing against the code at 2.234.19

Code: `07-frontend/src/features/rating/RateScheduleWizard.tsx`, `SizeMatrixStep`
at line **1349**; column set in `RateScheduleDetail.tsx:224-229`
(`MATRIX_COLUMNS`, shared by both screens on purpose).

## D1 · TWO COLUMN HEADERS ARE THE WRONG WORDS

`RateScheduleDetail.tsx:224-229`

```tsx
export const MATRIX_COLUMNS: readonly MatrixColumn[] = [
  { key: "size", labelKey: "rating.rateDetail.matrix.col.size", editable: false },
  { key: "base", labelKey: "rating.rateDetail.matrix.col.base", editable: false },
  { key: "minimum", labelKey: "rating.rateDetail.matrix.col.minimum", editable: true },
  { key: "accounts", labelKey: "rating.rateDetail.matrix.col.accounts", editable: false },
];
```

| # | drawn header | rendered header (`en.json`) |
|---|---|---|
| 1 | `SIZE` | `Size` ✔ |
| 2 | `BASE CHARGE` | `rating.rateDetail.matrix.col.base` = **`Base`** |
| 3 | `MINIMUM RATE` | `rating.rateDetail.matrix.col.minimum` = **`Minimum bill`** |
| 4 | `PER-SIZE ROW` | `rating.rate.sizes.rowActionsHeader` = `Per-size row` ✔ |

⚠ **`Minimum bill` → `Minimum rate` IS A PO INSTRUCTION WITH A STATED CAVEAT, AND
IT REACHES THREE SURFACES.** Page 44, verbatim: *"**Minimum bill is now Minimum
rate**, on your instruction. One caution, stated once: this figure is a floor on
what the whole formula produces rather than a rate per unit, so `minimum rate`
reads as the second to some people. Your call, and it is applied here, on the
next step, and on the schedule's own page so all three agree."*

**Every place the old word is spelled today**, all eleven catalogues:

| key | value |
|---|---|
| `rating.rateDetail.matrix.col.minimum` | `Minimum bill` |
| `rating.rateDetail.field.minimumBill` | `Minimum bill` |
| `rating.rateDetail.field.minimumBillAbsent` | `No minimum bill is set, so usage and base stand on their own.` |
| `rating.rate.minimumBillLabel` | `Minimum bill on this version` (step 3, `RateScheduleWizard.tsx:1679`) |
| `rating.rate.minimumBillHelp` | `Optional floor for what this formula can produce.` |
| `rating.rate.sizes.blankIsNoFloor` | `Blank is not zero: a blank minimum bill means none on that size.` |
| `rating.rate.sizes.noRow` | `No row — this size uses the schedule's single minimum bill.` |
| `rating.rate.sizes.fallbackNote` | `A size with no row is priced by the single minimum bill on the next step.` |
| `rating.rate.sizes.setAllHelp` | `Fills the minimum bill on every row you have added. It does not add rows.` |

## D2 · THE `accounts` COLUMN IS IN THE SHARED COLUMN SET AND THE DRAWING HAS NO SUCH COLUMN

`MATRIX_COLUMNS` carries a fourth column `accounts`. On **this** step it is
filtered out (`editableMatrixColumns()` keeps only `minimum`, so the header row is
size · base · minimum · per-size row) — so step 2 is CORRECT by accident of the
filter. On the **detail** screen the same array renders it, and there the drawing
removes it explicitly. See `CR-087-p055-view-overview.md` D5.

## D3 · `WHICH BASE APPLIES` IS NOT BUILT — because the class it names is not built

**Drawn:** an accent callout naming this schedule's class and the code it resolves
to, with the industrial contrast.
**Built:** a plain `Note`, one of two sentences, neither mentioning a class.

`RateScheduleWizard.tsx:1397-1401`

```tsx
      <Note>
        {props.baseCharge !== null && !pricesBaseBySize(props.baseCharge)
          ? t("rating.rate.sizes.oneBaseEverySize")
          : t("rating.rate.sizes.baseOwnedElsewhere")}
      </Note>
```

`rating.rate.sizes.oneBaseEverySize` = *"The base comes from a charge code, so it
is read-only here and the same on every size."*
`rating.rate.sizes.baseOwnedElsewhere` = *"The base comes from a charge code, so it
is read-only here."*

**This is D1 of `CR-087-p041-create-step1-basics.md` one step downstream.** The
callout cannot say *"this schedule prices the Residential class"* while step 1
offers no class to pick, and the base cell cannot print `BASE-W-RES · Residential`
for the same reason — `BaseCell` (`RateScheduleWizard.tsx:1590`) resolves through
`baseAmountForSize(baseCharge, sizeClass)`, which narrows by **size only**.

## D4 · THE BASE CELL PRINTS THE CODE AND NOT THE CLASS

**Drawn:** `$8.0000` over `BASE-W-RES · Residential`.
**Built:** `rating.rate.sizes.fromCode` = *"Read-only · from {{code}}"* — the
amount, then the code, and no class.

Two differences, and the second is the load-bearing one: the drawn quiet line is
`<code> · <class>` where the built one is `Read-only · from <code>`. Page 43 says
what the class is doing there: *"so a clerk can see at a glance that a residential
schedule is reading the residential base."*

## D5 · THERE IS NO LINK TO THE CHARGE CODE — the named defect, still live

`grep -n "CHARGES_TAB_ROUTE\|charge-codes\|chargeCode" RateScheduleWizard.tsx`
returns **nothing**. The cell says *"read-only here"* and offers no route to the
place it can be changed, which is page 44's `WHAT CHANGED · A WAY THROUGH`
verbatim.

## D6 · THE `NOT READ BY BILLING YET` CALLOUT DOES NOT EXIST ANYWHERE IN THE PRODUCT

A grep for the fact across the whole front end finds no string saying a schedule
minimum is unread by billing. The two sentences that exist near it —
`rating.rate.minimumBillHelp` (*"Optional floor for what this formula can
produce."*) and `rating.rateDetail.field.minimumBillAbsent` — both read as though
the figure bills.

⚠ **THIS IS THE `PRB-08` COMMITMENT'S OWN SUBJECT AND IT IS A LIVE DEFECT, NOT A
FEATURE.** Page 63: *"`DEF-2446` — a minimum typed on a rate schedule is published
to the engine and read by nobody. This is a live defect, not a new feature."*
The drawing's response is to **say so on the control**, which is the blueprint's
own RULES line for this screen: *"A control that changes nothing on a bill says so
on itself."* Compare `rating.tiers.size_override_not_billed`, which does exactly
that one step later — the pattern already exists in this file.

**Not verified here:** whether the engine reads the schedule minimum today. That
is `06-backend/apps/billing/` and B4/B5 territory; the claim is the blueprint's and
`DEF-2446` is its evidence. **Reported, not re-derived** — rating maths is ❄️
FROZEN and nothing here proposes moving a signed figure.

## D7 · `BLANK IS NOT ZERO` IS HALF THE SENTENCE, AND ITS SECOND HALF IS BURIED

**Drawn:** one quiet callout carrying both facts —
*"Blank is not zero: a blank **minimum rate** means none on that size. A size the
charge code has no amount for is not served, and a bill for it is refused rather
than charged $0.00."*

**Built:** `RateScheduleWizard.tsx:1546` renders only the first half:

```tsx
      <Note>{t("rating.rate.sizes.blankIsNoFloor")}</Note>
```

The second half exists, but per-row and only when it fires:
`rating.rate.sizes.baseSizeNotServed` = *"{{code}} has no amount for this size, so
this size is not served and a bill for it will be refused rather than charged
$0.00."*, printed inside `BaseCell`. So the general rule is never stated; only the
instance is, and only on the rows it hits.

## D8 · THE SET-ALL CONTROLS ARE BUILT AND THE FRAME DOES NOT DRAW THEM

`RateScheduleWizard.tsx:1504-1535` renders three controls under the table: a
`Set every size to` text field, a `Set all` button and an `Add a row for every
size` button.

**The frame draws none of them** — the table is followed directly by the link and
the two callouts. **But the frame's own COMPONENTS line names `BulkSetField`.**
Recorded as a blueprint inconsistency below, not acted on: an absence is a
decision (§2.5) and a component list is not a control list, so this needs one
sentence rather than a deletion.

## D9 · `Remove row` / `Add row` ARE WORD BUTTONS AND THE DRAWING AGREES

`RateScheduleWizard.tsx:1474-1489` renders one `Button` per row —
`rating.rate.sizes.removeRow` = `Remove row`, `rating.rate.sizes.addRow` =
`Add row` — matching the frame character for character, in the same column.

⚠ **B14 rule 15 (row actions are ICONS) DOES NOT BITE HERE and should not be
applied.** This is a form's editable matrix, not a list table; the drawing draws
words; the tier editor one step later does the same. Recorded so a later sweep
does not "fix" it.

---

## ABSENCES — drawn as absent, do not fill them

* **No base INPUT.** Page 43-44 gives the reason at length and it is a PO ruling:
  *"the charge code owns the base amount; a plan displays it, never defines it"*
  (2026-08-20) and *"plan → charges code → base scharges"* (2026-08-31). *"Making
  it editable here would create a second place to type one number — which is how
  every bill in this product once charged $0.00 for base."*
* **No per-size accounts count** on this step.
* **No uplift / increase-all-by-%** control — the code states why at
  `RateScheduleWizard.tsx:1495-1503` (B4 rounding is ❄️ FROZEN).
* **No tier columns** on this matrix; per-size block prices are step 3's.

---

## CONTRADICTIONS AND THINGS FOR THE PRODUCT OWNER

1. **`BulkSetField` IS IN THE COMPONENTS LIST AND NOT IN THE FRAME (D8).** The
   product has the control today. Deleting it on the strength of a frame that
   also names its component would be reading one half of the page. **One
   sentence to the PO: does the set-all row stay?**

2. **THE HINT NAMES `BASE-W` AND THE CALLOUT AND ROWS NAME `BASE-W-RES`.** The
   panel hint says *"The base belongs to charge code BASE-W"*; three lines down
   the callout says the base *"comes from BASE-W-RES"* and every row is
   attributed to `BASE-W-RES`. Under **B14 rule 37** these are illustrations and
   not in conflict as VALUES — but the hint is drawing the un-narrowed code and
   the rows the narrowed one, which is a real ambiguity about **which code the
   hint should name**. Reading, offered not taken: the hint should name the
   resolved code, because that is the one the link in §5 opens. **Recorded.**

3. **PRB-08 IS `UNVERIFIED` AND ITS SCREEN-SIDE HALF IS CHEAP.** The commitment
   waits on the engine reading the minimum. The **screen** half — saying on the
   control that it is unread — needs no engine change and is what the drawing
   actually asks this screen for. Worth splitting when the PO sizes it.

---

## ⚑ BUILT 2026-09-10 — `CR-087` RATE-SCHEDULE MAINTENANCE LANE

**D1 · THE TWO HEADERS ARE THE DRAWN WORDS.** `matrix.col.base` → `Base charge`;
`matrix.col.minimum` → `Minimum rate`, with the rename applied to **eight** of
the nine strings the file lists across all eleven catalogues.
⚠ `rating.rate.minimumBillHelp` does not contain the old word, so it did not move.

**D4 · THE BASE CELL NAMES THE CODE AND THE CLASS.** `From {{code}} · {{class}}`
where a class is set, `From {{code}}` where none is — which is only possible now
that step 1 offers the picker (D1 of `p041`).

**D5 · THE LINK IS BUILT** — the blueprint's named defect for this step. The cell
said *read-only here* and gave no route to the place it can be changed; there is
now an anchor to the charge code's own page, spelled through
`DEFINITION_ROUTES.charge`.

**D6 · THE `NOT READ BY BILLING YET` SENTENCE EXISTS** in all eleven catalogues
(`rating.rate.sizes.notBilledLegend` / `.notBilledNote`) and is rendered on the
REVIEW step's minimums block rather than here — see `p051`. `DEF-2446` is
unchanged and is not this lane's to close.

⚠ **D7 · THE SECOND HALF OF `BLANK IS NOT ZERO` IS STILL NOT STATED GENERALLY.**
The drawn callout carries two sentences; rule 32 gives a section one. The
per-row instance (`baseSizeNotServed`) is where the fact fires, and it is left
there. **Divergence recorded.**

**D3, D8, D9 · UNCHANGED.** The `WHICH BASE APPLIES` callout is still the plain
two-sentence `Note`; the set-all row stays pending the PO question this file
already raises.
