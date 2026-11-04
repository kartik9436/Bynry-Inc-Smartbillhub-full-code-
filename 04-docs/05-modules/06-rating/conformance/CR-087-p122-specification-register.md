# The Charge codes commitments (pages 20–21) and THE SPECIFICATION REGISTER (pages 122–126)

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`.
**Summarised, not diffed** — these pages carry no wireframe. The four screen
files in this folder hold the drawn specifications and their diffs.

This file exists because the register asks for exactly one thing from
engineering, page 122–123, verbatim: *"Every status reads UNVERIFIED, and none of
them is a guess: engineering fills this column in from the code, one row at a
time. **Several are expected to come back already done** — the reads behind two or
three of these tiles may exist under another name. Nothing here was marked built
from a change log or from a memory of having written it."*

---

## PART 1 — the four commitment cards in the Charge codes section (pages 20–21)

Page 20 opens them: *"Each card names what the work waits on and what a person
would be able to do once it is done. Nothing outside a card is undertaken."*
All four carry the `UNVERIFIED` stamp.

### `PRB-01` · A charge code's amount can differ by customer class

* **Waits on** — *"A new `account_type_id` column on `charge_code_amounts`, that
  column inside the unique key, and a migration. Nothing else on this list can be
  drawn until it lands."*
* **Screens** — `02` · `36` · `37`
* **What done looks like** — *"A clerk opens CONN, types 45.0000 against
  Residential and 85.0000 against Commercial in one grid, saves, and a commercial
  move-in is quoted $85.00 while a residential one is quoted $45.00 on the same
  charge code."*

⚠ **THIS IS BUILT.** `charge_code_amounts.customer_class` shipped on 2026-09-08
as CR-087 A1 — `06-backend/apps/rating/models.py:492–514`, migration
`06-backend/apps/rating/migrations/0029_cr087_a1_amount_by_customer_class.py`,
served as `size_amounts[].customer_class` at
`06-backend/apps/rating/selectors.py:2630–2649`, typed at
`07-frontend/src/api/endpoints.ts:4092` and edited by `PerSizeAmounts`
(`07-frontend/src/features/rating/ChargeCodeWizard.tsx:1090–1329`), with the
class-column grid test at
`07-frontend/src/features/rating/cr087ClassSizeGrid.dom.test.tsx`.

**Two departures from the card's own words, both deliberate and both documented
in the model:**
1. The column is **`customer_class`, a CODE**, not `account_type_id`, a uuid.
   `models.py:498–505`: *"`plan_deposit_rules` keys its class with
   `account_type_id`, so that precedent exists and this deliberately does not
   follow it. The resolver decides … A UUID here would make the row beside it on
   the same object narrow by a different key and force an id→code lookup on the
   hot path."*
2. It is **inside TWO partial unique keys, not one** (`models.py:519–537`),
   because PostgreSQL treats NULLs as distinct and a single four-column key would
   let two every-class rows exist for one size.

**So the card's blocking sentence — *"Nothing else on this list can be drawn until
it lands"* — no longer holds.** The register status column for `PRB-01` should
read as built.

### `PRB-02` · Who may approve a waiver, recorded on the charge code

* **Waits on** — *"A column on `charges`. No ruling exists on who the approvers
  are, so the field records a role rather than a person."*
* **Screens** — `02`
* **What done looks like** — *"A clerk opens LATE, sets the waiver approver to
  Supervisor, saves, and the charge code's page reads "Waived by: Supervisor"
  where it read an em-dash."*

**Not built.** `charges` carries `waivable` (a boolean, rendered as
`rating.charges.waivableLabel` = *"Staff may waive it"*) and no approver column.
The wizard states the gap in its own words —
`rating.chargeWizard.section.waiver.pending`: *"Whether a supervisor has to
approve a waiver, and whether a reason has to be given, are not stored per code
yet."*

### `PRB-03` · A staff-only description on a charge code

* **Waits on** — *"A column on `charges`. Distinct from the bill label, which the
  customer reads."*
* **Screens** — `01` · `02`
* **What done looks like** — *"A clerk types "Use for reconnections after a
  non-payment cut, not for new service" on CONN, saves, and the next clerk sees it
  on the charge code's page while the bill still reads "Connection fee"."*

**Not built**, and the wizard says so: `rating.chargeWizard.internalPending` =
*"There is one description column today, so a staff-only one is not offered."*
⚠ **AND SCREEN 04'S FRAME DRAWS IT ANYWAY** — its `What it is` block draws
`DESCRIPTION` and `SHOWS ON THE BILL AS` as two fields holding the same string.
Recorded in `CR-087-p013-charge-code-overview.md`.

### `PRB-04` · How often a charge code was applied, and what it billed

* **Waits on** — *"Two reads over invoice lines grouped by charge. Both tiles say
  "nothing totals this" today."*
* **Screens** — `04`
* **What done looks like** — *"CONN's page reads "Applied 31 times last month ·
  $1,395.00" in the two tiles that currently read an em-dash with a sentence under
  them."*

**Not built**, and the em-dashes are at
`07-frontend/src/features/rating/definitionDetail.tsx:485–495` (`NO_FIGURE` for
tiles 2 and 3, with TODO comments naming the missing reads). ⚠ **The card and the
frame disagree about where the answer goes:** the card puts the two figures back
in the TILES; screen 04's frame moves both out of the strip into a
`NOT WORKED OUT YET` band and gives the two freed tile slots to
`UNITS REACHED` and `CLASSES`. Both are on pages 13 and 20–21 of the same
document. Recorded, resolved nowhere.

---

## PART 2 — THE SPECIFICATION REGISTER (pages 122–126)

**Its own description, page 122:** *"One row per specification, no exceptions.
Every one appears both here and as a card in the section that owns it. This
document had no specification index before; this table fills a gap rather than
replacing one."*

**Columns:** `SPEC` · `TITLE, AND WHAT IT WAITS ON` · `SCREENS` ·
`WHAT DONE LOOKS LIKE ON SCREEN` · `STATUS`.

**Every row's STATUS reads `UNVERIFIED`** — including the one the table itself
marks *not applicable*.

### The rows that are present, in order

| spec | title | screens |
|---|---|---|
| `PRB-01` | A charge code's amount can differ by customer class | 02 · 36 · 37 |
| `PRB-02` | Who may approve a waiver, recorded on the charge code | 02 |
| `PRB-03` | A staff-only description on a charge code | 01 · 02 |
| `PRB-04` | How often a charge code was applied, and what it billed | 04 |
| `PRB-05` | The premises count narrows on class and service, not just the boundary | 07 · 09 · 10 |
| `PRB-06` | What one tax is charged on, and what it collected | 10 |
| `PRB-07` | The remittance worksheet | 10 |
| `PRB-08` | A rate schedule's minimum reaches the engine | 14 · 18 |
| `PRB-09` | Somebody is told when a price changes | 17 |
| `PRB-10` | Per-size block prices are billed, or the section goes | 15 · 16 |
| `PRB-11` | The structured eligibility rule builder on a discount | 23 · 26 |
| `PRB-12` | What a discount programme costs per month | 26 |
| `PRB-13` | The second-approval test is settled | 24 |
| `PRB-14` | The impossible enrolment pair is refused by the server | 23 |
| `PRB-15` | A plan can be built for a customer sub-type | 29 |
| `PRB-16` | The outside-city surcharge is entered as a percentage | 30 |
| `PRB-17` | The charge-code catalogue can be asked what a plan may add | 32 · 33 · 34 |
| `PRB-18` | Every base charge that applies to a service, listed | 31 · 36 · 37 |
| `PRB-19` | The combined tax rate is stated by the server | 36 · 37 |

### Three of the nineteen carry a warning rather than a dependency

* **`PRB-08`** — *"`DEF-2446` — a minimum typed on a rate schedule is published
  to the engine and read by nobody. **This is a live defect, not a new
  feature.**"*
* **`PRB-10`** — *"⚠ **NOBODY HAS RULED THIS.** Nine per-size block prices are
  typed, stored, published to the engine and read by nothing. The document's own
  footer names it as the one decision still open."*
* **`PRB-13`** — *"⚠ **TWO APPROVED POLICIES DISAGREE** and the document leaves
  both on screen deliberately. One measures projected monthly subsidy against
  $500; the other measures the budget cap against a setting defaulting to $10,000.
  A $7,332 annual budget is $611 a month — over the first bar, under the second."*

And **`PRB-15`** is *"⚠ RULED NOT REQUIRED by the PO on 2026-09-08 — kept here
only because the COLUMN exists and is written by nothing"*, with a
`WHAT DONE LOOKS LIKE` of *"Not applicable"* and a STATUS of `UNVERIFIED`.

### ⚠ THE DOCUMENT IS TRUNCATED — this is not a reading error

**The PDF has 126 pages and ends in the MIDDLE of `PRB-19`'s cell**, at
*"…already worked out on save for the same reason"*, with the sentence unfinished
and three quarters of page 126 blank.

Three consequences, all of them findings rather than complaints:

1. **THE MASTHEAD COUNTS 26 SPECIFICATIONS AND THE REGISTER HOLDS 19.** Page 1's
   figure block reads `SPECIFICATIONS 26`. Seven rows — `PRB-20` … `PRB-26` — are
   not in the file. **They are real ids: `PRB-20`, `PRB-21` and `PRB-24` are all
   cited by name in the running code** —
   `06-backend/tests/test_cr087_c2_discount_takeup.py:2` (*"CR-087 task C2
   (PRB-20's computable half)"*), `06-backend/apps/rating/selectors.py:867`
   (*"CR-087 D5 / PRB-21 · THE UNITS A PLAN PRICES"*),
   `06-backend/tests/test_cr087_outside_city_percent.py:2` (*"CR-087 task D1
   (PRB-16 / PRB-24)"*). So the register's own *"One row per specification, no
   exceptions"* is false of the file as delivered.
2. **SECTIONS 08 AND 09 DO NOT EXIST.** Page 1's contents list nine sections and
   names `08 What this pass changed` and `09 Appendix`. Neither is in the file.
3. **THE MASTHEAD CITES AN APPENDIX THAT IS NOT THERE** — *"a decision stays
   decided until another decision supersedes it, and the ones in **appendix D2**
   are dated and recorded."* There is no appendix D2, so the document's own
   authority for its rulings cannot be read from it.

### What is on page 122 above the register

The top half of page 122 is the tail of section `06 EVERY STATED ABSENCE` — the
out-of-scope register `PRB-15` points at. Its visible rows are struck through and
marked `OUT OF SCOPE`, each with a PO ruling of 2026-09-08 quoted: a specimen bill
on a plan that has never billed, eligibility rules that refuse an assignment, a
customer sub-type on a plan, a late fee or deposit set on the plan, and the
`"Formula"` amount type with the `"Base only"` rate structure. Section 06 opens on
page 118 and is outside this pass's range.

### Where page 22 belongs

Page 21 ends the Charge codes section and opens `02 TAXES & FEES`; **page 22 is
that section's screen `07 Create · Step 1 · What it is`**, not a charge-code
screen. It is inside the assigned page range and outside the assigned subject, so
nothing was diffed from it.

---

## THE STATUS COLUMN, FILLED IN FROM THE CODE FOR THE FOUR ROWS THIS PASS COVERS

The register asks for this and asks for it one row at a time. These four are the
Charge codes rows; nothing else was checked.

| spec | register says | the code at 2.234.19 says |
|---|---|---|
| `PRB-01` | `UNVERIFIED` · *"Nothing else on this list can be drawn until it lands"* | **BUILT 2026-09-08** (CR-087 A1) as `customer_class`, a code, under two partial unique keys. The blocking sentence no longer holds |
| `PRB-02` | `UNVERIFIED` | **NOT BUILT.** `charges` has `waivable` only; the wizard states the gap |
| `PRB-03` | `UNVERIFIED` | **NOT BUILT.** One description column; the wizard states the gap |
| `PRB-04` | `UNVERIFIED` | **NOT BUILT.** Two `NO_FIGURE` tiles with TODOs naming the missing reads |

⚠ **AND ONE ROW OUTSIDE THE FOUR IS WORTH FLAGGING BECAUSE THE CODE NAMES IT
DIRECTLY.** `PRB-17` (*"no endpoint takes a plan and answers with the codes it may
carry"*) — its FIRST blocker is gone: `applies_to_customer_classes` is now
declared on `ChargeRow` at `07-frontend/src/api/endpoints.ts:4092`, whose own comment
says it was *"Served on `charge_row` since it was written and never declared here,
so CR-087 D2's Add-button filter had no type to read (`PRB-17`)"*. Whether the
endpoint half landed was not checked by this pass.
