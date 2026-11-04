# What changed in the updated Accounts blueprint

**Measured 2026-09-20 by the blueprint-conformance lane.** This file is a
SNAPSHOT of a measurement, not a register. The moment it disagrees with
`01-open-questions.md`, `02-decision-log.md`, `10-defect-log.csv` or
`11-change-requests.md`, **those win and this is stale.**

| | |
|---|---|
| New file measured | `05-prototype/02 Accounts Menu Blueprint.pdf` on `origin/claude/confirm-understanding-3ktufc` |
| New blob sha | `2c1b412bf57d31eb01002d8ce26efe5804ec441d` · 10,188,127 bytes · sha256 `dfaac39fdce3f577958f75b6da25994fc7e8ec4c363575e74e09912d55932f4c` |
| Previous file compared against | the same path at commit `497cd2d4` |
| Previous blob sha | `0ad89622bf23a3258dd361afa03324a7cb2eb563` · 10,282,571 bytes · sha256 `5d8e63e48d5d8835492d9f50aabd23a43402e3a57d7922b35d2918967681d46c` |
| Method | every page of both files RENDERED to PNG and looked at, per B14 rule 42 |

The new file is 94,444 bytes **smaller** than the one it replaced while having
two more pages. That is a re-export, not a deletion — see "How I know" below.

---

## 1. What changed: four edits, all of them about one thing

**The old document is 281 pages. The new one is 283.** But "two pages were
added" is not the change — it is the most visible quarter of it. There are
**four** edits and they are all the same correction, which the document makes
in its own §13 changelog:

> **"THE NEW-ACCOUNT WIZARD'S LANDING GETS A LIST AND A RECORD, AND THE STATE
> THEY DRAW WAS IN NEITHER."** Ruled: *"in the new account wizard, there should
> be proper detailed view and list view also."* ... "This section used to refuse
> them, and the refusal was half right: there is no new-account request object
> and these two invent no queue — they are the same register tab and the same
> account page as screens 01 and 02. **What was missing is the STATE.** A new
> account is created *Pending activation*, and screen 01's table shows three
> rows of which every one is *Active* while its own KPI band says 1 pending
> activation."

**So this update was made because a Product Owner asked for a list view and a
detail view on the new-account wizard's landing** — and in drawing them the
author found that the two screens at the top of the document had been drawing
the wrong account state all along, and corrected those too.

### The four edits

**(a) Two drawings inserted, as new pages 69 and 70.** Both stamped
**"AS-BUILT, FROM CODE — COMPOSED FROM SOURCE, NEVER RENDERED"**, their reason
given as *"the register tab and the account page both exist and render any
account; neither was opened on a pending one during the walk."*

* **New page 69** — the register's Accounts tab at
  `?tab=accounts&f.status=pending_activation`. One row, A-12048, balance
  **"Awaiting"** rather than `$0.00`, status *Pending activation*. Stated
  absence: *"THE STATUS FILTER CANNOT OFFER EVERY STATUS — its five options are
  written into the front end, and a tenant may add a sixth. Disconnected is
  already that sixth and is missing here."*
* **New page 70** — that account's record page at `?tab=overview`, twelve tabs,
  `BALANCE Awaiting`, `DEPOSIT ON FILE None`, `PLAN FROM UNIT SCW-RES`. Stated
  absence: *"CLOSE OUT IS OFFERED ON AN ACCOUNT THAT NEVER TOOK SERVICE."*

**(b) A prose correction on page 69**, in the paragraph that was already there.
It is a factual change about what the product writes:

| | |
|---|---|
| Was | "A draft lands there too, **carrying its number and a Draft status**." |
| Now | "A draft lands there too — **the wizard's radio says Draft and the status the product writes is Pending activation**, which is the state the two drawings below are of." |

**(c) Screens 01 and 02 corrected — new pages 26 and 27.** These sit *before*
the insertion point, so they keep their numbers, and they are the edit a lane is
most likely to miss. The document flags it itself, on page 26:
*"⚠ corrected: this header read Active · Billable with Activate disabled, over
the dialog that activates it."*

| Page | Was | Now |
|---|---|---|
| 26 | header chips `Active · Billable` | `Pending activation · Non-billable` |
| 26 | `Adjust / Move-out / Activate account` with Activate disabled | `Activate account` live |
| 27 | balance `$0.00` | `Awaiting` |
| 27 | "has been charged" | "billable" |
| 27 | deposit `$150.00 · 08/22/2026` | `None — none was applied` |

**(d) The §13 changelog bullet quoted above**, on new page 239.

### Everything else is a re-export, not an edit

Apart from those four, **no page's content changed.** Old pages 69–281 are new
pages 71–283 — the same page, two numbers higher:

