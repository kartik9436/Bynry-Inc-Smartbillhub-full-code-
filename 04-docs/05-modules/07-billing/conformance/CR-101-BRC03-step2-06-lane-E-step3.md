# `CR-101-BRC03` · step 2 · §06 **Fix a bill** · lane E — step 3 `What it changes` (26.6 · 26.7) and step 2's `26.4 Goodwill`, built as drawn

**Lane:** E of a four-lane wave (C: `26.1`/`26.5` · D: `26.2`/`26.3` · F: `26.8`).
**Branch:** `claude/gifted-johnson-top7zn`, worktree `agent-a36e8d806b8ecb28e`.
**Base tip:** `05f555ed` at the start; **`ae762d7a` at the first push (`5efd979c`)** — lanes C, D and F all landed while this lane was building, and every shared file was re-derived from the tip before anything was pushed (§7). **Date:** 2026-09-15.
**Process:** `22-product-maintenance-process.md` — a live screen redrawn end to end is MAINTENANCE.
**Built through** `react-tailwind-css-ui-generator` (loaded before the first line of TSX and again before this record) and `build-one-commitment-end-to-end`.

**What this is.** Three drawn screens: step 3's four panels for one bill (`26.6`) and
for many (`26.7`), and step 2's goodwill body (`26.4`). It carries the Product
Owner's tax-panel ruling of today, the row-18 payments statement the orchestrator
added mid-build, what was found by LOOKING at the running screen, three defects
filed, and the proof.

**What this is NOT.** It does not touch the nine-section preview contract, the
correction engine, or any figure. It computes nothing: every number on these three
screens is the server's own, rendered.

---

## 1 · Which pages were read, as images, and at what scale

B14 rule 42 — *"a screen is built from the drawing AS AN IMAGE; extracted text is
an index, never the specification"*. No call was made to the text extractor.

| Page | Read at | What it gave this lane |
|---|---|---|
| p129 | scale 1.5 | the four-step table, and *"What each case shows, and what it deliberately does not"* — `26.4`'s row (THEIR MONEY absent and it says why · TAX absent · DISCOUNTS *Nothing is re-priced* · Credit note only) and step 3's own line, *"Four panels: their money · your books · the tax · the loose ends"* |
| p130 | scale 1.5 | *"An absent panel is drawn, never omitted … the reason is always the same shape: nothing on the bill moved"*, and the thirteen reasons in three classes |
| p138 | 1.5, **then cropped at 4** | `26.4`'s header, the answer band, group 1 `THE CREDIT` (three rows and the AMOUNT column) and the head of group 2 |
| p139 | 1.5, **then cropped at 4** | group 2's rows, the drawn *"Your ruling: …"* line, the two absent panels with their reasons, the footer, and the four annotations |
| p140 | scale 1.5 | `26.5`'s tail (lane C's) and `26.6`'s header |
| p141 | 1.5, **then cropped at 4** | `26.6`'s answer band, group 1 `WHERE THEIR MONEY GOES` (four boxes, their sub-labels, the three questions), group 2 `WHAT YOUR BOOKS DO`, group 3 `WHAT FINANCE NEEDS TO KNOW` |
| p142 | scale 1.5 | `26.6`'s loose ends and footer, its five annotations, and `26.7`'s header and answer band |
| p143 | scale 1.5 | `26.7`'s `MONTH BY MONTH` table and its five money columns, the two-big-numbers band, groups 2–4, the footer |
| p144 | scale 1.5 | `26.7`'s five annotations (`26.8` on the same page is lane F's) |

Whole pages at 1.5 are `10-scripts/pdf/pdf_render.py`; the scale-4 crops are
`SCRATCH/crop_render.py`, which is that script's PNG writer with pypdfium2's own
`crop` argument, because a whole page at scale 4 is downsampled again by the
reader and nothing is gained.

---

## 2 · Reproduce · locate · blast radius

