# 10 · View · Overview — THE DRAWN SPEC, AND WHAT THE PRODUCT DOES

`S13` · route `/:tenant/plans-rates/taxes-fees/:id` · **blueprint pages 30–34**
(heading on 30, frame drawn on **30–32**, specified on 32–34).

**State chip:** `NEW BUILD`
**Commitments on the chip line:** `PRB-05` · `PRB-06` · `PRB-07` · `PRB-23`

**Re-verify:** as-built claims were true at **2.232.0**; we are on **2.234.19**.

---

## 1 · Header

| slot | drawn |
|---|---|
| back link | `← Taxes & fees` |
| kicker | `TAX · STATE · TEXAS STATE` |
| title (H1) | `TX State Utility Tax` |
| status pill | `ACTIVE` |
| sub-line | `Effective from 06/01/2026 · Liability GL account 2200-02 — Tax payable · Editing a tax in force writes a new dated version with a reason; the rate on issued bills never moves.` |

## 2 · Header actions — in the drawn order

| # | label | tier |
|---|---|---|
| 1 | `Duplicate` | secondary |
| 2 | `Edit` | secondary |
| 3 | `Retire` | **danger** (accent outline) |

Page 33, verbatim: *"Five detail screens offered five different action sets. The
same button was called `Edit` here, `Edit rates` on a schedule, `Edit as new
version` on a plan and `Correct with a new version` on a tax; two screens put
Retire in the middle and two put it last … It is `Duplicate · Edit · Retire`
everywhere now, in that order, at that weight. **What editing does still differs —
and that belongs in a sentence, not in a fourth name for the same button.**"*

## 3 · Tabs — three, `Overview` active, each with ONE description sentence

`Overview` | `Plans` | `Audit`

Overview's line: `What this tax is, what is taxed, who it reaches, and how it is filed.`

## 4 · KPI strip — FOUR tiles

| # | value | label | detail line |
|---|---|---|---|
| 1 | `6.25%` | `RATE` | `of the taxable amount` |
| 2 | `6` | `PLANS IT TOUCHES` | — |
| 3 | `1,284` | `PREMISES IN SCOPE` | `every premises` |
| 4 | `Active` | `STATUS` | — |

⚠ **TILE 4 IS DRAWN AND IS DELIBERATELY NOT BUILT — PO RULING 2026-09-10,
verbatim: _"show only one status"_.** The drawing puts the status in the pill
under the title AND in this tile, which §14.1 below already recorded as the
blueprint contradicting itself. The ruling picks the **pill**, because that is
where every other Plans & Rates detail screen carries a lifecycle word. **So the
built strip is THREE tiles: `PLANS IT TOUCHES · PREMISES IN SCOPE · RATE`.**

Nothing was invented to refill the slot — adding a tile the drawing does not
draw would trade one divergence for a worse one — and `KPIStrip` lays out on
`repeat(auto-fit, minmax(180px, 1fr))`, so three tiles fill the row rather than
leaving a hole. The rating module's `DefinitionKpis` type moved from a strict
4-tuple to a 3-or-4 union for this, and still refuses a fifth.

## 5 · `NOT WORKED OUT YET` — an absence bar UNDER the tiles, two rows

| row | sentence |
|---|---|
| `Taxable base per month` | `Nothing totals the base one tax is charged on.` |
| `Collected per month` | `Nothing totals what one tax has collected. The remittance worksheet in Finance is where a filing figure comes from.` |

⚠ **THE ABSENCES LEFT THE TILE STRIP, AND THE RULES LINE SAYS WHY:** *"A figure
that does not exist is stated with its reason and never drawn at the weight of one
that does."*

## 6 · FIVE blocks, in the drawn order — one merged Overview

### 6.1 `What it is`
`NAME ON THE BILL` `TX State Utility Tax` · `AUTHORITY` `Texas State` · `LEVEL`
`State` · `HOW IT IS WORKED OUT` `A percentage of the bill`

### 6.2 `On the bill`
`CODE` `TX-UTIL` *(monospace)* · `BILL LABEL` `State Utility Tax`, with the caption
`What the customer reads. Blank shows the name above.`
Rule-marked note, kicker `EDITABLE`:
> `These two can be changed at any time, so the wizard no longer asks for them.`