| Old pages | New pages |
|---|---|
| 1 – 25 | 1 – 25, unchanged |
| **26 – 27** | **26 – 27, CORRECTED in place** |
| 28 – 68 | 28 – 68, unchanged |
| 69 | 69, prose corrected, **two drawings added after it (69–70)** |
| 70 – 281 | 72 – 283, unchanged (**+2**) — except **239**, which gains the §13 bullet |

### A caveat that governs the two AS-BUILT pages

Every wireframe in this document prints **`v2.234.15`** in its own chrome — 166
times across the new file, and no other version string appears anywhere.
`07-frontend/package.json` reads **`2.319.5`** today. An AS-BUILT page is
evidence about the build it was walked on, roughly 85 change-versions ago.

**That is not theoretical: one of the two stated absences is already fixed.**
The close-out finding on page 70 was filed as `DEF-CUS-5005` on 2026-09-12 —
which cites this same blueprint as one of its two independent sources — and
closed at version **2.237.11**. The drawing is not reporting an open defect; it
is a photograph of a build that has moved on.

For the other absence, about the status filter offering five of six statuses,
**I searched `10-defect-log.csv` (3,534 rows) for `sixth` and for
`five options` and found no matching row.** That is what I looked for; a
differently worded row would not have turned up. I filed nothing, because an
absence stated by a drawing of an 85-version-old build is not yet shown to be
true of the product today.

## 2. The transfer screens: NOT changed, and still FIVE steps

**This is the answer the transfer lane needs, and the headline is that there is
no new instruction.** The transfer wizard, the Transfers tab and the transfer
record page are **byte-for-byte the same drawings** in both versions. Only their
page numbers moved.

### The wizard is five steps, and was five steps before

The stepper is drawn on every one of the five screens and reads, in order:

| # | Step | Address |
|---|---|---|
| 1 | **Find the account** | `/transfers/new?step=1` |
| 2 | **The buyer** | `?step=2` |
| 3 | **Date of sale** | `?step=3` |
| 4 | **What they take on** | `?step=4` |
| 5 | **Review & confirm** | `?step=5` |

The document's own index entry reads *"Transfer wizard, five steps,
reassignment"*, and the caption under every step reads: *"BR-CUS-1030 made a
transfer a REASSIGNMENT and these **five** are drawn to that ruling."*

**If a lane is building the transfer wizard to a four-item list, that is wrong
against BOTH versions of the drawing, and the update is not the reason.** The
count has been five since the 2026-09-11 redesign.

What each step contains, as drawn:

1. **Find the account** — a search box, a results table
   (`ACCOUNT · CUSTOMER · SERVICE ADDRESS · STATUS · BALANCE`) with a radio per
   row, then two read-only panels: *The account — and all of it changes hands*
   and *What is changing hands with it*. Right column: *What this sale will not
   touch* (issued bills, payments, journal entries, account number, unit and
   meters, service agreements — all unchanged). One refusal is drawn in red:
   *"Selling the property, or moving house? If this customer is moving to another
   of our addresses, this is not a transfer."*
2. **The buyer** — customer kind, full name, one identifier (SSN or driving
   licence), phone, email, mailing address. Right column is the **changeover
   read**: a table of jobs to raise (`WT-0114` electric, `WT-0115` water, an
   unticked meter-condition check) with a *No visit needed* box. Drawn refusal:
   *"Needs one identifier to continue."* Stated absence: *"A FINAL READ, TYPED
   HERE — there is none, and it is not missing."*
3. **Date of sale** — **one date field, not two.** Drawn explicitly: *"One date,
   not two. The old step asked for a leaving date and an arriving date because
   the job closed one account and opened another."* Red band: *"Nothing is
   prorated at a sale."* Right column lists what the date does NOT do — split the
   bill, close a period, start a new ledger, trigger a final statement, move the
   deposit (*"there is nowhere to move it to"*).
4. **What they take on** — a bordered money box (balance, deposit on file,
   deposit interest, *Taken on by the buyer*), *"The debt goes with the
   property"*, a **Fees to collect** section stating there are none, and one
   checkbox: **"I have shown this to the buyer."** Drawn note: *"This step used
   to have two switches — should the deposit carry, should the arrears follow.
   Both were answered the same day: the debt follows the property."*
5. **Review & confirm** — four recap groups, each with a pencil link back to its
   step (*The account being sold* → Step 1, *The buyer* and *The changeover read*
   → Step 2, *The date* → Step 3, *The money* → Step 4), and a
   **What will happen when you confirm** table of seven outcomes. Closing line:
   *"One transaction. All five writes land together or none of them does."*

### The transfer record page

Drawn across new pages 133–134 (was 131–132). Title is the two names —
**"Tan, Wei → Ferraro, L."** — under a `TRANSFER TRF-26-0021` eyebrow, with
status chips *Completed · Account reassigned · Sold 05/07/2026*.