**Reproduced** at `05f555ed` in Chromium at 1440 on `/brazosbend/billing/fix`:
step 3 rendered lane A's carried body under *"New layout not built yet."* — the
three nine-section cards, and **for a BULK case nothing at all**, because
`corrections_api._case_detail` serves `aggregate` and no `sections` and
`NineSections` returns `null` on an empty `section_order`. Step 2 on a class-C
case could not be reached at all (§5, `DEF-BIL-5368`).

**Located:** `07-frontend/src/features/billing/fixABillSteps.tsx` — the registry
`FIX_A_BILL_BODIES` and, since lane C, the per-variant map `STEP2_DRAWN_BODIES`.
Mounted through `FixABillStepBodyView` from `FixABillTab.tsx` at
`/:tenant/billing/fix` and `/:tenant/accounts/:accountId/issue-credit`.

**Blast radius, both ways.** Inbound: nothing imports these two new files but the
registry. Outbound: replacing step 3's carried body retires
`CarriedWhatItChangesBody`, which is left in place deliberately — see §6. Two
suites in other modules read `NineSections` (`BillingSurfaces.test.tsx`,
`payments/releaseOnScreen.test.tsx`); both are green and neither was touched.
**Landing `26.4` completes step 2's five variants**, so the step leaves the hold
list and two of lane D's cases expire — flipped, not deleted (§4).

---

## 3 · What each screen draws, and where every figure comes from

Nothing below is computed on the client. Where the payload has no figure the panel
says so; it never writes a zero.

### 26.4 Goodwill (step 2, class C)

