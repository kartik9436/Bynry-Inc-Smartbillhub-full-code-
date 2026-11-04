# Billing blueprint — the page map, and what kind of document this is

**Source.** `05-prototype/04 Billing, As Built.pdf`, on the DEFAULT branch
(`claude/confirm-understanding-3ktufc`) and on no working branch. **14,363,163 bytes,
249 pages.**

⚠ **THE BRIEFING FOR THIS PASS SAID THAT FILE IS NOT IN THE REPOSITORY. IT IS.**
`git ls-tree -r --name-only origin/claude/confirm-understanding-3ktufc -- 05-prototype`
lists it, and `git log --all --diff-filter=A` shows it added in `21872a6a`. Corrected here
because a lane that accepts "the drawing is missing" measures nothing, and a lane that
substitutes r10 produces a record nobody can trust.

## ⛔ THE TITLE SAYS "AS BUILT". THE DOCUMENT IS MOSTLY A REDESIGN, AND IT SAYS SO.

**This is the single most important thing on this page, because getting it backwards sizes
the whole module wrongly — in the wrong DIRECTION.**

The briefing's stated default was: *"a difference is DRIFT, not a build item — the product
has moved away from what was drawn."* **Measured from the pages, that is inverted.**

| Evidence | Where | Reading |
|---|---|---|
| **`DRAWINGS 91 — 70 redesign · 21 as-built`** | cover, p1, in the document's own figure band | **77% of the drawings are proposals, not photographs** |
| *"There is one drawing per screen and it is the one to build. Nine screens in §02 open with a `BUILD THIS` band…"* | p2, in red | The redesign is the target |
| *"Their current state is kept directly underneath, **collapsed and marked do not build this** — the findings in §09–§11 point at it, so it stays as evidence"* | p2 | **The as-built drawing is explicitly NOT to be built** |
| *"`TWO REVISIONS` This entry holds **both**: an **AS-BUILT** drawing of 2026-09-11 and a **REDESIGN that has never been built**. **Build the REDESIGN**"* | p6, entry 01 | Per-entry, each caption declares which it is |

**74 of 249 pages carry the word REDESIGN; 71 carry NEVER BUILT; 68 carry both.** Against
that, `AS BUILT` in caps appears **once**.

**So the work in this module is NOT drift-closing. It is the 11 drawings the document marks
to build**, and §02's own reconciliation table (p6) counts them:

