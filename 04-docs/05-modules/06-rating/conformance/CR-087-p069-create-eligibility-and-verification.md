# DIS-02 step 3 · Create · Eligibility & verification — THE DRAWN SPEC, AND WHAT IS BUILT

Blueprint screen **23**, `/:tenant/plans-rates/discounts/new` · **blueprint
pages 69–71**, frame drawn on **pages 69–70**.

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`
(md5 `2e46f5053ca65804da9c1a90a487e044`), text **and** rendered PNGs at 2.0.

**State chip:** `NEW BUILD` · **Commitments:** `PRB-11` · `PRB-14`

**Re-verified at 2.234.19** (blueprint read at 2.232.0 / d2d493e4).

**Code read:** `DiscountWizard.tsx` — `EligibilityStep`, lines **1347–1546**;
the enrolment choice helpers `DISCOUNT_ENROLMENT_CHOICES` / `enrolmentChoiceOf`
/ `enrolmentChoicePatch`.

---

## 1 · Header, actions, rail

As step 1, with `3 Eligibility & verification` active.

## 2 · The one panel — heading `Who qualifies`

Section sentence, verbatim, **one sentence**:

> `A discount applies because of a fact about the customer, so this programme owns`
> `its own proof and renewal rules.`

## 3 · Controls, in the drawn order — three, plus one stated absence

| # | label | control | drawn value |
|---|---|---|---|
| 1 | `WHO QUALIFIES, IN PLAIN LANGUAGE` | text area, **example in the PLACEHOLDER** | placeholder `Age 65 or over.` |
| 2 | `HOW PEOPLE JOIN` * | dropdown, **three options** | `Apply and approve, with proof` |
| 3 | `VERIFICATION` * | dropdown | `One-time proof at enrolment` |
| 4 | `STRUCTURED ELIGIBILITY RULE` | **stated absence** — label, `—`, one sentence | `The rule builder is not built; enrolment is recorded by a member of staff.` |

**The three enrolment options, verbatim (page 70):** `Automatic` ·
`Apply and approve` · `Apply and approve, with proof`.

⚠ **TWO CONTROLS BECAME ONE DROPDOWN AND THE IMPOSSIBLE FOURTH CANNOT BE
EXPRESSED.** Page 70, verbatim: *"Enrolment was two buttons and a separate
tick-box, and one of the four combinations was impossible. Automatic enrolment
that also demands a document either enrols nobody or asks for nothing, and which
one it did depended on whichever check ran first — so the screen refused it, in
place, with the best refusal message in the product. **The three real answers
are now three options in one dropdown** … **A refusal that can no longer fire is
a better outcome than a refusal written well.**"*

⚠ **THE EXAMPLES MOVED INTO THE BOX.** Page 71: *"`Age 65 or over` and `income
at or below 150% of the federal poverty guideline` were help text under an empty
box. They are **the placeholder in the box**, where a clerk is looking when they
need them."*

⚠ **RESTRICTED PROOF (page 71).** *"Four of the ten proof kinds are badged
Restricted. Choosing one puts every such document behind a role rule and out of
the general lists a clerk browses — said on the screen, because a clerk ticking
`income statement` is making a data-protection decision without realising it."*

**Cognitive load, as stated:** *"Three controls and one stated absence. The step
went from five prose blocks to one."*

## 4 · Footer

`Continue`, right. **PRIMARY ACTION:** `Continue.`

## 5 · States — verbatim

| state | drawn behaviour |
|---|---|
| **Automatic** | *"The proof options and the whole renewal block are absent — nothing to prove and nothing to renew."* |
| **Apply and approve, with proof** | *"The proof kinds open and recertification appears."* |
| **Never expires** | *"Recertification months, notice and grace all collapse — a programme that never expires has no renewal to configure."* |

## 6 · WHAT THE SERVER NEEDS (page 71, verbatim) — this is `PRB-14`

> *"One refusal, moved to where it is true for every caller. The impossible
> combination — automatic enrolment that also demands proof — is now
> unrepresentable in the dropdown, and a client that cannot express a state is
> not the same as a server that refuses it. The API still accepts the two fields
> separately, so it should refuse the pair, for the reason `DEF-384` gives about
> a different endpoint: a client-side refusal is not a refusal."*

## 7 · Components named by the drawing

`WizardFrame` `TextArea` `SelectField` `NamedAbsence`

## 8 · Rules, verbatim — one clause more than the other steps

*"… Built in the shared utility classes, adding nothing to a stylesheet.
**Where a combination is impossible, make it unrepresentable rather than
refused.**"*

## 9 · Absences — drawn as absent

* **No separate `Proof is required to enrol` tick.**
* **No `STEP 3 OF 5` kicker** and no step heading sentence.
* **No helper line under any of the three controls.**

---

## AS BUILT AT 2.234.19 — the diff, with evidence

### Matches — and the largest single thing the drawing asks for is already built

* **The enrolment pair IS one dropdown of three options** — `:1392-1404`,
  options `enrolmentChoice.automatic | .apply_and_approve |
  .apply_and_approve_with_proof`. The impossible fourth cannot be produced;
  asserted at `DiscountWizard.test.tsx:643`.
* **The separate proof tick is gone** — asserted as an absence,
  `DiscountWizard.test.tsx:652`.
* **The proof list opens with the option that needs it** — `:1446-1482`, gated
  on `draft.proof_required`.
* **Four of ten proof kinds are badged `Restricted`** — `DISCOUNT_PROOF_KINDS`
  (10) and `DISCOUNT_RESTRICTED_PROOF_KINDS` (4) at
  `07-frontend/src/api/endpoints.ts:4269-4296`. **The drawn count is exact.**
* **The structured rule builder is a named absence, not a half-build** —
  `:1379-1382`, `ArrivesWithField`. The drawn component shape matches.
* **The refusal is retained for stored legacy rows** — `:1414-1421`, and the
  drawing's own *"THE REFUSAL IS NOT LOST, IT IS REPAID"* paragraph says it
  should be.

### 1 · The examples are still HELP TEXT, not the placeholder

`:1366-1375` renders the eligibility summary with
`help={t("rating.discountWizard.summaryHelp")}` —
*"One sentence a clerk can act on — this is what the Discounts list shows in its
Eligibility column. Age 65 or over. Income at or below 150% of the federal
poverty guideline."* — and **passes no `placeholder`**.

`TextField` already accepts `placeholder` and applies it in the multiline branch
(`components/FormModal.tsx:196`, `:228`, `:240-244`), so the kit is not the
obstacle. The drawn change is one prop and two catalogue values.

### 2 · Two controls the frame does not draw, both live in the drawn state

The frame is drawn with `Apply and approve, with proof` chosen, which sets
`proof_required`. In that state the built screen also renders:

* `:1427-1436` — `CheckboxField` **`Proof must arrive before the first
  reduction`** plus its `Note`
  *"Off means the reduction starts and the document is chased. On means the
  customer pays full price until it arrives."*
* `:1497-1525` — three numeric fields, **`Recertify every (months)`**,
  **`Notice before it is due (days)`**, **`Grace after it is due (days)`**, and
  `:1526-1537` **`If recertification lapses`**.
* `:1539-1542` — a fourth stated absence, **`Backdating limit`**.

The drawing's STATES row *"the proof kinds open and recertification appears"*
covers the proof grid and recertification. It says nothing about the
proof-before tick or the backdating absence. See CONTRADICTIONS §1.

### 3 · Four helper lines the frame does not draw

| built | evidence |
|---|---|
| `The kinds of evidence a clerk may accept. This is a policy list, not a customer's file — no document and no account is read on this screen.` | `:1449` |
| `Income and medical evidence is restricted by role and is kept out of the general document lists a clerk browses. Choosing one of the four marked Restricted puts every such document behind that rule.` | `:1480` |
| `How the qualifying fact is checked, and how often.` under `VERIFICATION` | `:1494` |
| `Leave blank where the programme never expires.` under recert months | `:1503` |