**Four sections, and if "a four-item list" means this, it is correct:**

1. **WHAT HAPPENED** — account, unit, service address, sold on, sold by, sold to,
   buyer kind, identifier given, buyer matched or created, changeover read,
   committed by.
2. **WHAT DID NOT CHANGE** — account number, unit and meters, plan, service
   agreements, status, the ledger, bills issued to the seller.
3. **THE MONEY, AS IT STOOD ON THE DAY** — a bordered box: balance, deposit on
   file, deposit interest, refunded to the seller, re-collected from the buyer,
   fees charged, *Taken on by the buyer*.
4. **WHAT THIS RECORD DOES NOT SAY** — whether the buyer was shown the figure
   (*"Not decided anywhere"*), the property's owner record (*"Still names the
   seller"*), the account's contact details (*"Still the seller's"*).

**The page has exactly two controls and no actions.** `Open the customer`
(primary) and `Open the account` (secondary). The drawing says so deliberately:
*"This record has no actions, and that is the answer rather than a gap... Drawing
a button here would invent a decision the product does not offer."*

Two stated absences ride on it: there is **no transfer numbering series**, so
`TRF-26-0021` is drawn as it *will* read once somebody adds one; and the
account keeps the **seller's** contact details, paperless election and autopay
instruction after the sale — *"somebody has to fix that."*

### The Transfers tab

New page 133 (was 131). Nine columns:
`REFERENCE · ACCOUNT · ADDRESS · SOLD BY · SOLD TO · SALE DATE · STEP ·
TAKEN ON · STATE`, plus a per-row `↗ Open`. KPI band of three: *OPEN*,
*SELLING THIS WEEK*, *OWED ON ACCOUNTS BEING SOLD*. Filter chips:
`Open · Selling this week · Completed · All · Filter▾`.

**Two things to be careful about here.** The caption above the drawing and the
document's own index both call the new column *"a waiting on column"*, but **the
drawn table header says `STEP`** and shows values `5 of 5` and `3 of 5`. B14
rule 41 and rule 42 make the drawing the specification, so the column is `STEP`.
The prose is the thing that is out of date, in both versions.

---

## 3. What we have built, measured against this

I read the front end but changed nothing in it.

**The wizard already matches.** `07-frontend/src/features/customers/transferDisconnectShared.tsx`
declares `TRANSFER_STEPS` as exactly the drawn five, with the drawn labels:
`Find the account · The buyer · Date of sale · What they take on ·
Review & confirm`. The record page already has the four drawn sections
(`whatHappened`, `nothingChanged`, `money`, plus the does-not-say panel).

**But the blueprint says the SHIPPED wizard is still the old job** — bearing in
mind the version caveat above, that it is describing `v2.234.15`. New page 134
carries a block headed *"⚠ Blocked in the shipped screen"*:

> "The buyer is never asked for. The five steps on the running product are still
> the old job — *Leaving · Final reads · Arriving · Money · Review* — so the
> wizard posts a destination unit, two dates and two elections that the commit
> does not read, and never sends the buyer, which the commit requires. Every
> attempt refuses at the second of five writes, naming a field that appears on
> none of the screens."

So the step COUNT was never the problem — **the step CONTENT was.** Both the old
and the new wizard have five steps, which is exactly why a count-based check
could not see this. **Anyone verifying transfer conformance by counting steps
will get a pass on a screen that cannot commit.** I did not run the wizard, so I
cannot say whether that block is still true of today's code; the front-end step
list has since been rewritten to the drawn five, and the blueprint block
describes the walk that produced the document. **Treat it as a question to
re-measure, not as a current fact.**

### The register's tab strip — two frames of the blueprint disagree

New page 69 (inserted) draws **eight** tabs: `Accounts · Requests ·
New connects · Move-ins · Move-outs · Transfers · Disconnects · Imports`.
New page 133 draws **ten**: the same eight plus `Complaints` and `Services`.
Both pages print the subtitle *"10 tabs"*.

Counted across the document, the ten-tab strip is drawn **9 times** and the
eight-tab strip **twice** (it was once in the old version; the inserted page is
the second). The built product carries **eight** tabs.

This is not a contradiction to escalate — it is the two banners doing their
jobs. The inserted page is stamped **AS-BUILT**, so it draws today's eight; the
redesign pages draw the intended ten. B14 rule 37 covers the leftover: the
number *"10 tabs"* is a figure drawn in a wireframe and is an illustration, not
a fact to build to. **Build the shape the frames agree on and do not treat the
subtitle as a count.**

---

## 4. The one thing this update actually breaks: page citations

**Every citation of an Accounts-blueprint page numbered 69 or higher is now off
by two.** The content did not move; the page number under it did.

