# The service request's own screen, rebuilt to its drawing

**`CR-094-BRC01` wave 2, the screen lane · 2026-09-15 · worktree cut at
`ce2fc2f6`.** Defect work under `CR-094-BRC01` (`13-change-process.md` §1 —
making the product match a signed drawing is a defect, not a change).

**Six lanes spent the day building behind this screen and a clerk could see none
of it.** Approval raises the job, the premises and the unit are served by their
numbers, the two letters queue, the request knows how many units are on the
property — and the screen still printed a database key where a place should be,
had no way to approve, and drew the wrong three tabs' worth of content in the
wrong places. This lane is what makes the day's work visible.

**Closes `DEF-CUS-5386` and `DEF-CUS-5389`. Files `DEF-CUS-5420` and
`DEF-CUS-5421`.**

---

## 1 · Which blueprint pages were read AS IMAGES, and at what scale

PO instruction of this date, four times over — *"we need to ensure all screns in
product are build from images taken rom document"*, *"I want you to use images
only to create scereens - do not use text or content ot create product
screens"*, *"build screen using document images nad UI generator skills"* — and
B14 rule 42: extracted text is an index, never the specification.

`05-prototype/02 Accounts Menu Blueprint.pdf`, pre-rendered at **scale 2** into
`scratchpad/acct/`, every one read with the Read tool as a PNG:

| page | scale | what it settled |
|---|---|---|
| `p082.png` | 2 | The head — `← The register`, the kicker `REQUEST SR-26-0001 · NEW CONNECTION`, the applicant as the title, the state / waiting-on / channel / received line, the address on its own line, and **`Refuse` · `Ask for more` · `Approve`** at the right. The **three tabs** `Applicant · Documents · History`. The Applicant tab's LEFT column: `WHAT THEY ASKED FOR` and the top of `WHO IS ASKING`; its RIGHT column: `DOCUMENTS · 4` as `DOCUMENT / FILE / STATE`. |
| `p083.png` | 2 | The rest of the left column — `WHO IS ASKING`'s Email · Phone · Channel, then `THE ADDRESS THEY GAVE` with `As given` / `Matched premises` / `Matched unit` — and the right column's `FEES` box (`Quoted · three lines`, `Settled by an invoice`, `Collected · cash · RCP-26-4471`, a rule, **`Outstanding`**) and `HISTORY` as `WHEN / WHAT / WHO`. Then the **Approve** dialog opening: title, sub-line, `WHAT IS THIS REQUEST?` and the first two radios. |
| `p084.png` | 2 | The remaining three radios with their consequence lines, the whole `WHAT APPROVING WILL DO` table (five `THEN`/`WHAT` rows), the footer `Cancel` / `Approve and raise the build`. Then the **Refuse** dialog: `Refuse SR-26-0001` / *"The applicant is told; the request stays on record"*, `WHY`, `Reason *` with its five values named under it, `What to tell them` with *"Goes into the refusal letter."* |
| `p085.png` | 2 | Refuse's `WHAT REFUSING WILL DO` (four rows) and its money panel, footer `Cancel` / `Refuse the request`. Then **Ask for more** entire: `Ask SR-26-0001 for more` / *"It stays open and stops waiting on you"*, `WHAT IS NEEDED` with four ticks, `Message to the applicant` with *"Sent to them and kept on the request's history."*, and `WHAT THIS WILL DO` (four rows). |
| `p086.png` | 2 | The Ask dialog's footer — `Cancel` / `Ask and queue the message`. |

**No higher-scale render was needed.** Every radio's sub-line, every consequence
row and every one of the five reason values was legible at scale 2; the two
earlier lanes that needed a scale-4 crop needed it for the address block and the
tick labels, both of which are transcribed in their own records and were read
here from those records plus the scale-2 image.

