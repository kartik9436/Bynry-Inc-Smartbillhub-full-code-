# CHG-01.discount · View · Overview — THE DRAWN SPEC, AND WHAT IS BUILT

Blueprint screen **26**, `/:tenant/plans-rates/discounts/:id` · **blueprint
pages 76–79**, frame drawn on **pages 76–78**.

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`
(md5 `2e46f5053ca65804da9c1a90a487e044`), text **and** rendered PNGs at 2.0.

**State chip:** `NEW BUILD` · **Commitments:** `PRB-11` · `PRB-12` · `PRB-20`

**Re-verified at 2.234.19** (blueprint read at 2.232.0 / d2d493e4).

**Code read:** `07-frontend/src/features/rating/definitionDetail.tsx`
(`presentDiscount`, **816–1035**; `DEFINITION_TABS`, **66–105**;
`DEFINITION_KPI_LABEL_KEYS`, **252–290**) and
`07-frontend/src/features/rating/DefinitionDetailPage.tsx`
(the shell, **340–630**; `FieldList`, **796–809**).

---

## 1 · Header

| slot | drawn |
|---|---|
| back link | `← Discounts` |
| kicker | `DISCOUNT · SENIOR · PERCENTAGE · V2` |
| title (H1) | `Senior citizen discount` |
| status | `ACTIVE` *(pill, below the title)* |
| sub-line | `Effective from 01/01/2026 · A discount references the plan's normal schedules and reduces what is owed. The bill shows the full tariff amount and the reduction as its own line, so the subsidy granted is reportable.` |

⚠ **THE SUB-LINE IS TWO PARTS, NOT THREE.** The effective date and the overlay
sentence. No funding source.

## 2 · Header actions — in the drawn order, top right

| # | label | tier |
|---|---|---|
| 1 | `Duplicate` | secondary |
| 2 | `Edit` | secondary |
| 3 | `Retire` | **danger** — outlined accent |

**PRIMARY ACTION:** `Edit.`

## 3 · Tabs — THREE, in this order, `Overview` active

`Overview` | `Plans` | `Audit`

⚠ **THREE TABS BECAME ONE QUESTION.** Page 78: *"Overview, `Value & rules` and
`Applicability` were three tabs and one question. … One tab, three blocks, in
the order a call goes: `what it is`, `what it is worth`, `who qualifies`."*

## 4 · Tab intro line, under the tab strip

> `What this programme is, what it is worth, and who qualifies.`

## 5 · KPI strip — four tiles, each with a caption

| # | value | label | caption |
|---|---|---|---|
| 1 | `10%` | `VALUE` | `of the subtotal before taxes` |
| 2 | `31` | `ENROLLED UNITS` | `of 86 eligible` |
| 3 | `$2,180.00` | `BUDGET REMAINING` | `of $5,000.00 this year` |
| 4 | `Active` | `STATUS` | *(none)* |

⚠ **ENROLLED AGAINST ELIGIBLE.** Page 78: *"`31` alone is trivia; `31 of 86` is
take-up, and low take-up on an assistance programme is a finding. It is one tile
now."*

⚠ **UNITS, NOT ACCOUNTS.** Page 78, verbatim: *"Same ruling as the rate schedule
and the charge code: a plan is assigned to a unit, so a count of accounts
undercounts by every vacant one."*

⚠ **THE BUDGET AS A FRACTION.** Page 78: *"A bare `$2,180` does not say whether
that is comfortable or nearly out. `of $5,000.00 this year` does, in the same
tile — and this is the figure that decides whether the programme suspends
itself."*

## 6 · The absence bar, between the strip and the panels

Label `NOT WORKED OUT YET` · name `Programme cost per month` · body:

> `Nothing works out a month's subsidy for one programme. The lifetime figure`
> `below is what is recorded.`

## 7 · Panel one — `What it is`, four facts, no intro

| label | drawn value | drawn absence reason |
|---|---|---|
| `DISCOUNT` | `Senior citizen discount` | — |
| `TYPE` | `Percentage` | — |
| `PROGRAMME OWNER` | `—` | `Nobody is recorded as answering for this programme.` |
| `FUNDING SOURCE` | `—` | `Not recorded.` |

## 8 · Panel two — `What it is worth`

Intro sentence: `What comes off, and everything that bounds it.`

