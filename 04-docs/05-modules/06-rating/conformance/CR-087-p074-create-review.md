# DIS-02 step 5 · Create · Review — THE DRAWN SPEC, AND WHAT IS BUILT

Blueprint screen **25**, `/:tenant/plans-rates/discounts/new` · **blueprint
pages 74–76**, frame drawn on **pages 74–75**.

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`
(md5 `2e46f5053ca65804da9c1a90a487e044`), text **and** rendered PNGs at 2.0.

**State chip:** `NEW READ` · **Commitments:** `NO COMMITMENT`

**Re-verified at 2.234.19** (blueprint read at 2.232.0 / d2d493e4).

**Code read:** `DiscountWizard.tsx` — `ReviewStep`, lines **1704–1836**.

---

## 1 · Header, actions, rail

As step 1, with `5 Review` active.

## 2 · Panel one — heading `What is changing`

**A three-column comparison table. No intro sentence** — page 76: *"the panel
intro is gone because the table's own heading says what it is."*

| header | alignment |
|---|---|
| *(row label, unheaded)* | left |
| `IN FORCE NOW` | left |
| `SAVING AS V3` | left |
| `CHANGE` | right, **accent, monospace** |

**The three drawn rows — only what CHANGED:**

| | `IN FORCE NOW` | `SAVING AS V3` | `CHANGE` |
|---|---|---|---|
| `Value` | `10%` | `15%` | `+5 points` |
| `Applies to` | `Subtotal before taxes` | `Subtotal before taxes` | *(blank)* |
| `Budget cap` | `$5,000.00` | `$7,332.00` | `+$2,332.00` |

⚠ **THE VALUE ROW READS BACK THE DRAFT, NOT THE STORED FIGURE.** Page 75,
verbatim: *"**It showed the stored value and ignored the one just retyped** — on
the one field a discount is actually about. It now reads back the draft beside
what it replaces, the same treatment as the rate schedule and the charge code,
so all five review screens behave the same way."*

## 3 · Panel one, below the table — a plain field grid, **six** facts

`CODE` `SENIOR` · `BILL LINE LABEL` `Senior citizen discount` · `TYPE`
`Percentage`
`HOW PEOPLE JOIN` `Apply and approve, with proof` · `VERIFICATION`
`One-time proof at enrolment` · `STACKING PRECEDENCE` `1`

⚠ **`Value` AND `Applies to` ARE NOT IN THE GRID** — they are the comparison
table's rows. Page 76: *"Only what changes is compared. Everything else is a
plain grid."*

## 4 · Panel two — heading `What saving does`

A bordered panel containing one callout: label `NOTHING CHANGES YET`, accent
left rule, body verbatim, **one sentence**:

> `This saves version 3 as a draft — the 31 enrolled accounts keep 10% until you`
> `activate it.`

⚠ **TWO SENTENCES BECAME ONE.** Page 75: *"`This saves version 3 as a draft. A
draft prices nothing and enrols nobody — 31 enrolled accounts keep the current
10%…` said the same thing twice. One sentence keeps the version, the 31 people
and the 10%."*

## 5 · Footer

`Save new version`, right. **PRIMARY ACTION:** `Save new version.`

## 6 · States — verbatim

| state | drawn behaviour |
|---|---|
| **Creating** | *"No comparison table and no reason — nothing exists to change from. The grid alone."* |
| **Nothing changed** | *"The comparison is absent rather than showing unchanged rows."* |

## 7 · Components named by the drawing

`WizardFrame` `OldNewTable` `FieldGrid` `ConsequenceNote`

## 8 · Rules, verbatim — one clause more than the other steps

*"… Built in the shared utility classes, adding nothing to a stylesheet.
**A review screen reads back what is about to be saved.**"*

## 9 · Absences — drawn as absent, and one is stated as a removal

* ⚠ **`Submit for approval` AND `Activate` ARE REMOVED.** Page 76, verbatim:
  *"`Submit for approval` and `Activate` sat here permanently disabled with a
  sentence explaining they live somewhere else. **A disabled control that has
  never once been usable is not a control**; the sentence is now the note above,
  which says where to go and why nothing changes yet."*
* **No `The bill line the customer will read` sample block.**
* **No panel intro sentence** over the comparison table.
* **No `STEP 5 OF 5` kicker** and no step heading sentence.

---

## AS BUILT AT 2.234.19 — the diff, with evidence

### Matches

* `Save new version` is the commit label on the edit door — `:881-883`,
  `rating.discountWizard.editSubmit`.
* The enrolment pair reads back as **one** row, not two — `:1737-1747`.
* The read-back grid carries `CODE`, `BILL LINE LABEL`, `TYPE`,
  `HOW PEOPLE JOIN`, `VERIFICATION`, `STACKING PRECEDENCE` — `:1721-1751`. All
  six drawn facts are present.

### 1 · THE VALUE ROW STILL READS BACK THE STORED FIGURE — the named defect is live

`:1717-1720`:

```
const valueLine =
  unit === null
    ? t("rating.discountWizard.asTyped")
    : (discount?.value_display ?? `${draft.value.trim()} ${t("…asTyped")}`);