### 6.3 `What is taxed` — note `The rate, and exactly what it is charged on.`
| label | value | caption |
|---|---|---|
| `RATE` | `6.25% of the taxable amount` | — |
| `USAGE CHARGES` | `Taxed` | — |
| `BASE SERVICE CHARGES` | `Taxed` | — |
| `DISCOUNTS` | `Taxed after the discount — the discount comes off first` | — |
| `APPLIES ABOVE` | `—` | `No threshold: every unit is taxed.` |
| `ROUNDING` | `Standard (half up)` | `Recorded only; bills use standard rounding.` |

### 6.4 `Who it reaches` — note `A tax attaches by jurisdiction and service. A plan cannot leave one off a bill.`
| label | value | caption |
|---|---|---|
| `SERVICES` | `All services` | — |
| `CUSTOMER CLASSES` | `Every customer class` | — |
| `HOW A PREMISE IS DECIDED TO BE IN SCOPE` | `Everywhere in this utility · 1,284 premises` | — |
| `EFFECTIVE FROM` | `06/01/2026` | — |
| `EFFECTIVE TO` | `—` | `Runs until a new version starts.` |

### 6.5 `Remittance & filings`
`TAX TYPE` `Utility tax` · `REMITTED TO` `Texas Comptroller` · `FILED` `Monthly` ·
`FILING FORM` `01-339` · `YOUR ACCOUNT NUMBER WITH THE AUTHORITY` `TX-4402-118` ·
`DUE-DATE RULE` `20th of following month` · `COLLECTION ALLOWANCE YOU KEEP` `0.5%`
with the caption `On $2,400.00 remitted that is $12.00 of your own income.` ·
`LIABILITY GL ACCOUNT` `2200-02 — Tax payable` · `WHO GETS THE FILING REMINDER`
`books@pinehill.example`
Rule-marked note, kicker `EDITABLE`:
> `Every field in this block can be changed at any time, on a live tax, without a new version. Filings themselves are recorded by the remittance worksheet in Finance.`

⚠ **ONE BLOCK, READ AND WRITTEN.** Page 23: *"the tax's own page already has a
`Remittance & filings` block where they live, are read, and are now entered."*

## 7 · States — the blueprint's own block, verbatim

| state | drawn behaviour |
|---|---|
| **A boundary nothing can evaluate** | *"Reads 0 with the reason … the screen says the tax reaches nobody — deliberately, because a boundary we cannot check must never read as applying to everyone."* |
| **Scheduled** | *"Edit is live; nothing has billed at this rate yet."* |
| **Specific services or classes** | *"Named, comma-joined, in the utility's own order — never `All` when it is not."* |
| **Read-only role** | *"A role that may read but not change Plans & Rates sees every figure and no button. The refusal names the role, not the screen."* |

## 8 · Components named in the frame

`PageHeader` `KPIStrip` `AbsenceBar` `Panel` `FieldGrid` `MatchedPremisesNote`

## 9 · What the server needs, as stated

*"Nothing. `update_tax` already refuses only the nineteen rate-history fields and
allows every remittance field to change on a live tax … Folding four tabs into one
moves no data."*

---

## 10 · WHAT THE PRODUCT DOES — file and line evidence

`07-frontend/src/features/rating/DefinitionDetailPage.tsx` and
`.../definitionDetail.tsx` at `2.234.19`.

### 10.1 Header

| drawn | built? | evidence |
|---|---|---|
| `← Taxes & fees` | ✅ | `DefinitionDetailPage.tsx:465` |
| kicker `TAX · STATE · TEXAS STATE` | ✅ | `definitionDetail.tsx:609-613` joins kind · level · authority |
| title | ✅ | `definitionDetail.tsx:607` / `DefinitionDetailPage.tsx:471` |
| `ACTIVE` pill | ✅ | `RatingStatusPill`, `DefinitionDetailPage.tsx:486-494` |
| sub-line seg 1 `Effective from 06/01/2026` | ⚠ | renders **`Effective from: 06/01/2026`** — a colon the drawing does not have, `definitionDetail.tsx:615-617` (`{t("rating.effectiveFrom")}: …`) |
| sub-line seg 2 `Liability GL account 2200-02 — Tax payable` | ⚠ | same colon, `definitionDetail.tsx:618` (`${t("rating.taxes.col.gl")}: …`) |
| sub-line seg 3 `Editing a tax in force writes a new dated version with a reason; the rate on issued bills never moves.` | ❌ **NOT BUILT** | renders `rating.definition.tax.policy` — *"Tax collected is a liability until it is remitted, never revenue, and it attaches by jurisdiction and service rather than by plan."* — `definitionDetail.tsx:620`. The string the drawing asks for exists in none of the eleven catalogues ⟨grepped⟩ |