| label | drawn value | drawn caption |
|---|---|---|
| `VALUE` | `10% of the subtotal before taxes` | — |
| `STACKING PRECEDENCE` | `1` | `Runs before any discount with a higher number.` |
| `BILL FLOOR` | `$0.0000` | `This programme may take a bill to nothing.` |
| `CAP PER BILL` | `—` | `No cap.` |
| `CAP PER YEAR` | `—` | `No cap.` |
| `BUDGET` | `$2,180.00 left of $5,000.00 a year` | — |

⚠ **THE BILL FLOOR SHOWS A STORED ZERO.** Page 78: *"A stored zero is a
decision — it says this programme may take a bill to nothing — and drawing it as
empty would hide a policy somebody signed."*

⚠ **`VALUE` AND `APPLIES TO` ARE ONE ROW**; `LIFETIME CAP` and `SUBSIDY GRANTED
TO DATE` are not drawn; `BUDGET CAP` and `BUDGET REMAINING` are one row.

## 9 · Panel three — `Who qualifies`

Intro sentence: `The counter script: what to ask, and what to accept.`

| label | drawn value | drawn absence reason |
|---|---|---|
| `ELIGIBILITY` | `Age 65 or over, on the account holder's own record.` | — |
| `ENROLMENT` | `Apply and approve` | — |
| `VERIFICATION` | `One-time proof at enrolment` | — |
| `ACCEPTED PROOF` | `Government ID · Birth certificate` | — |
| `RECERTIFICATION` | `Never expires` | — |
| `EFFECTIVE TO` | `—` | `No planned end.` |

## 10 · States — verbatim

| state | drawn behaviour |
|---|---|
| **Suspended, funding exhausted** | *"The pill says so in those words and the budget tile reads $0.00 left. A bill run can set this status by itself, and the edit screen names which setting allows that."* |
| **No budget cap** | *"`Unbounded`, not a dash, with the note that unbounded always needs a second approval."* |
| **Automatic enrolment** | *"The proof fields are absent, not empty — the two cannot coexist and the edit screen refuses the combination."* |
| **Draft** | *"No enrolments possible; the tile reads 0 and the header offers the lifecycle buttons."* |
| **Read-only role** | *"A role that may read but not change Plans & Rates sees every figure and no button. The refusal names the role, not the screen."* |

## 11 · Components named by the drawing

`PageHeader` `KPIStrip` `AbsenceBar` `Panel` `FieldGrid`

## 12 · Rules, verbatim

*"… **A figure that does not exist is stated with its reason and never drawn at
the weight of one that does.**"*

## 13 · The three commitments this screen carries

* **`PRB-11`** — the structured eligibility rule builder. *"A clerk builds
  'age ≥ 65 AND account type = Residential', saves, and the discount's page
  lists 86 accounts matching it beside the 31 enrolled."*
* **`PRB-12`** — what a programme costs per month. *"SENIOR's page reads
  '$418.20 last month' where it reads an em-dash."*
* **`PRB-20`** — how many accounts are ELIGIBLE. *"Until this exists, take-up
  cannot be stated and the cell shows the enrolled count with the gap named."*

⚠ **ALL THREE ARE `UNVERIFIED` COMMITMENTS, NOT INSTRUCTIONS.** Tile 2's drawn
denominator `of 86 eligible` **is `PRB-20`**, and `PRB-20`'s own card says the
figure cannot be stated until it exists.

---

## AS BUILT AT 2.234.19 — the diff, with evidence

### Matches — and the two structural rulings are already built

* **THREE TABS, `overview · plans · audit`** — `definitionDetail.tsx:85`. The
  five-to-three merge and the `versions → audit` rename are done. **Exact.**
* **THREE BLOCKS in the drawn order** — `identity` · `worth` · `qualifies`,
  `:994-1013`, rendered by `DefinitionDetailPage.tsx:733-747`.
* **The kicker** `DISCOUNT · SENIOR · PERCENTAGE · V2` — `:924-929`. **Exact.**
* **`Retire` takes the danger tier** — `DefinitionDetailPage.tsx:560`,
  `variant={key.endsWith("retire") ? "danger" : "secondary"}`.
* **Header action order** `Duplicate · Edit · Retire` —
  `DEFINITION_ACTION_KEYS`, `DefinitionDetailPage.tsx:170-174`. On an `active`
  discount no lifecycle button precedes them (`DiscountLifecycle.test.tsx:205`),
  so the drawn three are the three. **Exact.**
* **`What it is` is the four drawn facts, in the drawn order** — `:997-1005`.
* **`Who qualifies` is the six drawn facts, in the drawn order** — `:864-916`.
* **The bill floor renders a stored zero rather than an em-dash** — `:845-848`,
  with `BR-RAT-074` named. **The drawing's point is already the code's.**
