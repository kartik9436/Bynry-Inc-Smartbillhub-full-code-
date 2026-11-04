# 07 · Create · Step 1 · What it is — THE DRAWN SPEC, AND WHAT THE PRODUCT DOES

`S13 · TAX-02` · route `/:tenant/plans-rates/taxes-fees/new` · **blueprint pages
22–25** (the section opens on page 21, the frame is drawn on **22–23**, specified
on 23–25).

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`. Read as
RENDERED pages — text extraction printed the *Who it reaches* card's three fields
out of order and dropped the count line into the middle of the prose.

**State chip:** `NEW BUILD` **Commitment:** `PRB-05`

**Masthead warning that governs this whole file:** the blueprint's own cover says
every *as-built* statement in it was true at **2.232.0 / `d2d493e4` / 8 Sep 2026**
and *"must be re-verified before it is trusted or acted on"*. We are on
**2.234.19**. Everything below marked ⟨verified⟩ was read from the code at that
head; the drawing is authoritative, its claims about the product are not.

---

## 1 · Header — the drawn frame

| slot | drawn |
|---|---|
| kicker | `NEW TAX OR FEE` |
| title (H1) | `Add a tax, franchise fee, or surcharge.` |
| sub-line | `Three steps · takes about 2 minutes. Filing details are added later, on the tax itself.` |
| top-right, in order | `Cancel` *(accent text link)* · `Save draft & exit` *(outlined button)* |

## 2 · Step rail — three segments, `1 What it is` active

`1 What it is` | `2 How much` | `3 Review & save`

## 3 · Card `The tax` — two fields

| # | label | drawn value | required |
|---|---|---|---|
| 1 | `NAME ON THE BILL` | `TX State Utility Tax` | ✱ |
| 2 | `AUTHORITY` | `Texas State — or add your own` *(select)* | ✱ |

Page 24: *"The picker's last option is `+ Add an authority`, which takes a name and
a level inline; the full list is in Settings → Reference data."*

## 4 · Card `Who it reaches` — three fields, then ONE sentence

| # | label | drawn value | control |
|---|---|---|---|
| 1 | `WHERE A PREMISE HAS TO BE` | `Everywhere in this utility` | select |
| 2 | `CUSTOMER CLASSES` | `Every customer class` | select |
| 3 | `SERVICES` | `All services` | select |

Then, quiet, rule-marked, at the foot of the card:

> `As it stands this tax reaches all 1,284 premises, every customer class and every service.`

⚠ **THE COUNT IS THE ONLY NUMBER ON THE STEP AND THAT IS THE POINT.** Page 24,
verbatim: *"One sentence survives, and it is the only one that names a number —
`all 1,284 premises` — because it tells the clerk what they have just done rather
than what a word means."* And: *"Shown while you choose, not after you save. A
boundary that matches nobody is the commonest and most expensive mistake on this
screen … it now counts all three narrowings together rather than the boundary
alone."* **`1,284` itself is an illustration — B14 rule 37.**

## 5 · Footer — ONE control

`Continue`, right-aligned. No `Back`, no `Cancel` in the footer.

## 6 · States — the blueprint's own block, verbatim

| state | drawn behaviour |
|---|---|
| **No boundary** | *"Says plainly that every premises is in scope, with the number."* |
| **A boundary nothing can evaluate** | *"County, district and named-list boundaries are recorded and cannot be checked, so the screen says the tax reaches **nobody** — deliberately, because a boundary we cannot check must never be read as applying to everyone."* |
| **Zero matches** | *"No premises match. Check this before entering a rate — as it stands this tax would reach nobody."* |
| **Count unavailable** | *"Says the count could not be read and that nothing is wrong with the boundary, so a clerk does not chase a fault that is not there."* |

## 7 · Cognitive load, as stated

*"Five controls, two of them required, three arriving already answered with the
safe answer. Nothing on this step has to be typed to continue except the name and
the authority."*

## 8 · Components named in the frame

`WizardFrame` `TextField` `SelectField` `MatchedPremisesNote` `Panel`

## 9 · Absences — drawn as absent, do not fill them

* **No `CODE`, no `BILL LABEL`, no `TAX TYPE`.** Page 23: *"Code, bill label and
  tax type are all editable for ever, so none of them belongs in front of a clerk
  who has not yet said what the tax charges. They move to `On the bill` on the
  tax's page."*
* **No step kicker, no step heading, no helper paragraph** between the rail and
  the first card — see §12 finding 1.
* **No `Level`, no `Reference`** unless `+ Add an authority` is chosen.
* **Eight blocks of prose are gone.** Page 24 names the six that went: *"what a
  jurisdiction is, that authorities are yours to enter, that overlapping
  boundaries are expected, what a code is for, what a bill label is for, and how a
  tax type differs from a basis."*

---

## 10 · WHAT THE PRODUCT DOES — file and line evidence

Everything here read at `2.234.19`, from
`07-frontend/src/features/rating/TaxWizard.tsx` unless another file is named.

| # | drawn | built? | evidence |
|---|---|---|---|
| 1 | three steps | ✅ | `TAX_WIZARD_STEPS = ["jurisdiction","rate","review"]` — `TaxWizard.tsx:194` |
| 2 | kicker `New tax or fee` | ✅ | `rating.taxWiz.kicker` — `en.json`; `TaxWizard.tsx:729` |
| 3 | title `Add a tax, franchise fee, or surcharge.` | ✅ | `rating.taxWiz.title` |
| 4 | sub-line `Three steps · takes about 2 minutes. Filing details are added later, on the tax itself.` | ✅ | `rating.taxWiz.sub` |
| 5 | rail labels `What it is · How much · Review & save` | ✅ | `rating.taxWiz.step.jurisdiction/rate/review` |
| 6 | `Save draft & exit` top-right | ✅ | `TaxWizard.tsx:734-743` |
| 7 | `Cancel` top-right | ❌ | `Cancel` is a **footer ghost button** — `TaxWizard.tsx:846-849` |
| 8 | field `NAME ON THE BILL` ✱ | ✅ | `rating.taxes.nameLabel = "Name on the bill"`; `TaxWizard.tsx:917-925` |
| 9 | field `AUTHORITY` ✱ | ✅ | `rating.taxes.jurisdictionLabel = "Authority"`; `TaxWizard.tsx:926-947` |
| 10 | card heading `The tax` | ❌ | renders `rating.taxes.form.jurisdiction = "Authority"` — `TaxWizard.tsx:916` |
| 11 | card heading `Who it reaches` | ❌ | renders `rating.taxWiz.scope.title = "Where it applies"` — `TaxWizard.tsx:984` |
| 12 | `WHERE A PREMISE HAS TO BE` | ❌ | renders `rating.taxWiz.scope.kindLabel = "How a premise is decided to be in scope"` — `TaxWizard.tsx:988` |
| 13 | `CUSTOMER CLASSES` | ❌ | renders `rating.taxWiz.classes.label = "Customer classes this applies to"` — `TaxWizard.tsx:1045` |
| 14 | `SERVICES` | ❌ | renders `rating.taxes.appliesToLabel = "Services this applies to"` — `TaxWizard.tsx:1025` |
| 15 | classes and services drawn as ONE CONTROL each | ❌ | both are **`<fieldset>` walls of `CheckboxField`** — `TaxWizard.tsx:1024-1063` |
| 16 | order boundary → classes → services | ❌ | built order is boundary → **services** → **classes** — `TaxWizard.tsx:1024` then `1044` |
| 17 | one sentence naming the count | ❌ | with nothing narrowed the note is `rating.taxWiz.matched.everywhere = "With no boundary chosen, this tax applies to every premises you have."` — **no number at all**, `TaxWizard.tsx:1139-1141` (`matched.everywhere` at 1140) |
| 18 | count narrows on class and service (`PRB-05`) | ✅ **already built** | `TaxWizard.tsx:1073-1078` passes all three; `06-backend/apps/rating/api.py:452-485` reads `customer_classes` and `services` |
| 19 | `+ Add an authority` last option | ⚠ | reads `rating.taxes.jurisdiction.addNew = "Add a new authority"` — no `+`, different noun |
| 20 | overlapping-boundaries prose GONE | ❌ | still rendered: `rating.taxWiz.scope.help` — `TaxWizard.tsx:985` |
| 21 | `authorities are yours to enter` prose GONE | ❌ | still rendered as the authority field's `help` (`rating.taxes.jurisdictionHelp`) — `TaxWizard.tsx:934` and `945` |
| 22 | no `CODE` / `BILL LABEL` / `TAX TYPE` on this step | ✅ | they are in `TAX_REMITTANCE_KEYS` and collected on the tax's page — `TaxWizard.tsx:1464-1478` |
| 23 | footer holds `Continue` alone | ❌ (B14 rule 38 — see §11) | footer is `Cancel` ghost + `Back` + `Continue` — `TaxWizard.tsx:846-874` |

### The three states that ARE built, and the one that is not

* **A boundary nothing can evaluate** ✅ — `scopeIsResolvable`, `TaxWizard.tsx:237`,
  and `matched.unresolvableCount`, `TaxWizard.tsx:1148-1154`.
* **Zero matches** ✅ — `matched.none` / `matched.noneNarrowed`, `TaxWizard.tsx:1182-1192`.
* **Count unavailable** ✅ — `matched.unavailable`, `TaxWizard.tsx:1145-1147`.
* **No boundary** ❌ — states the fact **without the number** (row 17 above). The
  drawn behaviour is *"with the number"*, and the whole argument for the sentence
  on page 24 is that it names one.

### Catalogue parity ⟨verified⟩

All 324 `rating.taxWiz.*` / `rating.taxes.*` / `rating.definition.*` keys exist in
all **eleven** locales, and every `t("…")` literal in `TaxWizard.tsx` resolves in
`en.json`. Nothing on this step reaches a clerk as silence.

---

## 11 · B14 rule 38 divergences — RECORDED, NOT BUILT

Rule 38: *"where a drawing and our UI rules disagree about how a FORM is BUILT,
the UI rules win … the divergence is RECORDED in the conformance file, and nothing
is built for it."*

1. **`Cancel` in the header vs the footer.** B14 rule 3 gives a stepper a
   *wizard-actions footer*; `09-screen-inventory.md` §8 part 12 draws `Cancel`
   (ghost, accent) at footer-left, and the product has done that on CHG-02, RAT-03
   and PLN-03 since 2026-08-21. **The kit wins; the drawing loses.** Nothing built.
2. **A `Back` button the drawing does not show.** B14 rule 1 distinguishes the
   header's exit from a stepper's `← Back`; removing it would leave step 2 and 3
   with no way back but the rail. **Kit wins.** Nothing built.

## 12 · WHERE THE DRAWING CONTRADICTS ANOTHER SIGNED SPEC — FOR THE PRODUCT OWNER

1. **THE FRAME OMITS PARTS 8, 9 AND 10 OF THE TWELVE-PART WIZARD SHELL.**
   `04-docs/05-modules/06-rating/09-screen-inventory.md` §8 (PO ruling 2026-08-20,
   read off five r10 screenshots) mandates `STEP 1 OF n` as a small uppercase
   accent kicker (part 8), a step heading that is a sentence — *"Name and
   jurisdiction."* for this very screen (part 9) — and a muted helper paragraph
   (part 10). The blueprint draws **none of the three**, on all three tax steps.
   * **Part 10 is clearly deliberate**: the helper the product renders
     (`rating.taxWiz.jurisdiction.helper`) contains *"Overlapping authorities are
     expected"*, and page 24 names *"that overlapping boundaries are expected"* as
     one of the six explanations it deletes.
   * **Parts 8 and 9 are not argued anywhere in the blueprint's prose.** Two
     signed specs disagree and neither is a UI-construction question B14 settles.
     **One sentence to the PO decides it.**
2. **`Cancel` is drawn top-right here and at footer-left in §8 part 12** — the
   same conflict, from the other side. §11 above resolves it for the code; the
   drawing should be corrected or the ruling restated.

## 13 · THE BLUEPRINT AGAINST ITSELF

1. **`PRB-05` is drawn as an open commitment and is already built.** Page 38's
   card says it *"Waits on: Two more parameters on `GET /taxes/matched-premises`,
   which takes `premises_scope_kind` and `premises_scope_value` and nothing
   else."* At `2.234.19` that endpoint takes `customer_classes` and `services`
   too (`06-backend/apps/rating/api.py:476-485`), the wizard passes all three
   (`TaxWizard.tsx:1073-1078`), and the decision log records it built on
   2026-09-08. **The commitment's *waits on* is stale, not the drawing.** Its
   *"what done looks like"* — *"the count falls from 1,284 premises to 212"* —
   is the remaining unverified half, and it depends on finding 17 above (the
   sentence at *Everywhere* names no number to fall from).

## 14 · NOT VERIFIABLE WITHOUT THE APP RUNNING

* Whether the count sentence updates **while the clerk is still on the step**
  (page 24's *"Shown while you choose, not after you save"*). The query is keyed
  on all three narrowings and `staleTime: REFERENCE_STALE_MS`
  (`TaxWizard.tsx:1122-1138`), so it should — but that is a live-server
  statement, and `10-scripts/cr087b_tax_screens_walkthrough.mjs` is the thing
  that makes it.
* Column alignment, gap rhythm and whether the two cards read as two cards at
  1280 and 1440.