```

On the **edit** door `discount` is the loaded `DiscountDetail` (`:669`,
`:825`), so `discount.value_display` — **the stored figure** — wins and
`draft.value`, the thing the clerk just retyped on step 2, is discarded. The
draft branch is reached only when `discount` is null, i.e. on the create door,
where there is nothing to compare against anyway.

**So the exact sentence page 75 writes in the past tense is present tense at
2.234.19**, and it is on the one field a discount is about. This is the single
most consequential finding in pages 65–84.

⚠ **AND THE FIX IS NOT "PRINT `draft.value`".** `BR-RAT-087` / `DEF-364` make
the server the only formatter of a discount value: `discount_versions.value`
holds **percentage points** where `charges.percent` holds a fraction, and
`_display_percent_points` owns the conversion (`DiscountWizard.tsx:52-64`).
Rendering an unformatted `15` beside a formatted `10.00%` in the same column is
how the two conventions get read as one. The drawn table needs a **served**
display string for the draft, or an explicitly unformatted read-back both
columns share. **That is a design call with `B4`/`B5` exposure — record it,
do not choose it.**

### 2 · THERE IS NO COMPARISON TABLE AT ALL

`:1762-1772` renders one flat `<dl>` of **eight** rows —
`Code · Bill line label · Type · Value · Applies to · Enrolment · Verification ·
Stacking precedence` — with no old value, no new value and no change column.
`OldNewTable` is named by the drawing and exists nowhere in
`07-frontend/src/components/`. Both drawn STATES rows (*Creating*, *Nothing
changed*) describe a table that is not built.

### 3 · THE TWO DISABLED BUTTONS ARE STILL DRAWN

`:1803-1820` renders two `GuardedButton`s, `readOnly` with
`readOnlyReason={t("rating.discountWizard.lifecycleOnDetail")}`, labelled
`Submit for approval` and `Activate`, in the `secondary` tier.

The drawing removes both by name and gives the reason. The code gives its own
reason at `:1789-1801` — `BR-SHL-019` makes the wizard one transactional call —
and `DiscountWizard.test.tsx:824` asserts they are drawn. **Both positions are
coherent; they disagree.** The drawing does not dispute the rule, it disputes
the control: *"a disabled control that has never once been usable is not a
control"*, and the reason survives as the note above. **Recorded for the PO.**

⚠ **The refusal reaches the reader only as a `title` tooltip.** `GuardedButton`
puts `readOnlyReason` on `Button`'s `title` (`ratingShared.tsx:660-671`). The
same file argues elsewhere that a `title` is *"invisible on a touch device and
unreliable to a screen reader"* (`DefinitionDetailPage.tsx:500-503`). Staff
screens are desktop-only by the 2026-09-10 ruling, so a mouse can reach it — but
a keyboard-only clerk cannot. Recorded as an accessibility observation.

### 4 · THE CONSEQUENCE IS HAND-ROLLED, AND `ConsequenceBox` IS IN THE KIT

Drawn: a bordered panel headed `What saving does`, holding a labelled callout
`NOTHING CHANGES YET` with an accent left rule and one sentence.

Built `:1773`: `<Note className="mt-3">{t("…landsAsDraft")}</Note>` — a plain
grey note **inside** the field panel, with no heading, no label and no rule,
reading *"Saving creates this discount as a draft, with version 1 also a
draft."* — which is the **create** sentence; the drawn one names the version,
the 31 people and the 10%.

`components/ConsequenceBox.tsx` is the kit's answer and takes exactly the drawn
shape — `tone`, `tag` (the label word), `title`, one-sentence `body`
(`:81-93`). **B14 rule 11 makes a consequence preview mandatory before a commit
that writes money, and B14 rule 36 says compose the kit.** This screen does
neither.

⚠ **THIS IS THE ROOT CAUSE BEHIND FOUR SITES IN PAGES 65–84**, and it is worth
naming once: the drawn callout shape appears on step 4 (`SECOND APPROVAL —
OPEN`), step 5 (`NOTHING CHANGES YET`), the Plans tab (`OFFERED, NOT GIVEN`) and
the Audit tab (`DATED`). Built, they are a `Panel`+`Kicker`+`Note`
(`DiscountWizard.tsx:1668-1674`), a bare `Note` (`:1773`), nothing at all, and a
fourth hand-rolled left-rule `<section>` (`DefinitionDetailPage.tsx:771-782`).
**Four spellings of one component, none of them the kit's.**

### 5 · The sample bill line is drawn nowhere and is built

`:1780-1784` renders `ArrivesWith` titled `The bill line the customer will read`
with `samplePending`. The drawing draws no such block and its cognitive-load
line accounts for only the table, the grid and the consequence.

### 6 · The step head is three lines the drawing does not draw

`:1757-1761` — `Step 5 of 5` / `Read it back before it is saved.` /
`Nothing below reduces a bill yet. This saves a draft; a draft prices nothing
and enrols nobody.` The last of those says, above the panel, what the drawn
consequence says below it.

---

## CONTRADICTIONS INSIDE THE BLUEPRINT — recorded, not resolved

1. **THE FRAME IS AN EDIT DOOR UNDER A CREATE KICKER.** `NEW DISCOUNT` above,
   `SAVING AS V3` and `Save new version` below. B14 rule 37 settles the figures;
   the door is not a figure. **Reading: pages 65–75 draw the shape of the
   wizard, illustrated with an edit door's content.** Both STATES rows here are
   written for the create door and are consistent with that reading.

2. **`Save draft & exit`** — see `CR-087-p065` CONTRADICTIONS §2.

---

## WHAT NEEDS THE PRODUCT OWNER

* **§1 — how the draft value is displayed** beside the stored one without the
  client formatting a percentage. `B4`/`B5` exposure: a discount value is what a
  customer is charged.
* **§3 — `Submit for approval` and `Activate`.** The drawing removes two
  controls the product deliberately draws under `BR-SHL-025`. Two signed
  positions, one screen.

## WHAT COULD NOT BE VERIFIED WITHOUT THE APP RUNNING

* Whether the drawn `CHANGE` column's accent monospace is a token or a
  wireframe convention — no rendered comparison table exists to diff against.
* Whether the eight-row `<dl>` reads as two columns or one at 1280.

---

## FIXED 2026-09-10 — the review step reads back the draft

**§1 · THE VALUE ROW READS BACK THE DRAFT — FIXED. This was the single most
consequential finding in pages 65–84 and it was present tense at 2.234.19.**
`reviewValueLine()` now returns what is about to be SAVED — the draft, as typed
— and, on the edit door only, what it replaces. A clerk taking SENIOR from 10%
to 15% reads `15` back, not `10.00%`. `DEF-RAT-4834`.

⚠ **THE FIX IS NOT `print(draft.value)`, WHICH THIS FILE WARNED ABOUT.** The two
figures are not the same kind of string — the draft is KEYSTROKES and the stored
one is a SERVED display (`BR-RAT-087` / `DEF-364`) — so they are drawn as two
labelled facts (*as typed* · *In force now*) rather than as one column a reader
would compare digit by digit.

⚠ **THE DRAWN `CHANGE` COLUMN IS NOT BUILT AND MUST NOT BE.** `+5 points` is a
subtraction of two figures the client may not own. **It needs a served figure**,
and that is what this file already asks the PO for.

**§2 · THE COMPARISON TABLE IS STILL NOT BUILT.** `OldNewTable` does not exist,
and building it means building the CHANGE column above. The two labelled facts
are the honest subset that needs no arithmetic.

**§§3, 4, 5, 6 · NOT BUILT.** The two disabled lifecycle buttons stay (two signed
positions, one screen — this file asks the PO); the hand-rolled consequence
stays, and **the reason it stays is a collision rather than a disagreement**: the
kit piece it needs, `AccentBand`, was added to `components/TextBits.tsx` by a
sibling lane on 2026-09-10 and **is not on the branch**, and `DefinitionDetailPage
.tsx` carries `+284/−9` of that lane's uncommitted work. Composing a symbol that
is not on the branch is hard-won law 2 wearing a fix's clothes. **One commit's
work once `AccentBand` lands.**

⚠ **ONE OF THE FOUR SPELLINGS §4 NAMES IS GONE ALTOGETHER** — step 4's
`SECOND APPROVAL — OPEN` panel, deleted by the PO ruling recorded in
`CR-087-p072`. Three remain.
