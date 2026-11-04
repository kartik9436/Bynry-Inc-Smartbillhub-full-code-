# Meter Reads blueprint — entry → page map

**Source.** `05-prototype/03 SMARTBillHub — Meter Reads blueprint.pdf`, on the DEFAULT
branch (`claude/confirm-understanding-3ktufc`) and not on this one. 4,779,186 bytes.

> ⚠ **IT IS 120 PAGES, NOT 117.** The briefing for this pass said 117. Counted with
> `pypdfium2`: **120 pages, of which 114 carry content** — 115–120 are blank (each renders
> to the identical 4,540-byte PNG). Corrected here because every page number downstream is
> taken from this file.

**How this map was made.** Every page rendered with `10-scripts/pdf/pdf_render.py` (120
pages in 5.2 s) and the map built by **looking at the pictures**, per B14 rule 42. The text
layer was used only to find candidate pages; every heading below was then opened as an
image. Extraction is an index and not the specification — on this document it returns
`readstaball` for `/reads?tab=all` and scrambles the entry order in section 04.

```
git show "origin/claude/confirm-understanding-3ktufc:05-prototype/03 SMARTBillHub — Meter Reads blueprint.pdf" > /tmp/reads.pdf
mkdir -p /tmp/reads-png
python3 10-scripts/pdf/pdf_render.py /tmp/reads.pdf /tmp/reads-png 2 8,9,12
```
The filename carries an em-dash; quote it exactly. `pypdfium2` may be absent from a fresh
container — it was on 2026-09-13 — and `pdftoppm`, `PIL` and `pypdf` all fail here.

## What this document is

**An as-built blueprint of nineteen addresses**, read at product version **`2.237.10`**,
commit `3706b459`, on **2026-09-12**. Its own cover figures:

| | | | |
|---|---|---|---|
| Entries | **21** | Drawings | **26**, one per screen |
| Drawn | 17 of 21 | Processes | 3 |
| Wizard stages | 5 | Naming no door | **2 of 19** |
| Journeys walked | 3 of 3 | Journey issues | **10** |
| Rule violations | **18** | Fields served | 100 of 121 |
| Fields never traced | 0 | Cross-module facts | 28 |
| Stated absences | **181** | Specifications | **53** |
| Out of scope | 13 | | |

**It uses the same vocabulary as the Assets blueprint**, and the distinction decides what
may be built from it:

* a **description** — grey rail — *"a statement about what the code does today … It commits
  nobody to anything."*
* a **commitment** — accent card — *"a named piece of work … If a thing is not in a
  commitment card, nobody has undertaken to build it."* The series is **`MR-##`**.

Four state chips and only four: **EXISTS BEHIND** (19) · **NEW READ** (7) · **NEW BUILD**
· **BLOCKED**. A screen no specification covers carries **No commitment**, and the document
says *"that absence is the finding, not an oversight."* Every chip is DERIVED from the
register rather than typed beside the heading.

**Drawings are desktop only, one per screen, at a fixed 1440 viewport, never reflowed.**
Every screen in the module is a staff screen, so the absence of a phone drawing is a
property of the document and not of the product.

## ⚠ The staleness is 24 versions, and it is in our favour

The product is at **`2.261.3`** today (2026-09-13). **Verified this pass, by clicking:**

| The document's headline finding | State on this branch |
|---|---|
| *"The reading detail page does not open."* Clicking any meter replaces the page with `TypeError: t.history.map is not a function` | **FIXED.** `ReadDetailPage.tsx:469` reads `historyQuery.data?.rows` — it unwraps the paged envelope. Clicked a real reading in Chromium at 1440: the page opens with **zero page errors** and renders the usage math, the flag reasons, the rules that could not run, the tags and the compliance metadata |

So **every as-built sentence in this document is a hypothesis to re-check**, exactly as the
Assets blueprint turned out to be. What does NOT go stale is the rulings.

## ⚠ Thirteen rulings live here and NOWHERE else

The document's own section 01 carries a table of PO decisions from **2026-09-12 and
2026-09-13**, each marked `NOWHERE`, under this sentence:

> **Every August ruling reached the repo. Not one from this session did.** … This document
> becomes the single point of failure for thirteen decisions. **They cannot be grepped**, so
> no lane building any other screen will meet them, and **nobody can count what depends on
> them** — which is the honest answer to "how many gaps are there?": today, unknowable. A
> blueprint holding rulings that exist nowhere else is not a record, it is a hostage.

**At least one reverses a signed rule.** On entry 01:

> *"Need Attention — does not add any value."* The tab goes. That supersedes **`BR-MET-060`**,
> which says Reads *opens* on the exceptions, and retires **`US-MET-019`**.

