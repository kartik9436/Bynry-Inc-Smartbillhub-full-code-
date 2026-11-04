# `DEF-BIL-5247` · the bill run becomes FOUR steps — conformance record

**PO ruling 2026-09-14, verbatim:** *"we have 4 step only now in bill run"*, said after putting
our screenshot beside the blueprint and asking *"does this mean you did not build the plumbing
also the way we have detailed out in document?"*

**Source, and how it was read.** `05-prototype/04 Billing, As Built.pdf`, taken off the DEFAULT
branch (`origin/claude/confirm-understanding-3ktufc`) and checksum-verified before it was
trusted — **14,363,163 bytes, sha256 `137a2a48c0398c39897f49aa…`**. Every page below was read
**as an image** at scale 2.0, and at 3.0–5.0 where the type is small (B14 rule 42). The text
layer was used only to find a page and to cross-check a spelling.

---

## 1 · THE CARRY-OVER MAP, TRANSCRIBED FROM p86–p88 — THE ACCEPTANCE TEST

The document's own words: *"Merging three steps into one is the change most likely to drop
something quietly, so this table is one row per element across all six original steps."*

**25 rows, 38 element-instances once the `×N` multipliers are counted.** ✅ = carried across and
still on screen after this change; ⏳ = carried, and still rendered by the component it came
from rather than by the blueprint's single table (the redraw is wave 3).

| # | Element on the six steps | Disposition | Where it lands | |
|---|---|---|---|---|
| 1 | Billing cycle select · Bill date | UNCHANGED ×2 | Step 1, group **The cycle** | ✅✅ |
| 2 | Step 1's *What this step no longer asks you* panel | REMOVED | ruled — its content is in the document | ⏳ still on screen (`RunGap` step1) |
| 3 | Past runs table | MOVED | Step 1, group **Already run for this cycle** | ⏳ on step 1, not yet cycle-scoped |
| 4 | The *no actor column, money not served* panel | REMOVED | ruled by fact — `run_by` exists and is served | ⏳ still on screen |
| 5 | Step 2's six sub-tabs | MOVED ×6 | Step 2's filter chips, each with a count | ⏳ still TABS on step 2 |
| 6 | Step 2's KPI band (ready · blocked · decisions · silent) | RELABELLED | Step 2's band, in a clerk's words | ⏳ on step 2, old words |
| 7 | Step 2's per-row facts (meter, this period, average, ratio, threshold) | UNCHANGED | Step 2's *What is wrong* cell | ✅ |
| 8 | Step 2's *base charges are not gathered* cell | REMOVED | ruled by fact — `gather.py:699-705` gathers them | ⏳ still on screen |
| 9 | Step 3's 16 case kinds | MOVED | Step 2's chips and rows — **the nine the engine emits** | ✅ already nine (`G124` PASS) |
| 10 | Step 3's per-row decision select | UNCHANGED | Step 2's *What to do* column, amount beside it | ✅ **and now the screen's ONE control** |
| 11 | Step 3's bulk actions, and the refused waive | UNCHANGED ×2 | Step 2's selection bar | ✅✅ |
| 12 | Step 3's *a choice here has nowhere to be recorded* panel | MOVED | a per-row state | ⏳ still a panel |
| 13 | Step 3's *no charges are gathered yet* panel | UNCHANGED | the absence of two chips | ⏳ still a panel |
| 14 | Step 4's KPI band (bills · total · left out · broke) | MOVED | Step 2's band, live from the first paint | ✅ **now on step 2** |
| 15 | Step 4's three overcharge action words | RELABELLED | a real filter chip and a real control | ⏳ still inert |
| 16 | Step 4's *flagged bills cannot be listed* panel | REMOVED *(conditional)* | **only once the list exists** — `DEF-2855` is open, so **the panel MUST STAY** | ✅ kept, correctly |
| 17 | Step 4's three draft powers panel | RELABELLED | two become row actions; the third keeps its refusal | ⏳ |
| 18 | Step 4's per-account retry and hold | UNCHANGED ×2 | Step 2's row actions | ✅✅ **now on step 2** |
| 19 | Step 5's five gate facts | UNCHANGED ×5 | Step 3. BR-BIL-058 untouched | ✅×5 |
| 20 | Step 5's recomputed totals + the as-at-signing caveat | UNCHANGED ×2 | Step 3, in one sentence | ✅✅ |
| 21 | Step 6's *Nothing leaves the building* | UNCHANGED | Step 4, word for word | ✅ |
| 22 | Step 6's Issue action | UNCHANGED | Step 4 | ✅ |
| 23 | Save & exit | UNCHANGED | Steps 1–3 | ✅ |
| 24 | *Park*, disabled on all six steps | REMOVED | ruled by fact — it cannot work and its reason is false | ⏳ still drawn disabled |
| 25 | The six-tab Billing strip in the wizard header | UNCHANGED | kept — it is how a clerk leaves sideways | ✅ (seven tabs today) |

