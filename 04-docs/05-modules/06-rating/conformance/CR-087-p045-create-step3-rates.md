# 15 · Rate schedule → Create · Step 3 · Rates — THE DRAWN SPEC

`S11 · RAT-03` · route `/:tenant/plans-rates/rates/:id/edit` · **blueprint pages 45–48**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, section opening
on page 45, **frame drawn across pages 45–46**, specified on 46–48. Read as
RENDERED pages — the tier table's single header row, the inline red contiguity
message under `+ Add tier`, and the `HELD` chip beside `Price a size differently`
are visible only as a picture.

**State chip:** `BLOCKED`
**Commitment:** `PRB-10` — *"Per-size block prices are billed, or the section goes"*,
which page 64 marks **⚠ NOBODY HAS RULED THIS**. Screens `15` · `16`.

**Masthead warning, applied.** As-built lines were true at **2.232.0**; we are on
**2.234.19**.

---

## 1 · Header, step rail, footer

The wizard frame, unchanged, with **`3 Rates` active** — and the rail's third word
is `Rates`, not `Pricing formula`. Footer: `Continue`, right-aligned.

## 2 · The panel — `Rates`

**Heading:** `Rates`
**Hint, verbatim:** `Blocks of usage, each with its own price. Every unit is priced through the tiers.`

## 3 · `STRUCTURE` — one select, first in the panel

| slot | drawn |
|---|---|
| label | `STRUCTURE` |
| help | `One structure per schedule. Changing it replaces the numbers below.` |
| value | `Tiered` |

## 4 · The tier table — THREE columns and a row action

| # | header | content |
|---|---|---|
| 1 | `FROM` | narrow numeric input — `0` · `2` · `10` |
| 2 | `TO` | wide numeric input — `2` · `10` · *(blank on the last row)* |
| 3 | `RATE` | numeric input — `4.4096` · `7.1656` · `8.8192` |
| — | *(no header)* | `Remove`, an accent-coloured text link |

**One help line, under the LAST row's `TO` box only:**
`Blank on the last row means no upper limit.`

**Under the table:** `+ Add tier`, a secondary button.

**Under that:** an inline red refusal, accent-ruled, naming the two tiers and the
two numbers:

> `Tier 2 starts at 2 and tier 1 ends at 3. Tiers must run on from one another`
> `with no gap and no overlap.`

⚠ **B14 rule 37 — `0/2/10`, `4.4096/7.1656/8.8192` and the `2`/`3` in the refusal
are ILLUSTRATIONS.** What the frame specifies is that the refusal **names the two
tiers and the two numbers**, so the fix is visible without re-reading the table.

## 5 · `Sizes that price these blocks differently` — a second panel

| slot | drawn |
|---|---|
| heading | `Sizes that price these blocks differently` |
| hint | `Awaiting your decision — see the note beside this screen.` |
| callout | `NOT BILLED YET` — *"Per-size block prices are recorded and bills do not read them yet — every size is billed at the standard block prices above. Until the engine reads them, adding one changes nothing on a bill."* |
| control | `Price a size differently` — a button with a quiet `HELD` chip beside it, **disabled** |

⚠ **THIS IS THE DRAWN HALF OF AN UNRULED DECISION.** Page 47, verbatim: *"Drawn
here as the safer of your two options: the section stays, states plainly that it
is not billed yet, and the control is held. **The other option is to remove it
until the engine reads it.** Holding keeps a signed requirement visible; removing
stops a clerk recording a price that does nothing."* **Do not build either half
without the ruling.**

## 6 · States — verbatim

| state | drawn behaviour |
|---|---|
| **Seasonal** | *"A red banner first: it can be built and saved and a bill run will refuse it by name, because a period crossing a season boundary has an unsigned rule. Said before the fields, not after."* |
| **Demand** | *"The ratchet and power-factor options are off by default and say a bill run refuses a schedule with either ticked — billing the raw peak instead would undercharge every bill with nothing on the document to show it."* |
| **Base only** | *"Offered and permanently disabled: it is part of the agreed set and nothing prices it."* |
| **Time-of-use** | *"Each window must name the meter register it bills from, so a bill never has to guess."* |

## 7 · Components named in the frame

`WizardFrame` `SelectField` `TierTable` `InlineCheck` `Callout accent` `HeldButton`

## 8 · FOR · HOW YOU GET HERE · PRIMARY ACTION · COGNITIVE LOAD

* **FOR** — *"The clerk entering the numbers a council or a board approved."*
* **HOW YOU GET HERE** — *"Continue from Base rates."*
* **PRIMARY ACTION** — `Continue.`
* **COGNITIVE LOAD** — *"One structure, one table. The editor changes completely with the structure above it, so a clerk never sees a field belonging to a shape they did not pick."*

## 9 · The RULES line, which has an extra clause on this screen

