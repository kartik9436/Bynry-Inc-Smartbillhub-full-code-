# `CR-101-BRC03` · §06 **Fix a bill** — the four-step conversion, as MAINTENANCE

**Lane:** the whole Fix a bill journey, end to end. **Branch:** `claude/eager-johnson-r0k88b`.
**Date:** 2026-09-14. **Process:** `12-governance/22-product-maintenance-process.md`.

**THE HEADLINE.** Product Owner, 2026-09-12, verbatim: **"we will ahve to make it
wizard - 4 steps"**. It reached the blueprint — `05-prototype/04 Billing, As Built.pdf`
§06, drawn 2026-09-12, nine entries, every one banded `REDESIGN … NEVER BUILT` — and it
never reached the code. `FixABillTab.tsx` is two stacked panels and a case list. Two
days old at the start of this lane.

---

## 0 · WHICH PROCESS — **MAINTENANCE**, and the classification is the first finding

The maintenance process asks one question: *can a user do this task in the product
today?* **Yes.** Driven in a browser on 2026-09-14 (§1 below), a clerk signs in, opens
`/billing/fix`, finds a real issued bill, picks a reason, previews the case, approves it
and executes it, and the engine writes a credit note and a replacement bill. Nine write
paths are live. The only two things the screen says it does not offer are *"Cancelling a
bill"* and *"Your own reason codes"*.

**So this is a live screen redrawn end to end, which the process names by name:**
*"A live screen redrawn end to end — Maintenance — it BORROWS EXACTLY ONE THING FROM
BUILD: the drawing step."*

⚠ **THIS LANE STARTED DOWN THE BUILD TRACK AND WAS TURNED ROUND MID-FLIGHT, AND THAT IS
RECORDED RATHER THAN TIDIED AWAY.** Before the correction arrived it had read the four
required files, read §06's seventeen pages as images, and begun a NEW file
(`fixABillWizard.tsx`) holding new band, headline, footer and line-table components. The
process predicted the error exactly — *"it FEELS like building … a lane that follows the
Build track loses reproduce, blast radius, regression and the reporter"* — and all four
were indeed missing. The new file was **deleted unpushed**; what survives from that hour
is the drawing reading below, which is the one thing the two tracks share. **The
conversion is now done in the mounted file.**

---

## 1 · REPRODUCE — driven, not assumed

`10-scripts/cr101_fix_a_bill_walkthrough.mjs`, Chromium at 1440 then 1280, tenant
`brazosbend`, signed in as `dana@brazosbendutilities.com` through the real form.

| | |
|---|---|
| Subject | `BL-2608-000048` — **160.520000 USD**, `issued`, chosen as the newest issued bill with no case against it |
| Rail | **0 steps** (`[data-wizard-step]` matches nothing) — the ruling has not reached the screen |
| Bill picked | through the real finder, by typing the bill number |
| Reason | `wrong_read` — class R, the only class that exercises the credit-note **and** rebill pair |
| Preview | case opened, class `restatement`, net `0.00` |
| At preview | the original bill **did not move** — BR-BIL-014 holds |
| Approve → execute | both pressed; the case ran |
| After execution | the original keeps its **number and its total**; `status` moved `issued → corrected`; the case's bill row carries **a credit note id and a rebill id** |
| 1280 | no horizontal scroll |

**Screenshots:** `SCRATCH/fix-a-bill/before-*.png` — step 1 empty, step 1 with the bill
and reason chosen, the preview, the executed state, and 1280.

### ⚠ The one red, and it was the assertion rather than the product

The first run failed on *"the ORIGINAL bill was UPDATED: 160.520000/issued →
160.520000/corrected"*. **That is hard rule 4 working, not breached.**
`billing/0002_rls_w3_and_immutability` says so in its own words: the trigger allows an
UPDATE that changes **only** `status`, `updated_at` and the issue-time stamps, and only
along `issued → paid | void | corrected`. The walkthrough now asserts the money —
total, number — and that the status landed in that closed set. **Written out here
because the next reader's instinct will be to re-tighten it.**

**What this buys the conversion, and it is the reason the process puts it first:** the
money path was watched end to end BEFORE a line moved, so every later claim that the
restructure did not touch it is measured against a recorded run rather than against a
memory.

---

## 2 · LOCATE — the file actually mounted

