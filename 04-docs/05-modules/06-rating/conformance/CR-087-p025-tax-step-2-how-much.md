# 08 · Create · Step 2 · How much — THE DRAWN SPEC, AND WHAT THE PRODUCT DOES

`S13 · TAX-02` · route `/:tenant/plans-rates/taxes-fees/new` · **blueprint pages
25–27** (heading at the foot of 25, frame drawn on **25–26**, specified on 26–27).

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, read as
RENDERED pages — the frame's second card and its three fields are drawn and the
text extraction printed them after the commentary.

**State chip:** `NEW READ` **Commitment:** `NO COMMITMENT`

⚠ **`NEW READ` means the screen exists and something on it has no read; `NO
COMMITMENT` means nobody has undertaken to build any of it. Per the blueprint's
own legend (page 2), that absence *"is the finding, not an oversight."***

**Re-verify:** as-built claims here were true at **2.232.0**; we are on
**2.234.19**.

---

## 1 · The frame is the same shell as step 1

Kicker `NEW TAX OR FEE` · title `Add a tax, franchise fee, or surcharge.` ·
sub-line `Three steps · takes about 2 minutes. Filing details are added later, on
the tax itself.` · `Cancel` and `Save draft & exit` top-right · rail with
`2 How much` active.

## 2 · Card `The rate` — five slots, in this order

| # | label | drawn value | note under it |
|---|---|---|---|
| 1 | `HOW IT IS WORKED OUT` ✱ | `A percentage of the bill` *(select)* | — |
| 2 | `RATE` | `0.0625` | **`0.0625 is 6.25%.`** *(accent echo, directly under the box)* |
| 3 | `WHAT IS TAXED` | ☑ `Usage charges`  ☑ `Base service charges` | — |
| 4 | `DISCOUNTS` ✱ | `Taxed after the discount — the discount comes off first` *(select)* | `On a bill with a $1.00 credit, this 2% tax comes to $3.78 after the discount and $3.80 before it.` |

⚠ **THE ECHO IS THE FIX, AND THE BLUEPRINT ARGUES IT.** Page 27, verbatim:
*"`Stored as a fraction, so 6.25% is written 0.0625` was a sentence telling a
clerk what to do. It is now a line under the box that reads back what they did:
`0.0625 is 6.25%.` A scale typed wrong is invisible in a fraction and obvious in a
percentage."*

⚠ **THE WORKED EXAMPLE IS ONE SENTENCE AND SITS DIRECTLY UNDER THE SELECT.**
Page 27: *"Kept, and it is the design. Two sentences of rule cannot be checked;
`$3.78 against $3.80` can."* ⚠ **`$3.78` / `$3.80` / `2%` / `$1.00` ARE MONEY
FIGURES — see §6.**

## 3 · Card `From when` — three slots, in this order

| # | label | drawn value | note under it |
|---|---|---|---|
| 1 | `EFFECTIVE FROM` ✱ | `06/01/2026` *(date input with calendar affordance)* | — |
| 2 | `ROUNDING REQUIRED BY THE AUTHORITY` | `Standard rounding (half up)` *(select)* | — |
| 3 | `COMPOUNDING ORDER` | `—` *(absent style)* | `Nothing stores an order today, so every tax is worked out on the same base and no loop can be drawn.` |

## 4 · Footer — `Continue`, alone, right-aligned

## 5 · States — the blueprint's own block, verbatim

| state | drawn behaviour |
|---|---|
| **A percentage** | *"A rate box, its percentage echo, and the two basis ticks."* |
| **A fixed amount per bill** | *"An amount and a frequency; the basis ticks are absent, because there is no base to take a percentage of."* |
| **An amount per unit** | *"An amount, a unit that must be stated explicitly and is never guessed from the service, and an optional threshold."* |
| **Rounding set** | *"A note appears saying it is recorded only and bills still use standard rounding — the setting does not change arithmetic yet."* |

## 6 · Cognitive load, as stated

*"The rate box and the basis tick-boxes change with the method above them: a
per-meter tax shows no unit field at all, because a meter is counted, not
measured."*

## 7 · Components named in the frame

`WizardFrame` `SelectField` `MoneyTextField` `CheckboxGroup` `InlineCheck`
`WorkedExample` `NamedAbsence`

## 8 · Absences — drawn as absent, do not fill them

* **No `EFFECTIVE TO`.** `From when` holds one date.
* **No exemption-categories sentence.**
* **No `Statutory settings` card** — rounding and compounding are inside
  `From when`, and discounts is inside `The rate`.
