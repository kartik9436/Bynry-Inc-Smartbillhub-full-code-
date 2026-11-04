# 09 · Create · Step 3 · Review & save — THE DRAWN SPEC, AND WHAT THE PRODUCT DOES

`S13 · TAX-02` · route `/:tenant/plans-rates/taxes-fees/new` · **blueprint pages
27–30** (heading at the foot of 27, frame drawn on **28–29**, specified on 29–30).

**State chip:** `NEW BUILD` **Commitment:** `PRB-05`

**Re-verify:** as-built claims were true at **2.232.0**; we are on **2.234.19**.

---

## 1 · The frame — same shell, `3 Review & save` active

## 2 · Card `What will be saved` — a THREE-COLUMN grid, ten facts, read across

| row | col 1 | col 2 | col 3 |
|---|---|---|---|
| 1 | `NAME ON THE BILL` `TX State Utility Tax` | `AUTHORITY` `Texas State` | `HOW IT IS WORKED OUT` `A percentage of the bill` |
| 2 | `RATE` `0.0625 — 6.25%` *(monospace)* | `WHAT IS TAXED` `Usage charges and base service charges` | `DISCOUNTS` `Taxed after the discount` |
| 3 | `WHERE A PREMISE HAS TO BE` `Everywhere in this utility` | `CUSTOMER CLASSES` `Every customer class` | `SERVICES` `All services` |
| 4 | `EFFECTIVE FROM` `06/01/2026` | — | — |

Beneath the grid, quiet, rule-marked:

> `The rate is shown exactly as you typed it. Bills and the catalogue show the rounded figure the server sends back.`

## 3 · Card `Before you save` — TWO labelled notes, in this order

| kicker | sentence, verbatim |
|---|---|
| `WHAT SAVING DOES` | `This tax matches all 1,284 premises. Saving puts it in force now — save it as a draft instead if you are not ready, and a draft charges nobody until you activate it.` |
| `WHAT COMES NEXT` | `Nothing above can be changed once a bill is issued at this rate. Everything else — the filing form, your account number with the authority, the collection allowance, who gets the reminder — is added on the tax's own page and stays editable.` |

⚠ **THE SECOND NOTE IS THE WHOLE POINT OF THE SCREEN'S REDRAW.** Page 29:
*"A wizard that stops asking for eight fields owes the clerk a sentence saying
where they went. The second note names them and says they stay editable — so a
clerk who needs a filing form this afternoon knows it exists and knows it is not
lost."*

⚠ **THE FROZEN LINE IS STATED HERE AND NOWHERE ELSE.** Page 29: *"Every field in
the grid above is one the product refuses to change on a live tax. That is not
this document's rule: it is the server's, and it is the same list the wizard was
built from. Saying it on the last screen is what makes the two steps make
sense."*

⚠ **ONE READER, ONE NUMBER.** Page 29: *"The premises count, again. Drawn by the
same component as step 1, so the two counts cannot disagree."*

## 4 · Footer — `Save tax or fee`, alone, right-aligned

## 5 · States — the blueprint's own block, verbatim

| state | drawn behaviour |
|---|---|
| **In force now** | *"Saving puts this tax in force now."* |
| **Dated ahead** | *"Dated to start on 01/01/2027. It will show as Scheduled and charges nobody until then."* |
| **Matches nobody** | *"The zero-match warning from step 1 is repeated here, because this is the last moment to catch it."* |

## 6 · Cognitive load, as stated

*"Ten facts, then two sentences: what the button does, and what is still to come.
Nothing new is introduced on a review screen."*

## 7 · Components named in the frame

`WizardFrame` `FieldGrid` `MatchedPremisesNote` `ConsequenceNote`

## 8 · Absences

* **No `FILED` / filing-frequency fact.** The remittance step is gone; nothing
  from it is read back.
* **No `EFFECTIVE TO`.**
* **No step kicker, heading or helper.**

---

## 9 · WHAT THE PRODUCT DOES — file and line evidence

`07-frontend/src/features/rating/TaxWizard.tsx`, `ReviewStep` at line 1726.

### The read-back grid, built vs drawn

