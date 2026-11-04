# 17 · Rate schedule → Create · Step 5 · Review & activate — THE DRAWN SPEC

`S11 · RAT-03` · route `/:tenant/plans-rates/rates/:id/edit` · **blueprint pages 51–55**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, section opening
on page 51, **frame drawn across pages 51–53**, specified on 53–55. Read as
RENDERED pages — five stacked panels, three of them four-column comparison tables
with a right-hand `CHANGE` column, then two tick controls. Text extraction runs
the three tables together and prints the commit button before the tick it depends
on.

**State chip:** `NEW BUILD`
**Commitment:** `PRB-09` — *"Somebody is told when a price changes"*, `UNVERIFIED`.
Screen `17`.

**Masthead warning, applied.** As-built at **2.232.0**; re-checked at **2.234.19**.

---

## 1 · Header, step rail

The wizard frame, unchanged, with **`5 Review & activate` active**.

## 2 · Panel 1 — `Base charges`

**Heading:** `Base charges` · **Hint:** `What each size pays before a drop is used.`

| # | header | alignment |
|---|---|---|
| 1 | `SIZE` | left |
| 2 | `IN FORCE TODAY` | left, money |
| 3 | `FROM 01/01/2027` | left, money — **the header carries the effective date** |
| 4 | `CHANGE` | left, **empty on every row here** |

| SIZE | IN FORCE TODAY | FROM 01/01/2027 | CHANGE |
|---|---|---|---|
| `2"` | `$8.0000` | `$8.0000` | |
| `4"` | `$8.0000` | `$8.0000` | |
| `6"` | `$8.0000` | `$8.0000` | |

**Closing callout, accent:**

| legend | sentence |
|---|---|
| `OWNED BY BASE-W` | `Not changing, and it cannot change here. The base belongs to charge code BASE-W; edit it there and every schedule and plan carrying it follows on the same date.` |

Page 53: *"Deliberately included even though it never changes on this screen. A
clerk reviewing a price rise wants to see the whole of what a customer pays, and
its absence was read as `the base is changing too`."*

## 3 · Panel 2 — `Minimum rates`

**Heading:** `Minimum rates` · **Hint:** `The floor for each connection size.`

Same four columns. Change is **money**, and accent-coloured.

| SIZE | IN FORCE TODAY | FROM 01/01/2027 | CHANGE |
|---|---|---|---|
| `2"` | `$18.50` | `$19.25` | `+$0.75` |
| `4"` | `$24.00` | `$24.95` | `+$0.95` |
| `6"` | `—` / `No row` | `—` / `No row` | |

**Closing callout, accent:**

| legend | sentence |
|---|---|
| `NOT READ BY BILLING YET` | `A minimum on a schedule is saved and no bill reads it — billing takes its minimum from the plan. These figures are recorded and change nothing a customer pays until that is wired.` |

## 4 · Panel 3 — `Rates`

**Heading:** `Rates` · **Hint:** `What each block of usage costs.`

| # | header |
|---|---|
| 1 | `BLOCK` |
| 2 | `IN FORCE TODAY` |
| 3 | `FROM 01/01/2027` |
| 4 | `CHANGE` — a **percentage**, accent-coloured |

| BLOCK | IN FORCE TODAY | FROM 01/01/2027 | CHANGE |
|---|---|---|---|
| `0–2 kgal` | `$4.4096` | `$4.5860` | `+4.0%` |
| `2–10 kgal` | `$7.1656` | `$7.4522` | `+4.0%` |
| `10 kgal and above` | `$8.8192` | `$9.1720` | `+4.0%` |

⚠ **THE `CHANGE` COLUMN'S UNIT DIFFERS BY BLOCK, ON PURPOSE.** Page 53: *"The
change is a percentage on rates because a percentage is what a council approves,
and money on the minimums because those are typed as money."*

⚠ **THREE BLOCKS, NOT ONE TABLE.** Page 53: *"Three blocks rather than one because
they come from three different places and behave differently — the base is owned
elsewhere and cannot move here, the minimum is saved and unread, and only the
rates actually reach a bill. Merging them into one table made all three look
equally live."*

⚠ **B14 rule 37 — every figure above is an ILLUSTRATION**, the `+4.0%` included.

## 5 · Panel 4 — `Telling customers`

**Heading:** `Telling customers`
**Hint:** `Both are optional and neither is a legal notice — your regulator's notice period is a separate obligation.`