| Address | What is mounted | Where |
|---|---|---|
| `/:tenant/billing/fix` | `BillsListPage` → its `fix` tab branch renders `<FixABillTab client readOnly readOnlyReason />` | `BillsListPage.tsx:1192` |
| `/:tenant/accounts/:accountId/issue-credit` | `<FixABillTab />` **with no props at all** — `accountId` comes off the route | `App.tsx:867` |

**The two doors are not the same screen and the difference is load-bearing.** The
billing door has no account, so the Bill field is a read-back number over a server-paged
finder; the account door has one, so the field is a bounded select of that account's own
bill numbers. The page head and the seven-tab strip belong to `BillsListPage`, **not** to
`FixABillTab` — which is why the drawing's page head (`Fix a bill`, `Past corrections`)
is not this file's to draw.

---

## 3 · BLAST RADIUS — both directions

### What consumes this screen (inbound doors — all four must still open)

| Door | Lands on |
|---|---|
| `BillDetailPage.tsx:529` — the bill's own primary action | `/billing/fix?bill=<id>` |
| `BillDetailPage.tsx:2631` — Corrections tab, the chain head | `/billing/fix?bill=<head id>` |
| `BillDetailPage.tsx:2639` — Corrections tab, this bill | `/billing/fix?bill=<id>` |
| `accountRailReadiness.ts:306` — the account rail's `issueCredit` | `/accounts/<id>/issue-credit?bill=<id>` |

**All four hand the bill over as `?bill=`** (`FIX_A_BILL_PARAM`). The wizard must still
read it on mount, or four doors open onto an empty step 1 with every test green.

### What consumes this file's exports (must not change shape)

| Importer | What it takes |
|---|---|
| `billing/BillingSurfaces.test.tsx:25` | `NineSections` — asserts all nine in the SERVER's order, and WE-9's `$247.87 / $227.95 / $19.92` with their currency |
| `payments/releaseOnScreen.test.tsx:43` | `NineSections` — CS-36's settlement panel |
| `billing/FixABillTab.dom.test.tsx:52` | `FixABillTab`, `correctionCasesKey`, `correctionCatalogKey` |
| `customers/accountActionOverlays.dom.test.tsx:138` | mounts `FixABillTab` at the `issue-credit` overlay |
| `routing/renderedCopy.test.tsx:268` | `/billing/fix` is in its route list |

⚠ **`NineSections` IS THE ONE THAT BITES.** Two suites outside billing render it and
assert **all nine sections** in `section_order`. The wizard needs to deal them across
four steps. So the deal-out is an **opt-in `only` prop**: absent renders all nine, which
is byte-for-byte what both external callers already get. Widening the component's
default would have turned two suites in two other modules red for a reason neither is
about.

### The mirror — what else USED anything being removed

**Nothing is removed.** The carry-over map below is one row per element of today's tab
and its `REMOVED` count is **zero**. That is the check, not a claim: an element marked
`MOVED` that goes missing is a failed conversion, and one marked `REMOVED` that survives
is the same failure.

### Two things in the radius that landed today

* A sibling lane pushed **143 locale strings for the thirteen fix reasons**
  (`DEF-BIL-5233`, `CR-101-BRC03-step2-06-fix-a-bill.md`). The reason control moves into
  step 1 **carrying those strings and their sort** — not re-keyed, not re-worded.
* `BillDetailPage`'s Corrections tab links in from three places, added this week.

---

## 4 · THE DRAWING — read as images, and the counts tied out

**§06 is p129–p144**, read at scale 2 (and p132 cropped at scale 4 to settle one band's
wording). B14 rule 42: the wireframes are vector art and **p133 returns NOTHING from the
text layer**, so the extractor could not have given this at all.

### The four steps (p129, the section's own table)

| Step | Entry | What it is for |
|---|---|---|
| 1 | `26` **What and why** | The scope, the bills it resolves to, then the reason |
| 2 | `26.1`–`26.5`, **five variants** | The correction itself: one bill · several months · a batch · goodwill · the page only |
| 3 | `26.6` / `26.7` | Four panels: their money · your books · the tax · the loose ends |
| 4 | `26.8` **Generate and send** | The documents, the send options, and the one button that writes |

**Nine entries: 1 + 5 + 2 + 1 = 9.** ✓

### The thirteen reasons, and the count ties out three ways