⚠ **SEGMENT 3 IS THE SENTENCE THE WHOLE ACTION RULING DEPENDS ON.** Page 33: *"What
editing does still differs — and that belongs in a sentence, not in a fourth name
for the same button … the line under the title says so before anyone presses it."*
Without it, `Edit` on a live tax is an unlabelled trap — see 10.6.

### 10.2 Actions

| drawn | built? | evidence |
|---|---|---|
| order `Duplicate · Edit · Retire` | ✅ | `DEFINITION_ACTION_KEYS`, `DefinitionDetailPage.tsx:170-174` |
| `Retire` in the danger tier | ✅ | `variant={key.endsWith("retire") ? "danger" : "secondary"}`, `DefinitionDetailPage.tsx:560` |
| `Edit` live on a tax | ✅ **fixed since the drawing** | `EDITABLE_KINDS` includes `"tax"`, `DefinitionDetailPage.tsx:161`; the drawing's *"Edit was disabled for every role"* is `DEF-RAT-4647`, closed 2026-09-08 |
| `Duplicate` and `Retire` | ⚠ **held** | both disabled with `rating.definition.action.notBuilt = "This action is not built yet"`, `DefinitionDetailPage.tsx:389` and `HELD_ACTION_SEGMENTS`, `:168`. **In spec** — the screen's own RULES line allows it: *"A held control names a condition that is still true"*, and `definitionEditHoldExpiry` is the test that fires when a route appears |

### 10.3 Tabs

| drawn | built? | evidence |
|---|---|---|
| three tabs `Overview · Plans · Audit` | ✅ | `DEFINITION_TABS.tax = ["overview","plans","audit"]`, `definitionDetail.tsx:103` |
| a one-sentence description under the tab strip | ❌ **NOT BUILT** | nothing renders between the tab strip and the KPI strip — `DefinitionDetailPage.tsx:571-605`. No `rating.definition.tab.*.description` key exists |

### 10.4 The KPI strip — THE LARGEST STRUCTURAL GAP

Built tiles, in order (`definitionDetail.tsx:273-278` (labels) and `:625-636` (values)):

| # | label | value |
|---|---|---|
| 1 | `Plans it touches` | `used_by_plans` |
| 2 | `Taxable base per month` | **`—` always** (`NO_FIGURE`, `:630`) |
| 3 | `Collected per month` | **`—` always** (`NO_FIGURE`, `:634`) |
| 4 | `Rate` | `6.25% of the taxable amount` — the WHOLE sentence in the value slot |

Against the drawing: **`PREMISES IN SCOPE` and `STATUS` do not exist as tiles; the
two absences occupy half the strip; `RATE` and `PLANS IT TOUCHES` are in the wrong
order; and no tile passes a `detail` caption**, though `tiles()` takes one
(`definitionDetail.tsx:296-313`) and the DISCOUNT kind uses it.

⚠ **THIS IS THE DEFECT `CR-087 C2` ALREADY FIXED FOR DISCOUNTS AND NOT FOR TAX.**
The discount presenter's own comment, `definitionDetail.tsx:263-270`: *"`…discount.cost`
stood here and was an em-dash on every discount that has ever existed … the tile
was a permanently blank quarter of the strip — furniture, not a stated absence."*
The tax strip has **two** such quarters.

**`AbsenceBar` does not exist in the component kit** ⟨`ls 07-frontend/src/components`⟩.
Under B14 rule 36 the answer is to ADD IT TO THE KIT, not hand-roll it here.