* **Every cap is an em-dash when unset, never `0.00`** — `:838-840`.

### 1 · THREE OF THE FOUR KPI TILES ARE DIFFERENT TILES

| # | drawn | built | evidence |
|---|---|---|---|
| 1 | `VALUE` `10%` / `of the subtotal before taxes` | **`Plans using it`** / no caption | `:253`, `:948` |
| 2 | `ENROLLED UNITS` `31` / `of 86 eligible` | **`Enrolled accounts`** `31` / `accounts with an open enrolment` | `:254`, `:950`, `:976` |
| 3 | `BUDGET REMAINING` `$2,180.00` / `of $5,000.00 this year` | **`Offered to`** `86` / `86 units on a plan carrying it` | `:270`, `:967`, `:977-979` |
| 4 | `STATUS` `Active` | **`Type`** `Percentage · Subtotal before taxes` | `:271`, `:970` |

Three consequences, and they are different in kind:

**(a) `ENROLLED UNITS` against `Enrolled accounts` is a PO ruling the code
argues with, in writing.** Page 78 rules *"UNITS, NOT ACCOUNTS … same ruling as
the rate schedule and the charge code"*. `:955-960` states the opposite case and
gives its reason: *"`offered_units` is a fact about plans; the neighbouring
`enrolled` says ACCOUNTS and counts accounts (enrolment carries an FK to
`customers.Account`). They are deliberately NOT drawn as one fraction — a vacant
unit has no account and cannot enrol."* **Both are coherent. Only the PO can
say whether the drawn fraction `31 of 86` is being asked for over two different
populations.** ⚠ This is the highest-value question on the screen.

**(b) The drawn tile 2 denominator is `eligible`, and the built one is
`offered`.** `:961-966`: *"it is NOT `eligible`, which is what `PRB-20` asks
for. Eligibility on a discount is a sentence a person typed and nothing
evaluates one. Offered is computable, eligible is not, and drawing the first
under the second's name would be a wrong number rather than a missing one."*
**`PRB-20` agrees with the code** — its card says take-up cannot be stated until
the read exists. So the drawn caption `of 86 eligible` cannot be built today and
`PRB-20` says so on the facing page.

**(c) The drawn strip drops the reach figure entirely.** `Plans using it` is
tile 1 in the built product and `BR-RAT-069` (AVAILABLE ≠ GRANTED) is what it
exists for. The drawing puts VALUE there instead. See CONTRADICTIONS §1.

### 2 · There is no absence bar, and the cost sentence is in the wrong place

`AbsenceBar` is named by the drawing and exists nowhere in
`07-frontend/src/components/`. The cost sentence is built as the **`Who
qualifies` block's note** (`:1010`, rendered `DefinitionDetailPage.tsx:740`), so
*"Nothing works out a month's subsidy for one programme, or how many customers
qualify."* sits under a heading about eligibility.

The drawn body also differs: `…The lifetime figure below is what is recorded.`
against built `…, or how many customers qualify.`

### 3 · The drawn per-field absence reasons cannot be expressed by the type

Five drawn captions have nowhere to go:

`Nobody is recorded as answering for this programme.` ·  `Not recorded.` ·
`Runs before any discount with a higher number.` ·
`This programme may take a bill to nothing.` · `No cap.` (×2) ·
`No planned end.`

`DefinitionField` is `{ labelKey, value }` and nothing else
(`definitionDetail.tsx:319-322`), and `FieldList` renders `<dt>` + `<dd>` and
nothing else (`DefinitionDetailPage.tsx:796-809`). **Building the drawing means
adding an optional caption to the shared field type** — which reaches the charge
and the tax kinds too, so it is a kit change with a blast radius, not a screen
change. The drawing's own RULES line — *"a figure that does not exist is stated
with its reason"* — is what asks for it.

### 4 · `What it is worth` is ten fields where the drawing draws six

Built `:832-863`: `Value` · `Applies to` · `Cap per bill` · `Cap per year` ·
`Lifetime cap` · `Bill floor` · `Stacking precedence` · `Budget cap` ·
`Budget remaining` · `Subsidy granted to date`.

Drawn: `Value` (with the scope folded in) · `Stacking precedence` ·
`Bill floor` · `Cap per bill` · `Cap per year` · `Budget` (cap and remaining
folded into one).

So: **two merges** (`Value`+`Applies to`, `Budget cap`+`Budget remaining`), **two
drops** (`Lifetime cap`, `Subsidy granted to date`) and **a re-order**. See
CONTRADICTIONS §2 on the second drop.