p130's table and p133's banded list agree: **R 7 · C 1 · D 5 = 13**, plus **5** routed
away = **18 rows**, which is exactly what p134's annotation says in words — *"Eighteen
rows, five of which refuse"*. The server's `SEEDED_REASON_CLASSES` holds the same
thirteen in the same three classes. ✓

⚠ **THE COORDINATOR'S FIGURE WAS RIGHT AND ITS PAGE RANGE WAS NEARLY RIGHT.** Front
matter is p129–p132 (screen 26 starts halfway down p132, not after it); the screens run
p132–p144, not to p147 — **p145 is already §07 Past billing runs.**

### ⚠ §06 HAS NO CARRY-OVER TABLE, AND §03 DOES — so this lane wrote one

Searched the whole document for `DISPOSITION`: it appears on **p8, p11, p86, p230, p238,
p241** and **nowhere between p129 and p144**. The bulk run's is p86–88 and it says why
it exists — *"Merging three steps into one is the change most likely to drop something
quietly, so this table is one row per element across all six original steps."* §06 is
not a merge (one flat tab becoming four steps), so the document never drew one.

**The absence does not excuse the conversion, so §7 below is that table**, authored to
§03's shape and reconciled the same way.

---

## 5 · THE ONE OPEN QUESTION, SETTLED HERE — the class letters and the band length

The step-2 lane left this open in its own record and **filed no register row**, so
nothing counted it. It is settled now, in two halves that are not the same kind of
question.

### (a) `CLASS R` · the `CLASS` column of bare letters · `class R` in the subtitle — **NOT BUILT, and this is not a new ruling**

The drawing bands the reason list `CLASS R · THE MONEY AND THE DOCUMENT BOTH MOVE — 7`,
puts an `R`/`C`/`D` column beside every row, and writes `class R` into the page subtitle
of `26.1`–`26.5`.

**The repo already ruled this, twice, in the same direction, and the code already obeys
it.** `apps/billing/correction_reasons.py` quotes TC-1a verbatim: *"The class is shown in
the operator's words … never as an enum value."* `apps/billing/single_correction.py`
names the drawn element itself: *"the class is shown as a WORD, not a code — the epic is
explicit, and **'R' is a thing to go and look up**"*. B14 rule 31 says the same for every
internal value on every screen, and B14 rule 32 forbids an internal code in clerk-facing
copy.

So the drawing contradicts a rule that is already signed **and already implemented**.
Hard-won law 13 is explicit that re-asking a settled question is a bug in us, not
diligence — *"before putting anything to the PO, grep the decision log and the open
questions for the subject. If it was ruled, it is ruled — build it."* **The bands stay,
in the drawing's own words. The letters do not.** Nothing is invented to replace them:
the band already says what the class does, which is what TC-1a asks for.

### (b) The band LENGTH — a judgment, recorded rather than asked

B14 rule 33 caps a **LABEL** *(a name)* at 3 words and a **FACT** at 6. Read as labels,
**almost every band in §06 fails** — `WHERE THEIR MONEY GOES` (4), `WHAT YOUR BOOKS DO`
(4), `ROWS THAT NEED A HUMAN EYE` (6), and about twenty more.

**A band that says what a group DOES is a fact about the group, not its name.** Three
things settle it without a ruling:

1. **BR-BIL-044's own nine section titles already ship at four and five words** — *"What
   the customer will receive"*, *"The documents that will exist"* — ratified, live, and
   never filed against.
2. **The PO delegated exactly this judgment when rule 33 was ratified**, verbatim: *"5 to
   6 words - you can define what is reason we are showing this text based on reason you
   can vary the lenght"*.
3. Hard-won law 13: a judgment recorded with its reasoning is the deliverable; a question
   is the failure to make one.

**So every band is six words or fewer, in the drawing's own vocabulary.** Only three
drawn bands exceed six, and each is tightened using words already on the page — never
paraphrased, never invented:

