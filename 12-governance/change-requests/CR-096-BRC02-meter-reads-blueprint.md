# CR-096-BRC02 · Meter Reads against its blueprint

**Raised** 2026-09-13 · **Branch** `claude/hi-0jmv62` · **Block** `BRC02` (see §0)
**Status** OPEN — step 1 measuring; nothing built.

---

## 0 · The number, and why it is 096 and not 095

`13-change-process.md` §0 numbers a change request from its branch's reserved block.
This branch's own block, `BRC01` (`CR-090`–`094`), is **SPENT**: 091, 092 and 093 used,
and 090 and 094 taken by sibling branches. `14-id-reservations.md` says what to do —
*"a further CR raised on this branch takes a number from `BRC02` (`095`–`099`) only after
claiming that block here."*

⚠ **`CR-095` IS ALREADY TAKEN BY A SIBLING TOO.** Verified against the REMOTE at the
moment of use rather than trusted from the file: `allocate.py cr --verify 95` answers
*"TAKEN — a sibling pushed it"*, while `96` and `97` answer *"still free on every branch"*.

**So `BRC02` was breached before it was claimed, exactly as `BRC01` was** — the second time
this has happened, and it is the same lesson the reservations file already records: *"the
SUFFIX would not have saved us, because `CR-095-BRC01` and a sibling's `CR-095-BRCxx` are
different STRINGS that git merges cleanly; what caught it is `allocate.py --verify` asking
the REMOTE at the moment of use."* The block is claimed here with 095 recorded as lost.

## 1 · What arrived

The PO lifted the hold on Reads work (*"Hold on Reads work for some time"*) and asked for
the Meter Reads module to be measured against its blueprint and then built to it.

The drawing is **`05-prototype/03 SMARTBillHub — Meter Reads blueprint.pdf`**, on the
DEFAULT branch only. **120 pages, 114 with content** — the briefing for this pass said 117,
and every page number downstream is taken from the corrected count.

## 2 · WHAT SIGNED STATEMENT IS BEING REVERSED — the reason this is a CR and not a defect row

**This is the whole of why a change request exists here.** A defect says the product does
not do what was expected. This says **what was expected has changed**, and a defect row
cannot carry a supersedes chain.

The blueprint's section 01 carries a table of PO rulings from 2026-09-12 and 2026-09-13
marked `NOWHERE`, under the document's own words:

> **Every August ruling reached the repo. Not one from this session did.** … This document
> becomes the single point of failure for thirteen decisions. **They cannot be grepped**, so
> no lane building any other screen will meet them, and **nobody can count what depends on
> them** — which is the honest answer to "how many gaps are there?": today, unknowable. A
> blueprint holding rulings that exist nowhere else is not a record, it is a hostage.

**At least one reverses a ratified rule**, quoted from entry 01:

> *"Need Attention — does not add any value."* The tab goes. That supersedes **`BR-MET-060`**,
> which says Reads *opens* on the exceptions, and retires **`US-MET-019`**.

| | |
|---|---|
| **Reversed** | `BR-MET-060` — *Reads OPENS on Needs attention* |
| **Retired** | `US-MET-019` — the Needs-attention landing with its Missing / Flagged / Disputed tiles |
| **By** | PO ruling, 2026-09-12 |
| **Still obeyed in the product** | **Yes.** Walked at 1440 on 2026-09-13: `/:tenant/reads` opens on Needs attention with three tiles and no table. `ReadsListPage.tsx:24` states the superseded rule in its own words — *"It lands on Needs attention (BR-MET-060), on EVERY open."* |

⚠ **Two of the three counts survive the move and one does not.** *Flagged* and *Disputed* are
already declared filters on All reads, so they become filter chips. ***Missing* has no filter
and never had** — the server cannot slice the reads list that way. It moves to Read cycles
instead, *"which is the only place the number means anything: a cycle has a window and an
expected set, and 'short by five' is a sentence about a cycle."*

### ⚠ The count is NOT thirteen, and the document is wrong about its own table

Read as images at scale 4 (pages 4–7): the table holds **fourteen rows, of which five carry
a green repo chip and NINE carry `NOWHERE`.** The document's heading and its own `MR-53`
both say thirteen; counting quoted strings rather than rows gives ten. **Nine is the row
count.**

**And nine understates the exposure.** Ten more PO utterances from the same two days are
quoted only in the document's BODY, never in the table. All nineteen were grepped across
`12-governance/` and `04-docs/`: **zero hits.** The decision log holds 120 rows dated
2026-09-12/13 and not one is a Meter Reads ruling.

**So the real number is nineteen decisions that exist nowhere but inside a PDF**, and the
document undercounts its own hostages.

Classified, with both halves of each written out in
`04-docs/05-modules/04-metering/blueprint/04-rulings-and-specifications.md`:

