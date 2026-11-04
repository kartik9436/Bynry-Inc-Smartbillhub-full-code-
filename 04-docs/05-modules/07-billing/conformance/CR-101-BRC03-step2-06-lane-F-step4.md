# `CR-101-BRC03` · step 2 · §06 **Fix a bill** · lane F — step 4 `26.8 Generate and send`, built as drawn

**Lane:** F of a four-lane wave (C: 26.1/26.5 · D: 26.2/26.3 · E: 26.6/26.7 · F: 26.8).
**Branch:** `claude/gifted-johnson-top7zn`, worktree `agent-a46c5beaba03eacfe`.
**Base tip:** `05f555ed` at the start; `9d8eafe0` at the last push — siblings landed
six defect rows, 58 catalogue keys and lane C's step-2 body while this lane was building,
and every shared path was re-derived from the pinned tip before anything went out (§7).
**Date:** 2026-09-15. **Version:** not bumped here — the orchestrator versions the wave (§9).
**Process:** `22-product-maintenance-process.md` — a live screen redrawn end to end is
MAINTENANCE. **Built through** `react-tailwind-css-ui-generator` (loaded before the first
line of TSX and again before this record) and `build-one-commitment-end-to-end`.

**What this is.** One commitment: the step-4 body of the four-step Fix a bill wizard, built
to its drawn specification AS AN IMAGE, wired into lane A's registry, its hold retired, and
proved in a browser at both staff widths against real data.

**What this is NOT.** It does not touch the frame's buttons, step 1–3, the nine-section
preview contract, or the correction engine. It writes nothing: the only button that writes
was counted and never pressed.

---

## 1 · Which pages 26.8 is on, and how they were read

**`26.8` occupies p144 and the upper third of p145**, and the section boundary is worth
stating because the orchestrator asked: §06 runs p129–p144 and **§07 `Past billing runs`
begins part-way DOWN p145**, not at its top. The top of p145 is still 26.8's own frame —
group 2's three channel rows, the two send checkboxes, the ⚠ band, the footer
(`Each bill commits on its own.` · `← Back` · `Create 12 documents & post`), the
`v2.235.0 / 1440 × desktop` caption, and 26.8's five annotations. Only below those does the
red `07` heading start. Lane A's page map says the same thing in its last row, and adds the
general fact: *"the screens do not start on page boundaries."*

**Read as images (B14 rule 42), never from the text layer:**

| What | How |
|---|---|
| p144, p145, p146 whole pages | `10-scripts/pdf/pdf_render.py "05-prototype/04 Billing, As Built.pdf" <out> 2 144,145,146` → 2448×1584, opened with the Read tool |
| p144's frame, top half (header · rail · answer band · group 1's heading) | scale **4**, cropped to the frame box, opened as an image |
| p144's frame, lower half (group 1's table, the two buttons, group 2's heading) | scale **4**, cropped |
| p145's frame (group 2's rows, the checkboxes, the ⚠ band, the footer) | scale **4**, cropped |

The crop helper is in this lane's scratchpad; `pdf_render.py` renders whole pages and a
dense table at 1584px tall is not readable, which is why the frame was cut and re-read.

---

## 2 · Reproduce · locate · blast radius

**Reproduced** at `9125aef4` in Chromium at 1440 against the demo tenant: step 4 rendered
the carried body — *New layout not built yet.* over three generic section cards, the
server's 85-word no-rollback paragraph, and nothing the drawing draws. All 23 of this
lane's new cases were run against it and **19 of the 23 went red**, every one on the same
first fact: there is no `fix-send-group-1` and the screen draws no table at all. (The four
that stayed green read `en.json` and `corrections.py` rather than the screen, and the test
file says so.)

**Located:** `07-frontend/src/features/billing/fixABillSteps.tsx` — the registry
`FIX_A_BILL_BODIES` — mounted by `FixABillTab.tsx` at `/:tenant/billing/fix`
(`BillsListPage.tsx`) and `/:tenant/accounts/:accountId/issue-credit` (`App.tsx`). Both
doors kept; step 4 is reached through the rail from either.