⚠ **THE DRAWN FIGURES ARE ILLUSTRATIONS (B14 rule 37).** `SR-26-0001`,
`PR-0731`, `U-001884`, `$130.00`, `$105.00`, `6 units`, `S. Ortiz` are examples
of a SHAPE. The screen ships `P-00053` / `SCW-U-209` on the demo tenant's
`SR-26-0005`, and every figure comes from the payload.

---

## 2 · Before and after

| | before (`ce2fc2f6`) | after |
|---|---|---|
| the head's controls | `Save & exit` · `Park` · a primary reading `Decide what this is →` | **`Refuse` (danger) · `Ask for more` · `Park` · `Approve` (primary)**, each opening a dialog. The first two are REMOVED by the ruling |
| approving | a plain button two clicks away on a Decision tab | the **Approve dialog**: five radios, nothing preselected, each carrying the drawing's own consequence line, and `WHAT APPROVING WILL DO` rendered from the server per outcome |
| refusing | one modal with ONE control, a textarea labelled *"Why is it being refused?"* | the **Refuse dialog**: the five drawn reasons as a vocabulary, `What to tell them` as a second field, the consequence table, the money |
| asking for more | **not a dialog at all** — a plain button in the lifecycle row that sent the same canned sentence to every applicant | the **Ask-for-more dialog**: four ticks, the clerk's own message, the consequence table |
| the matched place | `RESOLVED TO 01a0a444-5ad2-7e88-be8a-bdb8aa86c05e` | `Matched premises P-00053 · exact` / `Matched unit SCW-U-209 · exact`, the id on `title=` |
| the addresses | the billing address served since W4 and drawn by nothing | **service address AND billing address**, both drawn, by name |
| units on the property | served by wave 1 and drawn by nothing | drawn; `null` reads *not supplied* and never `0` |
| the tabs | six | **three**, the drawing's, with every door kept — §4 |
| the Applicant tab | one column of field grids | **the drawing's six blocks in two columns** |

---

## 3 · What each state shows, in the clerk's own words

| state | what the head offers | what the clerk reads |
|---|---|---|
| under review, documents unchecked | all four buttons live | Approve opens; its commit is refused with *"Not yet: Documents verified."* beside the button, announced. The form stays live, so the clerk reads what will be asked |
| under review, documents cleared | all four live | the commit is live and reads `Approve and raise the build` |
| more info (waiting on the applicant) | `Refuse` · `Ask for more` · `Approve` **disabled**, Park live | each disabled button carries *"A closed request cannot be parked."*'s sibling reason on its `title`; the state's own actions (`info_received`, `withdraw`, `manual_close`) stay in the lifecycle row |
| refused / closed | every decision disabled with its reason | nothing is hidden (`BR-SHL-025`) |
| after approving | — | a status note: *"Raised CON-26-0131."*, or the NAMED refusal — *"Match the address first, then approve."* · *"This applicant has no live account."* · *"No job row. Its own wizard records it."* |
| after refusing or asking | — | *"Letter queued to david.okonkwo@example.invalid."*, or why nothing went — *"You wrote no letter, so none went."* · *"They gave no email address."* · *"Queued. Nothing sends it yet."* |

---

## 4 · THE TAB COUNT — three, and not one live door deleted

**The drawing draws three (`p082`). The code had six. Whether it is six or three
is OPEN with the Product Owner.**

`CLAUDE.md`'s prime directive forbids resolving an open question by choosing a
value, and deleting three tabs of working product is the most destructive value
available. B14 rule 41 says the product matches the blueprint. Both are honoured
the same way: **the STRIP is the drawing's three, and every door the other three
carried moved onto the block the drawing puts its content in.**