**`PREMISES IN SCOPE` has a server read already** — `GET /taxes/matched-premises`
(`06-backend/apps/rating/api.py:452`), which the wizard uses. Nothing on the detail
page calls it: `MatchedPremisesNote` is mounted only inside `TaxWizard.tsx`
(lines 1073 and 1804) ⟨grepped across `src`⟩, although the blueprint names it as a
component of this screen.

### 10.5 The five blocks

| block | built? | evidence |
|---|---|---|
| order `What it is · On the bill · What is taxed · Who it reaches · Remittance & filings` | ✅ | `definitionDetail.tsx:656-801` |
| `What it is` — four fields, drawn order | ✅ | `:659-677` |
| `On the bill` — `CODE`, `BILL LABEL` | ✅ | `:678-697` |
| `On the bill` caption `What the customer reads. Blank shows the name above.` | ❌ | `DefinitionField` has **no caption slot** — `definitionDetail.tsx:319-322` (`DefinitionField`) is `{labelKey, value}` and nothing else |
| the `EDITABLE` kicker on both notes | ❌ | rendered as a plain `<Note>` with no kicker — `DefinitionDetailPage.tsx:746` |
| `On the bill` note wording | ⚠ | `"These can be changed at any time…"` — the drawing says `"These two can be changed…"` |
| `What is taxed` — six fields, drawn order | ✅ | `:698-748` |
| `DISCOUNTS` value wording | ⚠ | reuses the wizard key (deliberate, `:713-733`), so it reads *"Taxed after discounts (discount applies first)"* not the drawn *"Taxed after the discount — the discount comes off first"* |
| `APPLIES ABOVE` caption `No threshold: every unit is taxed.` | ❌ | no caption slot |
| `ROUNDING` value | ⚠ | `rating.taxWiz.rounding.b4 = "Standard rounding (half up)"`; drawn `Standard (half up)` |
| `ROUNDING` caption `Recorded only; bills use standard rounding.` | ❌ | no caption slot — the sentence exists (`rounding.notHonoured`) but is rendered only on the WIZARD |
| `Who it reaches` — five fields, drawn order | ✅ | `:749-760` |
| `HOW A PREMISE…` value carries `· 1,284 premises` | ❌ | `scopeText` names the mechanism only — `definitionDetail.tsx:599-604` |
| `EFFECTIVE TO` caption `Runs until a new version starts.` | ❌ | no caption slot; `dateNode` renders a bare `—` — `definitionDetail.tsx:426-432` |
| `Remittance & filings` — nine fields, drawn order | ✅ | `:761-799` |
| remittance note's second sentence (*"Filings themselves are recorded by the remittance worksheet in Finance."*) | ❌ | `rating.definition.tax.block.remittanceNote` stops at *"…without a new version."* |

### 10.6 ⚠ THE REMITTANCE BLOCK IS DRAWN ONCE AND BUILT TWICE

The Overview renders the five blocks **and then a sixth panel**:
`TaxRemittancePanel`, `DefinitionDetailPage.tsx:625-627`, headed
`rating.definition.tax.remittance.formTitle = "Filing details"`
(`DefinitionDetailPage.tsx:897`) with its own `Save filing details` button.

So on a live screen the filing form number, the account number, the due-date rule,
the collection allowance and the reminder address each appear **twice** — once as a
read-only fact in the `Remittance & filings` block and again as an input below it,
under a heading the drawing does not have. The drawing has ONE block that both
reads and writes. **B14 rule 32:** *"a row never repeats what its own control
offers."*

### 10.7 States

* **A boundary nothing can evaluate** ⚠ — the block names the mechanism, but the
  drawn *"reads 0 with the reason"* needs the premises count that is not on this
  screen at all (10.4).
* **Scheduled** ❌ — `Edit` is live on a scheduled tax, but nothing says *"nothing
  has billed at this rate yet"*, because the sub-line sentence is not built (10.1).
* **Specific services or classes** ✅ — comma-joined, never `All` when it is not:
  `definitionDetail.tsx:578-596`.
* **Read-only role** ✅ — `GuardedButton` + `rating.readOnlyReason`,
  `DefinitionDetailPage.tsx:365-367`.