**Two ticks on one row:**

| # | control | drawn state |
|---|---|---|
| 1 | `Show a notice in the customer portal` | ticked |
| 2 | `Email every affected customer` | unticked |

**Reach sentence beneath, quiet:**
`74 accounts across 3 plans. A notice appears when they next sign in; an email goes to the 61 who have an address on file.`

**Closing callout, accent:**

| legend | sentence |
|---|---|
| `RECORDED, NOT SENT` | `Neither is built yet. The portal and email channels exist and nothing fires on a rate change — the only plan-related notice in the product tells a customer their account moved to a different plan, which is not this. Ticking a box records the intention against this version.` |

Page 54, on why two ticks and not a choice: *"A portal notice and an email are not
alternatives. One is passive and free and reaches whoever signs in; the other is
active, costs money and reaches the 61 with an address."*

## 6 · Panel 5 — `What activating does`

**Callout, accent:**

| legend | sentence |
|---|---|
| `ONE VERSION IS SHORTENED` | `Version v3 runs to 12/31/2026 today with no end date. Activating this closes it on 12/31/2026.` |

**A REQUIRED tick beneath it:**
`I understand v3 will be closed on 12/31/2026`

**A quiet consequence line beneath that:**
`74 accounts across 3 plans re-price from 01/01/2027. Nothing already billed is re-priced.`

## 7 · Footer

`Activate this version ✓` — right-aligned, **and it stays DISABLED until the tick
in §6 is made** (page 53, PRIMARY ACTION, verbatim).

## 8 · States — verbatim

| state | drawn behaviour |
|---|---|
| **Creating** | *"No comparison at all — nothing to compare against. One table of the new figures, no ticks."* |
| **Only rates changed** | *"The minimum-rates block shows three unchanged rows rather than being hidden, because a clerk needs to confirm the floors did **not** move."* |
| **No email addresses on file** | *"The email tick is held, and says how many of the 74 have no address."* |
| **Nothing shortened** | *"The version panel and its tick are absent, not shown saying nothing is affected."* |
| **Impact unknown** | *"The screen says so and states that activating records impact as unknown against this version."* |

## 9 · Components named in the frame

`WizardFrame` `OldNewTable` `NotifyChoice` `ConsequenceNote` `ConfirmTick`

## 10 · FOR · HOW YOU GET HERE · COGNITIVE LOAD · RULES

* **FOR** — *"The clerk one press away from changing what 74 households pay."*
* **HOW YOU GET HERE** — *"Continue from Effective & approval."*
* **COGNITIVE LOAD** — *"Five panels, each answering one question: what the base is, what the floors are, what the rates are, who gets told, and what the button does. Nothing unchanged appears in a comparison table."*
* **RULES, extra clause** — *"A review reads back what is about to be saved, in as many blocks as it has sources."*

---

# THE DIFF — drawing against the code at 2.234.19

Code: `RateScheduleWizard.tsx` — `ReviewStep` **2779**.

**This is the largest gap in the section.** The drawing specifies five panels,
three comparison tables, two ticks and a gated commit. The product renders one
`<dl>` of twelve fact rows, a disclosure, a sentence and a structure preview.

## D1 · THERE IS NO OLD-VERSUS-NEW COMPARISON ANYWHERE ON THE SCREEN

`RateScheduleWizard.tsx:2789-2838` is a single `<dl className="rating-facts">`:

| # | `<dt>` | `<dd>` |
|---|---|---|
| 1 | `Schedule name` | `draft.name` |
| 2 | `Service` | the service |
| 3 | `Structure` | the model |
| 4 | `Unit of measure` | `draft.uom` |
| 5 | `Base rates` | `None — one set of prices covers every connection size.` or `{{count}} connection sizes priced separately` |
| 6 | `Base` | `{{amount}} · from {{code}}` |
| 7 | `Effective from` | the date, or `No date yet` |
| 8 | `Regulator reference` | value or `—` |
| 9 | `Authority` | value or `—` |
| 10 | `Submitted on` | value or `—` |
| 11 | `Approved on` | value or `—` |
| 12 | `Approved by` | value or `—` |

Nothing on this list is a price the clerk just typed, apart from row 6's base —
which is the one figure that **cannot** change here.

## D2 · THE READ-BACK SHOWS THE VERSION IN FORCE, NOT THE DRAFT — the named defect, verified live

`RateScheduleWizard.tsx:2858`