**NOTHING IS LOST: every one of the 38 is still reachable on the four steps.** Fourteen are ⏳ —
carried by the component that drew them on six steps rather than redrawn into the blueprint's
shape. **Nine of the fourteen are elements the document REMOVES or RELABELS**, so they are
debt in the honest direction: the screen shows more than the drawing, never less.

### ⚠ THE DOCUMENT'S SUMMARY BLOCK DOES NOT RECONCILE WITH ITS OWN ROWS

p88's block reads *"unchanged 19 · moved 9 · relabelled 4 · removed 5"*, which sums to **37**
against its own stated total of **38**. Counted off the rows above with their multipliers:
**unchanged 20 · moved 10 · relabelled 3 · removed 5 = 38.**

The two totals that MATTER do hold, and were reproduced rather than taken on trust:
**38 elements**, and **47 = 38 − 5 removed + 14 new** — where the fourteen come out only if
*"3 defaults"* is read as ONE element (`scope · sweep-up · 3 defaults · label · open-run
takeover · search · chips-with-counts · Amount column · plain-words cause · link-out to fix ·
re-price · pagination · reconciling count · print door`). **The row table is the acceptance
list.** Recorded, not resolved — nobody should re-derive the split from the block.

---

## 2 · THE RAIL

p35, verbatim: *"The wizard rail now reads **Scope · Check · Sign off · Send**. It was What to
bill · Review · Sign off · Send, and Review was the wrong word for the step: reviewing is what a
clerk does ON it, and what the product does TO GET THERE is a check."*

Built, and walked in Chromium at 1440 and 1280 against a real seeded run: the rail reads
`1 Scope · 2 Check · 3 Sign off · 4 Send` on all four steps, and the resume band reads *"This run
is at 'Bills sent', so it opens on step 4, Send."*

---

## 3 · SCREEN 17's CHIP TAXONOMY — READ OFF p51, AND TIED OUT

**Seven category rows, twenty-six chips.** Rows 4–6 are INDENTED sub-rows of *Held*, drawn with a
corner glyph; counting only the un-indented rows gives four, which is how a reading lands on
three or four categories.

| # | Category | Chips | n |
|---|---|---|---|
| 1 | **Needs you · 12** | Missing read 4 · Unusually large 3 · Unusually small 1 · No usage 1 · Unusual days 1 · Meter changed 1 · Multiplier changed 1 | 7 |
| 2 | **Answered by your default** | Estimated 44 · Base charge only 31 | 2 |
| 3 | **Held · 21** | Never calculated 15 · Calculated and broke 6 | 2 |
| 4 | ↳ **Where the fix is** | The account or the plan 3 · The read 2 · The rates 1 | 3 |
| 5 | ↳ **The reason** | Master coverage 1 · City limits not recorded 1 · No base charge for this type 1 · Cart count missing 1 · Reading disputed 1 · No rate version in force 1 | 6 |
| 6 | ↳ **How long it has waited** | Under 14 days 10 · Escalated 9 · Over 60 days 2 | 3 |
| 7 | **Everything else** | Ready 1,251 · Masters 11 · In arrears 312 | 3 |
| | | **total** | **26** |