| the tab that went | where its content is now | the doors that came with it |
|---|---|---|
| `Location & services` | `THE ADDRESS THEY GAVE` (as given · service address · matched premises · matched unit · billing address · what we found) and `WHAT THEY ASKED FOR` (type · sub-category · services · requested start · units on the property · in their words · what is being built · plot or parcel) | the interruption section (`CR-068` wave B), unchanged |
| `Fees` | the drawn `FEES` box — quoted · settled by an invoice · collected with its method and receipt · **outstanding** | `Record what was handed over` OUTSIDE the disclosure (a clerk taking cash may not have to open a derivation first) and the per-line **waive** inside it |
| `Decision` | **the three head dialogs** — the PO's own ruling: *"`Decide what this is` … becomes the Approve modal"* | `Record that I searched` moved under `WHO IS ASKING`; it is what clears the arrears condition for a genuine first-time applicant, and deleting it with the tab would have removed the only way to clear it |

**If the answer comes back *six*, the strip grows again and nothing has to be
rebuilt.** `REQUEST_TABS` is one line and every block is its own component.

⚠ **`?tab=fees`, `?tab=location` and `?tab=decision` now fall back to
`applicant`** rather than blanking — asserted, because a bookmark is a door too.

---

## 5 · WHERE THE DRAWING AND A SIGNED RULE DISAGREE — recorded, not silently resolved

B14 rule 41: *"the only exception is a drawing that contradicts a signed rule"*,
and rule 38: a dialog's CONSTRUCTION is the kit's while its CONTENT stays the
drawing's.

| the drawing | what shipped, and under which rule |
|---|---|
| each dialog carries a **sub-line under its title** | **Rule 38** — the header's construction is the kit's and the kit has no sub-line slot; **the SENTENCE is built**, as the body's first line, because rule 38's last clause keeps content with the drawing |
| the footer draws `Cancel` then a grey primary | **Rule 38** — the footer's order and tiers are `FormModal`'s. Refusing wears the **danger tier** (rule 6) because it is a destructive commit |
| `✕` closes each dialog | rule 38 — the kit's close control |
| the head's `Approve` is greyed when documents block it | **`BR-SHL-025`** — the refusal moved to the COMMIT, where `commitBlocked` renders it as announced text rather than a `title` a keyboard or a phone cannot read. One block, said once, where it can be read |
| red and grey **annotation panels** on p084/p085/p086 | **Rule 33** — rationale is ZERO WORDS ON SCREEN. They are in `serviceRequestDecisions.tsx`'s own header |
| p085's *"holding $25.00 that may have to be given back"* | **withdrawn by the PO's own ruling of this date** — *"if it is refuse then it is application fees non refundable - it stya in books"*. Drawing it would print a promise the product had just stopped keeping (hard-won law 1) |
| the first tick reads *"A readable site plan — the one attached was rejected"* | **Rule 37** — the clause after the dash is true of the one request in the picture and false of a request with nothing attached, so the label is the first half |
| the drawn `HISTORY` has a **`WHO`** column with names in it | the payload carries an actor **ID** and rule 31 forbids drawing it. The column is **drawn empty with its reason** — *"Who acted is not named yet."* — rather than filled with a false *"Not supplied"*. `DEF-CUS-5421` |
| `WHAT THEY ASKED FOR` lists five rows | **eight** ship: the five drawn plus `In their words`, `What is being built` and `Plot or parcel`, which had no other home once the Location tab's content moved. Dropping a captured fact off a screen is worse than a row the drawing did not ask for |

⚠ **AND ONE THING THAT NEEDS THE PO, WHICH IS THE ONLY THING IN THIS LANE THAT
DOES.** **Four of the drawn section headings are FOUR words and B14 rule 33 caps
a heading at THREE** — `WHAT IS THIS REQUEST?`, `WHAT APPROVING WILL DO`, `WHAT
REFUSING WILL DO`, `WHAT THEY ASKED FOR`. That is rule 41's named exception
exactly. **The drawn words shipped**, because a three-word paraphrase would
silently diverge from the drawing the PO is about to hold beside the screen —
and the collision is raised here and in the decision log rather than decided.

---

## 6 · WHAT WAS PUBLISHED FOR THIS SCREEN, AND WHAT IT RENDERS

Everything below is wave 1's and is RENDERED, never recomputed.