**Blast radius, both ways.** Inbound: nothing imports a step-4 body except the registry.
Outbound — **what USED the thing being replaced**: `CarriedGenerateAndSendBody` was
rendered only by the registry, so pointing the slot at `FixSendStep` made it dead UI, and
`G40` named it by name. It is DELETED in the same commit (§6), which is why
`STEP4_SECTIONS` also left `fixABillSteps.tsx`'s imports — `FixSendStep.tsx` imports it
from the contract instead and marks each group with it, so BR-BIL-044's 3 + 3 + 3 deal is
still provable from the rendered screen.

---

## 3 · Before and after, measured on the running product

| | Before (`9125aef4`, Chromium 1440) | After |
|---|---|---|
| The head of step 4 | *New layout not built yet.* | the drawn answer band — **This step writes 2 documents. 2 entries in the books.** |
| What will be created | one generic card listing `documents: …` as the server's prose | a **table** — `Credit notes 1 · One per old bill, cancelling it` · `Replacement bills 1 · The corrected amount, original due date` · `Ledger entries 2 · Nothing — these are yours` |
| How it goes out | a card printing *"print is the floor and is what every bill gets. The delivery ELECTION (`accounts.paperless`) is PROPOSED-SCHEMA…"* | a **table** — `Print · Will go · Every document prints.` and `Other channels · Not offered here · Print is the only route.`, with *Printing starts on commit. Holding is not offered.* |
| The gate | a card with `approver_role`, `br_ref`, `status`, `preview_hash` and a 60-word statement citing `BR-BIL-044` | **Approved.** · *Only a System Admin can approve this.* · *Nothing is written yet. Approving locks these figures.* |
| No undo | the server's five-sentence, 85-word paragraph citing *(hard rule 4)* | the drawn ⚠ band — **NO UNDO** · *Entries and documents cannot be undone. Fix it with a new correction.* |
| Internal references on screen | `BR-BIL-044`, `BR-BIL-036`, `OQ-072`, `accounts.paperless`, `hard rule 4`, a `preview_hash` | **none** — asserted over the rendered DOM at both widths and in jsdom |
| Database ids on screen | none visible on this step | none, and now **guarded**: four gate states walked for a uuid (`DEF-BIL-5357`) |
| Buttons the body draws | 0 | 0 — the one that writes stays the frame's |
| Catalogue keys `billing.fix.send.*` | 0 | **45**, all eleven catalogues at **17,537** |

---

## 4 · What the drawing draws, and what was built for it