Measured in `07-frontend/src/features/customers/` — the Accounts module's own
front end — there are **631 page citations of the form `pNNN`, of which 613 name
a page at 69 or above, across 57 files.** Those 613 now point one screen early.

The most-cited of them:

| Cited as | Now | Occurrences |
|---|---|---|
| `p117` | `p119` | 78 |
| `p118` | `p120` | 42 |
| `p131` (Transfers tab) | `p133` | 41 |
| `p077` | `p079` | 37 |
| `p132` (transfer record page) | `p134` | 37 |

`TransferRecordPage.tsx` is a worked example: its header says
*"`Blueprint.pdf` p132, 'The transfer, opened · TRF-26-0021'"* and
*"built from a 2x page render and 3x crops of p132"*. In the new file that
caption is at the foot of **p133** and the drawing runs onto **p134**. New p132
is the step-4 wizard caption — a different screen entirely.

**What I did NOT measure.** I scoped this count to the `customers/` feature
directory because that is the Accounts module's front end. Repo-wide the same
`pNNN` pattern matches **5,728** occurrences, but this repo has at least six
blueprint PDFs (Assets, Accounts, Premises & Units, Customer Portal, Plans &
Rates, Billing), and a bare `p117` does not say which document it means. **I did
not classify those 5,728, so do not treat that number as an Accounts figure.**
The 613 is the defensible one, and even there a citation could in principle name
a sibling blueprint.

**Recommendation, and it is not mine to execute:** do not mass-rewrite these.
That is the shared-file rewrite CLAUDE.md law 11 exists to prevent, and a
citation is provenance rather than a live link. The cheap fix is to record the
+2 offset once, here and in the decision log, so the next lane that opens the
PDF at a cited page knows to add two.

---

## How I know, and what would prove me wrong

The re-export is the reason this needed rendering rather than reading, and the
reason a first pass got the answer half right.

* **Only 41 of 283 pages render byte-identically** to any page of the old file,
  so the document was re-exported end to end. Exact hashing is useless here and
  I did not rely on it.
* A coarse 16x16 luminance signature **could not tell these pages apart at all**
  (randomly chosen different pages scored a mean distance of 6.48; genuinely
  matching pages scored 5.35). I abandoned it rather than reporting its output.
* I aligned the two documents with a dynamic-programming alignment over per-page
  word sets: **281 one-to-one pairs, two insertions at new 69–70, zero
  deletions.**
* 219 of those 281 pairs show *some* text difference, which looks like a heavily
  edited document and is not. Diffing the transfer section as one concatenated
  block gives **35 hunks, every one a delete matched by an identical insert
  elsewhere** — text moving across a page boundary on re-export.
* Whole-document **word multiset**: old 120,468 tokens, new 121,320, **+852**.
* Phrase counts: the `REDESIGN — PUBLISHED` banner appears **112 times in
  both**; `AS-BUILT, FROM CODE` went 38 → 40; `Pending activation` went 5 → 14.
  The string `of 5 ·` appears **32 times in both**, which is the cleanest single
  proof that **no wizard's step count moved anywhere in the document.**

**⚠ The step that mattered, and that a first pass skipped.** All of the above
is consistent with *"two pages inserted, nothing else changed"* — and that
conclusion would have been **wrong in three places**. Reflow hides a real edit:
a page whose words scatter into its neighbours looks exactly like a page
somebody rewrote. What separates them is asking, for every word on a page,
**whether it has a home anywhere in a three-page window of the other
document.** Words with no home are genuine; words that merely moved are not.

Run that way, **50 of 281 pages carry an unexplained word, and 46 of those 50
are extraction artefacts** — hyphens (`UI-RULES` → `UI RULES`, `DEF-352` →
`DEF 352`, `move-out` → `move out`), spacing (`CloseLink` → `Link Close`) and
single-letter fragments. **Four are real, and they are the four edits in
section 1.** Pages 26 and 27 are the ones a page-count or an insertion-point
argument can never reach, because they sit *before* the insertion and keep
their numbers.

**What would prove me wrong:** a change that alters a drawing without altering
any word on it — a moved box, a recoloured chip, a changed line weight. My
page-level image signature was too coarse to catch that, and I say so rather
than implying the image comparison was decisive. It was decisive about *page
identity and ordering*; the *content* conclusion rests on the windowed word
test plus looking at the pages that mattered. **I rendered and looked at 26
pages, not 564** — new 68, 69, 70, 71, 126–134, 238 and old 69, 70, 124–132,
236.

**Tooling.** `10-scripts/pdf/pdf_render.py` rendered every page I looked at, at
scale 2.0 (2448x1584). It needs `pypdfium2`, which is installed neither in
`06-backend/.venv` nor on the system `python3`; I installed it into a throwaway
venv of my own. Nothing under `10-scripts/`, `06-backend/` or `07-frontend/` was
modified by this lane — it read them and changed nothing.