```tsx
        <StructurePreview structure={(detail.current_version ?? detail.draft_version)?.structure} />
```

`detail` is the SERVER's schedule, so `current_version.structure` is **the pricing
already in force**. The clerk's edits live in `draft` and are not read here at all.

Page 53, verbatim: *"This screen showed the prices already in force, not the ones
about to be saved. A clerk typed 4.4096 → 4.5860, walked here, and read back
4.4096."* **Still true at 2.234.19.**

The comment above the call states the intent and is honest about it
(`:2852-2854`): *"The STORED structure of the saved version, once there is one."*
It is a stored-state preview that was never a read-back.

## D3 · THE COMMIT LABEL IS NOT THE DRAWN ONE, AND NOTHING GATES IT

`RateScheduleWizard.tsx:1173`

```tsx
        commitLabel={t(activated ? "rating.rate.newVersion" : "rating.rate.activate")}
```

| | drawn | built |
|---|---|---|
| new schedule | `Activate this version ✓` | `rating.rate.activate` = `Create rate schedule ✓` |
| new version | `Activate this version ✓` | `rating.rate.newVersion` = `Create new version ✓` |
| gating | disabled until the shortening tick is made | **no tick exists**; `WizardFrame` commits whenever the step is reached |

Both built labels obey **B14 rule 4** (`Verb ✓` commits). The drawn one is one
label for both cases, and its gate is the substance.

## D4 · `Telling customers` IS NOT BUILT — and the two checkboxes that exist are a different intention, on the wrong step

Built, on **step 4** (`RateScheduleWizard.tsx:2457-2469`):

* `rating.rate.notifyLabel` = *"Note that customers should be told 30 days ahead"*
* `rating.rate.publishPublicLabel` = *"Note that this should appear on a public rate page"*

Drawn, on **step 5**:

* `Show a notice in the customer portal`
* `Email every affected customer`

These are not the same two facts. The built pair record a POLICY intention (*a
notice period exists*, *this belongs on a public page*); the drawn pair record a
CHANNEL instruction with its reach stated (*74 accounts … the 61 who have an
address on file*). Neither built checkbox states a reach, and there is no
`RECORDED, NOT SENT` callout.

⚠ **THE DRAWING IS EXPLICIT THAT THIS IS NEW WORK AND NOT A WIRING JOB.** Page 54:
*"So the tick boxes record the intention against this version and send nothing
until the notice is built. **It is a new requirement, not a wiring job.**"* That is
`PRB-09`, and its screen list names only screen 17.

⚠ **AND THE `61 who have an address on file` FIGURE HAS NO SOURCE TODAY.**
`RateChangeImpact` (`endpoints.ts:3815-3847`) carries `accounts_affected`,
`accounts_priced`, `accounts_unpriced`, `accounts_sampled` and `accounts_by_plan`
— **no email-address count**. The `No email addresses on file` state (§8) needs a
server figure that is not served. Recorded.

## D5 · `What activating does` IS ONE SENTENCE, NOT A PANEL, AND NOTHING NAMES THE VERSION BEING SHORTENED

`RateScheduleWizard.tsx:2878`

```tsx
      <p className="field-help">{t("rating.rate.review.activateNote")}</p>
```

`rating.rate.review.activateNote` = *"Activating stores this pricing from the
effective date. It does not reprice anything already billed."*

That is the drawn consequence line's **second** half, and it is missing the first:
which version closes, and on what date. Page 54: *"Activating silently truncated a
future version already filed. The version being shortened is named with its new
end date, before the button, and **the tick is required**. Your ruling: contiguity
stays; silence about it does not."*

**The data to name it is on the screen already.** `detail.versions` is served
(`endpoints.ts:3792`) and the detail screen derives the whole ordered chain from
it (`RateScheduleDetail.tsx`, `VersionLine`), so the version that would be
shortened is derivable from the draft's `effective_from` without a new endpoint.

## D6 · WHAT IS BUILT AND GOOD, SO A REBUILD DOES NOT LOSE IT

Four things on this step are right and are not in the drawn frame. Keep them:

* **`SecondApprovalNote`** (`:2850`) — the verdict repeated on the page where
  Activate is pressed, with its own comment explaining why it belongs on both
  steps.
* **The UoM gate refusal** (`:2861-2875`) — BR-RAT-038 stated before activation.
* **`NoticeList`** (`:2876`) — the server's own non-blocking notices. ⚠ It prints
  `br_ref` to the clerk; see `CR-087-p041-create-step1-basics.md` D5.