### 10.8 Catalogue parity ⟨verified⟩ — all keys present in eleven locales.

---

## 11 · ⚠ THE PRIMARY ACTION CANNOT DO WHAT THE DRAWING SAYS IT DOES

Page 32, PRIMARY ACTION, verbatim: *"`Edit`. On a tax in force it opens a new
dated version with a reason; on a scheduled one it changes the row in place. The
line under the title says which."*

**At `2.234.19` a tax IN FORCE cannot be edited by any route this UI offers.**

1. `Edit` is enabled and navigates to `…/taxes-fees/{id}/edit`
   (`DefinitionDetailPage.tsx:561-563`).
2. `TaxWizard` computes `inForce` (`TaxWizard.tsx:662`) and renders an absolute
   refusal panel plus two guarded commits (`:746-752`, `:736`, `:865`).
3. The refusal's own sentence, `rating.taxWiz.inForce.correction`, reads
   **"A mistake is corrected by a new version carrying a written reason, and that
   route has not been built, so nothing here can be saved."**
4. **That sentence is false.** `POST /taxes/{id}/corrections` is served
   (`06-backend/apps/rating/api.py:447`, `:784`) and a typed client exists —
   `correctTax`, `07-frontend/src/api/endpoints.ts:4996-5004`.
5. **`correctTax` is called by nothing** ⟨grepped across `07-frontend/src`, all
   non-test files⟩. The `TaxWizard.tsx` header comment says so itself at line 54
   and its `E6` exception at line 1829 says the correction FORM *"is the tax
   detail's Versions tab and is not built here"* — and the Versions tab is now
   `Audit`, which renders an `ArrivesWith` (see the `p036` file).

**This is hard-won law 2 in both directions at once:** a built-and-unwired server
door, behind a refusal sentence that is no longer true, on the one action the
blueprint calls this screen's primary. Filing left to the parent lane.

---

## 12 · COMMITMENTS ON THIS SCREEN — re-verified at `2.234.19`

| card | what it waits on, as drawn | state at HEAD |
|---|---|---|
| `PRB-05` | two more parameters on `GET /taxes/matched-premises` | **ALREADY BUILT** — `api.py:476-485`; decision log 2026-09-08. The tile it would feed on THIS screen is still absent (10.4) |
| `PRB-06` | *"Two reads over invoice tax lines"* for taxable base and collected | **NOT BUILT** — both tiles are `NO_FIGURE`, `definitionDetail.tsx:630`/`:634`, with the missing route named in the TODO beside each |
| `PRB-07` | the remittance worksheet in Finance | **NOT BUILT** — `rating.definition.tax.filingsPending` states it |
| `PRB-23` | waivers granted and exemption certificates | **PART BUILT** — `exemption_category_count` is served (`06-backend/apps/rating/selectors.py:2903-2905`) and this screen shows neither it nor a waiver count |

## 13 · B14 rule 38 divergences — RECORDED, NOT BUILT

1. **Three-column `FieldGrid` vs the built two-column `FieldList`**
   (`FieldList`, `DefinitionDetailPage.tsx:798-810`). Column count is form construction and the
   change would move every definition detail at once. **Record only.**
2. **A caption line under a field value.** The drawing wants one on four fields;
   `DefinitionField` has no slot. Rule 36's answer applies — **ADD IT TO THE KIT as
   an opt-in** so nothing existing moves — but that is a kit change and is not
   built here.

## 14 · THE BLUEPRINT AGAINST ITSELF

1. **`STATUS` IS DRAWN TWICE** — as the `ACTIVE` pill under the title and again as
   KPI tile 4. The same section's cognitive-load argument elsewhere is that nothing
   is drawn twice. ✅ **RESOLVED by PO ruling 2026-09-10, verbatim _"show only one
   status"_.** The pill stays, the tile is gone, and the strip is three (see §4).
   ⚠ **No B14 rule was minted from this, on the rule-30 precedent** — the PO
   answered the INSTANCE, and turning an instance into binding UI law is what
   that precedent forbids. A second screen with the same duplication needs its
   own reading, not an appeal to this row.