| drawn fact | built? | evidence |
|---|---|---|
| `NAME ON THE BILL` | ✅ | line 1745 |
| `AUTHORITY` | ❌ **MISSING** | no row for the jurisdiction anywhere in `rows[]`, lines 1744-1777 |
| `HOW IT IS WORKED OUT` | ✅ | line 1746 |
| `RATE` | ✅ | line 1747 — value is the raw string, **not** the drawn `0.0625 — 6.25%` pair |
| `WHAT IS TAXED` | ❌ **MISSING** | `base_includes_usage` / `base_includes_base` are never read back |
| `DISCOUNTS` | ❌ **MISSING** | `discount_treatment` is never read back — the field the detail page calls *"the field that changes the arithmetic"* |
| `WHERE A PREMISE HAS TO BE` | ✅ label differs | line 1749, label `rating.taxWiz.scope.kindLabel` |
| `CUSTOMER CLASSES` | ✅ label differs | line 1758, label `rating.taxWiz.classes.label` |
| `SERVICES` | ✅ label differs | line 1767, label `rating.taxes.col.appliesTo = "Applies to"` |
| `EFFECTIVE FROM` | ✅ | line 1776 |
| — | ⚠ **EXTRA** | `FILED` (`rating.taxes.filingFrequencyLabel`) at line 1775 — **a remittance field the wizard no longer collects, still read back on the review** |

**Shape:** the drawn grid is three columns (`FieldGrid`); the built one is a
two-column `<dl>` of label/value pairs — lines 1780-1791.

### The two notes

| drawn | built? | evidence |
|---|---|---|
| `WHAT SAVING DOES` — count + save consequence | ⚠ **half** | `MatchedPremisesNote` at line 1804 and `rating.taxWiz.outcomes.active` at line 1816. Two separate notes, neither carrying a `WHAT SAVING DOES` kicker |
| `WHAT COMES NEXT` — where the eight fields went | ❌ **NOT BUILT** | no such string in any of the eleven catalogues ⟨grepped⟩ |
| the frozen line stated once, here | ❌ **NOT BUILT** | no string says the grid is frozen on a live tax |
| `The rate is shown exactly as you typed it…` | ✅ | `rating.taxWiz.review.asTyped`, line 1793 — rendered **only** when the rate was retyped, which is the more careful behaviour |
| footer `Save tax or fee` | ✅ | `rating.taxWiz.create = "Save tax or fee"` |

### ⚠ THE ONE FINDING WITH REAL CONSEQUENCE — THE TWO COUNTS *CAN* DISAGREE

Page 29 says the count is *"drawn by the same component as step 1, so the two
counts cannot disagree. One reader, one number."* **The component is the same and
the ARGUMENTS ARE NOT.**

* step 1 — `TaxWizard.tsx:1073-1078` passes `scopeKind`, `scopeValue`,
  `customerClasses` **and** `services`;
* step 3 — `TaxWizard.tsx:1804-1807` passes `scopeKind` and `scopeValue` **only**.

`MatchedPremisesNote` defaults the two missing lists to `[]`
(`TaxWizard.tsx:1117-1120`), so `narrowed` is false and the query hits a
different cache key. **A tax restricted to Commercial on Water reads its narrowed
reach on step 1 and the boundary's whole count on step 3** — larger than the
truth, on the last screen before the commit, which is exactly the failure
`PRB-05` was written to remove one step earlier. Every test passes: both steps
render a sentence, and no assertion compares the two numbers.

### States

* **In force now** ✅ / **Dated ahead** ✅ — `rating.taxWiz.outcomes.active` /
  `.scheduled`, lines 1814-1817. The drawn `01/01/2027` is an illustration
  (B14 rule 37); the built sentence interpolates the typed date.
* **Matches nobody** ⚠ — the zero-match warning is inside `MatchedPremisesNote`
  and does render here, but under the un-narrowed wording (`matched.none`,
  *"Check the boundary…"*) even when a class or service is what emptied it.

### Catalogue parity ⟨verified⟩ — every key present in all eleven locales.

---

## 10 · B14 rule 38 divergences — RECORDED, NOT BUILT

1. **`Save tax or fee` alone in the footer** — the shared wizard footer keeps
   `Cancel` and `Back`. Kit wins; nothing built.