* **`rating.rate.review.notSavedYet`** — *"Nothing has been stored yet, so there is
  no saved structure to show."*, which is honest about D2's preview rather than
  mirroring the form back.

## D7 · THE PANEL HINT

`rating.rate.review.hint` = *"Check what will be stored, then activate."*
The drawing has no single review hint — it has five panel hints, one per block
(§2–§6). Recorded as part of the same restructure.

---

## ABSENCES — drawn as absent, do not fill them

* **No worked example bill.** The code already states this in a closed disclosure
  (`rating.rate.review.workedExampleGap`) and the reason is `B5` ❄️ FROZEN plus
  CLAUDE.md's ban on porting the prototype runtime. The drawing does not draw one
  either — the two agree.
* **Nothing unchanged appears in a comparison table** (§10) — except the base
  block, which is drawn unchanged **on purpose** and says so.
* **No filing read-back panel** — the drawing does not repeat the four filing
  fields here. The code does (rows 8–12 of D1).

---

## CONTRADICTIONS AND THINGS FOR THE PRODUCT OWNER

1. **THE `CHANGE` COLUMN IS ARITHMETIC AND `B4` IS ❄️ FROZEN.** `+4.0%` and
   `+$0.75` are differences between an in-force figure and a draft figure. Money
   arithmetic in a component is what `RateScheduleWizard.tsx:1495-1503` already
   refuses for the uplift control, on B4's rounding rule. **The safe reading is
   that the server computes the comparison and the screen renders it** — which is
   also `RateChangesTab`'s existing position (*"Every price in a preview row is
   the server's decimal string on both sides of the arrow — 0.11 → 0.1133 is
   rendered, never computed here."*, `RateChangesTab.tsx:33-34`). **Recorded so
   nobody builds the subtraction in TSX. Not a decision this lane makes.**

2. **`PRB-09` IS A NEW REQUIREMENT AND ITS FIGURE IS UNSERVED (D4).** Sizing it
   needs both halves named: the two ticks recorded against the version, and a
   count of affected accounts with an email address.

3. **THE SHORTENING TICK IS A GATE NOBODY HAS RATIFIED AS A RULE.** The drawing
   makes `Activate` depend on a confirmation tick. B14 rule 11 already requires a
   consequence preview before a money commit; a required TICK is stronger than a
   preview. Worth one sentence to the PO so the rule, not just this screen, is
   settled — the pattern would apply to the plan wizard and the tax wizard too.

---

## ⚑ BUILT 2026-09-10 — `CR-087` RATE-SCHEDULE MAINTENANCE LANE

**D2 · THE READ-BACK SHOWS THE DRAFT — the blueprint's named defect, closed.**
`StructurePreview structure={detail.current_version …}` is gone. A clerk who
types `4.4096 → 4.5860` and walks here now reads back **4.5860**.

**D1 · THE THREE OLD-VERSUS-NEW BLOCKS ARE BUILT** — `Base charges`,
`Minimum rates`, `Rates` — each with `IN FORCE TODAY` and a `FROM <date>` column
whose HEADER carries the effective date, and each with the drawn closing callout
(`OWNED BY <code>`, `NOT READ BY BILLING YET`). Three and not one for the reason
page 53 gives.

⚠ **THERE IS NO `CHANGE` COLUMN, AND THAT IS DELIBERATE.** Every cell the drawing
puts there is a SUBTRACTION between an in-force figure and a draft figure. `B4`
is ❄️ FROZEN, this wizard already refuses to compute an uplift on that ground,
and `RateChangesTab` states the module's position: *"the server's decimal string
on both sides of the arrow — rendered, never computed here."* **Nothing serves a
per-row change for an unsaved draft**, so the column is left out, a sentence
under the blocks says where the change figures are worked out, and the gap is
filed rather than closed with arithmetic in a component. This is contradiction 1
of this file, answered the way it recommends.

**D4 · `Telling customers` IS NOT BUILT.** `PRB-09`, and the drawing itself says
*"It is a new requirement, not a wiring job"*; its `61 who have an address on
file` figure has no server field. Untouched.
**D5 · NOT BUILT** — naming the version that would be shortened, and the required
tick, are contradiction 3 and need the PO to rule the tick as a pattern.
**D3, D6, D7 · UNCHANGED.** Everything D6 lists as built-and-good is still there.