| Drawn | Read from |
|---|---|
| the answer band | chrome — the class's own two facts |
| `1 THE CREDIT` · *Goodwill credit* | `scope.goodwill_amount`, which `open_for_bill` records *"so the executed case runs on the numbers the approver saw"* |
| *Tax on it* `$0.00` | **a signed rule, not a computation** — `goodwill_credit_amount` refuses a tax-inclusive figure by name (PO 2026-08-11). Drawn only where the case names a currency |
| *On the account* | the same figure, bold, as drawn |
| `2 WHAT DOES NOT HAPPEN` · the bill | `sections.what_is_being_corrected.bill_no`, and **only when it is not a uuid** |
| *Their next bill* | the credit through `MoneyCell`, then *as a credit line* |
| *Their discount* | `the_money.discounts.outcome` → `nothing_is_repriced` (lane B's panel), rendered from the CODE |
| `— NO PAYMENTS TO MOVE` · `— NO TAX TO GIVE BACK` | drawn absences with their reasons (p129/p130) |
| **row 18** · *Paid on this bill* | **nothing serves it** — `settlement` is `None` on every class but a restatement and no impact member carries what has been paid, so the row states the absence. The orchestrator is running a backend lane for the figure; §9 names the hunk |

### 26.6 What it changes (step 3, one bill)

| Drawn | Read from |
|---|---|
| the answer band | `net_delta`'s SIGN — owed back / will owe more / does not change |
| `1 WHERE THEIR MONEY GOES`, four boxes | `the_customers_balance.settlement`: `paid_to_date` · `released` · `rebill_takes` · `returns_to_credit`. The first two are ONE figure under two labels, *"which is how the engine serves it"* (p142) |
| the three questions | *is this a refund* is chrome; *do they owe anything now* is `still_owed`; *anything else on the account* is `credit_on_account`, SIGNED as payments serves it |
| `2 WHAT YOUR BOOKS DO` | the ENTRY COUNT and ORDER from `the_ledger_handoff.entries`; the WORDS from the catalogue keyed on the case's `class`; the amounts from `the_money.original_total · corrected_total` and `net_delta` |
| *Posts in* | `the_ledger_handoff.posting_period` (BR-BIL-045) |
| `3 WHAT FINANCE NEEDS TO KNOW` | `the_ledger_handoff.tax_by_authority` — §3's tuple, **drawn again**, per the PO's ruling of today |
| `4 THE LOOSE ENDS` | `warnings.warnings[].code` through the catalogue, plus the discounts outcome; late fee and due date are stated absences |

### 26.7 What it changes · many

| Drawn | Read from |
|---|---|
| `1 MONTH BY MONTH` | one row per `bills_detail[]`: `impact.invoice_no`, and `settlement.paid_to_date · corrected_total · rebill_takes · returns_to_credit · still_owed` |
| the totals row | `aggregate.bills` and `aggregate.rebill_total` — **and the other four columns are NOT totalled**, stated in one sentence (§6) |
| `2 WHAT YOUR BOOKS DO` | `aggregate.credit_total · rebill_total · net_delta`, with a BILLS column instead of debit/credit |
| `3 WHAT FINANCE NEEDS TO KNOW` | `aggregate.tax_by_authority` — **the Δ only**; the panel says so |
| `4 THE LOOSE ENDS` | every pinned row's warnings, DE-DUPLICATED by code with a count |

---

## 4 · The holds this lane retired, and the ones it flipped

| Hold | What happened |
|---|---|
| step 3 carried yesterday's body under *"New layout not built yet."* | **retired** — `FIX_A_BILL_BODIES[2]` opens `FixChangesStep` with `carried: false` and the step left `HELD_FIX_A_BILL_STEPS`, in one commit |
| step 2's `26.4` entry in the hold's `entries` string | **retired** — one line in lane C's `STEP2_DRAWN_BODIES`, exactly as that map's own comment asks |
| `fixABillSteps.test.tsx` *"gives steps 2 · 3 · 4 a CARRIED body"* | already generalised by lane F to `carried === held`; this lane adds the two cases that name WHICH body a released step opens, and both are SELF-FLIPPING (they read the variant map, not a number) |
| lane D's **TC-D5.1** | **flipped** — it asserted step 2's hold row `toBeDefined()`, true only while a variant was carried. A missing row now reads as an EMPTY hold; the invariant (*every variant is either drawn or named in the hold, never both*) is untouched |
| lane D's **TC-D5.4** | **flipped** — it asserted a goodwill case reaches the CARRIED body under its stated absence, and its own comment named the day: *"it expires when 26.4 lands"*. It now asserts the drawn body and NO stated absence, which is hard-won law 2's mirror |

`FixGoodwillStep` carries `data-fix-step2-variant="26.4"` — lane C and D's marker,
adopted rather than reinvented, so the shell's generic assertions keep working.

---

## 5 · Three defects, each measured rather than inferred

**`DEF-BIL-5368` — a goodwill correction cannot be opened from this screen AT
ALL.** `openCorrectionBodyFor` never sets `goodwill_amount` and no field on any
step collects one, so the server refuses every class-C case:

```
REFUSED: a goodwill credit of 0.00 is not a concession. A credit-only correction
reduces what the customer pays; zero changes nothing and a negative one is a
charge wearing a credit's name.
```

Measured against the running service on `brazosbend` before a line of TSX was
written, and again in a browser at both widths: ticking **Goodwill** and pressing
Continue leaves the rail on step 1 with *"This correction can't be made as asked."*
(`def-bil-5368-goodwill-refused-1440.png`). **So `26.4` has no reachable case
today.** The capture of the drawn screen was taken with the walk COMPLETING the
request — the walkthrough adds `goodwill_amount` to the POST and says so in its
own docstring and in the capture's caption. Nothing about the product was changed
to take it.

**`DEF-BIL-5381` — the screen never sends a posting period either**, so
`BR-BIL-045`'s *"the preview NAMES the posting period before confirm"* cannot be
satisfied from this wizard: step 3's books panel reads *"Not set on this
preview."* on every case the screen opens. The same shape as the goodwill amount,
on the field beside it.

**`DEF-BIL-5267` is closed on THIS screen and stays open elsewhere.** The carried
step-3 body printed the server's §5 prose through its generic key/value fallback.
`FixChangesStep.dom.test.tsx` TC-18 keeps that sabotage rather than describing it;
inverted, it names exactly what a clerk read:

```
AssertionError: expected [ …(6) ] to deeply equal []
+ Array [
+   "corrections.post_credit_note_reversal",
+   "issue.issue_invoice",
+   "BR-BIL-011",
+   "BR-TEN-038",
+   "BR-LED-002",
+   "BR-PAY-010",
+ ]
```

The row names `the_ledger_handoff` **and** `the_documents_that_will_exist`; the
second is step 4's section and lane F's half, so the row is **not** marked fixed
by this lane.

---

## 6 · What was NOT built, and why

| Not built | Why |
|---|---|
| the answer band's FIGURE (*"They are owed $99.24 back"*, *"A $40.00 credit…"*) | rule 33's caps and BR-SHL-023's one money path — a money figure interpolated into a translated sentence leaves `MoneyCell`, and every figure the band would carry is in the panel immediately below it. The band keeps the drawn CLAIM at two sentences of five and six |
| the drawn *"Your ruling: 'you dont touch the bill…'"* line | RATIONALE — zero words on screen (rule 33), settled 2026-09-14 and carried through lane A's step 1 |
| the reason half of *"A goodwill credit excludes tax — the tax is owed whatever the utility forgoes"* | the FACT is kept at five words; the reason is rationale |
| the GL account NUMBER drawn beside *"1200 Accounts receivable"* | no endpoint serves it, and it is not invented |
| the tax panel's caption *"Two authorities are affected, and they will see it in the month you post it"* | 15 words, and the table says it. Rule 32's one sentence per section |
| `26.7`'s `⚠ TWO BIG NUMBERS, AND ONLY ONE IS THE CORRECTION` band | the second number — what is *still to pay* across the batch — is served by nothing. Drawing one of two numbers under a heading about two would be worse than drawing neither; the net is in the books panel where it belongs |
| Σ paid · Σ moves across · Σ to credit · Σ still to pay on `26.7`'s totals row | the aggregate serves Σ credit, Σ rebill and Σ net and no settlement sums; a client-side sum would be a second definition of a money total, which `AggregatePanel`'s own docstring forbids one layer down. The row draws `—` and one sentence: *Only the new bill is totalled.* |
| WAS and BECOMES on `26.7`'s tax panel | `aggregate.tax_by_authority` carries `{authority, delta}` only. The panel draws AUTHORITY and CHANGE and says *Only the change is totalled.* |
| `CarriedWhatItChangesBody` | **deleted** — the moment the registry stopped pointing at it, `G40` counted it as dead UI by name and the total rose 13 → 15. Lane F set the form for step 4's an hour earlier; this follows it, and `G40` is back to **14**. ⚠ The only reason it was still alive was `FixChangesStep.dom.test.tsx` TC-18, which rendered it as the kept sabotage — so TC-18 now renders `NineSections` over `STEP3_SECTIONS` directly, which is the half the defect actually lives in and the half two other modules still mount |
| a shared `AbsentPanel` | lane C has a private one and this lane exports one; two components that agree today. Consolidation is a shared-component change, not this lane's |

### Three things found by LOOKING at the running screen (hard-won law 6)

1. **The third box's caption was a claim, and it was false on a real bill.** p141
   captions it *"the whole replacement"* — true of the drawn figures. On
   `brazosbend`, `$1,203.64` met a `$2,006.07` replacement with `$802.43` still to
   pay, under a caption saying the payment was all of it. It follows the server's
   `still_owed` now (`Part of the replacement`), and **TC-2b is the guard**. B14
   rule 37: a figure drawn in a wireframe is an illustration — and so is a caption
   that only holds for the drawn figures.
2. **The group headings were muted and the drawing draws them in the accent.** The
   first draft passed `tone="readOnly"` to `OneTimeWizardZone`; p138–p143 draw
   every group heading in red, and lane C's neighbouring step-2 screens do too.
3. **The answer band was the wrong band.** It reused step 1's consequence strip (a
   tinted block); the drawing and lane C's `AnswerBand` are a left accent rule with
   bold text. Five screens of one wizard may not carry two, and the Product Owner
   looked at lane C's band today.