The drawing keeps the restricted-proof consequence **as a sentence on the
screen** (page 71 says so explicitly), so `:1480` is drawn in substance. The
other three are not.

### 4 · `VERIFICATION` is in a different panel and a different position

Drawn: control **3 of 3** in the same panel, directly under `HOW PEOPLE JOIN`.
Built: a fourth `<Panel as="section">` at `:1484`, **after** the ten-checkbox
proof grid — so a clerk choosing *with proof* meets ten tick-boxes between the
two questions the drawing puts side by side.

### 5 · The rule-builder absence is 44 words where the drawing writes 12

Built `ruleBuilderPending`: *"The rule builder — customer class, age, an income
test against a stated index with a household-size table, programme
participation, veteran or disability status, medical certification, autopay,
combined with AND and OR — is not built yet. Enrolment stays something a member
of staff records."*
Drawn: *"The rule builder is not built; enrolment is recorded by a member of
staff."* B14 rule 32's description budget is on the drawing's side.

### 6 · Four panels where the drawing draws one

`:1363` · `:1385` · `:1447` · `:1484`.

### 7 · Five orphaned catalogue strings from the control this replaced

`rating.discounts.enrolment.automatic`, `rating.discounts.enrolment.
apply_and_approve`, `rating.discountWizard.proofRequiredLabel` and
`rating.discountWizard.enrolmentModeHelp` are referenced **only** by negative
assertions (`DefinitionDetail.test.tsx:520`, `DiscountWizard.test.tsx:656`) and
by nothing that renders. They are present in all eleven catalogues. Not a defect
in this screen — recorded because a string nobody renders is one copy-paste from
being read out loud again.

### 8 · `PRB-14` — the server half — is NOT done

The drawing is explicit that the client half is not the refusal. `POST` still
accepts `enrolment_mode` and `proof_required` as two independent fields
(`DiscountDraft`, `DiscountWizard.tsx:230-290`; the request body test at
`DiscountWizard.test.tsx:874`). **Backend, not this screen. Recorded, not
filed.**

---

## CONTRADICTIONS INSIDE THE BLUEPRINT — recorded, not resolved

1. **THE FRAME IS DRAWN IN ONE STATE AND VALUED IN ANOTHER.** `HOW PEOPLE JOIN`
   reads `Apply and approve, with proof`, and the frame draws **neither the
   proof kinds nor recertification** — while its own STATES row says both appear
   in exactly that state, and its cognitive-load line says *"three controls and
   one stated absence"*, which is only true of `Automatic`.
   **Reading, and it is the reconciling one: B14 rule 37 makes the drawn VALUE
   an illustration.** Build the SHAPE both halves agree on — three controls and
   one absence in the base state, proof kinds and recertification appearing on
   *with proof* — and ignore which option the illustrator happened to select.

2. **THE PROOF-BEFORE TICK AND THE BACKDATING ABSENCE** are neither drawn nor
   stated absent. Same shape as `CR-087-p067` §3: an omission to confirm, not a
   deletion to make.

---

## WHAT NEEDS THE PRODUCT OWNER

* **CONTRADICTIONS §2** — whether `Proof must arrive before the first reduction`
  and the `Backdating limit` absence stay on this step.

## WHAT COULD NOT BE VERIFIED WITHOUT THE APP RUNNING

* Whether the ten-checkbox proof grid still reads as two columns at 1280 with
  the `Restricted` badge beside four of them, in the longer catalogues.
* Whether the placeholder, once built, is distinguishable from a real value at
  the kit's input contrast.