| Drawn | Words | Built | Words | How |
|---|---|---|---|---|
| `CLASS R · THE MONEY AND THE DOCUMENT BOTH MOVE` | 9 | `The money and the document move` | 6 | letters dropped per (a); `both` dropped |
| `CLASS C · THE BILL IS RIGHT; THE UTILITY CHARGES LESS` | 10 | `The bill is right` | 4 | the drawing's OWN short form — `26.4`'s breadcrumb reads *"the bill is right"* |
| `CLASS D · THE MONEY IS RIGHT, THE PAGE IS WRONG` | 10 | `The page is wrong` | 4 | the drawing's OWN short form — `26.5`'s breadcrumb reads *"the page is wrong"* |
| `⚠ NOT A CORRECTION — THESE REFUSE, AND SAY WHERE TO GO` | 10 | `Not a correction — these refuse` | 5 | the second clause is what the row's own destination column shows (rule 32: a row never repeats what its own control offers) |
| `THIS BECOMES THE DOCUMENT THEY ARE ENTITLED TO` | 7 | `The document they are entitled to` | 6 | first two words dropped |
| `TWO BIG NUMBERS, AND ONLY ONE IS THE CORRECTION` | 9 | `Two big numbers, one correction` | 5 | the drawing's own words |

**Nothing goes to the PO from this section.** If they want the letters back, that is a
ruling they can make against this record.

### One more drawn element refused on the same ground

`26.4` draws, **inside the screen frame**, the line *"Your ruling: 'you dont touch the
bill… everything remain as it is.'"* That is RATIONALE — why the product works this way
— which rule 33 gives **zero words on screen**, and it names an internal party. Not
built. The sentence belongs here and in the code, which is where it now is.

---

## 6 · TWO DEFECTS FOUND AND NOT FIXED IN THIS WAVE — filed, per §3 of the process

*"Do not widen the change… If you find a second problem, file it."*

1. **The correction preview's line list renders BLANK.** `LineImpact.as_dict` serialises
   `key · label · kind · original · corrected · delta · moved`. `SectionBody`'s
   `the_lines` branch asks for `line.description`, `line.before` and `line.after` —
   **three keys the payload has never carried** — so every line renders as an empty
   bullet, or as the three characters `" · → "` where it moved. `tsc` passes because
   `CorrectionImpactLine` declares all six optional; every suite passes because no
   fixture asserts a line's text. It is the blueprint's `LINE BY LINE` table and belongs
   to step 2's wave.
2. **The correction CLASS and the case STATUS reach a clerk as raw enum codes.**
   `billing.fix.class.*` and `billing.fix.status.*` hold **zero keys in all eleven
   catalogues**, so `restatement`, `credit_only`, `document`, `pending_approval` and
   `executing` render through `defaultValue`. Same shape as `DEF-BIL-5233`, which fixed
   the thirteen REASONS and left the class and the status beside them.

---

## 7 · THE CARRY-OVER TABLE — one row per element of today's tab

**This is the acceptance test.** Authored to §03's shape (p86–88) because §06 has none.

| # | Element on today's Fix a bill tab | Disposition | Where it lands |
|---|---|---|---|
| 1 | `billing.fix.noEditNote` — *"An issued bill is never edited. It is credited and replaced."* | UNCHANGED | Step 1, word for word |
| 2 | Bill field — the read-back NUMBER at billing's own door | UNCHANGED | Step 1 |
| 3 | Bill field — the bounded select at the account door | UNCHANGED | Step 1 |
| 4 | `BillFinder` — the shared `DataTable` over `GET /invoices` | UNCHANGED | Step 1 |
| 5 | `Choose another bill` | UNCHANGED | Step 1 |
| 6 | The thirteen reasons, in words, sorted by the words | UNCHANGED | Step 1 |
| 7 | `mechanism_in_words` — the derived sentence | UNCHANGED | Step 1 |
| 8 | `Show me what it would do` | RELABELLED | Step 1's rail **Continue**. The button is gone; the CALL underneath it is the same `openCorrectionCase` |
| 9 | The preview failure line | UNCHANGED | Step 1 |
| 10 | The case status pill | MOVED | Step 2 head |
| 11 | `NineSections` — all nine, in `section_order` | MOVED | **dealt** across steps 2 · 3 · 4; see §8 |
| 12 | `Approve these figures` | RELABELLED | Step 3's Continue — *Send for approval* |
| 13 | `Make the correction` | RELABELLED | Step 4's commit — *Create the documents & post* |
| 14 | `Close without correcting` | MOVED | the rail's secondary action, on every step |
| 15 | `no_rollback` — the sentence where an undo button would be | MOVED | Step 4 |
| 16 | `result.summary` after execution | MOVED | Step 4 |
| 17 | `Corrections so far` table | UNCHANGED | below the rail |
| 18 | `Not offered here` — the void and the tenant's own reasons | UNCHANGED | below the rail |
| 19 | `GapNotes` — the catalogue's unavailable list | UNCHANGED | below the rail |
| 20 | The catalogue error panel and the loading skeleton | UNCHANGED | tab root, above the rail |