### 5 · The sub-line carries a third part the drawing does not draw — and a comment says it was removed

`:930-941` builds three sub-line parts: the effective date, then
`` `${t("rating.discounts.col.funding")}: ${row.funding_source ?? NO_FIGURE}` ``
— **`Funding source: —`** — then the policy sentence.

`:991-993`, twenty lines below, says: *"TWO FIELDS SWAPPED SIDES … the FUNDING
SOURCE moved off the sub-line into `what it is`."* It moved **into** `what it
is` (`:1002`) and **did not move off** the sub-line. It is in both places, and
the comment says otherwise — hard-won law 1, and the drawing is right.

### 6 · `ENROLMENT` reads back the picker's explanation, not the fact

`:875-889` renders the value through `rating.discountWizard.enrolmentChoice.*`,
so the field shows **`Apply and approve, with proof — a document is needed as
well`** where the drawing shows **`Apply and approve`**. The trailing clause is
a chooser's hint, on a read screen, as a fact value.

### 7 · `ACCEPTED PROOF` joins on a comma; the drawing uses ` · `

`:904-907`, `.join(", ")` → `Government ID, Birth certificate`. Drawn:
`Government ID · Birth certificate`.

### 8 · The tab intro sentence is not built

`PageHeader` has no slot for one (`components/PageHeader.tsx:115-213`) and none
is rendered. The three drawn sentences — one per tab — have nowhere to go
today.

### 9 · `Duplicate` and `Retire` are drawn as ordinary buttons and built as held

`DefinitionDetailPage.tsx:554-567`: only `edit` is `live`; the other two get
`readOnly={true}` with `actionReason` (`rating.definition.action.notBuilt`,
*"This action is not built yet"* — six words, B14 rule 33 respected).
`HELD_ACTION_SEGMENTS = ["duplicate","retire"]` (`:168`) with an expiry test.
**The drawing states no absence for either**, so it neither confirms nor
disputes the hold. Recorded.

### 10 · Block headings are the kicker style, not the drawn heading style

Drawn: `What it is` / `What it is worth` / `Who qualifies` in bold sentence case,
at heading weight. Built: `<Kicker as="div">` — small, uppercase, letter-spaced
(`DefinitionDetailPage.tsx:736`). **B14 rule 36 gives the visual style to `r10`
and the kit, so this is recorded rather than built.**

### 11 · Two orphaned catalogue strings this redesign left behind

`rating.definition.kpi.discount.cost` (*"Programme cost per month"*) and
`rating.definition.discount.arrivesWith` are in all eleven catalogues and are
rendered by nothing. ⚠ **The first is the exact label the drawn absence bar
wants** — so it is a string waiting for its screen rather than dead weight.

---

## CONTRADICTIONS INSIDE THE BLUEPRINT — recorded, not resolved

1. **THE REDESIGNED STRIP REINTRODUCES THE REPETITION THE REDESIGN NAMES.**
   Page 76's *"What was wrong"* says *"Overview repeated the value from a tile
   and said little else"*. The drawn strip's tile 1 is `VALUE 10% / of the
   subtotal before taxes` and the drawn `What it is worth` block's first row is
   `VALUE / 10% of the subtotal before taxes` — the same fact, twice, on one
   tab. `BUDGET REMAINING $2,180.00 of $5,000.00 this year` and
   `BUDGET / $2,180.00 left of $5,000.00 a year` are the same fact twice again,
   and `STATUS Active` restates the `ACTIVE` pill drawn six inches above it.
   **Three of the four tiles are duplicates of something else on the same
   frame.** One sentence to the PO.

2. **THE ABSENCE BAR PROMISES A "LIFETIME FIGURE BELOW" AND NOTHING BELOW IS
   ONE.** *"The lifetime figure below is what is recorded"* — the built field it
   can only mean is `Subsidy granted to date` (`:859-862`), which the drawn
   `What it is worth` block does not carry. **Reading: the drop of
   `Subsidy granted to date` is a drafting slip, because the absence bar points
   at it.** Recorded, not acted on.

3. **`$0.0000` IS FOUR DECIMALS ON A SCREEN WHOSE OWN RULES LINE SAYS TWO.**
   The drawn `BILL FLOOR` reads `$0.0000`; the RULES block on page 79 reads
   *"Money shows two decimals and is stored to four"*, and **CLAUDE.md hard rule
   2 is a PO re-sign of exactly that** (*"MOney 4 decimal, percentage 6 decimal,
   display both 2 decimal"*). The built product prints the server's
   `bill_floor_amount_display`, which is the two-decimal string. **The signed
   rule wins over a drawn glyph; the drawing's POINT — that a stored zero is
   shown rather than blanked — is already built and is not in dispute.**

---

## WHAT NEEDS THE PRODUCT OWNER

* **§1(a) — `ENROLLED UNITS` or `Enrolled accounts`.** A ruling is quoted
  against a written counter-argument in the code, and the fraction spans two
  populations. **This one changes a number a finance lead reads.**
* **§1(c) / CONTRADICTIONS §1** — which four tiles, given that three of the
  drawn four repeat facts drawn again below.
* **§3** — whether `DefinitionField` gains a caption slot, which reaches the
  charge and tax kinds too.
* **CONTRADICTIONS §2** — whether `Subsidy granted to date` and `Lifetime cap`
  are dropped or were missed.

## WHAT COULD NOT BE VERIFIED WITHOUT THE APP RUNNING

* Every drawn STATE (`suspended_funding_exhausted`, no budget cap, automatic
  enrolment, draft, read-only) — each needs a seeded discount in that state.
* Whether ten fields in a two-column `FieldList` read as the drawn six-field
  block at 1280.
* Whether the `ACTIVE` pill sits below the title as drawn.

---

## FIXED 2026-09-10 — three findings, and the tiles left alone on purpose

**§5 · THE FUNDING SOURCE PRINTED TWICE — FIXED.** It is off the sub-line, which
is now the drawn TWO parts (the effective date and the overlay sentence), and
stays in *what it is*. **The comment twenty lines below had said so since the
merge and it was not true** — hard-won law 1, and the drawing was right.

**§6 · `ENROLMENT` READ BACK THE CHOOSER'S HINT — FIXED.** The field showed
*"Apply and approve, with proof — a document is needed as well"*: a dropdown
option's explanatory clause, printed as a fact value on a read screen. It now
shows the answer alone. The clause is SPLIT OFF rather than re-written into a
second key set — three more strings saying the same three things in eleven
languages is how a product acquires two vocabularies for one field.

**§7 · ACCEPTED PROOF JOINS ON ` · ` — FIXED.** As the frame draws. A comma
reads as part of a document's own name where the mid-dot cannot.

**`CR-091-BRC01` · THE SERVICES ARE ON THIS SCREEN, WHERE THERE WAS NOTHING.**
A `Services` row in *what it is worth*, always drawn — `All services` where
nothing narrows, the named services joined by ` · ` where something does, and an
em-dash for the row that should not exist (a `specific_services` version with an
empty list, which the write path refuses).

**§1 · THE FOUR KPI TILES ARE NOT RE-CUT, AND THAT IS DELIBERATE.**
The PO ruled the units-vs-accounts half on 2026-09-10 — *"it should be on
accounts; discount is given to accounts"* — and **tile 2 already counts accounts
and says so**, so that ruling needed no code. **Which four tiles is a different
question and nobody has answered it**: this file's CONTRADICTIONS §1 shows three
of the drawn four repeating a fact drawn again below on the same frame, and the
drawn tile-2 denominator `of 86 eligible` is `PRB-20`, whose own card says the
figure cannot be stated until an eligibility read exists. A tile set is a number
a finance lead reads. **Raised, not guessed.**

⚠ **AND THE ADJACENT HALF OF THAT RULING CANNOT BE DONE HERE.** The PO also said
`ELIGIBLE UNITS` must be re-read *"because eligible and enrolled must count the
same kind of thing"*. **The Plans-tab table it belongs to is not built at all**
(`CR-087-p079` §1). The only live surface is tile 3 — `Offered to · 86 units on
a plan carrying it` — which counts UNITS beside a tile counting ACCOUNTS, and
making it count accounts needs a server read that does not exist. **Recorded.**

**§2 · THE ABSENCE BAR IS STILL NOT BUILT**, and the reason is the same
collision recorded in `CR-087-p074`: the kit's `AccentBand` is a sibling lane's
unpushed work and `DefinitionDetailPage.tsx` is mid-rewrite by that lane. The
orphaned key `rating.definition.kpi.discount.cost` is still the label it wants.

**§§3, 4, 8, 9, 10, 11 · NOT BUILT.** The per-field absence captions (a kit
change reaching the charge and tax kinds too), the ten-vs-six fields, the tab
intro sentence, the held `Duplicate`/`Retire` and the block heading style all
stand.