| §02 reconciliation (the document's own figures, p6) | |
|---|---|
| Route patterns mounted | **7** (`App.tsx:932–953`) |
| Screens a clerk can reach | **15** — 1 list + 4 tab screens + 6 wizard steps + 4 standalone |
| **Drawings to build** | **11**, across **nine screens** — 01, 02.1, 02.2, 02.3 (two states), 02.4 (two states), 02.5 (entirely new), 10, 13, 14. Marked ◆ in the contents rail |
| Drawings of today, kept as evidence | **18** — eight collapsed under a target, ten standing alone because nothing is proposed |
| Drawings in total, §02 | **29** (11 + 18) |
| Second addresses | 1 — `/billing/:tab` serves five tab screens and draws no screen of its own |
| Tabs drawn as their own entries | 4 — Document · Charges · Corrections · Audit, sharing one route and one screen id (`BIL-05`) |
| **Screens seen in a browser** | **4** of 15 |

⚠ **THE COVER'S 91 AND §02's 29 ARE DIFFERENT SCOPES AND MUST NOT BE ADDED OR CONFLATED.**
91 counts drawings across the WHOLE document (§02 plus §17's as-built set and the
appendices); 29 counts §02 alone. Both are quoted above with their source page.

## ⚠ What the document could NOT do, in its own words — and we can

> **THE WALK: "Partial, front end only.** Chromium 1194 via Playwright against a `vite` dev
> server at 1440×1100. **No backend** — Django is not installed in this environment and there
> is no PostgreSQL, by the user's decision. **So no real row ever reached a screen, and every
> data-shape behaviour went unwalked."**
>
> **SCREENS ACTUALLY SEEN: 4 of 15** by its author, plus the bill detail's four tabs by the
> PO — five screenshots of a real issued bill on a live tenant (`v2.234.17`), 11 September,
> *"which corrected ten details in this document."*
> *"With nothing stubbed, zero… With three boot reads stubbed, four rendered and six threw."*

**This container HAS PostgreSQL running and a seeded tenant.** So the eleven screens this
document could not open, and every data-shape behaviour it could not test, are reachable
here. That is the largest single opportunity in this pass and it is why the walk is not
optional.

## ⚠ 15 of its 27 rulings exist in NO FILE

> **REPO UNTOUCHED — "Ruled, not merely observed.** Nothing is written to the repository, and
> on **2026-09-13** that stopped being a working constraint and became the decision:
> *"We ahve to write everything in HTML artifact only Billing, as built - noting in repo"*.
> **So this artifact is the system of record** — it carries the rulings (§16), the judgments
> taken here (§16) and the one question still open (§16), because there is nowhere else for
> them to be. **The cost is stated rather than hidden: 15 of the 27 rulings quoted here exist
> in no file, cannot be grepped, and nothing can count what depends on them."**

**This is the same disease Meter Reads had (13 rulings trapped in a PDF, `CR-096-BRC02`), and
it is worse here — 15, and by an explicit ruling rather than an oversight.** A ruling that
cannot be grepped will not be met by any lane building any other screen.

## Staleness — 26 versions, and three B14 rules it could not know

| | Document | Today |
|---|---|---|
| Version read at | **`2.235.0`** | **`2.261.4`** |
| Commit | `a1d37a68` · 11 Sep 2026 | `0571a0d3` · 14 Sep 2026 |
| Branch read | `claude/gracious-newton-gj0eka` | `claude/eager-johnson-r0k88b` |
| B14 rules | **30** — rows 1–21 and 31–39 | **33** — rows 1–21 and **31–42** |

⚠ **ITS B14 COUNT IS RIGHT FOR ITS DATE AND WRONG FOR OURS.** §01 measured 30 and said so
loudly — *"This document said '39 rules', `CLAUDE.md` says 38, and B14's own line 602 says
thirty-one. **Three sources, three numbers, none of them the count**"* — which is the
rule-count rot `CLAUDE.md` documents, caught independently. **Rules 40, 41 and 42 were
ratified after it was read** (32px page-head title · the product matches the blueprint
exactly · a screen is built from the IMAGE), so **three rules this document could not
have applied are binding on the build.** Counted from B14's own status table today:
`1–21, 31–42`.

⚠ **AND IT WAS READ AT `2.235.0` WHILE ITS OWN COVER SAYS "IS IT CURRENT? Could not check"** —
*"`origin/HEAD` does not resolve in this checkout… whether that branch is the product is not
something I can establish from here."* So **every as-built sentence in it is a hypothesis to
re-check**, exactly as the Assets and Meter Reads blueprints turned out to be.

## The document's vocabulary — four chips and two kinds of statement

Identical to the Meter Reads blueprint, and the distinction decides what may be built:

* **grey rail** — *"describes what the code does today… It commits nobody to anything."*
* **accent card** — a change specification. *"If a thing is not in a commitment card, nobody
  has undertaken to build it."*
* **Four state chips, and only four**, each saying what the WORK waits on, never how
  confident anyone is: **Exists behind** (the server already answers — only a screen or a
  wire is missing) · **New read** (a read must be published first) · **New build** (new code,
  a table, a component or an engine change) · **Blocked** (waits on a ruling, or on something
  this module does not own).
* **`No commitment`** — *"that absence is the finding, not an oversight."*
* ⚠ **`Every figure in every drawing is an illustration, never a value to build to` (B14 rule
  37). Do not assert one in a test or seed a fixture from one** — appendix B lists them all.

## Section map

Taken from the contents rail on pages 1–3, **read as images**. ◆ in the rail marks a screen
that carries work.

| § | Title | Notes |
|---|---|---|
| 00 | The read | cover figures, the walk, what is current |
| 01 | What these drawings are drawn to | the authority table; 194 dropdowns and their sources; **three pickers whose source does not exist yet** |
| 02 | **The screens, in journey order** | entries 01–28, the nine `BUILD THIS` screens |
| 03 | The bulk bill run, redrawn | pre-bill check; 17.L1–L5 the five layers; 16 Scope; 17 Check; 17.1–17.9 case chips; 17.10–17.15 held/blocked/ready; 17.16–17.20 bulk actions; 17.21–17.22 arrears; 18 Sign off; 19 Send; 20 Held queue; 20.1–20.3 catch up/hold/release |
| 04 | Single bills | 21 Who and when; 22.1 Interim; 22.2 First bill; 22.3 Final; 22.4 Back-bill; 22.5 Penalty; 22.6 Fee; 23 Confirm and send; 24 Periods |
| 05 | Budget bills | 25 + 25.1 Enrol · 25.2 Settle-up forecast · 25.3 Asks · 25.4 Portal/Level pay |
| 06 | Fix a bill | the thirteen reasons; 26 + 26.1–26.8 |
| 07 | Past billing runs | 27 Past runs |
| 08 | Bill printing | 28 Print bills · 28.1 Held back |
| 09 | What happened when it was driven | **the walk findings — read with §00's "no backend" caveat** |
| 10 | Absence register | |
| 11 | Rule compliance | |
| 12 | Where to start — the build index | *the nine that cost the most*; every build component |
| 13 | Cross-module | |
| 14 | Specification register | the one minted after the ruling; the twelve minted here |
| 15 | What this pass changed | |
| 16 | Appendix A–K | **decisions taken here · still open for the PO · every ruling and where it lives** — the 15 ungreppable rulings live here |
| 17 | The rest of the screens, **as built** | 03 Bill document · 04–09 run steps 1–6 · 10 Past runs ◆ · 11 One-time bill · 12 Budget Bills · 13 Fix a bill ◆ · 14 Pending queue ◆ · 15 Print bills |

⚠ **§17 IS THE AS-BUILT HALF AND IT MOVED ON PURPOSE.** p6: *"Eleven of the thirteen now have
a redraw of their own… and their as-built drawings stay where they are, as the evidence those
sections argue from. **Moved 2026-09-12 at the PO's direction; not one word of them was cut.**"*

## ⚠ Extraction is an index here, and a bad one — proved, not assumed

The text layer **drops digits and punctuation from the monospace address line.** Page 6's
address, which the image renders as

    /:tenant/billing · second address /:tenant/billing/all · S30 · BIL-01

extracts as

    tenantbilling    second address tenantbillingall    S  BIL

**Every slash, every colon, and every digit is gone** — `S30 · BIL-01` becomes `S  BIL`. A
screen→page map built by grepping for a route or a screen id returns **zero rows** on this
document. That is measured: `git grep`-equivalent over the extracted text found 0 pages
carrying both a `BIL-nn` id and a `/:tenant/billing` address, while the images carry both on
every entry. **B14 rule 42 is not a preference on this PDF; it is the only thing that works.**

## Coverage of THIS map — stated plainly

**Pages rendered: 249 of 249**, at scale 2 (2448×1584), in 32 s.
**Pages opened AS IMAGES for this map: 4** — p1 (cover and figures), p2 (how to read an
entry; the chip vocabulary), p3 (§01 authority table; §12–§17 contents), p6 (§02
reconciliation; entry 01's TWO REVISIONS caption).
**The rest of this map is from the contents rail and the text index**, and the section rows
above are therefore a SECTION map, not a per-entry page map.

⛔ **WHAT THIS MAP IS NOT: a per-entry page map.** The Meter Reads blueprint needed one and
got one; this document is twice the size and its per-entry boundaries have not yet been
walked page by page. **Until that is done, no page number below §-level should be cited from
this file.** A neighbouring blueprint's text index pointed a lane 59 pages away from the
screen it named.

## What this map is not

A specification, a diff, or evidence that any screen matches any drawing. **No screen has
been walked in a browser for this pass, and no diff has been taken in either direction.**

---

## ⛔ AMENDED 2026-09-14 — a per-entry page map NOW EXISTS for §14 and §17

The clause above (*"no page number below §-level should be cited from this file"*) was written
when 62 of the 249 pages had never been opened. **`CR-101-BRC03` opened them.**

**`04-the-unread-pages.md`** carries, read as images:

* **§14 · p172–p201** — the full 100-row commitment index, **all 100 card bodies**, a
  **card→page index** so a lane opens the exact page rather than infers a card, and the four
  group headings that make the register's arithmetic close (70 + 32 minted − 2 withdrawn = 100).
* **§17 · p215–p247** — every one of the thirteen screens: its stamp, its address, the
  commitment ids on its heading, its spec table, data flow, field table and Health row.
* **§15 · p204–p205** and **§01 · p004**.

⚠ **It also records twelve places where the step-1 files, the shared brief or the document
itself say something the pages refute** — including that §14's cards start on **p177**, not
p180, and that `BIL-S102`'s late-fee floor is **ruled and unbuilt**, not *"untouched"*.
**Read it before citing any page number in §14 or §17 from here.**

§02 and §03–§08 are unchanged: **no per-entry page map exists for those**, and the cover's
**91 drawings does not reconcile** — see that file's reconciliation, which gives both numbers.