2. **`PRB-05` is drawn as open and is built** (see §12) — the same staleness the
   `p022` file records.

## 15 · NOT VERIFIABLE WITHOUT THE APP RUNNING

* Whether the duplicated remittance facts (10.6) read as duplication on screen or
  as a form under its own summary — a person has to look.
* Tile alignment and whether a whole sentence in tile 4's value slot wraps the
  strip at 1280.
* The `Read-only role` refusal wording as actually rendered.

---

## 16 · WHAT WAS BUILT — 2026-09-10, the CR-087 tax-screens maintenance lane

**Maintenance, not Build** (`12-governance/22-product-maintenance-process.md`):
every finding below is a defect against a screen clerks already use.

### 16.1 The primary action works (§11, `DEF-RAT-4820`)

`Edit` on a tax IN FORCE now files a **correction**. `TaxWizard` routes its
commit to `POST /taxes/{id}/corrections` — the door that has been served since
DEF-384 and **called by nothing** — instead of refusing every field, and the
refusal sentence that said *"that route has not been built, so nothing here can
be saved"* is gone, because it had been false since the day the endpoint landed.

**The rule did not move one inch.** A live tax is still never edited in place;
hard rule 4 and `BR-RAT-104` are unchanged. What changed is that the alternative
the refusal NAMED is wired to the door that serves it. Three things travel with
it: the body is `{reason, …only the keys that MOVED}`, so the server's own
*"a correction that corrects nothing"* refusal stays reachable; the statutory
window is shown DISABLED, because `correct_tax` copies both dates off the row
being corrected and ignores the payload; and the save lands on the NEW row,
which is the one now in force.

### 16.2 The sub-line's third segment (§10.1)

Built as `rating.definition.tax.editPolicy`. ⚠ **It REPLACES
`rating.definition.tax.policy` rather than joining it** — B14 rule 32's
description budget, and the drawing's own three-segment sub-line. Nothing is
lost that the page does not already say: the policy sentence's *"attaches by
jurisdiction and service rather than by plan"* half is the `Who it reaches`
block's own note word for word, and its *"a liability, never revenue"* half is
what the `LIABILITY GL ACCOUNT` segment beside it names. The key is kept in the
catalogue rather than retired (`DEF-CUS-3653` — grep a value's CONSUMERS before
retiring it).

⚠ **SHORTENED AGAINST THE DRAWING, DELIBERATELY.** The drawn sentence is 21
words in one clause; B14 rule 33 caps a consequence at six words per sentence,
at most two, and *"never cut below clarity"*. Built as **"Live taxes are
corrected, never edited. Issued bills keep their rate."** — two sentences, six
and five. Where a drawing and a ratified B14 rule disagree about LENGTH, B14
wins on rule 38's own principle and the divergence is recorded here.

### 16.3 The KPI strip (§10.4) — the largest structural gap, closed

| tile | before | after |
|---|---|---|
| 1 | `Plans it touches` | unchanged |
| 2 | `Taxable base per month` — **`—` always** | **`Premises in scope`**, from `GET /taxes/matched-premises` with all three narrowings, captioned *every premises* / *of N* |
| 3 | `Collected per month` — **`—` always** | **`Status`** |
| 4 | `Rate` | unchanged |

**This is `CR-087 C2`'s discount fix, reaching the tax at last.** The discount
presenter's own comment calls a permanently blank tile *"furniture, not a stated
absence"*; the tax had **two** such quarters. The two absences are not deleted in
silence — they are stated with their reasons in a `NOT WORKED OUT YET` bar under
the strip, which is the drawing's own bar and its own rules line.

⚠ **TWO DIVERGENCES, RECORDED RATHER THAN BUILT.**
1. **TILE ORDER.** The drawing puts `RATE` first and `STATUS` last. `§2` of
   `09-screen-inventory.md` makes tile 1 the REACH and tile 4 the object's
   defining characteristic on all five details, and the charge and discount kinds
   both obey it. Tile order in a shared four-tile strip is form CONSTRUCTION, so
   B14 rule 38 gives it to the kit; all four DRAWN FACTS are on the strip, which
   is the half the drawing decides.