---

## 7 · Proof

| Check | Result |
|---|---|
| `npx tsc --noEmit` (local TypeScript 5.5.4) | **clean** — and proved capable of failing first: a planted `const laneEProof: number = "not a number"` raised `TS2322`, then was removed |
| `npx vitest run FixChangesStep.dom.test.tsx` | **22/22** — including TC-18, the kept sabotage that names the six references the carried body printed |
| `npx vitest run FixGoodwillStep.dom.test.tsx` | **11/11** |
| `fixABillSteps.test.tsx` · `fixABillContract.test.ts` · `FixABillTab.dom.test.tsx` · `FixSendStep.dom.test.tsx` · `FixWhatStepSingle.dom.test.tsx` · `FixWhatStepBulk.dom.test.tsx` · `styles/routeBUtilities.test.ts` · `BillingSurfaces.test.tsx` · `payments/releaseOnScreen.test.tsx` | **175 passed** across the nine files, after lane D's two expiring cases were flipped |
| `eslint --max-warnings 0` on this lane's four files plus the two shared ones | clean |
| Catalogue parity | **95 keys** (94 + `meetsPartNote`), `+95 / −0 / ~0` in every one of the eleven; one value came back identical to English (Indonesian `Debit`) and is `Debet`, the spelling beside `Kredit`, exactly as the one-time lane settled it the same day |
| Browser walk — `10-scripts/cr101_fix_a_bill_step3_walkthrough.mjs` | **0 problems at 1440 and at 1280**: `26.6` draws the four panels in the drawn order · `26.7` draws month-by-month, the batch books and the Δ-only tax · `26.4` draws the credit, what does not happen and both absent panels · **no rule id, question id or dotted identifier on any of the three, read off the RENDERED DOM** · no horizontal scroll at either width · every case closed without correcting |
| Screenshots | `SCRATCH/lane-E-shots/` — eight files, **all eight hashes distinct**: `step3-26.6-one-bill-{1440,1280}` · `step3-26.7-many-{1440,1280}` · `step2-26.4-goodwill-{1440,1280}` · `def-bil-5368-goodwill-refused-{1440,1280}` |