* **No step kicker, no step heading, no helper paragraph.**
* **No `Applies above` field** in the percentage state (it belongs to
  *An amount per unit*, per §5).

---

## 9 · WHAT THE PRODUCT DOES — file and line evidence

All from `07-frontend/src/features/rating/TaxWizard.tsx` at `2.234.19`.

| # | drawn | built? | evidence |
|---|---|---|---|
| 1 | `HOW IT IS WORKED OUT` ✱ | ✅ | `rating.taxes.kindLabel = "How it is worked out"` — line 1214 |
| 2 | value `A percentage of the bill` | ✅ | `rating.taxes.kind.percent` |
| 3 | `RATE` | ✅ | `rating.taxes.rateLabel = "Rate"` — line 1228 |
| 4 | **the echo `0.0625 is 6.25%.`** | ❌ **NOT BUILT** | the field renders `help={t("rating.taxes.rateHelp")}` — line 1236 — whose value is **`"Stored as a fraction, so 6.25% is written 0.0625."`**, the exact sentence page 27 says was replaced. No echo key exists in any of the eleven catalogues ⟨grepped⟩ |
| 5 | `WHAT IS TAXED` + two ticks | ✅ | `rating.taxes.baseLabel`, `baseUsage`, `baseBase` — lines 1245-1258 |
| 6 | no prose under the ticks | ❌ | `<Note>{t("rating.taxes.baseHelp")}</Note>` — line 1261 — *"Only these two can be taxed. Fees, late charges and other taxes are never part of the base, so there is nothing else to choose."* |
| 7 | `DISCOUNTS` inside `The rate`, under the ticks | ❌ | it is in a **third card** — line 1398, inside the `Statutory settings` panel opened at line 1383 |
| 8 | option label `Taxed after the discount — the discount comes off first` | ❌ | reads `rating.taxWiz.discountTreatment.before = "Taxed after discounts (discount applies first)"` |
| 9 | the worked example as ONE sentence directly under the select | ⚠ | `rating.taxWiz.discountTreatment.help` is **two** sentences and the first is rationale: *"This is set by the authority's own rules, so it differs between them."* The **figures agree** — `$1.00`, `2%`, `$3.78`, `$3.80` |
| 10 | card `From when` | ✅ | `rating.taxWiz.effective.title = "From when"` — line 1362 |
| 11 | `EFFECTIVE FROM` ✱, date picker | ✅ | `DatePickerField` — lines 1364-1371 |
| 12 | no `EFFECTIVE TO` on this step | ❌ | a second `DatePickerField` for `effective_to` — lines 1372-1379 |
| 13 | `ROUNDING…` inside `From when` | ❌ | it is in `Statutory settings` — line 1412 |
| 14 | `COMPOUNDING ORDER` inside `From when`, one sentence | ❌ | rendered by `ArrivesWith` in `Statutory settings` — lines 1438-1441 — with a **two-sentence** message; the drawing keeps only the second (*"Nothing stores an order today…"*) |
| 15 | no `Statutory settings` card | ❌ | `rating.taxWiz.statutory.title = "Statutory settings"` — line 1383 |
| 16 | no exemptions sentence | ❌ | `<Note>{t("rating.taxWiz.exemptions.built")}</Note>` — line 1433 |
| 17 | state *Rounding set* says recorded-only | ✅ | `rating.taxWiz.rounding.notHonoured` — line 1430, rendered only when a rule is chosen |
| 18 | state *A fixed amount per bill* drops the basis ticks | ✅ | `taxFieldsFor` — line 213; the ticks are inside `fields.percent` — line 1225 |
| 19 | state *An amount per unit* requires an explicit unit | ✅ | `perUnitUomLabel` + `perUnitUomHelp` — lines 1327-1334 |
| 20 | `Continue` alone in the footer | ❌ (B14 rule 38) | shared footer, see the step-1 file §11 |

### The blueprint's *"What was wrong"* for this screen, re-verified ⟨important⟩

Page 25: *"The two options for how a discount interacts with tax were labelled the
opposite way round from the values they stored."* **At `2.234.19` they are NOT.**
`rating.taxWiz.discountTreatment.before` reads *"Taxed after discounts (discount
applies first)"*, which is what `06-backend/apps/rating/selectors.py`'s
`taxable_subtotal_for` documents `before` to mean — the word names where the
DISCOUNT goes. The decision log of 2026-09-08 records exactly this finding and
says it was *"flagged for the integrator rather than silently 'corrected' on a
money-adjacent label."* **Either it was fixed after the drawing was made, or the
drawing read it wrong. Do not re-word this label on the strength of the drawing.**