2. **Three-column read-back grid.** Whether a read-back is two columns or three is
   form construction, and `FieldList`/`FieldGrid` is a kit decision that would
   move every definition detail at once (rule 38's own reason). **Record only.**
   ⚠ But **which facts appear, and in what order, is the drawing's to decide** —
   rule 38's last clause — so the three missing facts in §9 are findings, not
   divergences.

## 11 · THE BLUEPRINT AGAINST ITSELF

1. **`THIS SCREEN IS THE MODEL`, page 29:** *"Nothing was wrong here and that is
   why it is worth naming. Alone among the five review screens, this one already
   read back what was about to be saved."* Read against the frame, three of the
   ten drawn facts are not read back at all and a fourth (`FILED`) is read back
   from a step that no longer exists. **Both statements cannot be true of the
   same build.** The likeliest reading is that *"the model"* praises the RATE
   read-back mechanism (stored display string vs retyped echo), which IS
   exemplary and IS built — and that the ten-fact grid is the new specification
   rather than a description. **Recorded, not resolved.**

## 12 · NOT VERIFIABLE WITHOUT THE APP RUNNING

* Whether the step-1 and step-3 counts differ in practice — it needs a tax with a
  class or service restriction and a live server. The unit tests cannot see it and
  `10-scripts/cr087b_tax_screens_walkthrough.mjs` reads the count on step 1 only.

---

## 15 · WHAT WAS BUILT — 2026-09-10, the CR-087 tax-screens maintenance lane

**Maintenance, not Build** (`12-governance/22-product-maintenance-process.md`): a
clerk can already save a tax on this screen, so every finding below is a defect
against a live surface rather than a new capability.

| §9 finding | now |
|---|---|
| `AUTHORITY` **MISSING** from the read-back | **BUILT** — resolved to the authority's NAME (`jurisdictions.find`), or to what was typed when `+ Add an authority` is chosen. B14 rule 31: the stored id is never the visible value |
| `WHAT IS TAXED` **MISSING** | **BUILT** — the two ticks joined, and offered ONLY on the percentage form, because the ticks only exist there (`fields.percent`). A flat fee has no base to take a percentage of, and reading back a base it never had is a fact about nothing |
| `DISCOUNTS` **MISSING** | **BUILT** — `rating.taxWiz.discountTreatment.*`, the SAME key the field uses. ⚠ The label was **not** re-worded: page 25's *"What was wrong"* says the two options are labelled the opposite way round from the values they store, and at `2.234.19` they are **not** — `before` reads *"Taxed after discounts (discount applies first)"*, which is what `selectors.taxable_subtotal_for` documents `before` to mean. A money-adjacent label that is already right |
| `FILED` **EXTRA** | **REMOVED.** The wizard stopped collecting it on 2026-09-08; a read-back that shows a field the form never collected presents a stored default as though the clerk had chosen it |
| the two counts **CAN DISAGREE** | **FIXED** — `MatchedPremisesNote` here now takes `customerClasses` and `services`, so both steps issue the SAME request. `DEF-RAT-4821`. The test asserts the two URLs are **equal, whole**: a substring check cannot see what is missing, and what was missing was the narrowing |
| the drawn row ORDER | **BUILT** — name · authority · how it is worked out · rate · what is taxed · discounts · boundary · classes · services · effective from |

**ADDED BEYOND THE DRAWING, AND IT IS THE OTHER HALF OF `p030` §11.** On a tax
that is IN FORCE this step now carries a required **`Reason for correction`**
box and a consequence line, because the commit files a correction
(`POST /taxes/{id}/corrections`) rather than a PATCH. The drawing draws this
screen for a NEW tax and says nothing about the edit case; `BR-RAT-104` requires
a reason and the server refuses without one. Its BOUND is the server's — the
module's money law forbids a second copy of a rule — so a reason that is too
short comes back as `rating.taxes.correction_reason` on this box.

**STILL OPEN, unchanged:** the drawn three-column `FieldGrid` (§10 divergence 2
— form construction, B14 rule 38), `WHAT COMES NEXT`, and the frozen-line
sentence. Both notes are copy the blueprint asks for and neither was built here.