**What the walk wrote, stated rather than implied.** Step 1's `Continue` opens a
PREVIEW case — the case row, its pinned bills and their impacts, and **no money**
(`BR-BIL-014`). **`Send for approval` was never pressed** and neither was step 4's
commit, so no signature and nothing money-bearing exists. Every case the walk
opened was closed through the screen's own *Close without correcting*, and the
three cases this lane had opened at the service layer for the first pass were
abandoned with a reason. **`BL-2608-000042` was never touched** (lane A left an
approved case on it). At the end, **no correction case on the tenant is open.**

---

## 8 · Reds, each with its date

| Red | Dated how |
|---|---|
| `FixWhatStepBulk.dom.test.tsx` TC-D5.1 and TC-D5.4 | **CAUSED BY THIS LANE and fixed in the same commit.** Landing `26.4` completes step 2's five, so the step leaves the hold list and both cases expire. TC-D5.4's own comment names the day — *"it expires when 26.4 lands"* — and both are flipped rather than deleted (§4) |
| `FixSendStep.dom.test.tsx` — *"expected [ 'billing.fix.send.state' ] to deeply equal []"* | ⚠ **NOT LANE F'S AND NOT ON THE BRANCH — IT WAS THIS WORKTREE'S STALE COPY OF THEIR FILE.** The re-derivation loop brought a sibling's file only when this tree LACKED it, so `FixSendStep.tsx` stayed at the version of two tips earlier while the catalogues moved on. Fixed by making the sync REFRESH rather than fill gaps; lane F's suite is **24/24** here. This is law 12's *"a tree is synced when it matches the tip in BOTH directions"* in a third shape, and the lesson is that *"I already have a file by that name"* is not the same statement as *"my copy is the tip's"* |
| `routeBUtilities.test.ts` — *"text-lg (asked for by FixChangesStep.tsx) renders NOTHING"* | **this lane's, and caught by the one check that can see it.** The theme kills Tailwind's own size names (`--text-*: initial`), so `text-lg` compiles to nothing while `className` still contains it — `tsc`, eslint and a `toContain` assertion all pass over an unstyled figure. It is `text-lead` now |

