# 16 · Work — the 54 stories

**Epics `EP-WRK-01` … `EP-WRK-11` · Stories `US-WRK-001` … `US-WRK-059`.** ⚠ **This
line read *`EP-WRK-10` … `US-WRK-054`* until 2026-10-21, when `EP-WRK-11` (the office side
of the field app, five stories) was added; the title's *54* and the paragraphs below
describe the blueprint's set and are left as written.**
Both families are new and both are **zero-padded to three, chosen at birth** — the
spelling `BR-CWP-001` and `US-CWP-001` took — allowed because neither series carries a
citation yet. Pattern `US-WRK-\d{3,5}(?!\d)`, and the lookahead is load-bearing
(`DEF-2804`). Reserved for this module by the parent lane: `US-WRK-001` upward,
`EP-WRK-01`–`10`.

**Every one of the blueprint's 49 specifications has a story, and every one of the 33
screens is cited by at least one story.** Checked both ways by a script over these files;
the counts are in `01-overview.md` §9.

**Delta against the approved count: ~55 stories were expected and 54 are written.** The
49 cards take one story each; the five that are ours are `US-WRK-004` (the two screens no
card covers), `US-WRK-005` (the module skeleton and its boundary gate), `US-WRK-006` (the
demo fixture), `US-WRK-019` (the seeded starters and the gate that keeps them read) and
`US-WRK-040` (the phone shell). Nothing else needed a story of its own.

---

## 1 · The ten epics

| Epic | Name | Stories | Phase | Screens |
|---|---|---|---|---|
| `EP-WRK-01` | Phase 0: a work order without a build, the fifteen actions, the approval queue, the module's skeleton | 6 | **0** | `Work-001`, `002`, `006`, `007`, `009` |
| `EP-WRK-02` | Settings and series | 6 | 1 (`WM-28` is 2) | `Work-018`, `019`, `025`, `007`, `008` |
| `EP-WRK-03` | The template bundle | 7 | 1 | `Work-004`, `005`, `013`–`017`, `022` |
| `EP-WRK-04` | Workforce and roles | 4 | 2 | `Work-023`, `024`, `009`, `003`, `010`–`012` |
| `EP-WRK-05` | Dispatch | 8 | 2 | `Work-007`, `002`, `008`, `010`, `021` |
| `EP-WRK-06` | The order in hand | 5 | 2 | `Work-008`, `003`, `002`, `009`, `012` |
| `EP-WRK-07` | Rules and doors | 3 | 2 | `Work-026`, `028`, `029`, `020`, `007` |
| `EP-WRK-08` | The phone | 6 | 2 | `Work-010`, `011`, `012` |
| `EP-WRK-09` | Readings and evidence | 4 | 2 | `Work-016`, `008`, `012`, `032`, `033` |
| `EP-WRK-10` | Costing, tax, the report and performance | 5 | 2 | `Work-025`, `027`, `030`, `031`, `032`, `008`, `009` |
| `EP-WRK-11` | The office side of the field app (`CR-187-BRC10`, added 2026-10-21 — after the ten above, which is why this table now reads eleven) | 5 | 2 | `Work-034`, `008`, `024` |

**The three phases are `CR-070` §11's, each one launchable:** phase 0 — *a clerk can
raise, hold, cancel and close a job this week*; phase 1 — *a utility authors its own job
templates, and the wizard proposes them*; phase 2 — *a dispatcher assigns work to a crew,
and the technician works it on a phone*. A story's `wave:` is its phase.

---

## 2 · Corrections to `CR-070` §8 and §9 — the ids stay, the titles and the count are corrected

⚠ **`CR-070` §9 says *"Nine of the thirty-three are already drawn (WS-01–WS-09)"*. That
is wrong.** The nine that exist are **`WS-01`–`WS-06` and `WS-18`–`WS-20`**;
`WS-07`, `WS-08` and `WS-09` — the dispatcher, the order detail and the approval queue —
are **new**. The blueprint's own state chips say so. Filed as a defect draft
(`DEF-WRK-3543`); the twenty-four new screens are `Work-007`–`017` and `Work-021`–`033`.

