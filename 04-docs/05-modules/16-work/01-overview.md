# 16 · Work — module overview

**Module:** `work` (product name: **Work**; the rail entry between Payments and Finance) ·
**Source:** `CR-070` · **Blueprint:** *SMARTBillHub Work Module Blueprint, read of 2.128.2 /
47108051* (≥128 pages, 21 sections; **sections 1–14 read, to card `WM-35`; §15–§21
UNREAD** — see §10) · **Docs module:** the sixteenth folder, following `15-portal/`
(`CR-070` §10 says `17-work/`; the next free number was 16 — `DEF-WRK-3547`).

## 1 · What this module is

The field half of a utility: who goes where, with what, to do which job — and the one
door through which what they find becomes a meter read. **It is built from the far end.**
The blueprint's own verdict:

> *"A utility using SMARTBillHub today can set nothing up, write no job down, raise no job
> from a screen, assign nobody, and send nothing to a phone — and yet if a work order
> somehow reaches Completed, the review, the acceptance, the meter reading and the audit
> trail are all correct and well tested. That is not a half-built module. It is a module
> built from the far end."*

Forty-three requirements checked against the code: **12 built · 4 partly · 27 missing.**
Six tables exist in `apps/metering/connections.py` under the name New Connect; fourteen
finished write actions have no route; twenty-four starter templates are seeded and inert;
four Settings cards render *arrives with Work*; four Work controls on the Assets screen ship disabled — three checkboxes and the *Parts in Work →* button (`CR-070` §0; this line said *three Assets checkboxes* until 2026-09-03 — `DEF-WRK-3601`).
*"Almost all of it was already designed by the Product Owner and never built."*

## 2 · Three Product Owner rulings of 2026-09-03 this module is built on

| Ruling, verbatim | What it decides | Where it lands |
|---|---|---|
| ***"it will become the module itself"*** | Field work is its own module — `apps/work/`, the eleventh code module — owning crews, technicians, skills, certifications, parts, work orders, templates, assignments, schedules, rules and labour rates. Cross-module writes forbidden from the first commit | `BR-WRK-001`, `BR-WRK-002`; `US-WRK-005`; decision log 2026-09-03 |
| ***"Use Work-nnn - code for this"*** | Screens are `Work-001`–`Work-033`, one per blueprint `WS-` label in its order; `S147` stays the next free `S` | `BR-WRK-005`; §6 below; decision log 2026-09-03 |
| ***"Dont add Tax on work order - for now"*** | `WM-46` is **not built** — no third tax base, no `Work-031`, no tax line on the report. B4 §Tax ❄️ stands. **`WO-4822`'s report totals `$138.42`, not the wireframe's `$149.84`** | `BR-WRK-052`; `US-WRK-052`; **decision-log row DRAFTED, not yet in the log** — `scratchpad/cr070/governance-rows.md` §B |

## 3 · Size — the approved count table, delivered, with every delta stated