| `G40` — *"unmounted components ROSE by 15"*, naming `FixGoodwillStep` | **a shared blind spot, not a dead component, and NOT baselined.** All three step-2 bodies are in that list — `FixWhatStepSingle` and `FixWhatStepBulk` were there before this lane — because `TheCorrectionBody` reaches them through `STEP2_DRAWN_BODIES[…]` and then an aliased local (`const Drawn = drawn`), while `G40` credits a lookup table only when the same file renders a MEMBER EXPRESSION `<x.PROP` and assigns `PROP: Name`. A variant chosen at runtime cannot be written as a member expression, so the rule cannot see any of the three. All three are proved mounted by the browser walk and by a case through `FixABillStepBodyView`. **Widening a baseline to go green is the one move the skill forbids outright**, so it is filed rather than silenced — lane D read G40's full list the same afternoon and filed it as **`DEF-SHL-5379`**, which is the row to fix it against: `G40` needs an alias clause, or step 2 needs a shape the gate can read |
| `npx tsc --noEmit` — *"pastBillingRuns.dom.test.tsx(241,11): Type 'false' is not assignable to type 'true'"* | ⚠ **NOT THIS LANE'S, AND FIXED ANYWAY (build skill §10).** Lane I wrote a compile-time TRIPWIRE at **13:03** (`93afce58`) holding the drawn VALUE column: *"the day the runs read serves a run's value and the row type declares it, `HasKey` becomes `true` … and `tsc` goes RED here naming the column"*. At **13:38** `95e4880e` widened `BillRunHistoryRow` to *"what the server now sends"*, which added `value`. The tripwire did its job; **`tsc` was then red for every front-end lane on this branch**, and a red that stops the next lane compiling is yours the moment you find it. FLIPPED, not deleted: the case records which keys the row carries today, still fires when `amount` or `currency` arrives, and **does not claim the column is drawn — it is not, and it is lane I's to draw** |

**No red on the branch was inherited and dismissed.** The two sibling reds above
were each traced to a cause in this worktree or in this lane's own change, which is
law 7's first habit run to its end rather than stopped at *"not mine"*.

---

## 9 · What needs somebody else

* **A backend hunk, the `DEF-BIL-5339` pattern:** each entry of
  `the_ledger_handoff.entries` should carry a `message_key` beside its prose, the
  way every warning already carries a `code`. Until then this screen holds the
  entry WORDS in the catalogue and ties them to the server's entry COUNT, and
  states an absence rather than mislabelling a row when the two disagree.
* **`aggregate` should carry the settlement sums and the before/after per
  authority** if `26.7`'s totals row and tax panel are to be drawn in full.
* **`DEF-BIL-5368` and `DEF-BIL-5381` are lane A's files** (`fixABillContract.ts`
  and `FixABillTab.tsx`): the wizard has to collect and send a goodwill amount and
  a posting period.
* **`CarriedWhatItChangesBody` is dead** from this commit and its removal hunk is
  in the lane report.

---

## 10 · Version and rollback

**Not bumped here** — the orchestrator versions once the wave lands. The
CHANGELOG sentence this lane would have written:

> *"Fix a bill's third step is the blueprint's four panels — where their money
> goes, what your books do, what finance needs to know and the loose ends — for
> one bill and for a batch, with every figure the server's own; a goodwill
> correction draws its own second step, showing the credit, its excluded tax, what
> does not happen and why there is no payments panel and no tax to give back."*

**Rollback:** code only — revert the commits. No case was approved or executed,
and every case opened was closed without correcting.