* **`decision.what_approving_will_do[<outcome>]`** (lane A) — one preview per
  outcome, **keyed by outcome**, so the modal redraws as a radio moves with no
  round trip. `then` and `what` are CATALOGUE KEYS and **this lane minted the
  words**, in eleven languages, under rule 33's caps. A screen that worked out
  *"a build is raised"* would be a second implementation of the rule.
* **`location_and_services.resolved_premises_no` / `resolved_unit_no` /
  `resolved_premise_address` / `premise_locality` / `resolved_match` /
  `units_on_property`** (lane B) — drawn by NUMBER, with the fallback ladder
  number → premises address → stated absence, **never the id**.
* **`refuse` taking `reason` · `reason_code` · `message_to_applicant`, and
  `transitions{request_info}` taking `reason` · `info_needed` ·
  `message_to_applicant`** (lane C) — both answer `applicant_message`, which the
  screen renders as whether the letter was queued and to what address.

### The five refusal reasons and the four ticks, fanned into the eleven

`customers.serviceRequest.refuseReason.*` (five) and
`customers.serviceRequest.infoNeeded.*` (four), plus 94 more keys, all through
`10-scripts/i18n_fanin.py` — **103 keys, +103 / −2 in every one of the eleven
catalogues, all at 17,892** (the two deletions are `refuse.title` and
`refuse.reason`, reworded to the drawing's `Refuse {{number}}` and `Reason` and
passed through `allow_overwrite`). No catalogue was edited by hand.

---

## 7 · PROOF

### Every new guard proved RED first, in the harness that runs it

Each break applied to the tree, run through `npx vitest run` — the harness that
runs them, not a hand-called module — then reverted.

| # | the guard | the sabotage | what vitest said |
|---|---|---|---|
| 1 | `DEF-CUS-5386` — the match is NAMED | `MatchedRecord` renders `internalId` again | `AssertionError: expected '<section …' to contain 'P-00052'` and, at the page level, `Unable to find an element with the text: /P-00074/` |
| 2 | the head carries four buttons | the Ask button's `testId` renamed | `expected null not to be null`, then `Unable to fire a "click" event` |
| 3 | nothing is preselected | the outcome state seeded `new_connection` | `expected '<div class="modal-overlay">…' not to contain 'checked=""'` and `expect(element).not.toBeChecked()` |
| 4 | the refusal is a VOCABULARY | the select swapped back for a text box | `expected '…' to contain 'Not our service area'` |
| 5 | the tab strip is the drawing's three | `REQUEST_TABS` restored to six | `expected 'fees' to be 'applicant'` and `expected [ 'Applicant', …(5) ] to deeply equal [ 'Applicant', 'Documents', 'History' ]` |
| 6 | both addresses are drawn | the billing-address label swapped | `expected '…' to contain 'Billing address'` |
| 7 | `DEF-CUS-5420` — a stored key never prints | the note rendered raw again | `expected '<section …' not to contain 'customers.serviceRequest.lookup.serve…'` |

⚠ **AND ONE GUARD THAT COULD NOT FAIL, FOUND BY ASKING WHAT WOULD MAKE IT PASS
WRONGLY (law 7, habit 2).** The first draft of the `WHO` column case asserted the
absence sentence and called `internalReferencesIn`. Putting `event.actor` back
into the cell left **all 70 cases green** — the fixture's actor reads `user-1`,
which is neither the id grammar nor a dotted Python identifier, so the shared
helper returned `[]` truthfully over the very thing the case exists to stop. The
case now feeds a real UUID actor and asserts it is drawn nowhere; that version
goes red on the same sabotage.

### Green