```
As-built elements   20
  unchanged         13
  moved              4
  relabelled         3
  removed            0      RECONCILES  13 + 4 + 3 + 0 = 20
```

**New from the drawing, owing nothing to today's tab:** the four-step rail itself.
Everything else the drawing adds — the six ways in, the resolved-bills table, the banded
eighteen-row reason list, step 2's five class variants, step 3's four panels and step
4's two groups — is the SUBSEQUENT waves' work and is not claimed here.

---

## 8 · HOW THE NINE SECTIONS ARE DEALT, AND WHY THAT IS NOT A BR-BIL-044 BREACH

BR-BIL-044: *"nine sections, all required, none collapsible away"*. A wizard that showed
three of them before the approval control would be the partial artifact that rule
refuses.

| Step | Sections |
|---|---|
| 2 · The correction | `what_is_being_corrected` · `the_lines` · `the_money` |
| 3 · What it changes | `the_customers_balance` · `the_ledger_handoff` · `warnings` |
| 4 · Generate and send | `the_documents_that_will_exist` · `what_the_customer_will_receive` · `the_gate` |

**3 + 3 + 3 = 9, no section in two steps and none in none.**

**The approver cannot skip any of them.** `WizardFrame`'s rail navigates BACKWARDS only
— `jumpBackTo` returns the same object on a forward click (BR-SHL-018) — so *Send for
approval* on step 3 is reachable only by walking steps 1 and 2 first. All nine are on
screen before the signature, in the server's own `section_order`.

---

## 9 · WHAT THE UI RULES TOOK OFF THE DRAWING (B14 rule 38)

Recorded rather than built, because each is FORM CONSTRUCTION and rule 38 gives
construction to the UI rules while leaving content to the drawing.

| Drawn | Built | Why |
|---|---|---|
| The footer's left-hand prose (*"Nothing is written."*, *"One approval for all six."*) inside the action band | at the end of the step CONTENT | `DEF-1083` already ruled that an action row holds only things a person can press |
| A per-step forward label | **built** — `WizardStep.continueLabel`, opt-in | This one is CONTENT, not construction: *Send for approval* is the act that records the signature, and a frame saying *"Continue"* there tells a clerk they are turning a page when they are signing. Added to the kit as an opt-in per rule 36, so none of the other fifteen wizards moves |

---

## 10 · VERSION AND ROLLBACK

**Rollback:** code only — revert the commit (PO 2026-09-10). ⚠ **One line of honesty the
process asks for:** this lane's REPRODUCE run **executed a real correction** on
`brazosbend` — `BL-2608-000048` now carries status `corrected` and a credit note and
replacement bill exist against it. **Reverting the code does not undo those rows.** It is
the demo tenant and the engine's own idempotent path, and it is stated rather than
implied.

---

## 11 · PROVE IT — the same journey, through the rail

`node 10-scripts/cr101_fix_a_bill_walkthrough.mjs --after`, same tenant, same script, same
assertions.

```
rail: 4 step(s) — ["1What and why","2The correction","3What it changes","4Generate and send"]
  ✓ four steps on the rail
  ✓ bill chosen through the finder — BL-2608-000093
  ✓ reason chosen from the select
  ✓ no amount, description or line field anywhere on the screen
  ✓ case opened — class restatement, net 0.00
  ✓ preview wrote nothing to the original bill
  reached step3
  reached step4
  ✓ the original BL-2608-000093 keeps its money — 160.520000 USD; status issued → corrected
  ✓ the correction wrote NEW rows — a credit note and a replacement bill
  ✓ no horizontal scroll at 1280
after: 0 problem(s)
```

**Screenshots, all four steps at 1440 plus 1280:** `SCRATCH/fix-a-bill/after-step1-1440.png` ·
`after-step1-chosen-1440.png` · `after-step2-1440.png` · `after-step3-1440.png` ·
`after-step4-1440.png` · `after-executed-1440.png` · `after-final-1280.png`.
**Every one of the four steps was reached in a browser and captured** — none is presented
from a fixture.

### ⚠ One regression this lane CAUSED, and only looking at the screen found it