| What | Approved | Delivered | Delta and why |
|---|---|---|---|
| Specifications | 49 (`WM-01`–`49`) | **49**, kept as handles, minted into no product series | none |
| Screens | 33 — 9 exist, 24 new (3 phone) | **33** — 9 exist (`Work-001`–`006`, `018`–`020`), **24 new** (`007`–`017`, `021`–`033`) incl. 3 phone; 7 undrawn surfaces as sub-screens | none. ⚠ `CR-070` §9's *"WS-01–WS-09 already drawn"* is wrong (`DEF-WRK-3543`) |
| Epics | 10 | **10**, `EP-WRK-01`–`10`, the report's §4 grouping | none |
| Stories | ~55 | **54**, `US-WRK-001`–`054` | −1: 49 cards + 5 of ours; nothing else needed one |
| Business rules | ~40 new + 9 signed cited | **57** new (`BR-WRK-001`–`057`) + **22 inherited rules cited, never restated** | +17: the cards carried more rule-shaped sentences than the estimate; each is cited by a story and names a test |
| Test cases | ~330 (≥4/story, ≥1 negative, +isolation) | **352** — 132 negative, 53 tenant-isolation; 53 of 54 stories ≥4 (`US-WRK-052` has one, by design) | +22 |
| Test data sets | ~55 | **53** concrete + 1 *None* (`US-WRK-052`) | one per story |
| Tables | 25 named in cards (§16 says 23) | **25** card-named **+ 9 ours** the wireframes need, each marked `[ours — §16 unread]` | 23-vs-25 unresolved until §16 is read (`03-field-map.md` D-15) |
| Changed columns | ~27 across 4 tables | **28** across `work_orders`, `work_order_templates`, `stored_documents`, `taxes` — **the two `taxes` changes NOT BUILT** | +1 |
| Endpoints | ~70 (`CR-070`: ~30) | **94** new + 5 existing, each marked card / wireframe / story | +24: reference data (21, may collapse onto `BR-SHL-035`'s generic routes) and the order's evidence (11) — foot of `07-endpoints.md` |
| Phases | 3 | **3** (`CR-070` §11) — 6 · 12 · 36 stories | none |
| Journeys | 8 | **8**, `J60`–`J67`, described; **files not written** | none |
| Open questions | 3 to mint + `OQ-376` cited | **8 minted** (`OQ-WRK-1490`–`1497`) + `OQ-376`, `OQ-249`, `OQ-371` cited | +5: four the report listed as candidates that a story genuinely could not proceed without (lapsed certification · web-blocked login · reschedule message · retention) and one the blueprint itself sends to the register (the dispatch batch, non-blocking) |

## 4 · Step 0 — what moved under the blueprint, and what the record got wrong

Read at `2.128.2` / `47108051` on 2026-09-03; HEAD `654034ed` at the predecessor's read
was 82 commits later and `package.json` still `2.128.2`. Every *"as built"* claim below was
re-verified by the predecessor lane at that HEAD and **is `UNVERIFIED` again for any lane
that reads this later** — the blueprint's own instruction.

| The blueprint or `CR-070` says | Measured 2026-09-03 | Consequence |
|---|---|---|
| Blueprint headline: *"thirty-eight specifications"*; §3 spine `WM-01`…`38`; §20's corrections never mention 38→49 | **FALSE.** 49 cards in the readable text | Build from the cards. `DEF-WRK-3542` |
| `CR-070` §9: *"Nine of the thirty-three are already drawn (WS-01–WS-09)"* | **FALSE.** Existing: `WS-01`–`06`, `WS-18`–`20`; `WS-07`/`08`/`09` are NEW BUILD / NEW READ by their own chips | `05-user-stories.md` §2. `DEF-WRK-3543` |
| `CR-070` §8 titles | **19 of 49 are not the card's title**; `WM-09`/`WM-11` effectively swapped; `WM-24` mis-titled | Ids stay; titles corrected in `05-user-stories.md` §2. `DEF-WRK-3544` |
| `CR-070` §11: *"read WM-24 in full before writing the offline queue"* | **Misaimed** — the offline queue is `WM-36`; the *trap* phrase is not in the readable text | `US-WRK-044` marks `WM-36` unread. `DEF-WRK-3545` |
| `CR-070` §3/§5: *"one change to an existing table"* | **Four tables, 28 columns** | `03-field-map.md` §3. `DEF-WRK-3546` |
| `CR-070` §10: `17-work/` | **16 is next**; 14 unused | Written here. `DEF-WRK-3547` |
| `CR-070` §6: *"raise the four open ones"* | **Three to mint** — `WM-27`'s is `OQ-376`, already OPEN *"blocking the send only"* | Cited, not re-minted (law 13). `DEF-WRK-3548` |
| No `14-id-reservations.md` row for `CR-070`'s ids at dispatch | **TRUE** | The parent lane reserved the block; the row is drafted. `DEF-WRK-3549` |
| `WS-25` draws On hand · Reorder at · *issues deduct stock* | **Contradicts `WM-07`/`WM-22`** and `CR-028` §11-D5 | Not built; `OQ-WRK-1490`. `DEF-WRK-3550` |
| `WS-23` draws *"blocked from 4 template types"* | **Contradicts `WM-21`** (*"refusing … is out of scope"*) | Not built; `OQ-WRK-1493`. `DEF-WRK-3551` |
| Blueprint §12: *"None carries an official screen id — the reserved band S61–S90 is exhausted"*; `WS-05`'s *"decision D1"* | **Superseded the same morning** — PO *"Allocate new numbers and code"*: `S87`, `S88` ratified, `S86` reserved, `S135` (`WRK-19`), `S136`–`S140` reserved to B18 | §6's dual-id table; B18's *work-order detail* slot released (decision-log draft) |
| Blueprint §17: *"Allocate screen ids beyond S90"* | **Moot** — `Work-nnn` | — |
| `WM-27` *"waits on a PO ruling on the vocabulary"* | Already `OQ-376` | Cited |
| `WM-44`: *"disconnects.py refuses this act four times"* | One constant `VISIT_NOT_SCHEDULED`, one payload site, two docstring mentions | The design it names is the same; recorded |
| *"fifteen finished write actions"* | §7 lists **16 names — 14 writers, 2 readers** | The 14 writers are pinned in `US-WRK-002` |
| Tenancy is path-based; `brazosbend` is the house slug | **TRUE** — every route here is `/{tenant}/…` | — |

**Two things the blueprint got right that a copying lane would get wrong, kept verbatim:**
gas is gated on the **light-up**, not the meter set (`BR-WRK-013`); and *"a value outside
its bounds is flagged and accepted … a missing required photograph is a different thing"*
(`BR-WRK-039`, `BR-WRK-040`).

## 5 · The three phases, each one launchable (`CR-070` §11)

| # | Phase | Launch | Stories | Decision needed |
|---|---|---|---|---|
| **0** | Foundations | *A clerk can raise, hold, cancel and close a job this week* — `connection_id` nullable, fourteen writers mounted, the approval queue, the module skeleton with its boundary gate, the honest state of two screens, the fixture | 6 | **None.** Exit test on a deployed build, not a green suite |
| **1** | The template bundle | *A utility authors its own job templates, and the wizard proposes them* — six lookups, the parts register, seven child tables, the eight-step builder, versions, step 6 | 12 | **None.** `BR-MET-109` already says templates are developed *"in work order section"* |
| **2** | Dispatch and the phone | *A dispatcher assigns work to a crew, and the technician works it on a phone* — workforce, twelve columns, append-only assignment, the dispatcher, the edit screen, the map, rules, the two doors, the phone, readings that post, evidence, costing, the report, performance | 36 | **Unblocked by the placement ruling.** Five stories stub on `OQ-WRK-1492`–`1496`; one on `OQ-376`; one is closed by the tax ruling |

**Rollback (`CR-070` §14):** phase 0 rolls back cleanly; from phase 1 rollback is *hide the
section and keep the data*, never *drop the tables*.

## 6 · The thirty-three screens, and the dual ids where a surface already had one

**Series `Work-\d{3,5}(?!\d)`** — the lookahead is load-bearing (`DEF-2804`); zero-padded to
three, chosen at birth. **Whether a `Work-` number is ever rendered on screen is unruled**;
the staff badge shows r10's module id (`WRK-01`…`19`) and `g29` is not pointed at these.

| Work | WS | Title | State | Also known as |
|---|---|---|---|---|
| `Work-001` | `WS-01` | New connects | exists · no commitment | `S86` (reserved to B18) |
| `Work-002` | `WS-02` | **The build** — its progress, its jobs | exists, on **TWO HOSTS** since 2026-09-04 | the premises' Build and Work orders tabs (`PRM-02`) and the account's Work tab (`ACC-02`). ⚠ **`S88` · `NCT-02` IS RETIRED** (`CR-070 §W.11`): `/connections/<uuid>` still resolves and redirects, so it carries no badge |
| `Work-003` | `WS-03` | Work order drawer | exists | a `?order=` drawer over EITHER host's work-orders tab |
| `Work-004` | `WS-04` | New Connect wizard · step 6 | exists | `S87` · `NCT-01` |
| `Work-005` | `WS-05` | Work order templates (blank, replaced by `Work-013`) | exists | `S135` · `WRK-19` |
| `Work-006` | `WS-06` | Work rail entry (becomes the dispatcher's shell) | exists · no commitment | — |
| `Work-007` | `WS-07` | Work · Orders — the dispatcher | **new** | r10 `WRK-01` |
| `Work-008` | `WS-08` | Work · Order detail · Checklist | **new** | r10 `WRK-02`; **B18's reserved *work-order detail* slot released** |
| `Work-009` | `WS-09` | Work · Awaiting approval | **new read** | — |
| `Work-010`–`012` | `WS-10`–`12` | The phone: Today · the job · readings, parts, signature, close | **new** | r10 mobile |
| `Work-013`–`017` | `WS-13`–`17` | Templates list · builder steps 1, 3, 5, 8 | **new** | r10 `WRK-04`, `WRK-05.x` |
| `Work-018` | `WS-18` | Settings › Reference data — the Work group | exists | `S8` · `SET-04` |
| `Work-019` | `WS-19` | Settings › Numbering — the Work group | exists | `S8` · `SET-08` |
| `Work-020` | `WS-20` | Assets — the four Work controls that ship disabled | exists · no commitment | the Assets screens |
| `Work-021`–`027` | `WS-21`–`27` | Edit · Template detail · Crews · Technician · Parts · Rules · Performance | **new** | r10 `WRK-03`, `15`, `07`, `08`, `10`, `06`, `11` |
| `Work-028` | `WS-28` | Assets › Asset detail › Raise work order | **new** | a sibling of `S53` · `AST-07` |
| `Work-029` | `WS-29` | Accounts › Move-out › Field visit | **new** | the move-out wizard's step 4 |
| `Work-030` | `WS-30` | Settings › Work › Labour rates | **new** | — |
| `Work-031` | `WS-31` | Settings › Work › Taxes on a work order | **NOT DRAWN — PO ruling** | a filter of `S13` |
| `Work-032` | `WS-32` | The work order report | **new** | — |
| `Work-033` | `WS-33` | Work order detail › Readings — the photograph | **new** | r10 `WRK-02` |

**Seven undrawn r10 surfaces take no id and are sub-screens** — the New order wizard and
the map under `Work-007`; the rule builder under `Work-026`; the skills wizard under
`Work-024`; part detail, issue parts and add part under `Work-025` (`05-user-stories.md` §4).

## 7 · What is already built, and it is the hard half

| Already finished | What this module adds |
|---|---|
| Six tables under RLS `FORCE`, a derived connection state (seven tests in order), a service state machine, an order state and outcome, `WO-{0000}` numbering, `blocked_by`, `mode` stamped per order, five audit actions | The third axis — dispatch state — and the twelve columns a dispatcher needs |
| `submit_field_result` → `accept_field_result`: one press, four consequences, a refusal anywhere rolls the whole acceptance back; the set read posts dated to completion | A phone in front of it, a queue behind it, and a report generated from it |
| Fourteen write actions, written and tested, reachable from a Python shell | One route each |
| Twenty-four starter templates seeded across eleven services, gas gated on the light-up | The seven child tables and the builder that make them bundles, and a gate that keeps them read |
| Four Settings cards, four number series, three disabled Assets checkboxes, one Work rail entry — every one an honest promise | The tables behind the cards, a column for the template number, the door the checkboxes open, the dispatcher the rail entry becomes |
| `taxes`, `tax_jurisdictions`, exemption categories and certificates, S13 | **Nothing** — PO 2026-09-03 |

**And what does not exist at all:** *"There is no app, no service worker, no manifest, no
native shell, no offline store and no technician role."*

## 8 · Sensitive paths, money, and what this module must NOT do

1. **Work writes no other module's tables** (`BR-WRK-002`; a gate proves it RED first). A
   reading becomes a meter read only through metering's set-read door (`BR-WRK-003`).
2. **No journal line, no link into Finance.** A job's cost is captured to four decimals and
   posted nowhere (`BR-WRK-004`, `CR-028` D3's precedent) until `OQ-WRK-1491` is ruled.
3. **No tax on a work order** (`BR-WRK-052`, PO 2026-09-03). B4 §Tax ❄️ is untouched.
4. **One named cost function** — `apps/work/costing.work_order_cost_lines()` — hours to
   two decimals, lines four stored / two displayed, the total the sum of the rounded lines:
   `0.87 × 48.5000 = 42.195 → 42.20`; `42.20 + 96.00 + 0.22 = 138.42` (`BR-WRK-051`). At
   four-decimal hours the figure would be `42.03`; the test pins it. Money on a non-invoice
   document; no GT; a decision-log draft records the judgment.
5. **The phone's Close activates nothing** (`BR-WRK-041`, `BR-MET-110`); the safety gate is
   enforced on the server or it is not a gate (`BR-WRK-037`).
6. **Photographs, signatures and reports are kept twelve months, and the utility is offered
   a download before anything is deleted** (`BR-WRK-048`; `OQ-WRK-1496` CLOSED 2026-09-04).
   ⚠ **Nothing is deleted today and nothing may be** — the export does not exist, so the
   pruning job is written last and refuses without it; and a file attached to an open
   dispute is not deleted while that matter is open. Nothing describes any of it as
   permanent.
7. **No B4/B5 figure is touched.** The one card that would have — `WM-46` — is closed by
   ruling. **Nothing 🔒 is authored by this documentation lane**; when phase 2 writes
   `costing.py`, that lane opens the review-ledger row and puts the worked figure to the PO
   in plain English.

## 9 · Coverage, checked both ways by a script over these files

`scratchpad/cr070/coverage_check.py`, run 2026-09-03 against this folder:

```
epics                 : 10
stories               : 54  (by phase: {'0': 6, '1': 12, '2': 36})
cards WM-01..49       : 49 of 49 have exactly one story
screens Work-001..033 : 33 cited of 33 declared
rules BR-WRK          : 57 defined; 57 cited by a story; 57 name a test
test cases            : 352  (negative 132, tenant-isolation 53)
stories with >=4 TCs  : 53 of 54
test data sets        : 53 concrete (+1 'None')
blocked stories       : 4 ['US-WRK-022', 'US-WRK-023', 'US-WRK-035', 'US-WRK-052']
stories with a stub   : 3 ['US-WRK-022', 'US-WRK-023', 'US-WRK-035']
endpoints (07)        : 95 new numbered (1..94 and 44a — `DEF-WRK-3579`)
journeys (04)         : 8
tables (03)           : 25 card-named + 9 ours
changed columns (03)  : 28 numbered rows
no gaps
```

⚠ **ONE story is blocked on a question — `OQ-376` (`US-WRK-035`) — and one on a ruling
(`US-WRK-052`). AMENDED 2026-09-05 by the wave I build lane at r11 step 0: this paragraph
named three blocked and six more stubbed, and all nine `OQ-WRK-*` questions had been CLOSED
by 2026-09-04** (`1490`…`1497`, `1561`). Nothing in this module now stubs a branch on a work
question. `OQ-376` is metering's and is not closed by `OQ-WRK-1495`.
**Two stories are written from unread cards** and say so: `US-WRK-044` (`WM-36`),
`US-WRK-045` (`WM-38`).

## 10 · What is NOT done, and who owns it

| Not done here | Why, and who |
|---|---|
| **§15–§21 of the blueprint are unread** — the nine signed rules, the build specification (23 tables, columns, endpoints), the sequence and decisions, the 66-row absence register, the specification register, §20, the appendices | The PDF is 16.3 MB, over the download cap, and the text reader stopped inside §14. Every row built from an unread section is marked `[from cards only — §16 unread]` (or §14, §15). **When read, the source wins on every such row and the row is stamped.** A phase-1 lane reads §16 before `work/0001` |
| The wireframe images, `08-screen-layouts.md`, `09-component-inventory.md` | **The parent lane's**, from the §13 PDF the PO uploaded 2026-09-03 (2.3 MB, 24 pages). Present in this folder; not written by this lane |
| The eight journey FILES in `08-qa/01-e2e/journeys/` | Described in `04-flows.md`, ids reserved; files are the next step |
| The register rows — eight questions, six decision-log rows (incl. the tax ruling), the reservation row, the CHANGELOG entry, ten defect rows | **Drafted ready-to-paste** in `scratchpad/cr070/governance-rows.md`; the parent lane applies them. This lane's write scope was this folder and the scratchpad |
| Corrections to `CR-070`'s own text | Filed as `DEF-WRK-3542`–`3548`; the CR text is left standing for the parent lane to stamp |
| Where the six existing tables live (`apps/metering` vs `apps/work`) | PENDING §16; `03-field-map.md` §4 states the three ways and makes no choice |

## 11 · Where the rest of it lives

| File | What is in it |
|---|---|
| `02-business-rules.md` | `BR-WRK-001`–`057`, the 22 inherited rules cited never restated, the eight questions |
| `03-field-map.md` | The six existing tables, 25 card-named + 9 new tables, 28 changed columns, the pending-§16 decision, 15 discrepancies, what is not modelled |
| `04-flows.md` | `J60`–`J67` with handoff contracts; the files are not written |
| `05-user-stories.md` | The index: 54 stories, 10 epics, the title and count corrections to `CR-070` §8/§9, the seven sub-screens |
| `06-epics/EP-WRK-01`…`10` | The stories, in the canonical eight-section format |
| `07-endpoints.md` | 94 new + 5 existing, each marked card / wireframe / story; why the count moved |
| `08-screen-layouts.md` · `09-component-inventory.md` · `wireframes/` | **The parent lane's** — one layout per screen from the images; the components; the pictures hard-won law 6 says to diff the running app against |

**Execution plan (2026-09-03):** [`10-execution-plan.md`](10-execution-plan.md) — the three phases as **14 waves and 105 tasks**, every wave ending in a clicked walkthrough of the running product against this folder's `wireframes/` and a version bump, every one of the 54 stories placed exactly once (PO: *"each phase/wave should produce tangila eoutcome"*).

## The visual reference — this module's own pack, then r10 (PO 2026-09-03)

**PO, verbatim: *"for Cr68, 69 and 70 - you will have to ensure you refer to screenshot we build and not just r10"*.**
The layout, copy and state authority for this module's screens is **`wireframes/` in this folder** (21 screens), read
through `08-screen-layouts.md` and `09-component-inventory.md`. **`05-prototype/r10` remains the default for every
screen the pack does not draw**, and for the shell and conventions a new screen inherits. **Where r10 and this pack
disagree on one of these screens, the pack wins** — it is the later drawing — and the divergence is stamped in
`08-screen-layouts.md` rather than followed silently. Diff the running app against the pack first (hard-won law 6). ⚠ `DEF-WRK-3550` and `DEF-WRK-3551` are exactly this hazard running the OTHER way: two of the pack's own drawings contradict their cards (stock levels, a lapsed certification), and both are open questions — so the pack wins over r10, and a CARD wins over the pack.