**THE TIE-OUT IS WHAT MAKES THIS A READING RATHER THAN A GUESS**, and every level holds:

* 4+3+1+1+1+1+1 = **12** = the *Needs you* header **and** the `NEEDS YOU` KPI cell
* 15+6 = **21** = the *Held* header **and** the `HELD` KPI's own *"15 by a default · 6 blocked"*
* 10+9+2 = **21** — the waiting-time chips sub-divide the whole held band
* 3+2+1 = **6** and 1×6 = **6** — both sub-divide the six that *calculated and broke*
* and the screen's own reconciling line: 1,251 + 12 + 21 + 0 = **1,284**

Cross-checked against the blueprint's build index (p165–p166), which gives most of them their own
layer entry: **17.1–17.7** are the seven *Needs you* chips (No read · Unusually large · Unusually
small · Zero use · Unusual days · Meter changed · Multiplier), **17.8–17.9** the two defaults
(Estimated · Base only), **17.10–17.15** the held/fix/ready/masters set (Held now · Account fix ·
Read fix · Rates fix · Ready · Masters), **17.16–17.20 and 17.22** the bulk actions (Estimate all ·
Hold these · Accept · Confirm factor · Waiver · Apply all), and **17.21** *In arrears* — a NEW
CHIP in *Everything else*.

⚠ **ONE DISAGREEMENT INSIDE THE DOCUMENT, RECORDED AND NOT RESOLVED.** p53's band table says
*Held* carries *"Four — by a default, and three by where the fix is"* chips; the p51 drawing
shows **two** under *Held* plus the three. The drawing plus the tie-out above is what is recorded
here. `DEF-BIL-5257`.

**The product today has none of this**: step 2 draws six TABS (Consumers · Plans & Rates · Meter
reads · Open balances · Credits · Charges to add), not seven chip rows with counts.

---

## 4 · SCREEN 16 SCOPE — THE FIVE GROUPS, AND WHAT IS ACTUALLY THERE

p46's own banner: *"Two inputs become five groups, and pricing starts here."*

| Drawn group | What it holds (p47) | Built? |
|---|---|---|
| **THE CYCLE** | Billing cycle ▾ with the site in its helper · Period (LAST / THIS, read-only, with the gap-overlap verdict) · Bill date · Due date | **PARTLY** — cycle, helper, continuity band, bill date and due date are built. **The period is two EDITABLE date pickers; the drawing and its own p48 annotation both make it READ-ONLY text derived from the cycle** |
| **SCOPE** *(new)* | ① Which accounts ▾ (*"Or a route, an area, or a named set"*) · ② Also include ☑ the accounts held from the last run (*"Waiting 11–27 days"*) | **NOT BUILT** — no route/area/named-set scope and no held-account sweep-up |
| **WHAT THIS COVERS** | five count cells — Units in the cycle · Accounts to bill · Master accounts · Meters this cycle · Points with no meter — then the service badges and *"3 unresolved from the last run → see the held queue · Last time: 1,263 bills"* | **NOT BUILT** |
| **DEFAULTS** *(new)* | ③ When there is no reading ▾ · When a bill looks unusually large ▾ · Unusual days ▾ · ④ Label this run | **NOT BUILT** — the document calls it *"the single biggest error-reducer in this redraw"* |
| **ALREADY RUN FOR THIS CYCLE** | a table (Run · Label · Started · By · Accounts · Status · Actions) with **Take it over**, and ⑤ *"Dana Reyes has this cycle open."* | **PARTLY** — `PastRunsPanel` exists on step 1, is not scoped to the cycle, has no label, no actor column and no takeover |
| commit bar | *"About three minutes, in the background. You can close this tab."* + **Check this run →** | **NOT BUILT** — the frame's generic *Continue* |