The approval toast read *"Approved. Nothing has moved yet — **choose Make the correction
to write it**."* The rail relabelled that button to *Create the documents & post*, so the
toast named a control nobody could find — the copy half of hard-won law 2, and **no check
in this repository could see it**: the key exists, it renders, it is in all eleven
catalogues, and `tsc`, eslint, 571 vitest cases and every gate pass over it.

Reworded in all eleven to **"Approved. Nothing is written yet."** The instruction half is
dropped rather than re-pointed: the rail has already put the clerk on step 4 with the
commit in front of them, and B14 rule 32 forbids a line repeating what its own control
offers.

### Rule 6, measured rather than eyeballed

The commit reads as filled red in a down-scaled full-page capture and is **not**: cropped
at scale, `Create the documents & post` is **transparent with red text and a red border** —
B14 rule 6's danger tier, *"outlined at rest, FILLED on hover"*. `commitVariant="danger"`
is declared because a correction REVERSES an issued bill, which rule 6 names by name, and
because the blueprint's own step-4 band says *"⚠ AFTER THIS THERE IS NO UNDO"*.

---

## 12 · REGRESSION — the neighbours walked

| Suite | Result |
|---|---|
| `src/features/billing` · `accountActionOverlays.dom` · `releaseOnScreen` · `WizardFrame` (both) · `src/routing` | **571 passed**, 2 failed — **neither this lane's, both dated below** |
| `npx tsc --noEmit` | clean, and **proved capable of failing first**: a planted `const x: number = "s"` was seen to raise `TS2322`, then removed |
| `06-backend/tests/test_cr101_fix_a_bill_sections.py` | **3 passed**, and **each proved RED first** — dropping `what_the_customer_will_receive` from a step named it; adding a fifth step printed *"the rail declares 5 steps; the ruling is four"* |
| Catalogue parity | all eleven at **16,865** keys; `git diff` shows **6 deletions per file and all six are this lane's** — the five reaped keys and the reworded toast |
| Built bundle | every new string present in the artifact the browser downloads, English through Japanese |

### The reds, each dated by MEASUREMENT and not by assertion

Both were re-run **at the pinned tip `42c76836` in a detached worktree, without this
lane's change**, and failed identically there.

| Red | Dated |
|---|---|
| `routing/screenIds.test.tsx` — the screen-id map holds **143** routes against `App.tsx`'s **149** | `screenIds.ts` last moved in `c66766c3`, 2026-09-14 (Meter Reads entry 20) |
| `billing/BillsPage.test.tsx` TC-2 — the bills search now has a fourth leg (`address`) and the test expects three | the leg landed in `cf45a3d2`, 2026-09-13 |
| `eslint` on `FixABillTab.tsx` — `react-hooks/exhaustive-deps` in `BillFinder` | **the identical single error exists at HEAD's own copy** (line 226 there, 232 here only because lines were added above it); `73957d21`, `DEF-BIL-5153`'s commit. Left standing and reported — the skill forbids silencing it, and the maintenance process forbids tidying the neighbourhood |

⚠ **One environment note, not a finding:** `06-backend` runs on **python3.12** here;
`python3` is 3.11 and has no `rest_framework`, so `python -m pytest` dies at
`django.setup()` with `ModuleNotFoundError` before a single test is collected. A lane
reading that as "the backend suite is broken" would be wrong. There is also **one
unapplied `metering` migration** in this container, another lane's, left alone.

---

## 13 · CLOSE — and which build to look in

**Fixed in `2.265.0`.** The Fix a bill tab at `/billing/fix` and at an account's
*Issue credit* both open on the four-step rail.

**What is NOT built and is the next wave's, stated so nobody reads this as §06 finished:**
the six ways in and their narrowing fields, the resolved-bills table, the banded
eighteen-row reason list with the five disabled refusals, step 2's five class variants,
step 3's four panels and step 4's two groups. **Nine drawn entries; this wave delivered
the rail they hang on.**

---

## 14 · AMENDMENTS MADE AFTER THE FIRST PUSH — each found by a check, and named

### (a) `G35 version-lockstep` — the ONE gate this lane turned red, and it is fixed rather than baselined

The full suite compares against its own last recorded run, and its verdict named this
lane exactly once: **`1 NEWLY FAILING — G35 version-lockstep: was PASS, now FAIL:
VERSION 2.265.0 HAS NO CHANGELOG ENTRY — CHANGELOG.md's newest heading is 2.263.0`.**

