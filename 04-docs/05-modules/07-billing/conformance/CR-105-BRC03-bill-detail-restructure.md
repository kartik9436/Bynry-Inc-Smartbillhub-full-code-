# `CR-105-BRC03` · Bill detail — the Document tab restructured into its seven drawn groups

| | |
|---|---|
| Screen | **S30 · BIL-05** · `/:tenant/billing/bills/:invoiceId` · blueprint entry **02.1** |
| Drawing | `05-prototype/04 Billing, As Built.pdf` **p011–p018**, sha256 `137a2a48…0971`, 14,363,163 bytes, read **AS IMAGES** at scale 2 and cropped to 5–6× for the header, the annotations and the Usage table (B14 rule 42) |
| Process | **MAINTENANCE** (`12-governance/22-product-maintenance-process.md`) — the screen is live and a user can do this task today, so this is the named REDESIGN case, borrowing only the drawing step from Build |
| Walked | Chromium, **1440 and 1280**, against a booted stack on tenant `brazosbend`, bill `BL-2608-000094`. Instrument: `10-scripts/cr105_bill_detail_walkthrough.mjs` |
| Version walked | `2.266.0` — ⚠ **the bump for THIS change is OWED, see §8** |

⚠ **THE CR NUMBER ON THIS FILE IS THE ONE THE LANE WAS GIVEN AND IT COLLIDES.**
`12-governance/change-requests/CR-105-BRC03-bill-template-at-scope.md` already
exists and is a DIFFERENT change — *"in this step 1 scope - you will ahve to
also decide on billing template"*, a template control on the bill-run wizard.
This work is the bill DETAIL and is not that. It is recorded under the id the
lane was instructed to cite rather than silently renumbered, because two lanes
picking their own replacement is how a number collides twice; **the coordinator
should renumber it, and until then a reader meeting `CR-105-BRC03` has to check
which of the two is meant.** That is `DEF-2804`'s shape — a real id read for a
different real id — filed rather than left in prose (`DEF-GOV-5229`'s lesson).

---

## 0 · Reproduce, locate, blast radius — the three steps Build does not have

**REPRODUCED FIRST, IN A BROWSER, BEFORE ANY CODE WAS READ.** `BL-2608-000058`
at 1440 on the booted stack: the Document tab drew an **AMOUNT** panel, then a
**760px embedded PDF viewer** with its own page thumbnails and toolbar, then
four panels — *Customer's bill · Where this bill came from · How this bill was
produced · Record check*. The header drew `View the bill as sent` as grey text
and `Fix this bill` as the FILLED red primary. The identity line read `CY-007`.

**LOCATED:** one file is mounted — `07-frontend/src/features/billing/BillDetailPage.tsx`,
3,024 lines at the start of the lane, routed from `App.tsx` at
`/:tenant/billing/bills/:invoiceId`. `BillDocumentPage.tsx` is a different
screen (03) and was **not** touched (see §6).

**BLAST RADIUS, both ways.**

| Direction | What |
|---|---|
| What else uses what I changed | `SummaryPanel` and `billTabs` are EXPORTED and read by `BillChargesTab.test.tsx`, `CR053BillSurface.test.tsx`, `CR043BillsSurface.test.tsx`, `BillingSurfaces.test.tsx` · `InvoiceDetail.cycle_label` is read by four screens (`ReadDetailPage`, `accountDetailTabs`, `BillsListPage`, this one) — which is why the cycle's NAME arrived as a NEW field rather than as a change of meaning |
| What else used what I removed | `WhenItIsDuePanel` — one call site, the Charges tab · the `<iframe>` — no other caller · fourteen catalogue keys — swept to **0** live call sites before retiring, in `src/`, `10-scripts/` and `08-qa/` |

---

## 1 · The carry-over map is the acceptance test — and it ties out

p011–p012 is titled **"Nothing on the bill detail is lost"** and does its own
arithmetic. Reproduced here against what was built:

```
As-built elements   43   (across the five tabs)
  unchanged         27
  moved             11   -> 2 buttons to the overflow · 1 pill to Dates · Delivery to Sent
                          When-this-is-due to Dates · 2 columns into a cell
                          Record merged · 3 sentences regrouped
  relabelled         4   -> Origin · By service · Tax · "Copy of what they received"
  removed            1   <- the embedded PDF viewer
Remedy elements     51   = 43 - 1 removed + 9 new
                          (name · address · billed date · cycle name · copy control
                           Owed today · Usage · download control · open-in-new-tab)
                                                                        RECONCILES
```

27 + 11 + 4 + 1 = **43** ✓ · 43 − 1 + 9 = **51** ✓

### The ONE removed row, and its ruling

| | |
|---|---|
| Element | The embedded PDF and its viewer |
| Ruling | Product Owner, **2026-09-11**, verbatim: *"we dont what full view of the document - you give a link to download but full view of document is not requires - it does not add any value to user"* |
| Was | `<iframe title="The bill as it prints" src="/api/{tenant}/invoices/{id}/document.pdf" class="h-[760px] …">`, under a banner reading **CR-053 TASK 3 — THE OUTPUT IS THE SCREEN** |
| Now | A download control, an open-in-new-tab control, and the two facts about the saved copy |
| Banner | **DELETED with it.** CR-053 task 3's reasoning is superseded, and a comment carrying a reversed decision's argument is what a later lane restores the viewer from |
| Proof | `cr105_bill_detail_walkthrough.mjs` — *"the embedded PDF viewer is gone"*, `document.querySelectorAll("iframe").length === 0` on a bill that HAS a printable page, at 1440 and 1280 |

**It was still in the product** when this lane started, three days after the
ruling, on a screen p015's own banner describes as *"REDESIGN drawn 2026-09-11,
still unbuilt at Version 35 … NEVER BUILT."*

---

## 2 · The seven groups, in the drawn order

p016's closing line: *"Seven groups, one word each, in the order a clerk asks
them: Amount → Breakdown → Usage → Dates → the document itself → Origin →
Record. The first four answer how much, why, why that much water, and when. The
last two are reassurance and are closed."*

| # | Group | Drawn rows | Built | Source |
|---|---|---|---|---|
| 1 | **Amount** | Previous balance · Payments received · Current charges · **Total due** · **Owed today**, linked · caveat | ✅ | `invoices.summary` (frozen) + `GET /accounts/{id}/open-bills` → `total_open` (live) |
| 2 | **Breakdown** | *why it is $251.45* · one line of per-service figures · `See every charge →` | ✅ | `charges_by_service`, already served — a MOVE, the Charges table stays |
| 3 | **Usage** | SERVICE · THIS PERIOD · AVERAGE · READ | ✅ | period = Σ of this bill's own `usage` lines · average = `GET /accounts/{id}/usage` `metrics.avg_per_month` over 12 months · read = **a stated absence, see §5** |
| 4 | **Dates** | Billed · Service period `· N days` · Due · Past due · Fees on this bill | ✅ | the invoice row; the day count derived from the two dates it already draws |
| 5 | **The bill** | `↓ Download the bill as sent (PDF)` · `Open it in a new tab ↗` · Saved copy `Kept — 2 pages` · Template `v1` · caveat | ✅ | one `pdf_url`, two anchors; page count from `GET /invoices/{id}/document` `pdf_page_count` |
| 6 | **Origin** ▸ | Bill type · Cycle (**the CODE**) · Billing run, linked · Service date · Issued | ✅ closed | unchanged rows, regrouped |
| 7 | **Record** ▸ | Bill template · Saved bill data · Record check's two verdicts | ✅ closed | *How this bill was produced* merged into *Record check* |

**Measured in Chromium at 1440**, group tops in page order:
`391 · 606 · 757 · 975 · 1230 · 1447 · 1500` — strictly increasing, which is
the assertion `cr105_bill_detail_walkthrough.mjs` makes rather than a reading.

---

## 3 · `DEF-BIL-5244` — CLOSED as **invalid**, and why the defect was the defect

The row reads: *"The step-1 diff has the bill detail header's two controls the
wrong way round — it makes View-the-bill-as-sent the primary and the drawing
makes Fix this bill the primary."* It was filed against a **correct** step-1
record, the inversion was built, and a comment naming six pages was written
into the code to defend it.

**The step-1 record was right.** p016 legend 6, verbatim:

> **One primary, and an overflow** · *View the bill as sent* filled; *Fix this
> bill* secondary; *Print bill* and *Cancel this bill* into `…`, Cancel keeping
> its reason · UI-RULES 4–6 · **CHANGED**

**The measurement was right too, and it was the wrong instrument.** On a 6×
crop of p015 `Fix this bill` really is the one boxed control and `View the bill
as sent` really is unboxed grey — **and neither is drawn FILLED anywhere in the
document**, so the pixels could not settle this in either direction. B14 rule
37: *a figure drawn in a wireframe is an ILLUSTRATION, never a fact to build
to.* The words could settle it and did.

The drawn ORDER is the corroboration: `View the bill as sent` is LEFTMOST, which
is where `PageHeader.leadingAction` exists to put a primary (US-SHL-020).

| | Before | After |
|---|---|---|
| `View the bill as sent` | `variant="ghost"`, and **ABSENT** on a bill with no saved copy | `variant="primary"`, filled, leftmost; **disabled with its reason** when there is no saved copy |
| `Fix this bill` | `variant="primary"` | `variant="secondary"` |
| `Print bill` · `Cancel this bill` | already in the `…` overflow | unchanged; Cancel keeps its reason |

⚠ **The refusal change closes p014's own finding**, which this lane did not
invent: *"Two controls, two different refusal strategies, side by side. Print
disables with a reason; View vanishes. A clerk cannot learn one rule from the
pair."* Both disable with the same reason now, read off the same fact in the
same order (`DEF-116`), and BR-SHL-044's *exactly one primary* now holds on
every bill rather than on bills that happen to have a document.

**The comment that defended the inversion is deleted** and replaced by one that
records the reversal and its instrument, so the next lane meeting the six pages
does not flip it back.

---

## 4 · Where this lane's brief disagreed with the document

The lane brief was written by someone who read p011–p017 once. Six differences,
every one checked against the images:

| # | The brief said | The document says |
|---|---|---|
| 1 | *"Of the nine new elements we have two. Built: the copy control, and **five tabs with counts**."* | **`Five tabs, with counts` is NOT one of the nine.** p012 lists the nine as *name · address · **billed date** · cycle name · copy control · Owed today · Usage · download control · open-in-new-tab*. `Five tabs, with counts` is legend **7**, marked `NEW`, and it is outside the carry-over map's arithmetic. The brief substituted it for **billed date** |
| 2 | *"the cycle **BY NAME from `cycles.label`**"* | The annotation does say `cycles.label`. **There is no `label` column** — `metering.Cycle` has `code`, `name` and `frequency`, and the drawn value *"Silver Creek — monthly"* is verbatim the `name` of `CY-007` in this deployment. Built as `name`, else `code`, which is the fallback `issue._cycle_label_for` has stamped into `bill_payload["cycle"]` since `DEF-2865` |
| 3 | *"**Breakdown** as a one-line summary from `charges_by_service`"* listed among the missing NEW elements | p012 marks *What each service cost* **RELABELLED** and legend 10 marks Breakdown **MOVED** — *"already served and already on the Charges tab as a table"*. It is a move, not a new element, and the Charges table stays |
| 4 | *"the Usage panel through `GET /accounts/{id}/usage`, which p016 notes **is mounted**"* | True, and incomplete: that endpoint serves the AVERAGE and nothing else the drawn table needs. `THIS PERIOD` comes off the bill's own frozen lines and the `READ` column is **not served at all** — see §5 |
| 5 | *"p015's banner says … **still unbuilt at Version 35**"* | Confirmed verbatim, and it is the REDESIGN banner. The same page also carries a `TWO REVISIONS` note — the as-built drawing is kept below, marked *do not build this* |
| 6 | *"the embedded PDF viewer is the ONLY REMOVED row **in the entire document**"* | Confirmed, and p017 puts it more strongly: *"Every carry-over table before this one reconciles with `removed = 0` because no ruling existed; this one does not."* |

⚠ **AND ONE THE BRIEF DID NOT MENTION AT ALL, WHICH IS THE ONE A LANE COULD
HAVE GOT WRONG.** p017 raises two questions and marks both as the reader's, not
the author's: **(1)** the tab is still called *Document* though it now holds
Amount, Breakdown, Usage and Dates — *"Overview or Summary would be truer"*;
**(2)** does the ruling extend to screen 03, `/billing/bills/:id/document`,
whose only purpose is the full view — *"I have not assumed either way."*
**Neither is assumed here either.** The tab keeps its id and its word, screen 03
is untouched, and both are §6's open items.

---

## 5 · Divergences from the drawing, each with its reason

| Drawn | Built | Why |
|---|---|---|
| Groups ruled off with a horizontal rule, no box | The kit's `Panel` — a box, 1px border, 16px padding | **B14 rule 36**: the packs give LAYOUT AND DETAIL, `r10` gives VISUAL STYLE, and the kit is how you comply. `Panel` is the information group on a detail screen in 145 files, and the skill names *"a detail screen that rules its groups off with a top border instead"* as the shape `R4` was raised against. The ORDER, the GROUPING and the ROWS are the drawing's and are built exactly |
| `READ` column: `M-8841 · 08/01` · `from water volume` · `3 meters` | The column is drawn and kept; every cell carries the **server's own sentence** for why it is empty | `GET /invoices/{id}/document` returns `absent: [{field: "meter_no · prior_read · current_read", why: "…stage 6 keeps only whether the service was measured, so the document can say WHETHER a meter was read and never WHAT it read"}]`. `GET /accounts/{id}` serves `meters` with **no service tag**, so a meter cannot be matched to a service row without guessing. A guessed meter number on a bill is a screen telling a clerk a reading came off the wrong meter |
| AMOUNT caveat: *"The four figures above are the ones saved on the bill the day it was issued. Owed today is the live balance on the account."* (17 + 9 words) | *"These four are as at issue. Owed today is the live balance."* (6 + 6) | **B14 rule 33** — *two sentences of six beat one sentence of twelve* — and the PO's 2026-09-14 working target, *"reduce the content to 5 to 6 meaningful words"*. Both facts survive. **This is a drawn element disagreeing with a signed rule, which under B14 rule 41 is the one thing that legitimately reaches the PO; it is recorded here rather than asked, because the shorter copy carries the drawing's whole meaning** |
| The customer's name in body colour; legend 1 says *"both linked"* | The name is a **link**, styled like the address beside it | The drawing and its own annotation disagree, and rule 37 makes the annotation the specification. A name a clerk cannot click while the address next to it opens the account is the harder thing to explain, and both go to the same place |
| `↓ Download the bill as sent (PDF)` — 6 words | Built as drawn | B14 rule 33 caps a LABEL at 3 words. The product's existing precedent on this very header is `View the bill as sent` (5 words), drawn and shipped, so the drawn label wins under rule 41. **Recorded, not silently followed** |

---

## 6 · What is deliberately NOT built, and who owns each

| # | Left | Why |
|---|---|---|
| 1 | The tab is still called **Document** | p017 raises *Overview* / *Summary* and does not rule. Renaming the default tab is a word every clerk reads first, and the tab id `document` is in URLs people have bookmarked |
| 2 | **Screen 03** (`/billing/bills/:id/document`) still exists | p017: *"Does the ruling extend to screen 03? … I have not assumed either way."* Both of `The bill`'s controls and the header's primary still reach the document |
| 3 | The `READ` column's values | §5. Needs a read `assemble_document` stage 6 does not keep |
| 4 | **The version bump** | §8 |

---

## 7 · Proof

| Instrument | What it covers | Result |
|---|---|---|
| `07-frontend/src/features/billing/CR105DocumentGroups.dom.test.tsx` | 30 cases — the removal, the emphasis, the seven groups and their order, both `<details>` closed, the cycle name/code split, the nine new elements, both directions of every move | **30 passed** |
| `CR053BillSurface.test.tsx` (3 cases REWRITTEN, not deleted) | the reversal of task 3 — a case that goes RED if the frame comes back | **16 passed** |
| `BillChargesTab.test.tsx` (2 cases rewritten) | the OTHER half of the `When this is due` move — that it is no longer on Charges | **passed** |
| `10-scripts/cr105_bill_detail_walkthrough.mjs` | rendered output: no iframe · the FILLED control is the left one, read from `getComputedStyle().backgroundColor` and not from a prop · seven group tops strictly increasing · both groups closed · no `CY-…` on the header · `THIS PERIOD` right-aligned within 2px of its figures · every quantity carries its unit · two controls at one URL · no horizontal scroll · all five tabs open · zero page errors | **24 checks PASS at 1440 and at 1280** |
| `npx tsc --noEmit` | — | clean, **and proved capable of failing first**: a planted `const x: number = "s"` gave `error TS2322` at `BillDetailPage.tsx(3587,7)`, then clean again |

**EVERY NEW CASE WAS PROVED RED BEFORE IT WAS TRUSTED GREEN, IN THE HARNESS
THAT RUNS IT.** A `git worktree` was pinned at the pre-change tip `cab896fa`,
the four test files and the eleven catalogues were copied into it, and vitest
reported **32 of 32 new/changed cases FAILING** there. Law 7's red proof, in
vitest and not through a second entry point.

⚠ **AND THE WALKTHROUGH ITSELF WAS WRONG TWICE BEFORE IT WAS RIGHT, BOTH TIMES
IN THE *looking at the wrong thing* SHAPE.** It first compared raw strings and
`Kicker` uppercases in CSS, so five group headings read as MISSING over a screen
drawing every one; then it selected `.kicker`, which is not a class this product
declares — the kit's handle is `data-kicker`. **Both were found by putting the
screenshot beside the output, not by reading the code**, which is hard-won law 6
happening to the check rather than to the screen.

### Reds in the suite this lane did NOT cause, dated

| Red | Dated |
|---|---|
| `BillsPage.test.tsx` → *US-BIL-025 TC-2* — `CONFIG.searchFields` is `["invoice_no","account_no","customer_name","address"]` and the test expects three | `git log -S 'address' -- 07-frontend/src/features/billing/BillsListPage.tsx` → **`cf45a3d2`, 2026-09-13** — *"Communication dialog: start from the utility's own wording"* added the fourth field and did not move the test. **Pre-existing, one day old, and in a file this lane does not own.** Filed rather than fixed in passing |

---

## 8 · Version — OWED, and why this lane did not take it

`allocate.py version --bump change` offers **2.267.0**. It was **not** taken.

The remote tip carries `2.265.0`; the shared working tree carries an
**uncommitted `2.266.0`** in all three version files, which is another lane's
in-flight bump. Writing 2.267.0 over it destroys their edit in a tree six lanes
share — law 11's mechanism two, with the file count correct and nothing red
anywhere. The screen was built and walked at **2.266.0**.

**So the bump is owed and is named here rather than skipped quietly.** Whoever
lands this alongside the lane that owns `package.json` should take it.

## 9 · Rollback

One commit, one screen, no migration, no data written. Reverting the commit
restores the embedded viewer, the inverted header and the four-panel Document
tab; the backend's `cycle_name` is additive and an older client ignores it.

---

## 10 · Gates, and what this lane moved in them

`run_gates.py` (the harness that runs at merge, not `python3 <gate>.py`) reports
**73 PASS · 50 FAIL · 3 SKIP** on this tree. **The repository was already in that
state**; the runner's own line reads *"0 newly failing"* against the previous
recorded run. Three are worth naming because they touch this change:

| Gate | Before / after | Whose |
|---|---|---|
| **G54 image-build** | **FAIL → PASS.** `npm run build` (= `tsc --noEmit && vite build`) failed mid-run on a fixture type error in this lane's new test file, and passes now (exit 0) | **this lane's, and fixed** |
| **G98 lint-clean** | still FAIL, over **11 files, none of them this lane's**. `BillDetailPage.tsx` left that list: `DetailTab` was imported and used by nothing at `cab896fa`, and was removed rather than walked past | 10 other files are other lanes' unused imports |
| **G31 declared-classes** | **PASS, 0 undeclared** — `features/billing/BillDetailPage.tsx` is on `route-b-migrated.txt` line 2291, so the Tailwind utilities this change writes are the strict checker's and not `G31`'s | — |
| **G15 i18n-parity** | still FAIL, 402 new values identical to English. **Exactly 2 of them are this lane's**, both French: `billing.bill.panel.dates` = *Dates* and `billing.bill.usage.col.service` = *Service*. Those ARE the French words a clerk uses (B14 rule 35), so they are left as they are and **the baseline is not widened** — widening a carried set to go green is the single most damaging move available here | 400 are other lanes' |
| **G38 stated-absences** | still FAIL, and it asks for the ratchet to be LOWERED from 65 to 58. **Not banked, because it is not this lane's gain:** measured directly, `BillDetailPage.tsx` contributes **1 untracked note at `HEAD` and 1 now**. Banking somebody else's tightening in a shared gate file is the collision this repo keeps having | another lane's |

⚠ **THE ELEVEN CATALOGUES WERE WRITTEN BY SOMEBODY WHO SPEAKS ONE OF THEM.**
39 keys added and 14 retired, through `10-scripts/i18n_fanin.py` — the tool that
owns those files — so parity holds by construction (16,890 keys in each).
**`NATIVE-REVIEW-OWED`** on the ten non-English catalogues, per B14 rule 35's own
honest clause.

## 11 · Two defects filed, one closed as not-a-defect, one fixed

| Id | What | Status |
|---|---|---|
| `DEF-BIL-5244` | The header's two controls, filed against a correct step-1 record | **invalid** — §3 |
| `DEF-BIL-5294` | `BillsPage.test.tsx` TC-2 pins three `searchFields` and the list has had four since `cf45a3d2`, 2026-09-13 | **open** — a file this lane does not own. ⚠ **Filed first as `DEF-BIL-5290` and LOST**: a sibling took the running number 5290 for `DEF-GOV-5290` in the same minute — the STRING differed and the NUMBER did not, which is what `G17` exists for and what `allocate.py` cannot prevent, because it asks the remote and cannot RESERVE — and the register rebuild-by-id that followed kept theirs |
| `DEF-BIL-5292` | A sibling's pathspec commit (`5c464e64`) published this lane's 39 uncommitted locale keys — law 11 mechanism five, live | **open** |
| `DEF-GOV-5293` | Five `## ` headings are duplicated in `02-decision-log.md`, from 2026-08-17 to 2026-09-10 — found by running the one-line check `DEF-GOV-5290`'s own note prescribes, over the whole file rather than over the block it repaired | **open** |
| `DEF-BIL-5291` | `test_us_bil_026_tc1`'s exact-key-set assertion has been RED since `faf130c5`, **2026-09-08**, because `taxes_by_authority` joined the payload and the set never grew | **fixed** — filed first, then fixed, in the same file this lane was already editing to add `cycle_name`. Six days red, and the comments on the four keys above it each say the assertion is exact *"which is the contract growing in the light"* — it only grows in the light if somebody reads the red |


---

## 12 · What it took to land, and it is a finding in its own right

Three commits, and the second and third exist only because the shared tree moved
under this lane twice in one afternoon — in **opposite directions**:

| | |
|---|---|
| `51687077` | the screen, the tests, the walkthrough, the catalogues and this record |
| `0d84a891` | the decision-log entry, **re-appended by authorship** after a sibling's excision of a different duplicated block (`DEF-GOV-5290`, commit `150c8e3b`) swallowed it while it was uncommitted |
| `bd96c0ca` | `DEF-BIL-5244` closed **again** — the first close was rewritten away by the register rebuild-by-id in the same repair — and the lost row re-filed as `DEF-BIL-5294` |

**Nothing was lost and nothing went red at any point**, which is the whole
difficulty: a lane's in-flight bytes are invisible to a repair that is correct
about its own subject, and an append-only register merges cleanly whether or not
somebody's row survived. All three were found by the same habit — re-derive
against the pinned tip and read the arithmetic — and by nothing else.