⚠ **`CR-070` §8 carries nineteen rows whose text is not the card's title.** Two are
effectively swapped — `WM-09` is *the seven template child tables* (the CR says *"A screen
to author a template"*) and `WM-11` is *the eight-step builder* (the CR says *"A service to
write a template"*); `WM-10` is the write service. `WM-24` is *Rules that raise work orders
on their own* (the CR says *"One trap that will pass every test and lose data"*, a phrase
not in the readable text and probably §16's). The titles below are the cards' own; the ids
do not move (`DEF-WRK-3544`).

| Spec | The card's own title | Story |
|---|---|---|
| `WM-01` | Let a work order exist without a connection | `US-WRK-001` |
| `WM-05` | Priorities, each with its SLA | `US-WRK-008` |
| `WM-09` | The seven template child tables | `US-WRK-014` |
| `WM-10` | The template write service — the one the seeder says is OWED | `US-WRK-015` |
| `WM-11` | The eight-step template builder | `US-WRK-016` |
| `WM-12` | Make New Connect step 6 propose orders from templates | `US-WRK-017` |
| `WM-24` | Rules that raise work orders on their own | `US-WRK-037` |
| `WM-25` | The consequence chain behind a failed outcome | `US-WRK-034` |
| `WM-27` | Give a connection message its own source kind | `US-WRK-035` |
| `WM-28` | Wire the Area lookup as the dispatcher's Area filter | `US-WRK-011` |
| `WM-31` | A Field technician role, scoped to Work on mobile only | `US-WRK-023` |
| `WM-36` | Offline capture and sync — *card unread; title from §3 step 10 and `WS-12`* | `US-WRK-044` |
| `WM-38` | The technician closes the job from the phone — *card unread; title from §3 step 14* | `US-WRK-045` |
| `WM-48` | Three document kinds, and the phone resize that pays for them | `US-WRK-048` |

**Where to look for a screen's layout.** Every story names its screens by `Work-` id. The
wireframe images, `08-screen-layouts.md` and `09-component-inventory.md` are the **parent
lane's** deliverables from the §13 PDF the Product Owner uploaded on 2026-09-03 (2.3 MB,
24 pages) — see `01-overview.md` §10. A builder opens those beside the story; where a
drawing and a B14 rule disagree, B14 wins and the layout entry says so.

---

## 3 · The 54 stories

`P` is the phase. `⚠` marks a story that must be implemented **to the boundary and
stubbed** — `raise NotImplementedError("OQ-…")` — because a question it needs is open.
`§14 unread` marks a story written from the flow table, the wireframe and the card list
only, because its card sits past the readable text.

### `EP-WRK-01` · Phase 0: foundations

| Story | Title | Screens | Spec | P | Blocked by |
|---|---|---|---|---|---|
| `US-WRK-001` | A work order may exist without a connection: `connection_id` nullable, `premises_id` and `account_id` beside it | `Work-007`, `Work-002` | `WM-01` | 0 | — |
| `US-WRK-002` | Mount the finished write actions: fourteen writers and two readers only a Python shell can reach | `Work-002` | `WM-02` | 0 | — |
| `US-WRK-003` | The approval queue, across every connection: every order where `accepted_by` is null | `Work-009` | `WM-03` | 0 | — |
| `US-WRK-004` | The two screens no card covers: New connects lists builds; the Work rail entry becomes the dispatcher's shell | `Work-001`, `Work-006` | — | 0 | — (`OQ-371` unchanged) |
| `US-WRK-005` | `apps/work/`: the eleventh module, its read-only seams, the migrated-list entry, and the boundary gate | — | — | 0 | — |
| `US-WRK-006` | The demo fixture: crews, technicians with certifications, a published template, a job in every state | — | — | 0 → 2 | — |

### `EP-WRK-02` · Settings and series

| Story | Title | Screens | Spec | P | Blocked by |
|---|---|---|---|---|---|
| `US-WRK-007` | A work order type catalogue | `Work-018`, `Work-007` | `WM-04` | 1 | — |
| `US-WRK-008` | Priorities, each with its SLA | `Work-018`, `Work-007`, `Work-008` | `WM-05` | 1 | — |
| `US-WRK-009` | Wire the three parked Settings cards: skills, safety kits, parts categories | `Work-018` | `WM-06` | 1 | — |
| `US-WRK-010` | The parts register — and no stock level, because none lawfully exists | `Work-018`, `Work-025`, `Work-008` | `WM-07` | 1 | ⚠ stock `OQ-WRK-1490` (register ships) |
| `US-WRK-011` | Wire `tenancy.Area` as the dispatcher's Area filter | `Work-007` | `WM-28` | 2 | — |
| `US-WRK-012` | Wire the four Work settings cards and the four number series; leave `dispatch_batch` unwired | `Work-018`, `Work-019` | `WM-42` | 1 | `OQ-WRK-1497` non-blocking |

### `EP-WRK-03` · The template bundle

| Story | Title | Screens | Spec | P | Blocked by |
|---|---|---|---|---|---|
| `US-WRK-013` | Template header columns, and one relaxed key | `Work-013` | `WM-08` | 1 | — |
| `US-WRK-014` | The seven template child tables — rows, not a blob | `Work-015`, `Work-016`, `Work-008` | `WM-09` | 1 | — |
| `US-WRK-015` | The template write service the seeder says is OWED | `Work-017`, `Work-013` | `WM-10` | 1 | — |
| `US-WRK-016` | The eight-step template builder, with starter packs on step 1 | `Work-014`–`017`, `Work-005` | `WM-11` | 1 | — |
| `US-WRK-017` | New Connect step 6 proposes work orders from the utility's templates | `Work-004` | `WM-12` | 1 | — |
| `US-WRK-018` | Template versions, and what v2 means | `Work-022` | `WM-40` | 1 | — |
| `US-WRK-019` | The seeded starters become editable bundles; gas stays gated on light-up; a gate keeps every seeded row read | `Work-013`, `Work-014` | — | 1 | — |

### `EP-WRK-04` · Workforce and roles

| Story | Title | Screens | Spec | P | Blocked by |
|---|---|---|---|---|---|
| `US-WRK-020` | Crews, technicians and their skills — a profile beside an identity | `Work-023`, `Work-007` | `WM-13` | 2 | — |
| `US-WRK-021` | The crews screen, technician detail and the skills wizard; the certification watch blocks nothing until ruled | `Work-023`, `Work-024` | `WM-21` | 2 | ⚠ `OQ-WRK-1493` (the block only) |
| `US-WRK-022` | A Work permission in identity: who may accept | `Work-009`, `Work-003` | `WM-26` | 2 | ⚠ **`OQ-WRK-1492`** |
| `US-WRK-023` | A Field technician role scoped to Work on mobile only | `Work-010`–`012` | `WM-31` | 2 | ⚠ **`OQ-WRK-1494`** |

### `EP-WRK-05` · Dispatch

| Story | Title | Screens | Spec | P | Blocked by |
|---|---|---|---|---|---|
| `US-WRK-024` | The twelve dispatch columns, kept apart from `state` | `Work-007`, `Work-002` | `WM-14` | 2 | — |
| `US-WRK-025` | Assignment as an append-only history | `Work-007`, `Work-008` | `WM-15` | 2 | — |
| `US-WRK-026` | One list of every work order, with six filters | `Work-007` | `WM-16` | 2 | — |
| `US-WRK-027` | The dispatcher screen: KPI strip, filter bar, ten columns, bulk select | `Work-007` | `WM-17` | 2 | — |
| `US-WRK-028` | The three-step New order wizard — sub-screen of `Work-007` | `Work-007` | `WM-20` | 2 | — |
| `US-WRK-029` | The map — sub-screen of `Work-007` | `Work-007` | `WM-23` | 2 | — |
| `US-WRK-030` | Push the order to the technician's phone on assignment | `Work-007`, `Work-010` | `WM-37` | 2 | — |
| `US-WRK-031` | The work-order edit screen: assign, reschedule, cancel, with a Change effects box | `Work-021` | `WM-39` | 2 | ✅ **nothing — `OQ-WRK-1495` closed 2026-09-04**; this cell named it a blocker until 2026-09-05 |

### `EP-WRK-06` · The order in hand

| Story | Title | Screens | Spec | P | Blocked by |
|---|---|---|---|---|---|
| `US-WRK-032` | The order's own copies of its template — copied at raise, never linked | `Work-008` | `WM-18` | 2 | — |
| `US-WRK-033` | The six-tab work order detail | `Work-008`, `Work-003` | `WM-19` | 2 | — |
| `US-WRK-034` | The consequence chain behind a failed outcome | `Work-002`, `Work-008` | `WM-25` | 2 | — |
| `US-WRK-035` | Give the connection letter its own source kind | `Work-003`, `Work-009` | `WM-27` | 2 | ⚠ **`OQ-376`** — cited, not re-minted |
| `US-WRK-036` | Attachments and the customer's signature | `Work-008`, `Work-012` | `WM-30` | 2 | — |

### `EP-WRK-07` · Rules and doors

| Story | Title | Screens | Spec | P | Blocked by |
|---|---|---|---|---|---|
| `US-WRK-037` | Rules that raise work orders on their own | `Work-026`, `Work-007`, `Work-020` | `WM-24` | 2 | — |
| `US-WRK-038` | The Assets door: one form, four ways in | `Work-028`, `Work-020` | `WM-43` | 2 | — |
| `US-WRK-039` | The Customers door: two calls from one wizard step | `Work-029` | `WM-44` | 2 | — |

### `EP-WRK-08` · The phone

| Story | Title | Screens | Spec | P | Blocked by |
|---|---|---|---|---|---|
| `US-WRK-040` | The phone shell: a web app, installable, offline-first | `Work-010`–`012` | — | 2 | — |
| `US-WRK-041` | Today's jobs on the phone | `Work-010` | `WM-32` | 2 | — |
| `US-WRK-042` | The job on the phone | `Work-011`, `Work-012` | `WM-33` | 2 | — |
| `US-WRK-043` | Safety checks block the task list — on the phone AND the server | `Work-011` | `WM-34` | 2 | — |
| `US-WRK-044` | Offline capture and sync — `§14 unread` | `Work-010`, `Work-012` | `WM-36` | 2 | — |
| `US-WRK-045` | The technician closes the job from the phone — `§14 unread` | `Work-012` | `WM-38` | 2 | — |

### `EP-WRK-09` · Readings and evidence

| Story | Title | Screens | Spec | P | Blocked by |
|---|---|---|---|---|---|
| `US-WRK-046` | Readings that post as meter reads, through metering's set-read door | `Work-016`, `Work-008` | `WM-29` | 2 | — |
| `US-WRK-047` | Out-of-range readings flag, and never refuse | `Work-012`, `Work-008` | `WM-35` | 2 | — |
| `US-WRK-048` | Three document kinds, and the phone compression that pays for them | `Work-032`, `Work-033`, `Work-012` | `WM-48` | 2 | — (⚠ `OQ-WRK-1496` **CLOSED 2026-09-04**: twelve months, export before deletion, 100 KB at capture) |
| `US-WRK-049` | A reading's photograph: the rule and the file are different columns | `Work-033`, `Work-016`, `Work-012` | `WM-49` | 2 | — |

### `EP-WRK-10` · Costing, tax, the report and performance

| Story | Title | Screens | Spec | P | Blocked by |
|---|---|---|---|---|---|
| `US-WRK-050` | Parts against a job — used-of-planned, no on-hand count moves | `Work-025`, `Work-008` | `WM-22` | 2 | ⚠ stock `OQ-WRK-1490` |
| `US-WRK-051` | Labour rates — per hour, overtime, dated, per role | `Work-030`, `Work-027`, `Work-032` | `WM-45` | 2 | — |
| `US-WRK-052` | **Tax on a work order — NOT BUILT** (PO 2026-09-03) | `Work-031` (not drawn), `Work-032` | `WM-46` | — | **blocked by a ruling** |
| `US-WRK-053` | The work-order report — generated on approval, frozen, versioned; one named cost function | `Work-032`, `Work-009` | `WM-47` | 2 | — |
| `US-WRK-054` | The performance tab, and the Finance arrow that is refused | `Work-027` | `WM-41` | 2 | ⚠ `OQ-WRK-1491` (the posting only) |

### `EP-WRK-11` · The office side of the field app (added 2026-10-21, `CR-187-BRC10`)

Not one of the blueprint's 49 specifications: the native field app's walkthrough (§4) names
these office surfaces and draws none of them, so `Work-034` is a NEW screen id (*Next free*
in `CR-070` was `Work-034`) and the layout is composed from the kit — see the epic.

| Story | Title | Screens | Spec | P | Blocked by |
|---|---|---|---|---|---|
| `US-WRK-055` | Finished jobs — what the field said; accept, reopen or follow on | `Work-034`, `Work-008` | Walkthrough §4 | 2 | — |
| `US-WRK-056` | Raised on site — accept into dispatch, or refuse with a reason | `Work-034` | Walkthrough §4, R23 | 2 | — |
| `US-WRK-057` | Alerts — answered, overdue, dispatch told; *Send alert…* from an order | `Work-034`, `Work-008` | N25, R28 | 2 | — |
| `US-WRK-058` | A technician's handsets, and *Sign out this device* | `Work-024` | Security §4, R115 | 2 | — |
| `US-WRK-059` | On the order — what the field said, and every reopen and follow-on | `Work-008` | E2E-04, -17, -18 | 2 | — |

---

## 4 · The seven undrawn prototype surfaces, recorded as sub-screens

The blueprint names seven r10 surfaces in captions and draws none of them. **None gets a
`Work-` id**; each is a sub-screen of the screen it opens from, and its story says so.

| r10 | Surface | Parent | Story |
|---|---|---|---|
| `WRK-12` | The three-step New order wizard | `Work-007` | `US-WRK-028` |
| `WRK-09` | The map | `Work-007` | `US-WRK-029` |
| `WRK-13` | New rule — the five-step builder | `Work-026` | `US-WRK-037` |
| `WRK-14` | The skills wizard | `Work-024` | `US-WRK-021` |
| `WRK-16` | Part detail — Overview · Movements · Audit | `Work-025` | `US-WRK-050` |
| `WRK-17` | Issue parts — two steps | `Work-025` | `US-WRK-050` |
| `WRK-18` | Add part | `Work-025` | `US-WRK-010` |

---

## 5 · Coverage, checked both ways

**All 49 specifications have a story** — `WM-01` … `WM-49`, one each, named in the
story's heading. **All 33 screens are cited** — `Work-001` … `Work-033`, from the stories'
`screens:` frontmatter; `Work-031` is cited by `US-WRK-052` as *not drawn*, which is the
honest citation. **All 57 rules are cited by a story and name a test.**

⚠ **ONE STORY CARRIES A BLOCKING QUESTION, NOT SIX — AMENDED 2026-09-05 BY THE WAVE I BUILD
LANE AT r11 STEP 0.** This paragraph named six until today, and **all nine `OQ-WRK-*`
questions had been CLOSED by 2026-09-04** — `1490`, `1491`, `1492`, `1493`, `1494`,
`1495`, `1496`, `1497` and `1561`. The one that remains is **`OQ-376`** (`US-WRK-035`, the
*your service is live* letter), which belongs to metering and is a different question from
`OQ-WRK-1495` in as many words. **`US-WRK-052` is blocked by a ruling, not a question**, and
has no `OQ`.

⚠ **THE PATTERN IS WORTH MORE THAN THE CORRECTION.** Closing a question and un-marking the
stories it blocked are two acts, and only the first feels like the work — the same shape as
B14's rule-count line (wrong five times) and `CR-068` R3's expired holds
(`DEF-CWP-3925`). A lane reading only this paragraph would have built `US-WRK-031`'s send as
a `NotImplementedError` a day after the PO ruled what it should send.

**Two stories are written from unread cards** (`US-WRK-044`, `US-WRK-045`) and say so in
their headings; the rest of §14, §15, §16 and §17 may amend them before code is written.