### Catalogue parity ⟨verified⟩

Every key on this step exists in all eleven locales.

---

## 10 · ❄️ FROZEN / MONEY — REPORTED, NOT TOUCHED

* **The `$3.78` vs `$3.80` worked pair** is the only figure a clerk checks their
  statutory choice against. It is identical in the drawing and in
  `rating.taxWiz.discountTreatment.help`, so nothing is in conflict — but it is a
  worked money example and `B4`/`B5` govern the arithmetic behind it. **No change
  proposed.**
* **`ROUNDING REQUIRED BY THE AUTHORITY` is stored and NOT honoured.** B4's money
  rounding is ❄️ FROZEN and `OQ-309` is the open sign-off. The drawing shows the
  control with no caveat on the field itself; the product shows
  `rating.taxWiz.rounding.notHonoured` when a rule is chosen. **The product is
  more honest than the drawing here and must stay that way.**

## 11 · B14 rule 38 divergences — RECORDED, NOT BUILT

1. **`Continue` alone in the footer** — same as step 1 §11.
2. **`WHAT IS TAXED` drawn as two inline ticks with no help.** B14 rule 9 governs
   MULTI-SELECT (chips, never a wall of checkboxes); two ticks is not a wall and
   the kit's `CheckboxField` is the right piece. **No divergence — the drawing and
   the kit agree.**

## 12 · WHERE THE DRAWING CONTRADICTS A SIGNED RULE — FOR THE PRODUCT OWNER

1. **`DISCOUNTS` IS DRAWN WITH A REQUIRED ASTERISK AND `EFFECTIVE FROM` TOO.**
   `rating.taxWiz.discountTreatment` has a stored default and `effective_from` is
   optional in the product — a tax with no `effective_from` *"has never been in
   force"* (`TaxWizard.tsx:258-270`, `taxIsInForce`), which is the whole basis of
   the in-place-edit refusal. Making `effective_from` required would remove that
   state. **B14 rule 10 puts the asterisk on required fields, so the drawing is
   asserting a requirement change. One sentence to the PO.**

## 13 · THE BLUEPRINT AGAINST ITSELF

1. **`NEW READ` with `NO COMMITMENT`.** The chip says something on this screen has
   no read; every field on it is served today and the only genuinely absent thing
   is the compounding column (`DEF-381`, **deferred by the PO** 2026-08-21 —
   *"stacking later — because that one needs care to avoid a tax that taxes
   itself in a circle"*). Read against the legend, `NEW READ` here is really
   *"one named absence, already ruled"*. Recorded; nothing resolved.

## 14 · NOT VERIFIABLE WITHOUT THE APP RUNNING

* Whether the three non-percentage states actually swap the field set on a live
  click (`taxFieldsFor` is pure and unit-tested; the swap is not).
* The date picker's calendar affordance, keyed entry and Today shortcut (B14
  rule 7).

---

## 15 · WHAT CHANGED ON THIS STEP — 2026-09-10, the CR-087 tax-screens lane

**One change, and it belongs to the correction door** (`p030` §16.1). On a tax
that is IN FORCE the two `From when` dates are rendered **disabled**, with the
sentence *"A correction keeps these dates."* under each.

`correct_tax` copies `effective_from` and `effective_to` off the row being
corrected and IGNORES whatever the payload carries, because *"a 'correction'
that moved the window would be a rate change wearing a correction's clothes, and
it would silently rewrite which bills the old figure was ever right for"*
(BR-RAT-104). A live box whose typing the server discards is the silent-discard
shape, so the fields are SHOWN — a clerk filing a correction has to read the
window they are restating — and disabled WITH the reason (BR-SHL-025).
`taxCorrectionChanges` drops both keys from the body explicitly rather than by
luck.

**`DatePickerField` gained an opt-in `disabled?: boolean`** to make that
possible — the same prop `TextField` has carried since the kit was written.
Absent means editable, so every existing date field renders byte-for-byte what
it rendered before (B14 rule 38: *"ADD IT TO THE KIT as an opt-in, so nothing
existing moves"*).

**§9 findings 4, 6, 7, 8, 12, 13, 14, 15, 16 and 20 are UNCHANGED** — the
percentage echo, the `Statutory settings` card, `EFFECTIVE TO`'s presence and
the prose the drawing deletes are all still as this file records them. Nothing
in §10's ❄️ FROZEN / MONEY section was touched, and `ROUNDING REQUIRED BY THE
AUTHORITY` still says on screen that it is recorded and not honoured — the
product is more honest than the drawing there and stays that way (`OQ-309`).