*"… A control that changes nothing on a bill says so on itself, **not in small
print underneath**."*

---

# THE DIFF — drawing against the code at 2.234.19

Code: `RateScheduleWizard.tsx` — `StructureStep` **1636**, `TierEditor` **1766**,
`SizeTierOverrides` **1881**.

## D1 · THE STEP IS STILL CALLED `Pricing formula`, IN ALL THREE PLACES THE RENAME NAMES

`rating.rate.step.structure` = **`Pricing formula`** in `en.json` and in all eleven
catalogues (`Preisformel` · `Fórmula de preços` · `価格計算式` · `मूल्य-सूत्र` · …).
It is read in exactly the three places page 46 names:

| place | line |
|---|---|
| the step rail | `RateScheduleWizard.tsx:836` (`RATE_WIZARD_STEPS`, rendered at `:1122-1126`) |
| the panel heading | `RateScheduleWizard.tsx:1647` — `<Panel title={t("rating.rate.step.structure")} …>` |
| the review summary | not read there today; the review's own labels are listed in `CR-087-p051-create-step5-review-activate.md` |

Page 46: *"a step a clerk repeats down the phone should be the word they would
use."*

## D2 · THE PANEL HINT IS THE WRONG SENTENCE, AND THE RIGHT ONE IS ONE PANEL LOWER

**Drawn:** panel `Rates`, hint *"Blocks of usage, each with its own price. Every
unit is priced through the tiers."*

**Built:** two panels, and the hint the drawing wants is on the inner one.

`RateScheduleWizard.tsx:1647` — `<Panel title="Pricing formula" hint={t("rating.rate.structure.hint")}>`, where `rating.rate.structure.hint` = *"Pick the shape of the formula, then fill in its numbers."*
`RateScheduleWizard.tsx:1779` — `<Panel title={t("rating.model.tiered")} hint={t("rating.rate.tiers.hint")}>`, where `rating.rate.tiers.hint` = *"Blocks of usage, each with its own price. Every unit is priced through the tiers."* — **the drawn sentence, verbatim, on the wrong panel.**

**The drawing has ONE panel where the code has TWO nested ones**, and the inner
one is titled with the structure's own name (`Tiered`). B14 rule 32 clause 3 —
*"a row never repeats what its own control offers"* — is the same objection: the
select says `Tiered` and the panel beneath it says `Tiered` again.

## D3 · CONTIGUITY, INVERSION AND THE OPEN MIDDLE TIER ARE SERVER-ONLY, AND THE MESSAGE NAMES NEITHER TIER NOR NUMBER

**Drawn:** all three checked **here, where the numbers are typed**, with a message
naming the two tiers and the two numbers.

**Built:** the file's own header states the opposite as a design decision —
`RateScheduleWizard.tsx:29-37`:

> *"**The server owns every rule.** Tier contiguity, "only the last tier may be
> open-ended", 24-hour window coverage, ≤ 3 windows, season coverage, rate ≥ 0,
> percent > 0, and "activation needs a date" are all validated by the backend …
> This file therefore performs NO money validation of its own — Activate is
> pressable with an empty date precisely so the server's refusal is what the user
> reads. The only client-side checks are SHAPE (is this text a decimal at all) and
> PRESENCE."*

