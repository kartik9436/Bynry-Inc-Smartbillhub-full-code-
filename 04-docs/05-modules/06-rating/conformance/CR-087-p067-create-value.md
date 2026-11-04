# DIS-02 step 2 · Create · Value — THE DRAWN SPEC, AND WHAT IS BUILT

Blueprint screen **22**, `/:tenant/plans-rates/discounts/new` · **blueprint
pages 67–69**, frame drawn on **pages 67–68**.

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`
(md5 `2e46f5053ca65804da9c1a90a487e044`), text **and** rendered PNGs at 2.0.

**State chip:** `NEW READ` · **Commitments:** `NO COMMITMENT`

**Re-verified at 2.234.19** (blueprint read at 2.232.0 / d2d493e4).

**Code read:** `DiscountWizard.tsx` — `ValueStep`, lines **1050–1316**;
`MoneyField` **1320–1344**.

---

## 1 · Header, actions, rail

Identical to step 1 (`NEW DISCOUNT` · `Define an overlay.` · the five-step
sub-line · `Cancel` · `Save draft & exit`), with `2 Value` active.

## 2 · The one panel — heading `The reduction`

Section sentence, verbatim, **one sentence**:

> `The type decides the unit; the scope decides what the reduction is taken from.`

## 3 · Controls, in the drawn order

| # | label | control | drawn value / note |
|---|---|---|---|
| 1 | `PERCENTAGE POINTS` * | numeric text | `10` |
| — | *(read-back)* | inline accent line under the box | `10 is a 10% reduction — points, not a fraction.` |
| 2 | `APPLIES TO` | dropdown | `Subtotal before taxes` |
| 3 | `CAP PER BILL` | money | *(empty)* |
| 4 | `CAP PER YEAR` | money | *(empty)* |
| 5 | `LIFETIME CAP` | money | *(empty)* |
| 6 | `BILL FLOOR` | money | *(empty)* |
| — | *(one line, under all four)* | note | `Blank means uncapped. Zero on the floor means this programme may take a bill to nothing.` |
| 7 | `STACKING PRECEDENCE` | numeric text, help **above** the box | help `Lower runs first.` · value `1` |
| 8 | `BEFORE AND AFTER` | **stated absence** — label, `—`, one sentence | `A figure worked out here would not be the figure the bill uses.` |

⚠ **THE VALUE FIELD'S LABEL CHANGES WITH THE TYPE.** Page 68: *"percentage
points, amount off, units allowed free — so a clerk never has to translate."*

⚠ **THE CAPITALS WARNING BECOMES A READ-BACK.** Page 68, verbatim: *"Two
sentences in capitals telling a clerk what to type — `percentage POINTS, not a
fraction; charge codes and taxes store a fraction and discounts do not` — is a
rule to remember while typing. It is now a line under the box that reads back
what they actually typed: **10 is a 10% reduction.** Type 0.15 and it says
`0.15 is a 0.15% reduction`, which is wrong on the face of it and needs no rule
to spot."*

⚠ **ONE LINE FOR FOUR FIELDS.** Page 68: *"The four bounded fields shared one
distinction — blank against zero — and it was written under only one of them.
It is one line under all four."*

## 4 · Footer

`Continue`, right. **PRIMARY ACTION:** `Continue.`

## 5 · States — verbatim

| state | drawn behaviour |
|---|---|
| **Charge waiver** | *"No value box at all, and a sentence: a waiver removes the whole of whatever the scope selects."* |
| **Usage allowance** | *"Warned that an allowance is counted in the service's own unit, so it must apply to one service, and told to choose that scope above."* |
| **Named charge codes scope** | *"A checkbox list of priced codes; empty says none are priced on this tenant yet and where to add one."* |

## 6 · Components named by the drawing

`WizardFrame` `MoneyTextField` `SelectField` `InlineCheck` `CheckboxList`
`NamedAbsence`

## 7 · Rules, verbatim

*"Money shows two decimals and is stored to four; a percentage six. Colour is
never the only signal — every state carries its word. … Built in the shared
utility classes, adding nothing to a stylesheet."*

## 8 · Absences — drawn as absent

* **No `Caps` sub-heading** over the three cap boxes.
* **No `Currency` field** (correct — the drawn type is `percentage`).
* **No `May stack with other discounts` tick.**
* **No `Exclusivity group` field.**
* **No overlay sentence repeated here** — page 66 makes it step 1's only
  sentence.
* **No `STEP 2 OF 5` kicker** and no step heading sentence.

---

## AS BUILT AT 2.234.19 — the diff, with evidence

### Matches

* Value label switches with the type — `valueUnitFor` + `valueLabel.percentage
  | .fixed_amount | .usage_allowance`, `:1093-1100`. **Exact.**
* A type with no value gets a sentence, not a box — `:1073-1091`
  (`valueNotUsed.charge_waiver` / `.rate_override`).
* The usage-allowance one-service warning — `:1170-1174`.
* The named-codes checkbox list, with the empty state — `:1210-1236`.
* All five scopes offered — `DISCOUNT_SCOPES`, `:1138-1151`.
* Blank stays blank and is never sent as zero (`BR-RAT-075`) — asserted in
  `DiscountWizard.test.tsx:601`.
* The before/after absence is NAMED, not invented — `:1311-1314`.

### 1 · THE READ-BACK IS NOT BUILT — the capitals warning is still there

`:1120-1125` renders `valueHelp.percentage`:

> *"Percentage POINTS, not a fraction: type 15 for a fifteen percent reduction.
> Charge codes and taxes store a fraction and discounts do not."*

That is, word for word, the two-sentence rule page 68 says the redesign
replaces. **There is no `{{typed}} is a {{typed}}% reduction` key in any of the
eleven catalogues** (checked across all 11 files). `DiscountWizard.test.tsx:460`
asserts the *old* behaviour by name — *"the value help line names the convention
IN WORDS instead of rescuing it"* — so the suite is currently pinned to the
thing the drawing removes.

⚠ **This one is NOT blocked by `DEF-364`.** The drawn line is a literal echo of
the keystrokes with a `%` glyph — no division, no conversion, no money
arithmetic. `0.15` echoes as `0.15`, which is the whole point. Nothing about it
asks the client to compute a figure the server owns.

### 2 · The one blank-versus-zero line is four separate help lines

| drawn | built | evidence |
|---|---|---|
| one line under all four | `Caps` kicker + `Leave a cap blank for uncapped. Blank and zero are different facts: a cap of zero grants nothing at all.` | `:1243-1244` |
| — | `CAP PER BILL` help `Type the amount exactly as it should be stored. It is sent unchanged; the server checks the limits.` | `:1245`, default in `MoneyField:1341` |
| — | `CAP PER YEAR` — same default help | `:1252` |
| — | `LIFETIME CAP` — same default help | `:1259` |
| — | `BILL FLOOR` help `The lowest a bill may fall once this reduction is applied. Blank means no floor. Zero is a decision, not a blank — it says this programme may take a bill to nothing.` | `:1274` |

So the section the drawing gives **one** sentence carries **five**, three of
them the same sentence printed three times.

### 3 · Two controls the frame does not draw

* `:1292-1297` — `CheckboxField` **`May stack with other discounts`**.
* `:1298-1305` — `TextField` **`Exclusivity group`** with help
  *"Discounts in the same group cannot both apply. Leave it blank unless this
  programme excludes another."*

Both are real, saved fields. The frame draws neither and page 68's cognitive
load names neither. **The drawing does not state them as absent, it simply does
not draw them** — so this is an omission to confirm, not a deletion to make.

### 4 · Three more sentences the frame does not draw

| built | evidence |
|---|---|
| `Whatever is set here, the bill still prints the full tariff amount and this reduction as its own line.` | `:1134` (`overlayNote`) |
| `What the reduction is taken from. It never changes the rate itself.` under `APPLIES TO` | `:1147` (`scopeHelp`) |
| `Lower runs first. Order is DATA, not the order the code happens to run in: a percentage of usage taken after a usage allowance gives a different number than the reverse.` under `STACKING PRECEDENCE` | `:1289` (`precedenceHelp`) — the drawing keeps only the first three words |

### 5 · `BEFORE AND AFTER` is the wrong absence component and twice the words

Drawn: a label, an em-dash, one sentence — the shape `ArrivesWithField` renders
(`ratingShared.tsx:551-562`), and the shape the drawing uses again for
`STRUCTURED ELIGIBILITY RULE` on page 70.

Built `:1311-1314` uses `ArrivesWith` (`settingsShared.tsx:261-272`) — an `h3`
title over a paragraph — with `previewPending`:
*"The worked before-and-after example belongs here and cannot be shown yet:
nothing prices a discount that has not been saved, and a figure worked out on
this screen would not be the figure the bill uses."* The drawing keeps the
second clause only.

### 6 · Four panels where the drawing draws one

`:1073` · `:1137` · `:1242` · `:1279` are four `<Panel as="section">`. The frame
draws a single bordered panel headed `The reduction`.

### 7 · Recorded under B14 rule 38 — construction, not content

The frame puts `CAP PER BILL · CAP PER YEAR · LIFETIME CAP` **side by side in
one row** and `BILL FLOOR` on its own half-width row. B14 rule 38 names fields
sitting side by side as **form construction**, where the UI rules and the kit
win and the divergence is recorded rather than built. **Recorded. Not a defect.
Build nothing.**

⚠ **AND ONE THING THAT LOOKS LIKE A DIVERGENCE AND IS NOT.** The frame puts the
`Lower runs first.` help line **above** its input. So does the kit —
`components/FormModal.tsx:238-243` renders `field-help` between the label and
the control on every `TextField`. Drawing and kit agree; nothing to record.

---

## CONTRADICTIONS INSIDE THE BLUEPRINT — recorded, not resolved

1. **THE STATES BLOCK DESCRIBES A SCREEN THE FRAME DOES NOT DRAW.** The three
   states are `charge_waiver`, `usage_allowance` and the `named_codes` scope;
   the frame is drawn on `percentage` + `whole_bill`, which is none of them. Not
   a conflict — recorded so a lane does not read the frame as the only shape.

2. **`Save draft & exit`** — see `CR-087-p065` CONTRADICTIONS §2. Same button,
   same frame, same standing question.

---

## WHAT NEEDS THE PRODUCT OWNER

* **§3 — `May stack with other discounts` and `Exclusivity group`.** The drawing
  neither draws them nor states them absent. Deleting two saved fields on the
  strength of an omission is not a lane's call.

## WHAT COULD NOT BE VERIFIED WITHOUT THE APP RUNNING

* Whether the read-back line, once built, would fit on one line at 1280 in the
  longer catalogues.
* The rendered spacing of five help lines stacked inside the caps panel.

---

## FIXED 2026-09-10 — the read-back is built

**§1 · THE READ-BACK IS BUILT AND THE CAPITALS RULE IS OFF THE SCREEN.**
`{{typed}} is a {{typed}}% reduction — points, not a fraction.` in all eleven
catalogues, rendered under the value box only once something is typed. It is a
literal echo — `0.15` reads back `0.15 is a 0.15% reduction`, which is wrong on
its face, which is page 68's whole argument. `valueHelpKey()` returns null for
`percentage`, so the two-sentence rule the drawing removes is not rendered
anywhere; the key stays in the eleven catalogues because deleting one is a
parity change across eleven shared files and buys nothing on screen.

⚠ **PERCENTAGE ONLY, AND THE OTHER TWO UNITS ARE A STATED ABSENCE.** Money would
need a formatted figure, which `DEF-364` reserves to the server, and a usage
allowance takes its unit from the service it is attached to (`BR-RAT-960`),
which this box does not know. Both keep the help lines they had.

⚠ **THE DRAWN LINE IS AN *inline accent line* AND IS BUILT AS THE KIT'S `Note`
(grey).** B14 rule 36 gives the visual style to `r10` and the kit, and the kit's
caption-under-a-field is `Note`. **Divergence recorded, nothing built for it.**

**§3 · THE SCOPE GAINED A PAIR — `CR-091-BRC01`.** The frame draws a SINGLE
service; the PO ruled on 2026-09-10 that a discount takes one or more. **The
drawing is now behind the ruling** and `All services` / `Specific services` join
the scope, the second opening the kit's `ChipMultiSelect`. See `BR-RAT-963`.

**§§2, 4, 5, 6 · NOT BUILT.** The five help lines, the three undrawn sentences,
the `ArrivesWith`-vs-`ArrivesWithField` shape and the four-panels-for-one all
stand — a copy and layout sweep this wave did not take.