| Kind | Count | Where it belongs |
|---|---|---|
| Reverses or collides with a **signed rule** | **3** | this change request, with its supersedes chain |
| A **new rule** | 9 | the module's `02-business-rules.md` — except one, which governs every detail screen in the product and belongs in **B14** |
| A **judgement** | 6 | `12-governance/02-decision-log.md` with its figure |
| **An open question wearing a ruling's clothes** | 1 | `01-open-questions.md` |

## 3 · Classification

**CHANGE**, for the thirteen rulings and the 53 specifications they and the drawing create.

**NOT a change, and filed separately as defects** — `13-change-process.md` §1 and the PO's
own ruling of 2026-09-10 (*"CR is change in product, defect is product does not do what is
expected"*), plus the standing rule that an ambiguous case is a DEFECT, because filing our
misunderstanding as a change converts our error into the customer's new requirement.

## 4 · What is already built, and what the document gets wrong about it

⚠ **THE DOCUMENT IS 24 VERSIONS STALE AND IT IS STALE IN OUR FAVOUR.** Read at `2.237.10`
on 2026-09-12; the product is at `2.261.3`. Its own page 2 scopes the staleness: it covers
every sentence about what the code does today, **and not the rulings**.

**Its headline finding is already fixed**, verified this pass by clicking rather than by
reading:

| The document says | Measured 2026-09-13 |
|---|---|
| *"The reading detail page does not open."* Clicking any meter replaces the page with `TypeError: t.history.map is not a function` | **FIXED.** `ReadDetailPage.tsx:469` reads `historyQuery.data?.rows` — it unwraps the paged envelope. Clicked a real reading in Chromium at 1440: **zero page errors**, and the page renders the usage math (`(46754.000000 − 44000.000000) × 10.000000 = 27540 kWh`), the flag reason, the three rules that could not run, the tags and the compliance metadata |

Its other two headline claims are under measurement and are **not** being taken on trust —
the equivalent claim in the Assets blueprint (*"the screen has no door"*) turned out to be
false, with eight doors that had existed since the day before.

## 5 · Size — TO BE COMPLETED BEFORE ANY BUILD

The document names **53 specifications** (`MR-##`). Sizing this CR as "build 53" would be
inventing scope. Each is being given a verdict against the code — **already done / partly /
not done / blocked** — and the sorted list goes to the PO with counts, which is what
§5 asks for: sized and confirmed in plain English with a figure.

⚠ **AND THE ANSWER IS NOT THE ASSETS ANSWER. I EXPECTED IT TO BE AND SAID SO; IT IS NOT.**
`CR-092-BRC01` found **17 of 24** already built. Meter Reads, measured against this
branch's code:

| Verdict | Count |
|---|---|
| **Already done** | **1** (`MR-01`) |
| Partly done | 9 |
| Blocked | 3 |
| **Not done** | **40** |

The reason is structural rather than surprising: **17 of the 53 are `NEW BUILD`**, and the
four largest are a redesign the PO ruled on 2026-09-12/13 — *after* the code this branch
carries. What did move is the one that mattered most: **`MR-01`, the crash the PO called
"the priority", is fixed.**

⚠ **TWO OF THE FOUR LARGEST SCREENS ALREADY EXIST, AT ANOTHER ADDRESS.** `MR-30` (a cycle
detail) and `MR-44` (a route detail) are drawn at `/reads/cycles/{id}` and
`/reads/routes/{id}`, **which are routed to nothing**. But
`features/tenancy/CycleDetailPage.tsx` (45,982 bytes) and `RouteDetailPage.tsx` (42,688
bytes) are built, tabbed and routed at
`settings/reference-data/routes-cycles/{cycles|routes}/{id}` as `SET-07D` and `SET-06D`.
**Verified in `App.tsx` this pass.** Two measure lanes disagreed about whether these screens
exist — one walked the drawn address and found *"not built yet"*, the other found the files
— and **both were right about different things**. That is the maintenance process's step 2
exactly: locate the file actually MOUNTED, not the one whose name matches.

**So step 2 moves and extends these two; it does not build them.** Two of `MR-44`'s own
claims are already false against them — read-windows *is* called and the walk order *is*
written.

## 6 · Execute

Through `12-engineering-plan.md` Addendum r11, unchanged — except where the maintenance
process applies instead. **Most of these screens are live and a user can reach them today**,
so by `22-product-maintenance-process.md`'s one question they are MAINTENANCE, not BUILD,
and they get reproduce → locate → blast radius → minimal fix → browser proof → regression
walk. A live screen redrawn end to end is named in that process as maintenance on purpose.

## 7 · Version

Not yet allocated. `10-scripts/allocate.py version --bump change` at the first build.

## 8 · Rollback

Stated before shipping, per §8. Nothing is shipped yet.

---

### Related

* `04-docs/05-modules/04-metering/blueprint/00-index.md` — the entry → page map, made from
  the pictures per B14 rule 42.
* The module's `conformance/` folder holds 23 records and **every one is `CR-089`,
  Premises & Units**. Counted, not assumed. **Nothing in this repository has ever diffed
  these routes against any drawing.**
