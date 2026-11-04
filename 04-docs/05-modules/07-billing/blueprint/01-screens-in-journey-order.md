# Billing blueprint · the per-entry page map for §02 — "The screens, in journey order"

**What this is.** One row per drawn entry in section **02 · The screens, in journey order** of
`05-prototype/04 Billing, As Built.pdf` (249 pages, on the DEFAULT branch
`claude/confirm-understanding-3ktufc`). Per entry it records: the number and title **as
drawn**, the page range, the address line and screen ids, the state chips, whether each
drawing's own caption marks it **AS-BUILT** or **REDESIGN**, whether it carries a `BUILD THIS`
band, and the specification ids that band closes.

**What this is NOT.** Not a specification, not a diff against the product, not evidence that
any screen matches any drawing. **Nothing here was measured against running code and no screen
was walked for this file.** Step 1 measures and classifies; it fixes nothing.

**Companion file.** `02-runs-single-budget-fix.md` maps §03–§08 (p28–p151). This file stops
where that one starts.

## How it was read

**Every page in the range was opened AS AN IMAGE with the `Read` tool** (B14 rule 42, PO:
*"When you use images to create screens your accuracy is higher; hence dont create screens
using only Text"*), plus 13 targeted crops rendered from the PDF at 4× for the small chip rows
and `CLOSES` lists. The text layer **drops every slash, colon and digit from the monospace
address line** — p6's address, which the image renders as
`/:tenant/billing · second address /:tenant/billing/all · S30 · BIL-01`, extracts as
`tenantbilling    second address tenantbillingall    S  BIL`. It also **drops the `◆` glyph
entirely**: the contents rail carries 50 diamonds and a `grep` of the extracted text finds 2.
The text dump was used only to split the file into pages and to pick candidates.

⚠ **B14 rule 37: every figure drawn in these frames is an ILLUSTRATION, never a value to build
to.** Figures quoted below (`BL-2608-000043`, `$251.45`, `19 kgal`, `−$53.15`) are quoted as
*what the drawing shows*, so a builder can find the element. Do not assert one in a test or
seed a fixture from one.

## The real section boundary — measured, not assumed

The lane brief estimated **"p005 through roughly p100, §03 begins somewhere near there."**
**§03 begins on p28.** Measured off the images:

| Boundary | Page | What is on it |
|---|---|---|
| §02 head — `02 The screens, in journey order` | **p005**, foot of page | *"The two screens a clerk lives in — the bills list, and one bill with its five tabs. **All seven entries** here lead with the drawing to build. The bulk bill run is its own section (§03, redrawn end to end)"* |
| §02 last content | **p028**, upper third | tail of entry 02.5's commentary (*"One group here is a proposal, not a redraw"*) |
| §03 head — `03 The bulk bill run, redrawn` | **p028**, middle | new section rule and title |

**So §02 is p005–p028, 24 pages — not 96.** A lane that read to p100 on this brief would have
read the whole of §03 believing it was §02. The sibling lane measured the same boundary
independently and from the other side (`02-runs-single-budget-fix.md`: *"§03 starts p28 (lower
half; entry 02.5 of §02 ends on p28's top)"*). **Two lanes, two directions, same page.**

## The seven entries

Ids as drawn. **Page range** is first page the entry's own heading appears on, to the last page
before the next entry's heading. `BIL-Snn` are specification ids; `BIL-01` / `BIL-05` are
screen ids; `S30` is the A1 screen id.

### 01 · All bills — p006 (foot) – p011 (upper)

| | |
|---|---|
| **Heading chips** | `New build` BIL-S3 S9 S15 S16 S44 S79 S94 S97 · `New read` BIL-S19 · `Exists behind` BIL-S1 S13 S14 S24 S25 S99 |
| **Address** | `/:tenant/billing` · **second address** `/:tenant/billing/all` · `S30` · `BIL-01` |
| **Question** | *"A customer is on the phone about a bill. Find it."* |
| **Revision kind** | `TWO REVISIONS` — *"This entry holds **both**: an AS-BUILT drawing of 2026-09-11 and a REDESIGN that has never been built. **Build the REDESIGN** — it is the first drawing below. The as-built one is kept as the evidence §09–§11 argue from; it is marked do not build this."* |
| **`BUILD THIS`** | YES — `New build` · *"All bills — eight changes, drawn"* |
| **CLOSES** | `BIL-S13 · BIL-S14 · BIL-S15 · BIL-S16 · BIL-S3` |
| **Drawing** | **1, REDESIGN**, p007. Caption: *"REDESIGN drawn 2026-09-11, still unbuilt at Version 35 (2026-09-13), drawn to B14 31 · B14 37 · the Product Owner's 2026-09-11 ruling removing the embedded viewer. **NEVER BUILT.**"* Corner stamps `v2.235.0` / `BIL-01` |
| **Legend** | 8 numbered items, p007–p008 |
| **Carry-over** | p008. `As-built elements 24` → `unchanged 23 · moved 1 · relabelled 0 · removed 0`; `Remedy elements 28 = 24 − 0 removed + 4 new`. Verdict printed: `RECONCILES` |
| **As-built drawing** | **collapsed and NOT RENDERED** (see the finding below). p009 carries the `▶ As built today — … Do not build this.` disclosure followed by the spec table; p010 the data flow + 11-field table; p011 two findings |
| **Walked** | `SEEN` — *"Rendered at 1440. Title measured 40px/800…"* |
| **Health** | `STUBBED` — *"the worst of 11 fields. 9 SERVED · 1 STUBBED · 1 NOT SERVED"* |

### 02 · Bill detail — p011 (middle) – p014

| | |
|---|---|
| **Heading chips** | `Blocked` BIL-S22 · `New build` BIL-S9 S12 S27 S71 S86 S98 · `New read` BIL-S17 · `Exists behind` BIL-S20 S28 |
| **Address** | `/:tenant/billing/bills/:invoiceId` · **tabs as** `?tab=` · `BIL-05` · **no A1 id** |
| **Question** | *"Is this the bill the customer received, and what is on it?"* |
| **Revision kind** | **NONE — this entry carries no drawing and no `TWO REVISIONS` / `AS BUILT` / `REDESIGN` caption.** It is the parent of 02.1–02.5 and holds only the combined carry-over |
| **`BUILD THIS`** | YES — `New build` · *"Nothing on the bill detail is lost"* |
| **CLOSES** | **none printed** |
| **Drawings** | **0** |
| **Carry-over** | p011–p012, *across all five tabs*. `As-built elements 43` → `unchanged 27 · moved 11 · relabelled 4 · removed 1`; `Remedy elements 51 = 43 − 1 removed + 9 new`. Verdict printed: `RECONCILES`. The single `removed` row is **the embedded PDF viewer** — *"The only REMOVED row in this document, and the only one with a ruling to quote"* (PO 2026-09-11: *"we dont what full view of the document - you give a link to download but full view of document is not requires - it does not add any value to user"*) |
| **Correction band** | p013, `CORRECTED 2026-09-11 against the running product` — the PO sent screenshots from `ottumwa-water-works`, `v2.234.17`; **ten details in the drawings were wrong**, each struck through rather than quietly fixed |
| **Walked** | `SEEN, BY THE PO` — *"Five screenshots of a real issued bill on a live tenant, 11 September 2026. **This is the only screen in the document seen with real data behind it**, and it moved ten findings"* |
| **Header controls** | p014 tabulates all four: `Print bill` (no screen — an `<a href>` to a PDF, `NONE — BY DESIGN`), `Fix this bill` (→ screen 13), `View the bill as sent` (→ screen 03), `Cancel this bill` (`NONE — PERMANENTLY DISABLED`) |

### 02.1 · Bill detail · Document — p015 – p017 (upper)

| | |
|---|---|
| **Heading chips** | `SEEN LIVE` · `Blocked` BIL-S22 · `New build` BIL-S98 · `New read` BIL-S17 S19 · `Exists behind` BIL-S18 S20 |
| **Address** | `…?tab=document` · **the default tab** · `BIL-05` |
| **Question** | *"Show me the bill they actually got, and tell me it is intact."* |
| **Revision kind** | `TWO REVISIONS` — build the REDESIGN |
| **`BUILD THIS`** | YES — `New read` · *"Bill detail · Document — the new heading, and the overview grouped"* |
| **CLOSES** | `BIL-S17 · BIL-S18 · BIL-S19 · BIL-S20` |
| **Drawing** | **1, REDESIGN**, p015–p016 (one frame across two pages). Same NEVER BUILT caption as entry 01 |
| **Legend** | 13 numbered items, p016 |
| **As-built drawing** | **collapsed and NOT RENDERED**; p017 carries the disclosure and a four-row table (`PANELS` · `WHAT CORRECTED` · `FINDINGS THAT STAND` · `WALKED`) |
| **Open questions it raises** | two, stated as the PO's not the author's: ① the tab is still called *Document* once the document is a download; ② does the 2026-09-11 ruling extend to screen 03, whose *only* purpose is the full view |

### 02.2 · Bill detail · Charges — p017 (lower) – p021 (upper)

| | |
|---|---|
| **Heading chips** | `SEEN LIVE` · `Blocked` BIL-S22 · `New read` BIL-S17 · `Exists behind` BIL-S20 S23 |
| **Address** | `…?tab=lines` · **the tab id is** `lines`**; the label is** *Charges* · `BIL-05` |
| **Question** | *"What is the $251.45 actually made of, and which rates priced it?"* |
| **Revision kind** | `TWO REVISIONS` — build the REDESIGN |
| **`BUILD THIS`** | YES — `Exists behind` · *"Bill detail · Charges — Rate version folded under the description"* |
| **CLOSES** | **none printed** (verified at 4× — the band ends at the title) |
| **Drawing** | **1, REDESIGN**, p018–p019. Same NEVER BUILT caption |
| **Legend** | 2 numbered changes, p019 |
| **As-built drawing** | **collapsed and NOT RENDERED**; p019 carries the disclosure and a five-row table (`PANELS` · `WHAT CORRECTED` · `THE BEST TABLE IN BILLING` · `THE ONE LAYOUT FAULT` · `WALKED`) |
| **Extra tables** | p020 *"Is the content properly aligned? No — six things"* (6 rows) and *"What is missing from this tab"* (7 rows, the 7th `OUT OF SCOPE`) |

### 02.3 · Bill detail · Corrections — p021 (middle) – p024 (upper)

| | |
|---|---|
| **Heading chips** | `SEEN LIVE` · `Blocked` BIL-S22 · `New read` BIL-S17 · `Exists behind` BIL-S20 S21 |
| **Address** | `…?tab=chain` · **the tab id is** `chain`**; the label is** *Corrections* · `BIL-05` |
| **Question** | *"Is this still the bill that counts, or has something replaced it?"* |
| **Revision kind** | `TWO REVISIONS` — build the REDESIGN |
| **`BUILD THIS`** | **TWO bands, one per state** |
| — state 1 | `Exists behind` · *"Bill detail · Corrections — two groups, and a way out"* · **CLOSES: none printed** (verified at 4×) |
| — state 2 | `Exists behind` · *"Bill detail · Corrections — the populated state"* · **CLOSES `BIL-S21`** |
| **Drawings** | **2, both REDESIGN** — empty state p021 (+p022 top), populated state p022 (+p023 top). Same NEVER BUILT caption on each |
| **Legend** | 5 numbered items, p023 (for the populated state) |
| **As-built drawing** | **collapsed and NOT RENDERED**; p023–p024 carry the disclosure and a table (`PANELS` · `THREE STANDINGS` · `THE FINDING` · `WALKED`) |
| ⚠ **Money note** | p023's red rail states the correction arithmetic against hard rule 4: original stays at `$251.45` for ever, credit note `−$251.45`, replacement `$198.30`, customer `$53.15` better off — *"Three documents, not one edited one."* It also states plainly that **nobody has seen this state**: `DEF-2901` records no database in this repo has a draft bill, and this repo has no corrected bill either, *"so the three standings, the credit-note table and the replacement link have **never been rendered together**. Every figure above is an illustration (B14 rule 37) and none is a served value."* |

### 02.4 · Bill detail · Audit — p024 (middle) – p026

| | |
|---|---|
| **Heading chips** | `SEEN LIVE` · `Blocked` BIL-S22 · `New read` BIL-S17 · `Exists behind` BIL-S20 |
| **Address** | `…?tab=audit` · `BIL-05` |
| **Question** | *"Who touched this bill, and what did they change?"* |
| **Revision kind** | `TWO REVISIONS` — build the REDESIGN |
| **`BUILD THIS`** | **TWO bands, one per state** |
| — state 1 | `Blocked` · *"Bill detail · Audit — newest first, dates in words, nothing hidden"* · **CLOSES: none printed** (verified at 4×) |
| — state 2 | `Blocked` · *"Bill detail · Audit — one row per field, not three parallel lists"* · **CLOSES `BIL-S22`** |
| **Drawings** | **2, both REDESIGN** — p024 and p025. Same NEVER BUILT caption on each |
| **Legend** | 3 items on state 1 (p025 top), 4 items on state 2 (p025–p026) |
| **As-built drawing** | **collapsed and NOT RENDERED**; p026 carries the disclosure and a five-row table (`WHAT RENDERS IT` · `MECHANICALLY THE STRONGEST TAB IN BILLING` · `THREE FAULTS, ALL VISIBLE ABOVE` · `WHY IT IS LOAD-BEARING` · `WALKED`) |
| ⚠ **Why this one is `Blocked`** | the tab is **borrowed** — `import { AuditTab } from "@/features/metering/PremisesDetailPage"`, the S61 viewer every detail screen uses, *"so one audit surface keeps one set of masking and window rules."* Fixing it here fixes it everywhere: *"the right outcome and the wrong blast radius to take on inside a billing change. **It needs its own change request.**"* |
| ⚠ **Caveat it inherits** | p026 names the question *whether an audit row recording a `payments` reference correction is exempt from retention pruning* as **open**, and states that nothing here may describe this tab as a permanent record. The constraint is right and binding. ⚠ **The id it prints is not: p026 says `OQ-1330`, and the question is `OQ-1340`.** The drawing took the wrong id from `CLAUDE.md` hard rule 4, which carried it until 2026-09-14 — **`DEF-GOV-5229`**, now CLOSED; see the note at the foot of this file |

### 02.5 · Bill detail · Sent — p027 – p028 (upper)

| | |
|---|---|
| **Heading chips** | `ENTIRELY NEW` · `Blocked` BIL-S22 |
| **Address** | `/:tenant/billing/bills/:invoiceId?tab=sent` · **does not exist today** — *"Delivery is currently the last panel on the Document tab"* |
| **Question** | *"Did the customer actually get this?"* |
| **Revision kind** | `ENTIRELY NEW` — **no as-built revision exists, and none is drawn** |
| **`BUILD THIS`** | YES — `New build` · *"Bill detail · Sent — a new tab, split out of Document"* |
| **CLOSES** | `BIL-S19` |
| **Drawing** | **1, REDESIGN**, p027. Same NEVER BUILT caption |
| **As-built drawing** | **none — correctly; the tab does not exist** |
| **Note** | p028 marks one group on this tab a **proposal, not a redraw**: *How they hear from us* (the paperless election and contact details) is `NEW` and needs a customers read |

## The counts, and whether they reconcile

### What I counted in §02

| | Count | Note |
|---|---|---|
| Entries | **7** | 01 · 02 · 02.1 · 02.2 · 02.3 · 02.4 · 02.5 — matches p5's *"All seven entries here"* |
| `BUILD THIS` bands | **9** | one each on 01, 02, 02.1, 02.2, 02.5; **two** each on 02.3 and 02.4 |
| Bands printing a `CLOSES` list | **5** | 01, 02.1, 02.3-state-2, 02.4-state-2, 02.5 |
| Bands printing **no** `CLOSES` | **4** | entry 02, 02.2, 02.3-state-1, 02.4-state-1 — each verified by a 4× crop, not inferred from the text layer |
| **Drawings rendered in §02** | **8** | p007 · p015 · p018 · p021 · p022 · p024 · p025 · p027 |
| — of them **REDESIGN** | **8** | every one carries `REDESIGN … NEVER BUILT` verbatim |
| — of them **AS-BUILT** | **0** | see the finding below |
| Entries holding **both** kinds | **5** by caption | 01, 02.1, 02.2, 02.3, 02.4 all carry `TWO REVISIONS`; **their as-built half does not print** |
| Entries holding a redesign **only** | **1** | 02.5 (`ENTIRELY NEW`) |
| Entries holding **neither** | **1** | entry 02 — a band and a carry-over table, no drawing |
| Distinct `BIL-S` ids closed | **11** | S3, S13, S14, S15, S16, S17, S18, S19, S20, S21, S22 |
| Carry-over tables | **2** | entry 01 (24 → 28) and entry 02 (43 → 51); both print `RECONCILES` |
| `No commitment` in §02 | **0** | every entry carries work |

### Against the document's own reconciliation (p6)

| p6 says | I measured | Verdict |
|---|---|---|
| **Drawings to build 11**, across nine screens — 01, 02.1, 02.2, 02.3 (two states), 02.4 (two states), 02.5 (entirely new), 10, 13, 14 | §02 supplies **8** of those 11 (01·1, 02.1·1, 02.2·1, 02.3·2, 02.4·2, 02.5·1). The other **3** (screens 10, 13, 14) are not in §02 at all | **RECONCILES for the §02 share.** 8 + 3 = 11 |
| **Drawings of today, kept as evidence 18** — *"eight collapsed under a target, ten standing alone"* | §02 declares **5** collapsed as-built (01, 02.1, 02.2, 02.3, 02.4); the other 3 collapsed and all 10 standing alone are in §17 | **RECONCILES as a count** — 5 + 3 = 8 collapsed, 10 alone, 18 total. ⚠ **But see the finding: the five in §02 are not in the PDF** |
| **Drawings in total, §02 — 29.** *"11 + 18 = 29. Nothing absorbed into a total."* | §02's own pages hold **8 drawings**, not 29. The 29 is a count over the **fifteen screens** (§02 + §17), not over §02's pages | **ARITHMETIC HOLDS, LABEL DOES NOT.** The row is headed "§02" and is scoped to §02 + §17 |
| Route patterns mounted **7** · screens a clerk can reach **15** · second addresses **1** · tabs drawn as their own entries **4** · tabs still described inside an entry **6** · screens seen in a browser **4** | not measurable from §02's pages alone — 11 of the 15 screens are drawn in §17 | **NOT CHECKED HERE** |

**So my count does not disagree with theirs on 11 / 18 / 29.** It disagrees on two labels, and
one of those matters.

⚠ **And a sibling lane has since measured the other end of that row, which sharpens it rather
than contradicts it.** `03-rulings-and-registers.md` reports that §17's screens **10, 13 and 14
carry no drawing to build at all** — each is stamped `SUPERSEDED` with a `REDRAWN AS` pointer
(13 → §06 screens 26–26.8, 14 → §03 screens 20–20.3), while the contents rail, the lane brief
and §17's own summary table on p215 all still say those three carry a drawing. **Both
measurements hold together:** the reconciliation's *nine screens* is a count that still adds to
11, and it is **the old nine-screen list** — the three drawings it points at are no longer
where the list implies. **Nothing in §02 moves**, because §02 supplies 8 of the 11 and every one
of those eight is in this file with its page. The instability is entirely in the other three.

⚠ **1 · "Marked ◆ in the rail" is false.** The reconciliation's *Drawings to build* row says the
eleven are *"Marked ◆ in the rail"*, and the rail's own legend on p1 reads **"◆ carries a
drawing to build."** **Counted off the rail images at 3.2×, the rail carries 50 diamonds**, not
11: §02 7 · §03 14 · §04 9 · §05 5 · §06 9 · §07 1 · §08 2 · §17 3. Even scoped to the rows the
eleven could come from (§02's 7 + §17's 3) it is **10, not 9** — the extra is `02 Bill detail
◆`, which carries a band and a carry-over table and **no drawing**. A reader who takes the ◆ as
the index of what to build will size this module at roughly 50 screens rather than 9.
*(Several rail rows stand for many drawings — `17.1–17.9 the case chips` is nine — so the true
document-wide figure is the cover's `DRAWINGS 91 — 70 redesign · 21 as-built`, and neither 11
nor 50 is it.)*

⚠ **2 · `BIL-S19` is closed twice.** Entry **02.1** closes `BIL-S17 · BIL-S18 · BIL-S19 ·
BIL-S20` and entry **02.5** closes `BIL-S19`. Both verified at 4×. And 02.5's own heading chip
row lists only `Blocked BIL-S22` — it does not carry S19 at all, so the entry closes a
specification its own chips do not name. Two entries claiming one id is a build-order question
(which one closes it?) rather than a defect in the drawing, and it is recorded here because
§02's reconciliation counts drawings and never counts closures.

## ⚠ Two elevens, and they are not the same eleven

**The `BUILD THIS` string occurs on 14 pages of the document.** Every one was opened as an
image. **Three are prose mentions of the vocabulary, not bands** — p2 (*"Nine screens in §02
open with a `BUILD THIS` band…"*), p6 (*"How to read a screen entry. The `BUILD THIS` band
names the target…"*) and p203 (§15's change table). **The other 11 are real bands:**

| Where | Pages | Bands | Drawings under them |
|---|---|---|---|
| **§02** | p7 · p11 · p15 · p17 · p21 · p22 · p24 · p25 · p27 | **9** | **8** — entry 02's band covers the five tabs and has no drawing of its own |
| **§03** | p46 — `16 Scope` · `STEP ONE`, band `New build` *"Two inputs become five groups, and pricing starts here"*, **CLOSES `BIL-S24 · BIL-S25 · DEF-106 · DEF-1084`** · p51 — `17 Check` · `STEP TWO`, band `New build` *"One screen, priced, filterable, decisions inline"*, **CLOSES `BIL-S26 · BIL-S27 · BIL-S28`** | **2** | **2** |
| **§17** | — | **0** | — |
| | | **11** | **10** |

**So there are two elevens in this document and they name different sets.**

* **p6's eleven** is *"Drawings to build — 11, across nine screens: 01, 02.1, 02.2, 02.3 (two
  states), 02.4 (two states), 02.5, 10, 13, 14."* That is **8 in §02 plus 3 for screens 10, 13
  and 14**, and it does not count §03's two at all.
* **The eleven bands that exist today** are **9 in §02 plus 2 in §03**, and screens 10, 13 and
  14 carry none.

⚠ **p203 says outright that they used to be the same eleven, and why they stopped being.**
§15's own change table: *"**Three screens were told to build twice, differently.** Screens 10,
13 and 14 each carried a `BUILD THIS` band **and** a `REDRAWN AS` stamp pointing somewhere else
— two drawings to build for one screen, which is exactly the confusion the PO warned about when
the redraws moved. **The bands read `SUPERSEDED` now**, naming the destination, and the
drawings stay as the earlier reading rather than as work."* And on the next row: *"**Eleven
`BUILD THIS` bands** said nothing about readiness."*

**So the document counts eleven bands in §15 and eleven drawings to build in §02's
reconciliation, the two numbers agree, and the sets do not.** That coincidence is why this
survived a pass that was explicitly checking arithmetic: **both figures are 11 and only one of
them is still true of the pages.**

**What a build lane should take from it, stated plainly:** §02's eight drawings are safe to
build from and each is in the table above with its page. **The three the reconciliation
attributes to screens 10, 13 and 14 are not there to build** — follow the `REDRAWN AS` stamp
(13 → §06 screens 26–26.8, 14 → §03 screens 20–20.3) as `03-rulings-and-registers.md` records.
**And §03's two bands are work the reconciliation does not count**, so a lane sizing the module
off p6 alone will under-scope by at least those two, one of which (`16 Scope`) also closes two
defect ids — `DEF-106` and `DEF-1084` — that no other band in the document closes.

## ⚠ The finding that changes how this section is used

**Every `As built today` drawing in §02 is inside a collapsed disclosure, and the PDF renders
the disclosure closed — so not one as-built drawing in §02 exists in the file anyone reads.**

The document's own how-to-read (p6) says: *"Then a carry-over table whose arithmetic must
reconcile… Then **As built today, collapsed**. Then the spec table, the data flow and the field
table, which all describe today, not the target."* Measured on the pages: p009, p017, p019,
p023 and p026 each carry the line
`▶ As built today — kept because the findings below point at it. Do not build this.`
and **what follows it is a table, never a frame**. Across all 24 pages of §02 there are eight
rendered wireframes and every one of them is the REDESIGN.

**Why this matters for this pass, in two directions:**

* **It does not change what to build.** The brief's framing holds exactly: §02's work is the 8
  redesign drawings, every one captioned `NEVER BUILT`, and an as-built drawing was never a
  build target anyway.
* **It does change what can be checked.** §09–§11 of this document *"point at"* those as-built
  drawings as their evidence, and `CLAUDE.md` hard-won law 6 says to diff the running app
  against the drawing. **For §02 there is no as-built drawing to diff against** — only the spec
  tables, the data-flow blocks and the field tables on p009–p011, p017, p019–p020, p023–p024
  and p026. Any statement of the form *"the product has drifted from the as-built drawing"*
  about a §02 screen cannot be sourced from this PDF. The five frames exist only in the HTML
  artifact this PDF was printed from.

This is stated rather than filed as a defect because it is a property of the **source document**
(which lives on the default branch and which this pass does not own), not of this repository.
If a build lane needs those five frames, it needs the HTML, not the PDF.

## What I could not read, and why

| | |
|---|---|
| Pages in range | **p005 – p028, 24 of 24 opened as images.** None unreadable |
| Crops taken | 13, at 3.2×–4.0×, for the chip rows on 01/02/02.2, the four bands with no `CLOSES`, the three `CLOSES` lists, and the three contents-rail columns |
| **Could not read** | **the five collapsed as-built drawings** — they are not in the PDF (finding above), so they were not read and nothing about their content is recorded here |
| Not attempted | any comparison against running code. This lane measured the drawing only |

## One defect filed from this lane — `DEF-GOV-5229`

Not a billing defect and not a fault in the drawing. Found by verifying this file's
**own** citations before pushing it, which is the only reason it surfaced here at all.

**`CLAUDE.md` hard rule 4 says the audit-row pruning question *"is `OQ-1330`"*. It is
`OQ-1340`.** Read the two register rows side by side:

| id | row 106–107 of `12-governance/01-open-questions.md` | status |
|---|---|---|
| **`OQ-1340`** 🔒 | *"IS THE AUDIT ROW FOR A CORRECTED CHEQUE NUMBER KEPT WHEN AUDIT ROWS ARE PRUNED?"* — minted for hard rule 4's own narrowing | OPEN |
| **`OQ-1330`** | *"CAN A UTILITY SWITCH OFF THE CHECK THAT A READING'S UNIT MATCHES WHAT THE TARIFF PRICES IN?"* — `BR-MET-1160`, a metering question | OPEN — non-blocking |

**So the citation does not dangle — it points at somebody else's question**, which is
`DEF-2804`'s shape, this time on a money path. `12-governance/14-id-reservations.md` shows
why: `OQ-1330–1339` is the block reserved for `BR-MET-1160` and `OQ-1340–1349` the block
reserved for the 2026-09-02 payments rulings.

**Two lanes found this before me and neither filed a row.** `12-governance/11-change-requests.md:25052`
(2026-09-02): *"AND ONE CITATION IS WRONG IN `CLAUDE.md` ITSELF, WHICH IS WHY IT IS STAMPED
HERE RATHER THAN QUIETLY EDITED."* `EP-CWP-09-paying.md:393` (2026-09-04): *"AMENDED …
THE QUESTION IS `OQ-1340`, NOT `OQ-1330`."* Both recorded it in prose, in their own file,
and moved on. **Nothing counted it, so nothing knew it was spreading.** Measured today:
`OQ-1330` appears on **65 lines in 36 files**; **at least 34 of those lines are about
audit-row pruning**, the subject of `OQ-1340`. Among them `06-backend/openapi/schema.json`,
which is generated — so the wrong question id is served to every API caller — and p026 of
this blueprint's own PDF, which took it from `CLAUDE.md`.

*(The 34 is a floor, measured by matching the citing line itself for the pruning subject.
20 further lines were too mixed to classify mechanically and were left uncounted rather
than guessed at.)*

**Filed, not fixed.** `CLAUDE.md` is outside this lane's write scope and step 1 fixes
nothing. The row carries the whole measurement.

⚠ **FIXED 2026-09-14, BY PO RULING (Q3 of *"BILLING STEP 1 — THE FIVE QUESTIONS, RULED"*):**
*"It's a money-path rule pointing at the wrong question, and it spread precisely because
nobody filed it."* Hard rule 4 now cites `OQ-1340` and carries a dated note saying what it
read before. **54 further occurrences on 50 lines in 30 other files moved with it; 41
occurrences on 31 lines in 14 files were deliberately LEFT** — they cite the metering question `OQ-1330` legitimately (its own
register row, `BR-MET-1160`, `metering/validation.py`, the reserved ID blocks) or they exist
to RECORD this misread, including every sentence in this section. `DEF-GOV-5229` is closed.
⚠ **The measurement above is left at its original figures** — 65 lines in 36 files — because
it is what this lane measured on 2026-09-14 before the fix, and a measurement rewritten to
match its own remedy proves nothing.

## Two smaller notes, recorded so nobody re-derives them

* **p005 repeats a claim this repo corrected on 2026-09-12.** It states *"A Tailwind utility
  only emits CSS for a file listed in `07-frontend/src/styles/route-b-migrated.txt`; written
  anywhere else it renders as nothing at all."* `CLAUDE.md` records the PO ruling
  (`DEF-GOV-5102`, verbatim *"Yes correct it"*) that **it renders fine** — `tailwind.css`
  declares `@source "../"`, the compiler scans all of `src/`, and the ledger gates the *checks*
  (`G31`), not the CSS. The document's practical conclusion for Billing is still right for a
  different reason (*"All fifteen billing `.tsx` files are on that list"*), so nothing in §02
  changes; but a lane that takes the sentence as a rule will reach for a stylesheet class,
  which B14 rule 21 forbids. The document was read at `2.235.0` on 11 September and could not
  have known.
* **The document's B14 count is 30 and ours is 33.** §01 (p003) measured *"rule rows 1–21 and
  31–39 — 30 rules"* and said so loudly. Rules **40, 41 and 42** were ratified after it was
  read, and rule 42 (*a screen is built from the drawing AS AN IMAGE*) is the one that governs
  how this map was made.