**That is a change to the agreement, not a defect**, and it is why this pass raises a change
request rather than only defect rows: a defect row cannot carry a supersedes chain.

⚠ **AND THE PRODUCT STILL OBEYS THE SUPERSEDED RULE.** Walked at 1440 on 2026-09-13:
`/:tenant/reads` opens on **Needs attention** with its three tiles (Missing 18 · Flagged 24
· Disputed 0) and no table. `ReadsListPage.tsx:24` says so in its own words — *"It lands on
Needs attention (BR-MET-060), on EVERY open."*

## The 21 entries

Entry numbers are the document's own. **They are NOT in page order** — entries 20 and 21
are drawn in place inside section 04, between 15 and 16, because the cycle and route detail
screens belong beside the lists they open from. A text index cannot see that.

### § 02 · Reading the meters — pages 8–20

| # | Entry | Page | Address |
|---|---|---|---|
| 01 | Reads — Needs attention | 8 | ~~`/:tenant/reads?tab=attention`~~ — **the tab and its three tiles are WITHDRAWN by ruling** |
| 02 | Reads | 9 | `/:tenant/reads` |
| 03 | One reading | 12 | `/:tenant/reads/{readId}` |
| 04 | Correct the reading | 16 | dialog |
| 05 | Dispute the reading | 18 | dialog |
| 06 | Clear the dispute | 20 | dialog |

### § 03 · Getting the readings in — pages 21–38

| # | Entry | Page | Address |
|---|---|---|---|
| 07 | Upload reads · stage 1 · Extract | 22 | `/:tenant/reads/upload` |
| 08 | Upload reads · stage 2 · Transform | 24 | stage 2 of 5 |
| 09 | Upload reads · stage 3 · Validate | 27 | stage 3 of 5 |
| 10 | Upload reads · stage 4 · Load | 29 | stage 4 of 5 |
| 11 | Upload reads · stage 5 · Result | 33 | stage 5 of 5 |
| 12 | Add a single reading | 34 | dialog |
| 13 | Accept flags in bulk | 37 | bulk bar + dialog |

### § 04 · Read cycles — pages 39–60

| # | Entry | Page | Address |
|---|---|---|---|
| 14 | Routes | 40 | `/:tenant/reads/routes` — **NO DOOR** |
| 15 | Read cycles — the list | 40 | `/:tenant/reads/cycles` — **NO DOOR** |
| 20 | A cycle — the detail | 42 | drawn in place; a NEW screen |
| 21 | A route — the detail | 49 | drawn in place |
| 16 | Meters still to read | 54 | panel |
| 17 | Route sheet | 56 | dialog → print tab |
| 18 | Estimate a missing read | 58 | dialog |
| 19 | The retired drawer address | 60 | a second address rather than a screen |

### The back sections

| § | Title | Pages |
|---|---|---|
| 01 | The standards every screen here is drawn to | 2–7 |
| 05 | What broke when the product was driven | 61–62 |
| 06 | Every stated absence, and its one decision | 63–66 |
| 07 | Where the screens depart from the rules | 67–70 |
| 08 | Where Meter Reads meets the other modules | 71–74 |
| 09 | The specification register — the 53 `MR-##` | 75–81 |
| 10 | What this pass changed, line by line | 82–93 |
| — | Appendices | 94–114 |
| — | *(blank)* | 115–120 |

## What the document says a reader should not miss

Three, quoted and then checked:

1. **The reading detail page does not open.** → **Already fixed.** Verified by clicking.
2. **Routes and Cycles have no door.** Both routed, built, tested and translated; the
   sidebar renders no submenu by two PO rulings, their route constants are imported by
   nothing, and no page links to either. *"They open only by typing the URL."* The suite that
   looks like it would catch this asks whether a declared path renders a real screen — **not
   whether a user can get there** — and the gate that does ask the door question covers
   customer-portal screens only. **NOT YET RE-CHECKED THIS PASS.**
3. **A primary button renames itself for a door it will not open.** On a billed reading the
   action becomes *Correct billed read* and is disabled with *"that path is not built"* —
   while `POST /reads/{id}/billed-correction` **is served**, the money screen exists, and the
   server's own copy tells clerks to use it. **NOT YET RE-CHECKED THIS PASS.**

## Prior records — there is no coverage to inherit

`04-docs/05-modules/04-metering/conformance/` holds **23 files and every one of them is
CR-089, Premises & Units.** Counted, not assumed: zero mention Reads. **Nothing in this
repository has ever diffed these five routes against any drawing.**

## What this map is not

A map. Not a specification, not a diff, and not evidence that any screen matches its
drawing.