The refusal that arrives is `rating.tiers.not_contiguous` = *"Tiers must run on
from one another with no gap: each tier starts where the one before it ends."* —
**no tier numbers, no figures**, and it lands on the last step rather than under
the table. The other two are `rating.tiers.inverted` (*"A tier has to end above
where it starts."*) and `rating.tiers.open_middle_tier` (*"Only the last tier can
be left open-ended."*), both equally general.

⚠ **THIS IS A REAL TENSION AND IT NEEDS A DECISION, NOT A LANE'S PREFERENCE.** The
"server owns every rule" position is not a shortcut — it exists so one rule is not
written twice — and the drawing is asking for the CHECK to be shown early, not for
the rule to move. The reconcilable reading, offered rather than taken: keep the
server authoritative, and either (a) surface its field error against
`structure.tiers` **on this step** instead of at commit, or (b) send tier indices
and quantities as params so the sentence can name them. **Recorded for the PO;
nothing built.**

### ✅ RESOLVED 2026-09-17 BY THE PO — BOTH (a) AND (b) (`DEF-RAT-5717`)

**The PO answered this in the beta without being asked it as a question**, which
is how the tension above was meant to be settled:

> *"in tied rates - if tier 1 start from 0 to 100 and tier 2 start from 101 to
> 300 ; then it give error - tier 2 should start from 100"*

That is **(b)** in the PO's own words — *tell me which tier and which number* —
and the blueprint p047 asks for **(a)** in the same breath: *"Contiguity,
inverted tiers and an open middle tier are checked here, where the numbers are
typed. All three were server refusals discovered on the last step."*

**BOTH ARE BUILT AND THE SERVER STILL OWNS THE RULE.** `services` now sends
`tier`, `previous`, `starts` and `expected`; the sentence is
`Start tier {{tier}} at {{expected}}. Tier {{previous}} ends there.` and it is
the **same catalogue key** the server raises, so the screen and the server cannot
say different things. `tierGapAt` computes the same arithmetic on this step so
the message appears under the box it is about — it is a PREVIEW of the server's
refusal, not a second copy of the rule: the server still refuses, and a ladder
this check is silent about is still refused by the server if it is wrong.

⚠ **AND ONE DIVERGENCE FROM THE DRAWING, FILED RATHER THAN FOLLOWED.** p046
draws the sentence as *"Tier 2 starts at 2 and tier 1 ends at 3. Tiers must run
on from one another with no gap and no overlap."* — **10 words then 13**, where
B14 rule 33 caps an instruction at **six words per sentence** and puts the rule
itself (*why* the blocks must run on) at **zero words on screen**. The UI rules
win where they disagree with a drawing about construction, so the built sentence
is two sentences of five and four that name the same two tiers and the same two
numbers. The drawing is right about WHAT to say and is over the cap in HOW.

## D4 · THE `TO` HELP LINE IS ON EVERY ROW, NOT ONLY THE LAST

`RateScheduleWizard.tsx:1802`

```tsx
            help={t("rating.tier.toHelp")}
```

sits inside `draft.tiers.map(...)`, so `Leave blank on the last row for no upper
limit.` prints under **every** `TO` box. The drawing prints it once, under the
last one, and words it `Blank on the last row means no upper limit.`

**B14 rule 32**, clause 3 — the repeated sentence is exactly what the rule bans.

### ✅ CLOSED 2026-09-22 — `DEF-RAT-6164`, in `2.327.1`

⚠ **AND THE PART THIS ENTRY DID NOT KNOW: THE REPEATED SENTENCE WAS ALSO THE
MISALIGNED ROW.** `help` renders INSIDE the field's box, so `To` measured
**103px** where `From` and `Rate` measured **60px**; `.rating-tier-row` is a
grid on `align-items: end`, which bottom-aligns the BOXES, so the taller box
carried its input **43px** above its neighbours — on every row. Measured in
Chromium at 1440 before the fix: `FROM 642 · TO 599 · RATE 642 · REMOVE 644`,
a 45px spread. After: **1px**.

**The Product Owner reported the two halves as two separate faults** — *"align
all input field in one row"* and *"'Leave blank on the last row for no upper
limit.' This text is reapeted"* — and they were one prop.

**What was built, and where it diverges from the drawing.** The sentence is
written ONCE after the last row and pointed at from the last row's `To` through
a new opt-in `describedBy` on the kit's `TextField`. The drawing puts it
*inside* the last row, under that `To` box; **that placement is what makes the
box taller, so it is exactly the construction B14 rule 38 hands to the UI
rules** — and the PO's own instruction to align the row is the ruling. A second
reason it could not be followed literally: at 390 the row's `auto-fit` grid
collapses to one column, so a sentence offset to the `To` column would start an
implicit column and scroll the page sideways.

**The wording moved too.** The drawing's `Blank on the last row means no upper
limit.` is nine words in one sentence where B14 rule 33 caps an instruction at
**six per sentence**; built as `Leave the last To blank. That block has no upper
limit.` — five and six. **This is D3's finding a second time: the drawing is
right about WHAT to say and over the cap in HOW.** ⚠ No gate reads it — `G33`
walks REFUSAL keys only and `G129` walks `metering.premises*`/`metering.units*`
— so the cap is asserted in the test below or nowhere.

**And it never became a check, which is why a beta user found it.** This
divergence was recorded here the day this file was written, and the screen went
on printing the sentence six times on a six-block ladder for days. The check now
exists: `07-frontend/src/features/rating/tierLadderOneSentence.dom.test.tsx`
(10 cases, 7 of them shown RED against the pre-fix source) and
`10-scripts/def_rat_6164_tier_row_walkthrough.mjs`, which measures the baseline
in a browser because jsdom has no layout and nothing else here reads rendered
output.

**One more thing the same fix carried, also reported by the PO as *"UI breaking
at bottom"*:** `+ Add tier` measured **1088px**, the full width of its panel,
because `Panel` is a column flex container and a `Button` that is its direct
child stretches. It read as an empty input rather than a button. Wrapped, it is
**111px** — and the drawing on p046 draws exactly that, a small button under the
table.

## D5 · THE TIER EDITOR IS NOT A TABLE — three labelled fields per row, no header row

`RateScheduleWizard.tsx:1779-1830` renders each tier as a
`<div className="rating-tier-row">` holding three `TextField`/`MoneyTextField`
controls, each carrying its own visible label (`rating.tier.from` = `From`,
`rating.tier.to` = `To`, `rating.tier.rate` = `Rate`).

The drawing draws **one header row** (`FROM` · `TO` · `RATE`) above three
unlabelled input rows. That is a per-row label repeated N times against a header
stated once — the same shape as D4.

⚠ **B14 rule 38 — this is FORM CONSTRUCTION and the UI rules win.** A labelled
input is what the kit gives and what a screen reader needs; a bare input under a
column header needs the header wired as its accessible name. **The divergence is
RECORDED and nothing is built for it** — but note the drawing is still right about
what the row CONTAINS and in what order, and about the `Remove` action's position.

## D6 · `Remove tier` vs `Remove`

`rating.tier.remove` = `Remove tier`; the frame draws `Remove`. `rating.tier.add`
= `+ Add tier` ✔ matches, including the `+` (B14 rule 4).

## D7 · THE PER-SIZE SECTION IS LIVE WHERE THE DRAWING HOLDS IT

| | drawn | built (`SizeTierOverrides`, `RateScheduleWizard.tsx:1881`) |
|---|---|---|
| heading | `Sizes that price these blocks differently` | `rating.rate.sizeTiers.heading` — **matches** |
| hint | `Awaiting your decision — see the note beside this screen.` | `rating.rate.sizeTiers.hint` = *"Add a size only when its block prices differ from the standard ones."* |
| the warning | an accent `NOT BILLED YET` callout **above** the control | a plain `Note` **below** it, `RateScheduleWizard.tsx:1967` |
| the control | ONE button `Price a size differently`, **disabled**, with a `HELD` chip | one button PER available size, live — `rating.rate.sizeTiers.add` = *"Price {{size}} differently"*, `RateScheduleWizard.tsx:1960-1964` |
| what it does | nothing | adds an override **seeded from the base ladder** (`addOverride`, `:1894-1900`) |

The warning that IS built is well-worded — `rating.tiers.size_override_not_billed`
= *"Block prices set for a single connection size are saved, and bills do not use
them yet — every size is still billed at the standard block prices."* — and it is
the one place in this module that already obeys the RULES line in §9. Its position
is the divergence: **under** the control rather than before it, which is the
*"not in small print underneath"* clause.

**Page 47 names the exact hazard the built version has:** *"adding a size copied
the standard prices in, so a clerk who changed nothing still saved an override."*
That is `addOverride`'s seed, and the file's own docstring at `:1867-1873`
defends it on a different ground (the server refuses a half-filled ladder). **Both
readings are true and they point opposite ways. PO decision, PRB-10.**

---

## ABSENTED BY THE DRAWING — do not fill

* **No `Minimum` field is drawn on this panel** — but see the contradiction below.
* **No worked example**, no preview, no chart.
* **No per-size tier table** — only the held control.

## WHAT THE CODE HAS THAT THE DRAWING DOES NOT

* **`Minimum bill on this version`**, a money input at `RateScheduleWizard.tsx:1677-1684`.
* **A `MoreAbout` disclosure** holding `rating.rate.baseOnlyGap` and
  `rating.rate.baseNotEditableHere` (`:1663-1666`). B14 rule 32 makes a stated
  absence a closed `<details>`, so this is rule-compliant; the drawing simply does
  not draw it.
* **Six structure editors** the frame never shows (`flat`, `tou`, `seasonal`,
  `capacity`, `demand`, `percent`) — the frame draws the `tiered` case and the
  STATES block covers four of the others.

---

## CONTRADICTIONS AND THINGS FOR THE PRODUCT OWNER

1. **WHERE IS `the schedule's single minimum rate` TYPED?** Two frames refer to it
   — step 2's empty cell (*"this size uses the schedule's single minimum rate"*)
   and step 5's `Minimum rates` block — and **no frame in pages 41–64 draws the
   control**. Page 44 resolves it in prose rather than in a picture: the rename
   is applied *"here, on the next step, and on the schedule's own page"*, and *"the
   next step"* is this one. **Reading: the field stays on step 3 and is
   relabelled `Minimum rate`. Recorded rather than assumed** — a lane building
   only from the frame would delete it.

2. **PRB-10 IS UNRULED AND THIS SCREEN IS `BLOCKED` ON IT.** Page 64: *"⚠ NOBODY
   HAS RULED THIS. Nine per-size block prices are typed, stored, published to the
   engine and read by nothing."* Two options are on the table (hold it, or remove
   it). **Nothing on this screen should move until that is answered**, including
   the callout's position, because removing the section removes the callout with
   it.

3. **D3 IS A COLLISION WITH A STATED ENGINEERING POSITION, NOT A MISS.** The
   drawing asks for three checks where the file's header says client-side rule
   checking is deliberately absent. Both sides have a reason. **This is the one
   item in this screen that a lane must not resolve alone.**