The first draft of the entry went under `## [Unreleased]` with the version inline as
`(2.265.0)`, **which is what the two lanes before this one did** — the tip's
`[Unreleased]` carries `(2.263.1)` and the shared tree carries `(2.264.0)`, neither with
a heading. G35 reads `^##\s*\[(\d+\.\d+\.\d+)\]` and **nothing else, deliberately**: its
own docstring says a body legitimately NAMES other versions, so a substring search would
accept an entry that only mentions the version it is supposed to be about.

Fixed by giving the version its own `## [2.265.0] - 2026-09-14` section above the newest
existing heading. `python3.12 10-scripts/gates/g35_version_lockstep.py` now prints
*"all 4 version literals agree at 2.265.0, and it has a changelog entry"*.

⚠ **The number skips 2.264.0 on purpose.** `allocate.py version --bump change` asked the
remote and answered `2.265.0`; the tip reads `2.263.1` and the Budget Bills lane holds
**2.264.0 unpushed in the shared working tree**, with its entry and its three literals.
Taking 2.264.0 would be `DEF-GOV-3756` — two lanes shipping one version. **Whoever lands
2.264.0 after this must not step the literals backwards:** G35 refuses a *disagreement*
between the two files, not a *regression* they make together.

### (b) A third defect, found by LOOKING at step 3 rather than by any check

**`DEF-BIL-5267` — the preview prints module paths, rule ids and `CLAUDE.md` at a clerk,
on the surface where an approver signs.** The sections whose bodies the screen does not
model by name fall through to a generic renderer that prints every key and value the
server sent, verbatim. On a real preview that is
`corrections.post_credit_note_reversal`, `issue.issue_invoice`, `BR-BIL-011`,
`BR-BIL-045` and the words *CLAUDE.md rule 5*.

**`G28` part 1 reports ZERO and is not lying** — it scans the eleven CATALOGUES, and
these strings are the SERVER's, composed at runtime and never keyed. That is hard-won law
7's *reporting zero over a scope it silently excludes*, and the shape of the fix is the
one `warnings` already uses in this same file: the server sends a CODE, the UI renders
the language.

Pre-existing since 2026-08-16 and **not fixed here** — the maintenance process's §3 is
explicit that a second problem is filed, not folded in.

### The three filed, in fix order

| Id | What | Order |
|---|---|---|
| `DEF-BIL-5249` | the preview's line list renders **blank** — the blueprint's `LINE BY LINE` table | 3 · the queue, and it is step 2's wave |
| `DEF-BIL-5250` | the correction **class** and the case **status** render as enum codes | 3 · the queue |
| `DEF-BIL-5267` | module paths, rule ids and `CLAUDE.md` on the approval surface | 3 · the queue |

None is order 1 or 2: no money is wrong and no core task is blocked — a clerk can correct
a bill, and could before this change.

### (c) ⚠ TWO OF THIS LANE'S OWN WRITES WERE SUBTRACTED BY A LATER COMMIT — found by re-reading the push

Law 11's last habit — *"after pushing, re-read each file you changed FROM HEAD and confirm
your own change is still in it"* — is the only thing that found either of these, and both
are the same mechanism (`DEF-GOV-5268`, filed; the commit is also the one `DEF-GOV-5265`
was filed against for carrying this lane's commit message verbatim while not being it).

| What | State |
|---|---|
| **The version** | `2.265.0` landed in `67ddeee9` in all three literals. A later commit put **`2.264.0`** back over all three. The branch now carries a `## [2.265.0]` heading and **no `## [2.264.0]`**, so `G35` fails on the changelog rather than on the literals — it refuses a *disagreement* between the files and has nothing to say about a *regression* they make together |
| **`DEF-BIL-5264`** | appended to the register and **never reached the tip** — subtracted from an append-only file, which is law 11 mechanism two. Its id is a HOLE at the tip (5263, then 5265) and it is re-filed here as **`DEF-BIL-5267`**. Every citation in this file was moved with it |

**The version is put FORWARD, not back:** `G35`'s own refusal text says *"Move BOTH,
forward for both and backward for neither; if a sibling lane has already taken the next
number, skip it rather than reusing it."* So the three literals go to `2.265.0` again,
which loses nothing — the 2.264.0 entry is in `[Unreleased]` and stays there.
