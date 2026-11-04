# `CR-101-BRC03` · step 2 · §06 **Fix a bill** · lane C — step two's two single-bill shapes, `26.1 One bill` and `26.5 The page only`

**Lane:** C of a four-lane wave (D · E · F on the other step-2 variants and steps 3–4).
**Branch:** `claude/gifted-johnson-top7zn`, worktree `agent-aaea86ed412f188e0`.
**Base tip:** `05f555ed` at the start; **`9b73d6ff` at the first push, `550bb803` at the second.**
Lane F landed step 4, lane D landed `26.2`/`26.3` on this lane's own dispatcher, and the
orchestrating session pushed defect rows — so every shared path was re-derived from the pinned
tip THREE times and four defect ids were renumbered under the allocator (§7). **Date:** 2026-09-15.
**Process:** `22-product-maintenance-process.md` — a live screen redrawn end to end is
MAINTENANCE. **Built through** `react-tailwind-css-ui-generator` (loaded before the first line
of TSX and again before this record) and `build-one-commitment-end-to-end`.

**What this is.** One commitment: step two of the Fix a bill wizard renders the blueprint's two
single-bill screens instead of the body a clerk used yesterday. It carries the before/after, the
seven judgments where the drawing ran out, what was deliberately NOT built and why, every red
with its date, the proof, and the **five** defects this lane filed — **three of them found by
looking at the rendered screen and by nothing else** (hard-won law 6). Two were closed here;
the other three are backend work and are open.

**What this is NOT.** It does not close step 2, and at this lane's last push entries
`26.2 Several months`, `26.3 A batch` and `26.4 Goodwill` were still the carried body under
its stated absence — lane D landed the first two while this record was being written and
lane E has since landed the third, each by adding ONE line to the dispatcher map this lane
introduced (§4). Read `STEP2_DRAWN_BODIES` and `HELD_FIX_A_BILL_STEPS` for the current
state rather than this paragraph. It does not touch `FixABillTab.tsx` or `fixABillContract.ts`.

---

## 1 · The pages, and that they were read AS IMAGES

| Page | Read at | What was taken from it |
|---|---|---|
| **p129** | 1.5 | §06 front matter and the case table — *"what each case shows, and what it deliberately does not"* — THEIR MONEY · TAX · DISCOUNTS · WHAT GOES OUT for each of 26.1–26.5, and *"An absent panel is drawn, never omitted"* |
| **p130** | 1.5 | the thirteen reasons in three classes, and the class-D line *"Reprints the document with the details corrected — Exactly $0.00"* |
| **p134** | 1.5 **and 4** | screen 26.1 begins: `STEP TWO · CLASS R`, the answer band, group `1 LINE BY LINE` with WAS · BECOMES · CHANGE |
| **p135** | 1.5 **and 4** | 26.1's table foot and its bold `The bill` total row, the caption, group `2 THEIR DISCOUNT IS SAFE`, the footer, and the four annotations — *"The answer is the first thing on the screen"*, *"Was, becomes, change — per line, not net"*, *"Nothing is edited, and that is structural"*, *"Group 2 answers the question a clerk is actually asked"* |
| **p139** | 1.5 | 26.4's two absent panels (the SHAPE an absence is drawn in), then screen 26.5 begins: `STEP TWO · CLASS D` and its answer band |
| **p140** | 1.5 **and 4** | 26.5's three groups, its two absent panels, its footer, and the three annotations — *"The $0.00 is drawn, not implied"*, *"Group 3 is a fact worth a clerk knowing"*, *"It reads master data; it does not write it"* |

The extractor was not used on any of them. Scale 4 was rendered through a crop wrapper around
`10-scripts/pdf/pdf_render.py`'s own raw-bitmap path, because a whole page at scale 4 is
4896×3168 and comes back downscaled to nothing.

**§06 is p129–p144. p145 opens §07 and nothing here was built from it.**

---

## 2 · Reproduce · locate · blast radius

**Reproduced** at `05f555ed` in Chromium at 1440: `/brazosbend/billing/fix` → pick an issued
bill → *Wrong read* → Continue lands on step 2 showing **`New layout not built yet.`** over a
pill reading **`pending_approval`** and three generic section cards. The lines were a bullet
list of descriptions with `before → after` appended where something moved — which is why §5's
`DEF-BIL-5365` had been invisible.

**Located:** `fixABillSteps.tsx`'s `CarriedTheCorrectionBody`, reached from
`FixABillTab.tsx` (mounted at `/:tenant/billing/fix` and `/:tenant/accounts/:accountId/issue-credit`)
through `FixABillStepBodyView`. Both doors kept.

**Blast radius, both ways.** Forward: the new body is reached only through `FIX_A_BILL_BODIES`,
which now points step 2 at a dispatcher. Backward — **what else used the thing being replaced:**
`CarriedTheCorrectionBody` is NOT removed and is still what 26.2, 26.3 and 26.4 render, so
`fixABillSteps.test.tsx`'s *"a hold is not a regression"* case still holds; `NineSections` and
`STEP2_SECTIONS` are untouched, so the two suites in other modules that import them
(`BillingSurfaces.test.tsx`, `payments/releaseOnScreen.test.tsx`) and the Python guard that ties
the three step lists to the server's `section_order` are all unaffected.