| what | command | result |
|---|---|---|
| types | `npx tsc --noEmit` (the repo's own 5.5.4) | **exit 0** — and **proved able to fail first**: the mid-build runs printed 14 errors across three files, quoted in the lane report |
| this screen | `npx vitest run ServiceRequestDetailPage.test.tsx ServiceRequestDetailPage.dom.test.tsx` | **70 passed** (57 unit + 13 DOM) |
| Route B | `npx vitest run src/styles/routeBUtilities.test.ts` | **11 passed** — `serviceRequestDecisions.tsx` is on `route-b-migrated.txt` |
| lint, my files | `npx eslint <the five files I touched> --max-warnings 0` | **exit 0** |
| catalogue parity | eleven files, key count | **17,892 each**, `+103 / −2` per file |
| gates | `run_gates.py --changed ce2fc2f6` | 31 PASS · 7 named FAIL · 54 not run. **One named my file — `G98 lint-clean`, `'ServiceRequestOutcome' is defined but never used`. Fixed.** The other six are §8 |
| the running product | browser walk, 1440 and 1280 | §9 |

---

## 8 · Reds I did not cause, DATED

Law 7 habit 1, and *"was it red before I started"* is a claim about history, so
it was checked rather than asserted.

| red | dated how | verdict |
|---|---|---|
| **18 cases in `AccountDetailPage.test.tsx` and `NewAccountWizard.test.tsx`** | **Re-run in the SHARED checkout at `cba62900`** — a tree this lane has never written to and which is AHEAD of its base: **18 failed, 110 passed, 12 todo**, the same eighteen. `git log -S "Statements are not built yet."` → `fbf07102`, 2026-09-14; `git log -S '"plan"' -- NewAccountWizard.tsx` → `c107eaae`, 2026-09-13 | **NOT MINE.** Already filed: `DEF-CUS-5185` (*the wizard draws six steps; the blueprint and the PO rule five*) and its neighbours `DEF-CUS-5104` / `DEF-CUS-5124` / `DEF-CUS-5184` / `DEF-CUS-5188`. The cases still assert the superseded shape |
| **`G98 lint-clean`, eleven other files** | the same run names `AccountCommunicationDialog.tsx`, `AccountDetailPage.tsx`, `AccountUsageTab.tsx`, `fixABillSteps.tsx`, four metering files and three test files — none of which this lane opened | **NOT MINE** (the twelfth was, and is fixed) |
| `G103` holds-cannot-rot · `G105` screen-matches-its-drawing · `G106` cited-ids-exist · `G107` one-responsive-direction · `G114` list-envelope · `G116` cited-tests-exist | every path each of them names is in `portal/`, `billing/`, `metering/`, `integrations/`, `work/` or `runbooks/` | **NOT MINE** — no file this lane touched appears in any of the six |

---

## 9 · WALKED IN A BROWSER, AND IT FOUND A DEFECT NOTHING ELSE COULD

Hard-won law 6: no gate in this repo looks at rendered output. The built SPA was
served by `server.mjs` on `:8124` over a Django `runserver` on `:8123`, against
the real `brazosbend` database, at **1440 and 1280**.

⚠ **NOTHING WAS COMMITTED ON THE SHARED TENANT.** The three dialogs were OPENED
on `SR-26-0005` and `SR-26-0004` and closed again; no approve, refuse, ask or
park was ever submitted, and the demo tenant's eleven requests are in the states
they were found in.

### What the walk measured, at both widths

```
title="Ridge Coffee Co."  fontSize=32px          ← B14 rule 40
tabs=["Applicant","Documents","History"]
head buttons: refuse ✓ ask ✓ park ✓ approve ✓ — all four present, none disabled
panels: what-they-asked-for · who-is-asking · the-address-they-gave ·
        documents-summary · fees · history-summary — all six
rendered UUIDs=[]  catalogueKeys=[]  internalIds=[]
names the match: P-00053=true  SCW-U-209=true
horizontal overflow: false
approve rows: Now/This request becomes Approved. Your name is recorded. ·
              Now/A job is raised. It names this request. ·
              Now/The money still owed travels with it. ·
              Next/The job's wizard asks for the rest. ·
              Not now/No account opens. Nothing is energised.
approve commit blocked: 1
refuse options: Pick a reason · Not our service area · Documents not provided ·
                Applicant withdrew · Duplicate of another request · Other
refuse money: $130.00 · $25.00 · $105.00
ask ticks: A readable site plan · Proof of identity, checked ·
           A connection date · Something else
```

**`$130.00 / $25.00 / $105.00` is `BR-CUS-090`'s worked case, read off the
running product on a real request** — and it is the blueprint's own figure,
which is a coincidence worth naming rather than a fact built to (rule 37).

### What the walk found — `DEF-CUS-5420`, and it was in this lane's own new code

**The first walk reported `catalogueKeys=["customers.serviceRequest.lookup.servedAndOccupied"]`
— a catalogue key printing at a clerk, in the `WHAT` column of the history.**

`service_request_events.note` carries two different things: a clerk's own
sentence on a `Note` row, and a **stored message key** on a system row — the
address lookup writes `customers.serviceRequest.lookup.servedAndOccupied` into
it. Both the new `HistorySummary` and the **older `HistoryTab`, which has done
this since REQ-02 was written**, rendered `event.note` verbatim.

**Every check passed over it.** `tsc`, 81 vitest cases, the gates, and — the one
that hurts — `internalReferencesIn`, which reads the rendered DOM for exactly
this class of leak and returned `[]` **truthfully**: it looks for the id grammar
and for dotted *Python* identifiers, and a dotted catalogue key is neither. A
declared blind spot with no number attached is indistinguishable from an empty
one (law 7, shape five).

Fixed in both components through `CatalogueSentence`, which resolves a key and
falls back to the value, so a clerk's own sentence still reads as itself. The
walk now greps the whole rendered body for `customers.serviceRequest.*` as well
as for UUIDs and the id grammar.

### One more thing the walk found and this lane fixed

`SR-26-0005` has no fee, and the drawn four-row `FEES` box printed *"No fee has
been raised on this request yet."* **four times** — `MoneyOrAbsence` states the
absence per FIGURE, which is right in a field grid and is noise in a box. B14
rule 32 gives a section one sentence, so the four rows are drawn only when there
is money to put in them.

### Screenshots

`scratchpad/wave2-request-screen-shots/` — `request-screen-1440.png` ·
`request-screen-1280.png` · `approve-modal-1440.png` · `approve-modal-1280.png` ·
`refuse-modal-1440.png` · `refuse-modal-1280.png` ·
`ask-for-more-modal-1440.png` · `ask-for-more-modal-1280.png` ·
`history-tab-1440.png` · `history-tab-1280.png` · `walk.log`.

---

## 10 · What I did NOT build, and why

| | |
|---|---|
| **A three-word paraphrase of the four drawn headings** | rule 41's named exception — it goes to the PO, §5 |
| **A resolved actor NAME on the history** | `DEF-CUS-5421`. It is a read-model change in `service_request_reads.history_tab` and it belongs with whoever owns actor display across the product, not with one screen |
| **The `separate` sentence on the connection quote** | the drawing does not draw the quote panel on this block at all, and the sentence is 33 words against rule 32's one-sentence budget. `Not raised` and *"A quote is raised after review…"* both survive, inside the disclosure |
| **`customer_category`, which the server serves and no screen draws** | `applicant_tab` has served `customer_category` (the `Customer category` + `Sub-category` pair, REQ-03.2) since W4 and the TypeScript type does not even declare it. The drawing's `Sub-category` row is filled from `property_type`, which is what the request's own capture asks for. Naming the second pair is its own piece of work and it needs the two vocabularies told apart first — `DEF-2804`'s shape |
| **A `?tab=` redirect for the three retired tabs** | they fall back to `applicant`, asserted. A redirect would claim the tab still exists |
| **Anything on the shared tenant** | §9 |

---

## 11 · One stale line amended on the way (step W)

`07-frontend/src/routing/screenIds.ts` described `REQ-02` as *"the request detail
and its six tabs"*. It has three. Amended in the same commit as the change that
made it wrong, which is the only way that line has ever been right.