| Drawn (p144–p145) | Built | Why, where it differs |
|---|---|---|
| Answer band *"This is the first thing that writes. Twelve documents, and twelve entries in your books."* | **This step writes {n} documents. {n} entries in the books.** | The figures are the payload's, never the drawing's (B14 rule 37). Two sentences of five words each — rule 33's consequence cap. *In the books* is rule 34's ratified pair |
| `1 WHAT WILL BE CREATED` · COUNT · THE CUSTOMER GETS | the same three columns, the first with no visible header (the rows are `<th scope="row">`) | as drawn |
| `Credit notes 6` · `Replacement bills 6` · `Ledger entries 12` | the same rows, counted off the payload | **the KINDS come from the class and the COUNTS from the bills.** Each kind's count is the number of bills that really carry a document at that position, never `bills × a number typed here` |
| *"One per old bill, cancelling it"* · *"At the corrected amount, original due date"* · *"Nothing — these are yours"* | the first and third verbatim; the second as **The corrected amount, original due date** | 7 words → 6 (rule 33's fact cap) |
| `See a credit note →` · `See a replacement →` · *"Neither writes anything."* | **NOT BUILT** | nothing has been created yet, and there is no endpoint that previews a document that does not exist. A button that opens nothing is dead UI (hard-won law 2), the same reason lane A refused a run chip the server ignores |
| *"Both documents go — a replacement alone leaves two bills for one month."* | **Both documents go together.** | the clause after the dash is RATIONALE, which rule 33 puts at zero words on screen. Drawn only where the class makes two documents |
| `2 HOW THEY GO` · CHANNEL · NOW · WHY | the same three columns | as drawn |
| `Print · Will go · The floor. Every document prints` | **Print · Will go · Every document prints.** | *"The floor"* is our word, not a clerk's |
| `Email · Not available · Needs a channel election we do not publish` and `Text · In-app · Portal · Not available · Not named in billing's delivery seam` | **ONE row — Other channels · Not offered here · Print is the only route.** | two reasons at once. Both WHY cells are internal rationale (rule 33), and the CHANNEL cells are a **hand-typed channel list billing's own seam does not name** — `what_the_customer_will_receive.channels` serves `["print"]` and nothing else. Typing the rest here is the eleventh-service mistake: it rots silently the day a channel arrives. Served channels get a row each; everything else gets one row that says the same thing to a clerk. **This is the largest visible difference from the drawing and it is a judgment, so it is in the decision log** |
| `☑ Print all twelve now` · `☐ Hold them for next month's run` | **NOT BUILT**; the fact is stated instead — *Printing starts on commit. Holding is not offered.* | `POST /corrections/{id}/execute` takes `issued_at` and `on_date` and has no hold field. A checkbox the server ignores is dead UI |
| *"Only what can leave the building is offered."* | folded into the sentence above | rule 32's description budget: one sentence per section |
| `⚠ AFTER THIS THERE IS NO UNDO` | **NO UNDO** | a heading is ≤ 3 words (rule 33) |
| *"A posted entry cannot be un-posted and a sent document cannot be un-sent. The remedy is a new correction over exactly these bills."* | **Entries and documents cannot be undone. Fix it with a new correction.** | a consequence before an irreversible act: two sentences, six words each, and nothing cut below clarity |
| The page head's *"approved by M. Okonkwo, 12 Sep"* | **Approved.**, naming nobody | `DEF-BIL-5357` — the server serves `approved_by` as a bare uuid. §5 |
| Footer *"Each bill commits on its own."* | drawn, at the END of the step content, only where the case holds more than one bill | rule 38 / `DEF-1083`: a row of controls holds only things a person can press. One bill commits on its own by definition |
| Footer `← Back` · `Create 12 documents & post` | the frame's action row, `commitVariant="danger"` | the body adds no button — §5's first row |

**Two things the drawing does not draw that are on screen, and both are required:**
`3 APPROVAL` is a numbered group because `the_gate` is one of BR-BIL-044's nine sections
and *"all required, none collapsible away"*; the drawing puts the approval fact in the page
head, which is the frame's. And `Close without correcting` (BR-BIL-047) is the frame's
secondary action, reachable from step 4 as the drawing places abandoning in the flow.

---

## 5 · Judgments where the rules ran out

**(a) The body draws; the frame writes — and the brief and the contract disagreed.**
The lane brief said *"move that behaviour into your step body"* for approve and execute.
`fixABillContract.ts` says the opposite, in terms: *"A body READS; it never opens,
approves, executes or abandons… a body drawing its own button would lose that guard
(DEF-712)."* The contract wins, and the reason is not deference: the frame single-flights
the commit (BR-SHL-019), renders A18 §3's working state and A18 §4's
failure-with-entered-state-preserved, and a second button beside it keeps none of the
three — which is `DEF-712` word for word. The calls were not re-implemented and were not
moved; approve is still step 3's Continue and execute is still the frame's commit, and they
are still TWO acts. **The body adds no button at all, and a test asserts that.**

**(b) The drawn button counts its documents and the frame's label does not.**
p145 draws `Create 12 documents & post`; the tab passes the uncounted
`billing.fix.commit.createAndPost`. `WizardFrame.commitLabel` is already a `ReactNode` for
exactly this, so the change is one line in a file this lane may not edit. **The hunk lane A
(or the orchestrator) applies is in §10.** It was not worked around: a second, counted
button here would be the `DEF-712` mistake with better manners.

**(c) One "Other channels" row instead of the drawn two.** Recorded in §4 and in the
decision log, because it is the one place a person comparing the screen to the drawing will
see a row missing. If the Product Owner wants `Email` named, the honest way is for the
server to serve the channels it knows about with a state each — which is what the bill
run's own send step already does.

---

## 6 · Holds retired, and the one I made worse before fixing it

| Hold | What happened |
|---|---|
| `26.8` on `HELD_FIX_A_BILL_STEPS` | **RETIRED.** `FIX_A_BILL_BODIES` points at `FixSendStep` with `carried: false` and the step left the held list, both in one commit. Lane A's *hold 1* was watched to fail first and named the file: *"FixSendStep.tsx is built against FixABillStepBodyProps and no step opens it."* |
| `fixABillSteps.test.tsx`'s *"gives steps 2 · 3 · 4 a CARRIED body"* | **FLIPPED, not deleted.** That case asserts `carried === true` for all three, which is true only while all three are held — so the day a drawn body landed the suite went red on the very thing it was waiting for. The FLOOR is unchanged and is the half that matters: every step 2–4 must still have a non-null body. What moved is the second half — `carried` is asserted against the hold list, so a HELD step must still render yesterday's body and a RELEASED one must not. Lanes C, D and E inherit the fixed form |
| `CarriedGenerateAndSendBody` | **DELETED in the same commit.** The moment the registry stopped pointing at it, `G40` counted it as dead UI by name and its total rose by one. Landing a screen and removing the thing standing in for it are two acts and only the first feels like the work; the second is done here. Nothing else referenced it (grepped `07-frontend/src`, `06-backend`, `10-scripts`, `04-docs` first) |

---

## 7 · Proof

| Check | Result |
|---|---|
| `npx tsc --noEmit` (local TypeScript, `node_modules` symlinked) | **clean** — and proved capable of failing first: a planted `const x: number = "…"` raised `TS2322` at `FixSendStep.tsx(454,7)`, then was removed |
| `npx vitest run FixSendStep.dom.test.tsx` | **25/25.** Proved red first, in the harness that runs them: pointing the registry back at the carried body turned **19 of 23** red. Then seven sabotages one at a time — §7a |
| `fixABillSteps.test.tsx` | **9/9** with the flipped case; the flip was watched to fail before it was written (`fix-generate-and-send: expected false to be true`) |
| `FixABillTab.dom.test.tsx` · `BillingSurfaces.test.tsx` · `styles/routeBUtilities.test.ts` | **all green, 73 cases across five files** |
| `eslint --max-warnings 0` on this lane's three files | **clean** |
| Catalogue parity | **+45 / −0 / ~0** in each of the eleven, all at **17,537**. 46 keys were fanned in through `i18n_fanin.py` and one (`state.approvedBy`) was removed again by bytes when `DEF-BIL-5357` was found — one line per file, every other byte proved identical to the tip |
| Tailwind ledger | `features/billing/FixSendStep.tsx` added in the commit that creates it; `routeBUtilities.test.ts` 11/11 |
| Browser walk — `10-scripts/cr101_fix_a_bill_step4_walkthrough.mjs` | **0 problems at 1440 and at 1280** on the final build. Three groups in the drawn order, the band's counts, the three document rows with their captions, the two channel rows, the gate's four states, the ⚠ band, no uuid, no internal id, no button in the body, the commit in the **danger** tier, `Close without correcting` reachable, no horizontal scroll |
| What the walk wrote | **one preview case per width on `BL-2608-000043`**, each walked to step 4 through step 3's approval — a signature and no money (BR-BIL-014) — and each **ABANDONED with a reason** afterwards. `Create the documents & post` was counted and never pressed. §8 |
| Gates — `run_gates.py --changed 9d8eafe0` | 35 PASS · 40 FAIL · 2 SKIP of 77 run (49 not run). **One finding named this lane's work and it is fixed above** (`G40`, `CarriedGenerateAndSendBody`). Every other red is dated in §8 |

### 7a · The seven sabotages, and what each one actually named

Two surprised their author, and both are written into the test file rather than smoothed over:

| Broken | Red |
|---|---|
| the registry pointed back at the carried body | **19 of 23** — no `fix-send-group-1`, no table at all |
| the ledger count hard-coded to `bills × 2` | **2** — the goodwill case (`2` where the payload says `1`) and the page-only case (`2` where it says `0`). ⚠ It did **not** move the batch case, and the first draft of the comment claimed it would: a batch has no section at all, so the `null` return happens BEFORE the arithmetic. *Not counted* is guarded by the absence, never by the multiplication |
| the gate reading `status` alone | **1** — the abandoned case claiming the correction had been written |
| the server's `standing_statement` rendered | **5**, and the shared internal-reference helper named `BR-BIL-044` by itself |
| a `<button>` added to the body | **1** — the no-second-button case |
| a fourth document on a class's kind list | **1** — the engine tie-out, `[2, 1, 1]` against `[2, 1, 2]` |
| one `SectionMark` removed | **1** — the BR-BIL-044 deal, two marks where three are dealt |
| the word counter pointed at a known-long key family | **1** — so it is capable of failing rather than passing over an empty set |

⚠ **The engine tie-out's first draft was a regex and it was WRONG.**
`documents = \(([\s\S]*?)\n\s*\)` counted the class-D tuple as **3**, because that tuple is
written on ONE line and the lazy match ran on to the next closing paren in the file. It now
walks characters — paren depth, string literals skipped whole — and the helper says what
would still make it miscount.

---

## 8 · Every red, with its date

| Red | Dated how |
|---|---|
| `G40` unmounted components, **13 now, 0 baselined** | **RED AT THE TIP AND THIS LANE ADDED ONE.** Lane A's record dates the tip's 11 (`AuditEventInlineCell` 2026-09-09, `CyclesOpsPage` 2026-09-14, `LevelCell` 2026-09-14, `OpenBalanceLine` 2026-09-04). The 12th was **this lane's** — `CarriedGenerateAndSendBody`, dead the moment the registry moved — and it is deleted above. The 13th is **lane C's** `FixWhatStepSingle`, assigned through a computed `Object.fromEntries` map the gate cannot read; that is lane C's to answer |
| `G98` eslint RED, 10 files | none is this lane's: `assets/AssetLifecycle.test.tsx`, four `customers/` files, four `metering/` files. This lane's three files pass `eslint --max-warnings 0` |
| `G15` **403** new untranslated values | the same 403 lane A measured at the tip on 2026-09-15 before its own keys landed; none of this lane's 495 non-English values is named |
| `G33` three refusals over six words | the same three lane A dated to `cf45a3d2`, 2026-09-13 — `integrations.field.site_id`, `metering.import.parts_unwired`, `portal.documents.queueUnavailable`. None of this lane's 45 keys is named |
| `G13` unwired props (3 files) | `customers/AccountUsageTab.tsx`, `AccountCommunicationDialog.tsx`, `portal/components/listTable.tsx` — not this lane's; `AccountUsageTab.tsx` last moved `f6fa3670`, 2026-09-13 |
| `G17`, `G28`, `G29`, `G32`, `G44`, `G61`, `G67`, `G72`, `G95`, `G103`, `G105`, `G106`, `G113`, `G114`, `G116` and the rest of the 40 | files this lane never touched. `G113` names `DEF-BIL-5349` as fixed-but-open, which is a sibling's row to close |
| **The raw enum codes in *Corrections so far*** — `restatement`, `document`, `credit_only` under WHAT IT DOES, visible in this lane's own screenshots | **already filed as `DEF-BIL-5250`** (2026-09-14) and **half fixed**: a sibling landed the seven `billing.fix.status.*` keys, so STATUS now reads *Approved* and *Done*; `billing.fix.class.*` does not exist in any catalogue, so the class half is still live. Not re-filed |
| The one `credit_notes` row on the demo tenant | created **2026-09-15 08:53:43 UTC**, nearly four hours before this lane's stack was started. Not this walk's — no case on the tenant has `executed_on` set |

---

## 9 · What was NOT built, and what needs somebody else

| Not built | Who |
|---|---|
| `See a credit note →` / `See a replacement →` | nobody, until there is an endpoint that previews a document that does not exist yet. §4 |
| The two send checkboxes | nobody, until `POST /corrections/{id}/execute` takes a delivery timing. §4 |
| Naming `Email` and `Text · In-app · Portal` as their own rows | the server: `what_the_customer_will_receive` serves one channel and no state for the others. §5(c) |
| The counted commit label | **lane A's file** — the hunk is §10 |
| The approver's NAME on the gate and in the page head | `DEF-BIL-5357` — billing needs rating's `{id, name}` user-display seam |
| Opening a case from *Corrections so far* and seeing it | `DEF-BIL-5369` — the link loads the case and the rail stays on step 1 |
| A caption that can be resized by its caller | `DEF-SHL-5370` — `.text-xs` is emitted after `.text-sm`, so `<Note className="text-sm">` does nothing; this lane reverted its own dead class rather than leave one in the DOM |
| The tax panel, steps 1–3, the nine-section contract, the engine | out of scope by the brief |

---

## 10 · The one hunk this lane needs in a file it may not edit

`07-frontend/src/features/billing/FixABillTab.tsx`, the `WizardFrame` call — so the drawn
`Create 12 documents & post` counts its documents. `commitLabel` is already a `ReactNode`,
and the count is `bills_detail`'s own documents, the same number the band prints:

```tsx
commitLabel={t("billing.fix.commit.createAndPost", {
  count: (detail?.bills_detail ?? []).reduce(
    (total, row) => total + (Array.isArray(row.impact?.documents) ? row.impact.documents.length : 0),
    0,
  ),
})}
```

with `billing.fix.commit.createAndPost` becoming a plural pair in the eleven catalogues —
`Create {{count}} document & post` / `Create {{count}} documents & post`. It is one line
and eleven strings; this lane did not take it because the file is lane A's and four lanes
are editing that file this hour.

---

## 11 · Version and rollback

**Not bumped here** — the orchestrator versions the wave. The line this lane would have
written: **`2.277.0`** (a change: a screen redrawn to its blueprint), and the CHANGELOG
sentence:

> *"Fix a bill's last step is the blueprint's — before the one button that writes, a clerk
> sees what will be created and how many of each, that print is the only way it leaves the
> building, and that approval has bound these exact figures and nothing has been written
> yet; the step counts every document off the bills themselves and says *Not counted*
> rather than guessing where the server cannot tell it."*

**Rollback:** code only — revert the three commits. Nothing money-bearing was written: the
two cases this lane opened were abandoned with a reason, and the case a sibling had left
approved on `BL-2608-000042` was abandoned too, so both bills are free and still `issued`.

---

## 12 · The screenshots handed to the Product Owner

In `SCRATCH/lane-F-shots/`, eight files, hashes checked distinct:

| File | What it shows |
|---|---|
| `step4-1440.png` · `step4-1280.png` | the whole page at both widths, step 4 on a fresh approved case |
| `step4-frame-1440.png` · `step4-frame-1280.png` | the wizard frame alone — the picture to put beside p144/p145 |
| `step4-after-abandon-1440.png` · `step4-after-abandon-1280.png` | the same case after `Close without correcting` |
| `step4-approved-case-opened-from-the-list-1440.png` | `DEF-BIL-5369` as a clerk sees it: the approved case opened from *Corrections so far*, and step 1 still on screen with nothing about it |
| `step4-approved-case-abandoned-1440.png` | that case abandoned with a reason, never executed |

<!-- ── Lifecycle ─────────────────────────────────────────────
packet: CR-101-BRC03@lane-F (sources: 05-prototype/04 Billing, As Built.pdf §06 entry 26.8 — p144 and the upper third of p145, read as images at scale 2 and 4 · CR-101-BRC03-step2-06-lane-A-step1.md §1 · 06-backend/apps/billing/{single_correction,bulk_corrections,corrections,corrections_api,selectors}.py)
generated: 2026-09-15 by lane F (Fix a bill step 4)
status: VERIFIED-UNRATIFIED
────────────────────────────────────────────────────────── -->