**Every one of these needs a server contract that does not exist** (a scope read, five counts,
three run-level default columns and a migration, a cycle-scoped runs read with a takeover write).
That is why this record stops here rather than half-landing a migration on a money path.
`DEF-BIL-5255` is the row; the chip taxonomy's own gap is `DEF-BIL-5256`.

---

## 5 · WHERE THE DOCUMENT DISAGREES WITH ITSELF, AND WHAT WON

B14 rule 37 — a drawn figure is an ILLUSTRATION — and the ruling that **where a drawing and its
own annotation disagree, the ANNOTATION is the specification**.

| | p35 (the zone sketch) | p46–p48 (the screen frame + its annotation) | Taken |
|---|---|---|---|
| screen 16's shape | *"three zones and a commit bar"* | **five groups** (p46's own banner) | the frame |
| the sub-line | *"nothing has been written yet"* | *"nothing has been created yet"* | the frame |
| the period | `Period start 📅  Period end 📅` — editable | read-only LAST/THIS rows, and p48 in words: *"the period is read-only text"* | the frame + annotation |
| the commit | *"Prepare — looks, writes nothing, takes ~2 min →"* | **Check this run →** over *"About three minutes, in the background"*, and annotation ⑥ agrees | the frame + annotation |

One more, left open: **screen 18's header action is drawn as *Back to Check***, while the
carry-over map row 23 says *Save & exit* is UNCHANGED on steps 1–3. Both are the document's.
Screen 18 was renumber-and-relabel only in this change, so nothing was moved for it.

---

## 6 · WHAT THIS CHANGE ACTUALLY DID

* `BILL_RUN_STEPS` is four; `phaseOfStep`, `runStepFromParam`, `stepForPhase` and the resume band
  all follow from the array. **The phase words did not move** — `prepare · breaks · summary ·
  release`, one step each, the same four the six carried.
* The decision control has ONE owner on the merged screen (`RowDecision.readOnly`, required).
* The step number is DERIVED (`stepNumberOf`), not a catalogue literal in eleven files.
* Eleven catalogues: 5 keys added, 17 retired, parity 16,826 each. **NATIVE-REVIEW-OWED** in ten
  of the eleven (B14 rule 35).
* Billing suites: **404 cases, 1 failure, pre-existing** (the bills-list search census, proved red
  at the tip in a detached worktree, introduced 2026-09-13 in `cf45a3d2`).
* Gates: **51 fail against 49 at the tip**; both extra are a sibling's untracked in-flight file
  (`G27`, naming `billing.fix.*` / `billing.oneTime.*` keys — no family this change touched) and
  `G87` flipping SKIP↔FAIL on an interpreter check over Python nothing here edited.

---

## 7 · ⚠ THE VERSION BUMP IS OWED, AND DELIBERATELY NOT TAKEN

`13-change-process.md` step 7 exists because the version step is *"many times not followed
correctly"*, so this says plainly why it was not taken rather than leaving a silence.

At the moment this landed, the shared working tree held **an UNCOMMITTED bump to `2.263.1`** in
`07-frontend/package.json` and `06-backend/pyproject.toml`, with eleven changelog lines, belonging
to another lane (the one-time bill wizard). `10-scripts/allocate.py version` asks the REMOTE, and
the remote's newest is `2.263.0` — so the allocator would have handed back `2.263.1` as well, and
two lanes would have shipped one number. That is `DEF-GOV-3756`'s shape exactly.

Writing `2.263.2` over those files instead would have reverted a sibling's in-flight bump, which
CLAUDE.md law 11 forbids by name and which no check in this repo can see.

**So neither version file nor `CHANGELOG.md` was touched.** The bump for this work is OWED: take
it once the sibling's `2.263.1` is on the branch, with `allocate.py version --bump fix --verify`,
and give this record's section 6 its changelog paragraph then.

---