2. **TILE 4 IS NOT SPLIT.** The drawing puts `6.25%` in the value and *"of the
   taxable amount"* in the caption. The product renders the whole sentence from
   ONE catalogue key per computation form. Splitting it means a second copy of
   half a money sentence in three more keys × eleven catalogues, and two copies
   of a money string is `DEF-364`'s own shape.
3. **`STATUS` IS STILL DRAWN TWICE** — as the pill and as a tile (§14.1, the
   blueprint against itself). Recorded, not resolved; the tile is built because
   the drawing draws it.

`AbsenceBar` is still not a kit component. The bar is composed from `Kicker` and
`Note` inside `taxDetailTabs.tsx`, the way `DatedBanner` already is in
`DefinitionDetailPage.tsx`, and it is a `<details>` **closed by default** —
B14 rule 32.

### 16.4 The remittance block renders ONCE (§10.6)

The `Filing details` panel — *"a heading the drawing does not have"* — is gone.
`TaxRemittancePanel` no longer wraps the field set in a fourth panel; the field
set's own two panels now carry the **drawn** headings `On the bill` and
`Remittance & filings`, each with the drawn `EDITABLE` kicker and its note, and
the two READ-ONLY blocks that showed the same eleven facts are removed from
`presentTax`. **One block that both reads and writes**, which is what page 23
describes. `TAX TYPE` moved into `Remittance & filings`, where the drawing puts
it. B14 rule 32: *a row never repeats what its own control offers*.

⚠ **ORDER DIVERGENCE:** the drawn block order is `What it is · On the bill ·
What is taxed · Who it reaches · Remittance & filings`. The two writable blocks
are rendered by the form, which sits after the read blocks, so the built order
is `What it is · What is taxed · Who it reaches · On the bill · Remittance &
filings`. Recorded.

### 16.5 The three tab description lines (§10.3)

Built as `rating.definition.tab.description.tax.{overview,plans,audit}`, one
sentence each, shortened to B14 rule 33's caps — the drawn lines run to nine and
fifteen words.

### 16.6 What was NOT built, and stays a finding

* the **caption slot** under a field value (§13 divergence 2) — a kit change;
* `PRB-06` and `PRB-07` — neither read exists, and both are now stated in the
  absence bar rather than drawn as tiles;
* `PRB-23`'s waiver and certificate counts;
* the four `EDITABLE`/caption sentences the drawing gives fields inside the read
  blocks;
* the colon in sub-line segments 1 and 2 (`Effective from: …`).

### 16.7 ⚠ FOUND BY CLICKING, AFTER EVERYTHING ABOVE WAS GREEN — `DEF-RAT-4838`

§11 said *"at `2.234.19` a tax IN FORCE cannot be edited by any route this UI
offers"*, and it named the client's own test, `taxIsInForce`. **That test is
narrower than the server's, and the gap is the defect.**

* the CLIENT froze a tax that is active **and started and not ended** —
  `taxIsInForce`, a date test;
* the SERVER refuses every rate-history field with **`if blocked and not
  tax.is_draft`** — every non-draft tax, window open or not.

**So the screen offered `Save changes` on exactly the taxes the server refuses**,
including all five seeded Texas rates, which carry no `effective_from` at all.
Measured on the built product through the browser: `PATCH /taxes/{id}` with
`{"effective_from": "2026-01-01"}` on *Local · Bexar County* answered
**`409 BIZ-IMMUTABLE · rating.taxes.in_force_edit_refused`** while the wizard
rendered an ordinary edit with no correction panel and no reason box.

**Fixed by making the client ask the server's question** — `status !== "draft"`,
which `tax_row` already serves. `taxIsInForce` is unchanged and still true of
what it says; it is not the question this screen asks. The objection its
docstring raises — that reading the status would make those five rates
*uneditable* — no longer applies: they are **CORRECTABLE**, through the route
§16.1 wired.

⚠ **NOTHING BUT A BROWSER WITH A LIVE SERVER COULD HAVE FOUND IT.** Two layers
each held a correct, carefully argued expression of one rule and neither could
see the other; a test on either side alone passes. The walk is
`10-scripts/cr087_tax_tabs_walkthrough.mjs`, and it reads the 409 rather than
asserting the screen.