---

## 3 · Before and after, measured on a real bill

| | Before (`05f555ed`, Chromium 1440) | After |
|---|---|---|
| What step 2 says about itself | *New layout not built yet.* | the drawn screen; the stated absence is **gone for these two entries and kept for the other three** |
| The case status | `pending_approval` | **Waiting for approval** — and *Draft · Approved · Running now · Still open · Done · Failed* for the other six (`DEF-BIL-5349`) |
| *Corrections so far*, WHAT IT DOES | `restatement` · `credit_only` · `document` | **Credits and rebills · Credit on the account · Sends the page again** (`DEF-BIL-5366`, found in this lane's own capture) |
| The answer | — | first thing on the screen: *The bill total does not move.* on a netting case, *This bill drops by $62.57. They will be $67.82 in credit.* on a moving one |
| The lines | a bullet list of descriptions | **WAS · BECOMES · CHANGE per line**, every line moved AND unmoved, with the tax as its own line per authority, over a bold `The bill` total row |
| The discount | nothing | one sentence, with the version it was priced on |
| What has been paid | **step 3 only** | at step 2 as well — *Paid to date $261.03 · Replacement takes $261.03 · Returns to credit $0.00 · Still owed $174.02* (the PO's action row 18) |
| 26.5's absences | nothing | **three panels DRAWN**, each with its reason |
| Catalogue keys | `billing.fix.*` was **150** at `05f555ed` | **+61 by this lane** (58 for the two screens, 7 of them the case statuses; then 3 class words), 0 removed, all eleven catalogues in parity |

---

## 4 · The seven judgments

All seven are written out in `12-governance/02-decision-log.md` under *"FIX A BILL STEP TWO,
THE TWO SINGLE-BILL SHAPES — SEVEN JUDGMENTS WHERE THE DRAWING RAN OUT"*, with the drawn and
built copy side by side. In one line each: the *"THEIR DISCOUNT IS SAFE"* heading is used only
for the outcome it was drawn for · 26.5 gets a third absent panel for the discounts · step 2's
one registry slot dispatches to five variants · the group rules take the divider because two
frames disagree · the answer band is composed from the payload's own figures and never from the
server's prose · *payments already made, and applied* comes to step 2 as the settlement panel's
four figures · six drawn sentences are shortened to rule 33 and the group HEADINGS are not.

---

## 5 · What was NOT built, and why

| Not built | Why |
|---|---|
| 26.5's `FIELD · WAS · BECOMES` document diff | **`DEF-BIL-5355`** — `corrections.py`'s `CLASS_DOCUMENT` branch builds `impact_lines` from the bill's CHARGE lines with every delta zero and composes no field comparison at all. The client cannot make one: the WAS is what the ISSUED document says and the BECOMES is what the account says now, and that comparison has to be inside the artifact `preview_hash` binds. Drawn as a stated absence |
| A paid figure on a class-C or class-D case | **`DEF-BIL-5356`** — the case's pinned bill rows carry no `paid`, though `GET /corrections/resolve` has served one since lane B landed. 26.1 draws the settlement panel's four figures; 26.5 draws the absence the drawing already gives it |
| The `documents` list from section 4 | not drawn on either screen, and section 4 is dealt to STEP FOUR (3 + 3 + 3). p129's WHAT GOES OUT is the caption under 26.1's table and group 3 of 26.5, exactly as drawn |
| A separate tax panel on 26.1 | p129's TAX cell is *"Per authority"* and the drawing answers it with the bill's own tax LINES inside the trail, each with its own three figures. The PO ruled the same reading for step 3's tax panel on 2026-09-15 |
| The `CLASS R` / `CLASS D` kicker beside the screen title | it is the page head's, which is `FixABillTab.tsx`'s, and the letters were settled as *"a thing to go and look up"* on 2026-09-14 |
| A control of any kind | a step body READS. Open, approve, execute and abandon stay in the tab, which single-flights the commit (BR-SHL-019, `DEF-712`) |
| Anything for 26.2 · 26.3 · 26.4 | lanes D and E. They keep the carried body under its stated absence, and step 2 stays on the hold list until they land |

---

## 6 · Five filed, two closed — and three of the five were found by LOOKING

Two of the five are in §5 because they are the reason something drawn was NOT built:
`DEF-BIL-5355` (the class-D document diff nothing composes) and `DEF-BIL-5356` (no paid
figure on a case's pinned bill rows). The other three, and the one of lane A's this lane
closed:

| | What | How it was found |
|---|---|---|
| **`DEF-BIL-5349`** | the case status reached a clerk as `pending_approval` | filed by lane A, **closed here** — the seven words in eleven catalogues |
| **`DEF-BIL-5366`** | *Corrections so far* printed `restatement` / `credit_only` / `document` | **reading this lane's own 1440 capture**, the identical shape as 5349 on the same screen, one column away. **Closed here** — three words in eleven catalogues, no code change |
| **`DEF-BIL-5365`** | ⚠ **every restatement's line trail shows each charge line TWICE** — once removed, once added — because the original side keys on `line.service_id` (a uuid) and the corrected side on `rated.service` (the CODE). A five-line bill produces nine impact rows; only the tax line, keyed on `tax_id` on both sides, matches. It rides inside `preview_hash`, and it fires *"The lines moved; the total did not"* on a bill where **nothing moved** | **reading the rendered trail.** The carried body drew the lines as a bullet list, so nine rows for a five-line bill read as a long list. Confirmed against the stored artifact: `'usage:01a0a436-ff74…' 95.50 → 0` beside `'usage:electric' 0 → 95.50`. **Open — backend** |
| **`DEF-BIL-5367`** | a case closed WITHOUT correcting reads **Done**, the same word as one that ran | **reading the capture after the status words landed** — twelve rows reading Done, ten of them abandoned. It was invisible while the word was `done`. **Open** |

---

## 7 · Proof

| Check | Result |
|---|---|
| `npx tsc --noEmit` (local TypeScript 5.5.4 through the worktree's symlinked `node_modules`) | **clean** — and proved capable of failing first: a planted `const x: number = "s"` raised `TS2322: Type 'string' is not assignable to type 'number'` at `FixWhatStepSingle.tsx(686,7)`, then was removed |
| `npx vitest run FixWhatStepSingle.dom.test.tsx` | **29/29** |
| Seven sabotages, each in the harness that runs it | all **RED** first: hide the unmoved lines · delete 26.5's third absent panel (*expected 2 to be 3*) · make the discount heading unconditionally *safe* · draw `$0.00` for an unreadable settlement · print the status code instead of the word (six cases red at once) · unwire `26.5` from the registry map · put the status pill back above the answer band (*expected +0 to be 4*). ⚠ **The first attempt at the absent-panel sabotage was a NO-OP** — it passed `hidden` to a component that does not spread unknown props, so the guard was never actually exercised and the run came back green. Law 7's *structurally incapable of failing*, in the sabotage rather than in the check; it was rewritten to delete the panel |
| `DEF-BIL-5349`'s red, dated | measured against the tip (`05f555ed`): **zero** `billing.fix.status.*` keys existed in `en.json`, and all seven now resolve |
| `fixABillSteps.test.tsx` · `fixABillContract.test.ts` · `routeBUtilities.test.ts` · `FixABillTab.dom.test.tsx` · `BillingSurfaces.test.tsx` | **86 green** together with this lane's suite; lane F's flipped `carried` assertion passes because step 2 is still held |
| Catalogue parity | **+61 / −0 / ~0** in every one of the eleven, all at **17,542**; none of the 610 non-English values is byte-identical to its English |
| Browser walk — `10-scripts/cr101_fix_a_bill_step2_single_walkthrough.mjs` | **0 problems at 1440 and at 1280**, on a real bill through the real API: both entries rendered, no stated absence over either, the status as words, no rule id / question id / dotted identifier / uuid, every figure at two decimals, no horizontal scroll, nine lines drawn with one unmoved, the total row, the payments panel with its four figures, all three absent panels on 26.5, and `$0.00` drawn rather than implied |
| Screenshots, compared by eye against p134/p135 and p139/p140 | `SCRATCH/lane-C-shots/` — four distinct files (hashes checked), both entries at both widths. Presence, order and labels match group for group; the differences are the ones in §5 and the decision log |
| What the walk wrote to the demo tenant | **ten preview cases, all ten abandoned with a reason.** Verified in the database: `status='done'`, `closed_reason='Closed from the Fix a bill screen without correcting.'`, `executed_on IS NULL`, and **0** of them wrote a credit note, a rebill or a document instance. `BL-2608-000042` was never opened — lane A holds an approved case on it |

### Reds this lane did not cause, dated

Nothing in the suites above was red. The two the suite does not cover and that were not run
here — the full gate tier and eslint — were not re-measured after lane F's and the
orchestrator's pushes, so no claim is made about them either way; lane A's record of the same
day dates `G40`, `G15`, `G33`, `G28`, `G13`, `G17` and `screenIds.test.tsx`, and none of those
names a file this lane touched.

**One thing the browser could NOT exercise:** the seed's bills re-rate to the same total, so the
answer band's *drops* / *rises* forms and the credit sentence were driven only in jsdom. Making
a real one move would mean writing a changed read to the shared tenant, which this lane did not
do. The forms are asserted on fixtures and their absence from the walk is stated here rather
than left to be assumed.

---

## 8 · Version and rollback

**Not bumped here** — the orchestrator versions once the wave lands. The line this lane would
have written: **`2.277.0`** (a change: two screens redrawn to their blueprint), and the CHANGELOG
sentence: *"Fix a bill's second step now shows the correction itself — for one bill, every charge
line as it was, as it becomes and what changed, with the tax per authority, whether the customer's
discount survives and what they have already paid; and for a fix to the page alone, that the money
does not move at all, drawn as $0.00 rather than implied, with three panels each saying why they
do not apply. Every case status now reads in words rather than as a code."*

**Rollback:** code and catalogue only — revert the commits. No money-bearing row was written;
the ten preview cases the walk opened were all abandoned.