## 8 · ⚠ THE 26 CHIPS MUST NOT BE COUNTED IN THE BROWSER — `DEF-BIL-5258`

**Screen 17's redraw was NOT reached by this change** and this section exists so the lane that
does reach it does not inherit the pattern that is there today.

**WHAT IS THERE TODAY, verified in the source rather than taken on trust.** Every count on the
Check screen is the length of an array the browser was sent —
`billRunStep23.tsx:229 findings.ready.length`, `:238 findings.blocked.length`,
`:214 facts.cases.filter((row) => row.chosen === null).length`, `:857 counts = { all: rows.length }`,
`:1423 consumersKicker { count: findings.ready.length }`. The endpoint behind them is unpaginated
by declared design and its own docstring (`selectors.py` around line 2983) records the cost:
*"At 1,000 accounts the pass is 66,053 SQL statements and this endpoint is 66,054"* and *"a clerk
pays for the whole pass on every refresh, and at that size waits about two minutes"*.

**Twenty-six chips means twenty-six client-side filters over that same fetched array.** On the
repo's own measured ~66 statements per account, 10,000 accounts extrapolates to roughly 660,000
statements per refresh — in the core journey of the **T5** tier, which `CLAUDE.md` puts squarely
in scope at up to 40,000 accounts.

**A CACHE IS NOT THE ANSWER AND IS NOT REOPENABLE.** `OQ-843` is CLOSED on a PO ruling —
*"it is dyanmic, so at the time of compute if data is changed, process will dynamically use it
becuase it will collect data at that instansce"* — and the docstring ends *"A lane may not reopen
this by proposing a cache."* That stands.

**WHAT THE DOCUMENT SPECIFIES INSTEAD, and it is why pricing moved to step 1.** p48: `run_calculate`
runs *"phase 1's prepare pass (which writes nothing), then one DRAFT per ready account"*, and
*"step 2 opens with money on every row"*. **Drafts are real rows**, so the 26 counts are `GROUP BY`
aggregates over those drafts and the exception rows the pass recorded — recomputed per request, so
nothing is cached and the ruling is honoured, and no account row is materialised to be counted.
The table under the chips then paginates normally (B14 rule 16), and p52's annotation ⑧ marks
`/findings`, `/exceptions`, `/pricing-shadow` and `/breaks` as unpaginated and the pagination as
NEW work under **`NFR-3`** — which `CLAUDE.md` already lists as breached in four places that cite
the retired 3,000-account ceiling as their excuse. This would be the fifth.

⚠ **AND THE DOCSTRING'S REASON FOR NOT PAGINATING DISSOLVES ONCE COUNTS ARE SERVED SEPARATELY.**
It reads *"A page of it would make `ready.length` a page size, and the screen would confidently
report the wrong number of accounts."* That is true only because the screen counts rows it was
sent. Serving the counts as aggregates removes the reason, so pagination stops contradicting that
decision and starts being what makes it safe.

### ⚠ ONE CORRECTION TO THE BRIEFING THIS SECTION CAME FROM

It says the background mode *"has existed and gone uncalled"* and that **nothing in the front end
ever asks for it**. **That was true when the blueprint was drawn (p48 dates it *"since 11
August"*) and it is not true of `/calculate` today.**
`billRunEndpoints.ts:calculateBillRunMaybeBackground` posts `{"background": true}`, and
`BillRunWizard.tsx:898` calls it, renders the 202's poll (`job`), and distinguishes the inline 201
(`ranInline`) — `CR-051` task 12 built that caller.

**What IS unbuilt is the TIMING, not the mode.** The blueprint fires the pass from **step 1's**
commit bar — *"About three minutes, in the background. You can close this tab"* + **Check this
run →** — so that step 2 opens with money already on every row. Today the button sits inside
Check, which is why the drawing says *"the clerk decides blind and the consequences appear one
screen later"*. Moving the call is the fix; the mode is already there and already honest about
whether it queued.
