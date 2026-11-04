# 18 · Field app — execution plan (`CR-187-BRC10`)

**Source:** the design canvas's *Work to be done* page (version `2.587.0`), in full — *"Seventy-six tasks in
seventeen phases, in build order."* Statuses are this repository's, as of **2026-10-21**. **Where:** *Native* is the
React Native app (`field-app/`) · *Server* is Django (`06-backend/`) · *Repo* is documents and governance · *Admin*
is outside the code · *Web* is `07-frontend/` · *Beta* is a real crew. **Sizes are bands, not promises: S up to a
week · M one to two · L two to four.**

**Status words:** **DONE** (with its date and where it is recorded) · **IN PROGRESS** (started, with its date) ·
**DEFERRED** (a ruling put it off) · **NOT STARTED**.

| Phase | Tasks | Status |
|---|---|---|
| 0 · Before any code | T-01 … T-05 | **DONE 2026-10-21** |
| 1 · Foundations | T-06 … T-14 | **IN PROGRESS** (started 2026-10-21) |
| 1b · Telemetry | T-73 … T-76 | **IN PROGRESS** (started 2026-10-21) |
| 2–11 · The phone screens | T-15 … T-26 | NOT STARTED |
| 12 · Tablet | T-27 … T-29 | NOT STARTED |
| 13 · Server | T-30 … T-43 | NOT STARTED |
| 14 · Proof | T-44 … T-55 | NOT STARTED |
| 15 · Release | T-56 … T-60 | IN PROGRESS — written 2026-10-21; waits on the PO's accounts (`15-release-and-rollback.md` §7) |
| Running alongside · the repository | T-61 … T-72 | NOT STARTED — T-72 **DEFERRED** (see below) |

PO, verbatim (decision log 2026-10-21): *"once phase 0 is completed -start phase1"*. And every screen is built from
its IMAGE in `wireframes/`, never from text (*"please ensure all native app screens are build using images not using
text or contents"*; B14 rules 42, 44, 45).

---

## Phase 0 · Before any code — DONE 2026-10-21

*"Four of these five have a clock that cannot be compressed by adding people, so they start on day one whatever else
is happening."*

| # | Task | Where | Size | Status |
|---|---|---|---|---|
| T-01 | Apply for the Apple Critical Alerts entitlement. Without it an emergency cannot break silent mode on iPhone. Days to weeks at Apple's pace — start it before anything else | Admin | S | **DONE 2026-10-21** — applied for by the PO (*"we have taken this permission-Apply for the Apple Critical Alerts entitlement"*). **Applied, not granted:** T-23 and E2E-22 still wait on Apple |
| T-02 | Raise the change request that supersedes BR-WRK-045 — the signed rule saying the phone is a web app, not a native shell. A native app reverses a confirmed rule, so it needs the supersession stated, not assumed | Repo | S | **DONE 2026-10-21** — `CR-187-BRC10` (`12-governance/change-requests/CR-187-BRC10-native-field-app.md`); BR-WRK-045 SUPERSEDED |
| T-03 | Close OQ-272 — ratify Archivo. It still reads OPEN, and the app bundles the font. Licensing is fine; the ruling is missing | Repo | S | **DONE 2026-10-21 — as far as it was ruled**: `OQ-272` (a) answered (Archivo); **(b) web self-hosting still OPEN**, never asked, so the row is `PARTIALLY CLOSED`, not `CLOSED` |
| T-04 | Write the native type ramp into the UI standard beside the web one — title 22, section 17, body 15, label 13, micro 12 — and the touch standard: 56 pt primary, 48 pt any control, 8 pt clearance | Repo | S | **DONE 2026-10-21** — B14 rule 45 |
| T-05 | Write every ruling from this conversation into the decision log, with its worked figure. *"Twenty-six PO rulings and twenty-one derived judgments"* | Repo | M | **DONE 2026-10-21** — decision log *"Field app Phase 0 (T-05)"*. That count was stale on the design's own page; the Rules page's **58 ruled and 49 derived** are what was recorded |

## Phase 1 · Foundations — IN PROGRESS (started 2026-10-21)

*"Nothing here is a screen. Everything after it depends on all of it."*

| # | Task | Where | Size | Status |
|---|---|---|---|---|
| T-06 | The shared token module — colours, spacing, type and radius as a plain TypeScript object imported by both web and native. One source, two renderers (`shared/tokens.ts`, with a drift test against `tokens.css` until the web reads it — decision log conflict 2) | Native | S | IN PROGRESS |
| T-07 | The native component kit — button in three tiers and two sizes, field with its 5/6/20 px anatomy, card, list row, status chip, sheet, empty state, toast. **A piece of UI is a component; standalone code inside a page is not reuse** (B14 rule 43). Same names and props as the web kit (conflict 10) — `09-component-inventory.md` | Native | L | IN PROGRESS |
| T-08 | The three themes — light, dark and sunlight — as token sets, not as per-screen overrides. Sunlight is white on black with 2–3 px borders and one size up | Native | M | IN PROGRESS |
| T-09 | The SQLite schema and its migrations — the twenty tables, their indexes and the FTS5 search table (`03-field-map.md`) | Native | M | IN PROGRESS |
| T-10 | The sync engine — outbox, batches of fifty, per-item receipts, backoff, the photo queue as a second phase, the delta puller and its watermarks | Native | L | IN PROGRESS |
| T-11 | The retention purge — on app start, never on a timer; nothing unsent, at any age | Native | S | IN PROGRESS |
| T-12 | Auth, the device register and the multi-technician session — several technicians on one handset, each with their own capture token, none of them able to see another's unsent work as their own | Native | M | IN PROGRESS |
| T-13 | Navigation — drawer, native stack, the one or two bottom tabs, and the tablet's permanent sidebar. ⚠ **`AD-22` superseded the tab count: the bottom bar is Home · Jobs · Reads** (three) | Native | S | IN PROGRESS |
| T-14 | The i18n layer with runtime language switching, against the eleven existing catalogues (field words under `field.*`, through `10-scripts/i18n_fanin.py` — conflict 3) | Native | S | IN PROGRESS |

## Phase 1b · Telemetry — IN PROGRESS (started 2026-10-21)

*"Built with the foundations, not bolted on at the end — because the scrubber has to exist before the first screen
that touches a customer record."*

| # | Task | Where | Size | Status |
|---|---|---|---|---|
| T-73 | The crash reporter and PostHog with their offline queue — crash reports and events held locally through a whole shift, yielding to the outbox and the photo queue, and invisible to the technician when the endpoint is dead. ⚠ **The design wrote *"Sentry and PostHog"*; the PO ruled on 2026-10-21 that the crash reporter is Crashlytics** (`11-technology.md` §5) | Native | M | IN PROGRESS |
| T-74 | The scrubber — an allow list of fields through which every event and breadcrumb passes before it leaves the handset. Session replay off; identity as tenant, role and an anonymous device id. ⚠ **The identity clause is superseded: the PO ruled on 2026-10-21 that analytics MAY name the individual technician**; customer facts still never leave the handset (`12-security.md` §6) | Native | S | IN PROGRESS |
| T-75 | Feature flags with cached defaults, and the Settings line that says diagnostics are on and what they leave out | Native | S | IN PROGRESS |
| T-76 | Prove the scrubber by breaking it — force a crash on FF-25 Customer with a real account on screen and assert the report carries no name, no address, no account number and no balance. Then force one on FF-20 Readings and assert no reading leaves. *A privacy guard nobody has watched fail is not a guard* | Native | S | IN PROGRESS |

## Phases 2–11 · The phone screens — NOT STARTED

*"Grouped as the flow stages, in the order a technician meets them. Each wave ends with the screens clickable on a
real handset, not with a component that nothing mounts."* The design says *"fifty-five phone screens"*; the canvas
has since added FF-56 … FF-63 and RW-01 … RW-29 (`08-screen-layouts.md`), which have no wave of their own below — see
the note after the table.

| # | Wave | Screens | Size | Status |
|---|---|---|---|---|
| T-15 | Getting in | FF-01 Splash · FF-02–04 Intro · FF-05 Sign in · FF-06 Forgot · FF-07 Permissions · FF-08 First sync · FF-09 Drawer | M | NOT STARTED |
| T-16 | The day | FF-10 Today · FF-11 Nearby · FF-12 Claim | M | NOT STARTED |
| T-17 | Getting there | FF-13 Map · FF-14 Stop — needs the Esri tile connection live | M | NOT STARTED |
| T-18 | Opening a job | FF-15 Job · FF-16 Safety — the safety gate is all-or-none and the server re-derives it | M | NOT STARTED |
| T-19 | Doing the work | FF-17 Tasks · FF-18 Add step · FF-19 Checklist · FF-20 Readings · FF-21 Photos · FF-22 Compare · FF-23 Materials · FF-24 Parts. The largest wave: photo capture lives on the step and on the reading | L | NOT STARTED |
| T-20 | Context on site | FF-25 Customer · FF-26 Restoration · FF-27 Disconnect · FF-28 Documents · FF-29 Crew · FF-30 Notes · FF-31 Activity | L | NOT STARTED |
| T-21 | Closing | FF-32 Debrief · FF-33 Signature · FF-34 Close · FF-35 Completed · FF-36 Reopen | M | NOT STARTED |
| T-22 | Assets and raising work | FF-37 Raise · FF-38 Scan · FF-39 Asset · FF-40 History · FF-41 Search | M | NOT STARTED |
| T-23 | Alerts | FF-42 Alerts · FF-43 Emergency — blocked on T-01 (Apple's grant, not the application) | M | NOT STARTED |
| T-24 | Me and admin | FF-44 Profile · FF-45 Availability · FF-46 Shifts · FF-47 Timesheet · FF-48 Admin · FF-49 Van | M | NOT STARTED — ⚠ except FF-46's week and End shift and FF-47's Submit the day, **WIRED 2026-10-26** (`CR-193-BRC10`, MQ-040 step 1; N27). Time-off requests (step 2) not approved. |
| T-25 | Sync and settings | FF-50 Sync · FF-51 Settings · FF-52 Notifications · FF-53 Logout | M | NOT STARTED |
| T-26 | Theme proof | FF-54 Night · FF-55 Sunlight — every screen walked in all three themes, not just these two | S | NOT STARTED |

**Screens drawn after this plan was written, and the wave each most naturally joins (our judgment, recorded so it is
not lost; the design names none):** FF-56 Activate and FF-57 Your password → T-15 · FF-63 Home and the Switch
technician sheet → T-16 · FF-58 Hand it back → T-18 · FF-59 Add a reading and FF-60 Asset papers → T-19 · FF-61
Reconnect → T-20 · FF-62 Pick a template → T-22 · **RW-01 … RW-29, the reading mode (`AD-20`, 29 screens), have no
wave** and need at least one of their own after T-19, behind the route endpoints in `07-endpoints.md` §2 (N1, N5,
N6). Sizing them is for whoever plans that wave.

## Phase 12 · Tablet — NOT STARTED

*"Not fifty-five more screens — the same screens in a two or three-pane frame. Eight are drawn; the rest follow the
same three rules."* (The canvas has since drawn all of them — 92 tablet boards; the canvas note says *"ALL 55, NOT
EIGHT"* and *"Four frames do all 55"*.)

| # | Task | Where | Size | Status |
|---|---|---|---|---|
| T-27 | The tablet frame — 220 px permanent sidebar, a 320–360 px list pane, a detail pane that keeps the list visible | Native | M | NOT STARTED |
| T-28 | The eight screens that genuinely change shape — Today, Job, Map, Assets, Alerts, Readings, Photos, Completed. These are drawn | Native | M | NOT STARTED |
| T-29 | The remaining forty-seven in the frame. Mostly mechanical once T-27 is right; the readings grid and the photo wall are the two that need real thought at width | Native | L | NOT STARTED |

## Phase 13 · Server — NOT STARTED

*"Most of the work module exists. These are the gaps this design opens."* Each is detailed in `07-endpoints.md`.

| # | Task | Where | Size | Status |
|---|---|---|---|---|
| T-30 | Batched sync at volume — the existing per-item contract proved against 1,000 readings in 20 batches, with a savepoint per item on real PostgreSQL. ⚠ **Route readings have no sync route today** (`07-endpoints.md` N1) | Server | M | NOT STARTED |
| T-31 | Tombstones in the delta. The change feed must report what was taken away, not only what changed. *This is the one gap that is invisible in testing and wrong in the field.* (Unassignment is already a tombstone; cancellation and route changes are not — N3) | Server | M | NOT STARTED |
| T-32 | A watermark cursor per table on the day read, so a refresh is a delta | Server | M | NOT STARTED |
| T-33 | The money freshness endpoint — balance and cleared-payment state with an as-at stamp, so the handset can say how old the number is | Server | S | NOT STARTED |
| T-34 | A server push when money changes on an account with an open restoration or disconnect order | Server | M | NOT STARTED |
| T-35 | Freshness on the template step — so a step can declare it needs a figure no older than five minutes, and no code anywhere knows what a disconnect is | Server | M | NOT STARTED |
| T-36 | Partial and failed outcomes end to end — the four outcomes carried through the order, the invoice path and the office queue | Server | M | NOT STARTED |
| T-37 | Reopen versus follow-on — the same order reopened, or a new order linked to it, with the office deciding which | Server | M | NOT STARTED |
| T-38 | A second technician on an order, with their own labour record | Server | M | NOT STARTED |
| T-39 | Contractor claim of unassigned work, within the tenant and within their skills | Server | M | NOT STARTED |
| T-40 | Server-side search for assets and nearby work — paged, no hard cap, spatial on the premise point | Server | M | NOT STARTED |
| T-41 | Push kinds and channels — urgent assignment, emergency, schedule change, dispatch message — each with its own sound and its own channel | Server | M | NOT STARTED |
| T-42 | Field-raised orders from the handset, auto-filled with premise, account, customer and position | Server | M | NOT STARTED |
| T-43 | The six Work tables moved out of `apps/metering/connections.py` into the work module, where they belong | Server | M | DONE 2026-10-21 — declarations moved (`work/0046`, `metering/0078`, no SQL; byte-identical before/after on PostgreSQL); the writing services remain in metering |

**Server work the design's list does not name, found while writing `07-endpoints.md`** (recorded, not sized): the
two-credential model and device activation (N24 — Security §7 item 1 calls it a precondition), the template
catalogue read for a technician (N8), the can't-read reason catalogue (N12), field-capture columns on `meter_reads`
(`03-field-map.md` §2.5), the route download and turn-in (N5, N6), a minimum-version refusal (N7).

## Phase 14 · Proof — NOT STARTED

*"Every one of these exists because a check that cannot fail has cost this project a production defect at least
once."*

| # | Task | Where | Size | Status |
|---|---|---|---|---|
| T-44 | The offline soak — a whole shift in airplane mode: eleven jobs opened, worked and closed, then one sync. Nothing lost, nothing doubled | Native | M | NOT STARTED |
| T-45 | The thousand-reading run — 1,000 captured offline, sent in 20 batches, the connection killed mid-batch twice, and the arithmetic checked at the other end | Native | M | NOT STARTED |
| T-46 | The savepoint proof on real PostgreSQL, not the suite's SQLite. A refused row must not poison the batch — and SQLite has no aborted-transaction state, so the broken version passes everything | Server | S | NOT STARTED |
| T-47 | The tombstone test — a job reassigned away must leave the handset. Asserted by address and by what the screen then shows | Native | S | NOT STARTED |
| T-48 | The handover test — technician A's unsent work survives B signing in, working, and signing out, and sends under A's name | Native | S | NOT STARTED |
| T-49 | The retention test — a photo file gone on confirmation, present while merely sent, and an unsent item still there at ninety days | Native | S | NOT STARTED |
| T-50 | Tenant isolation on the handset — the local store scoped, and the day read proved against a second tenant's data | Native | S | NOT STARTED |
| T-51 | Touch and reach audit — every control measured against 48 pt, every primary against 56, every pair against 8 pt clearance. Gloved hands, on a real handset | Native | S | NOT STARTED |
| T-52 | Sunlight walkthrough outdoors, at noon, on the cheapest handset the utility issues | Native | S | NOT STARTED |
| T-53 | Accessibility pass — contrast, screen reader, text scaling to 200%, and the eight portal questions where they apply | Native | M | NOT STARTED |
| T-54 | Every hold gets the test that fires when it expires, asserted by address and by screen. A hold with no such test is a promise nobody is keeping (hard-won law 2) | Native | S | NOT STARTED |
| T-55 | Repoint the web app's field-app button at the app store — with the test that fires on the day the app ships (`FieldAppNotice`, `AD-16`) | Web | S | **HOLD BUILT** 2026-10-21 — `FIELD_APP_STORE_URLS` (empty) + `FieldAppNotice.hold.dom.test.tsx`, red the day a store address is set; the repoint itself ships with the app |

## Phase 15 · Release — IN PROGRESS (2026-10-21)

| # | Task | Where | Size | Status |
|---|---|---|---|---|
| T-56 | Store listings, screenshots, privacy declarations and the location-use justification for both stores | Admin | M | **DRAFTED** 2026-10-21 — `14-store-listing.md`; needs the PO's items and §7's pre-flight before submission |
| T-57 | Build pipeline, signing and over-the-air updates for the JavaScript layer | Native | M | **CONFIGURED** 2026-10-21 — `eas.json`, `app.json`, `.github/workflows/field-app-eas.yml.disabled` (disabled by the 2026-09-04 ruling); never run — needs `expo-updates` and the PO's accounts |
| T-58 | Version on screen — in the drawer, as the change process requires, so a reported defect names a build (`R40`) | Native | S | **DONE** 2026-10-21 — *2.590.0 · build n* from the running binary (`src/release/build.ts`); `G35` clause 6 and `allocate.py version` hold `field-app/package.json` |
| T-59 | One crew, one week, real work — the going-live customer's own technicians, before anyone else gets it | Beta | M | **PLANNED** 2026-10-21 — `15-release-and-rollback.md` §6; needs the crew |
| T-60 | Rollback stated before shipping, and the reporter told which build to look in | Repo | S | **STATED** 2026-10-21 — `15-release-and-rollback.md` §4–§5; the minimum-version refusal it relies on (`07-endpoints.md` N7) is BUILT 2026-10-21 (`DEF-FLD-10355`; this cell read *"not built and blocks the first store release"* until then) |

## Running alongside · The repository

*"None of this design is in the repository, by your instruction. These are the write-backs, and they are roughly
nine-tenths of the real work on a change this size."* That instruction has lifted: the decision log of 2026-10-21
(*"Field-app write-up: on the payments branch, all of it now"*) puts T-61 … T-71 on this branch now, as several small
commits — **this file is one of them.** Each row's status moves in the commit that lands it.

| # | Task | Size | Status |
|---|---|---|---|
| T-61 | The fifty requirements as an epic with its stories, in the canonical eight-section format. Every screen needs a story — the last field app shipped without them and that is why it was a test build | L | NOT STARTED |
| T-62 | The sixty-five rules into the work module's business rules, each CONFIRMED or SUPERSEDED with its date (ruled 2026-10-21: into `18-field-app/02-business-rules.md` as `BR-FLD-`; the Rules page now holds 134) | M | NOT STARTED |
| T-63 | The seventeen architecture decisions as ADRs (the Decisions page now holds twenty-four, AD-01 … AD-24) | M | NOT STARTED |
| T-64 | The open questions this design leaves, minted and stubbed rather than guessed (`OQ-FLD-`, through the allocator) | S | NOT STARTED |
| T-65 | Journeys in the end-to-end folder for every case on the Walkthrough tab, since each spans modules | M | NOT STARTED |
| T-66 | Read the Work blueprint's unread half — §15–§21, nine signed rules, a 23-table build spec and a 66-row absence register. The document is not in the repository at all; it has to be obtained first | M | NOT STARTED |
| T-67 | Draw Work-010–012, the technician's phone screens, which were never drawn — which is the root cause of the test build | L | NOT STARTED |
| T-68 | A review-ledger row per sensitive file, stating in plain English with a figure what was shown to you and what you ruled | M | NOT STARTED |
| T-69 | Reserve a change-request number block for whichever branch does this work, before it starts | S | NOT STARTED |
| T-70 | Version every change, and refuse a change request marked done without one | S | NOT STARTED |
| T-71 | A defect row for anything found on the way, with its escape reason — why no existing check caught it | S | NOT STARTED |
| T-72 | Decide what happens to the existing web field app — retired, or kept as the fallback for a handset that cannot install. That is a product decision, not an engineering one | S | **DEFERRED 2026-10-21** — PO: *"once native app is build after that we will decide"*. Until then `07-frontend/src/features/work/mobile/` and its service worker stay untouched (decision log conflict 9) |

---

## What can run at once

* **Day one, in parallel:** T-01 (Apple, because it waits on someone else) · T-02–05 (the repository, which needs no
  code) · T-06–09 (tokens, kit, themes, schema).
* **T-74, the scrubber, comes before any screen that shows a customer** — otherwise the first crash report off a real
  handset is the privacy incident.
* **Then the real constraint: T-10, the sync engine.** Every screen that captures anything sits behind it, so it is
  the one task worth over-staffing.
* **Server and phone run side by side** once the day read and the sync contract are agreed — they already exist,
  which is why this is a redesign and not a new build.
* **The tablet frame (T-27) can start as soon as the component kit lands**, well before the phone waves finish.
* **Two things cannot be parallelised and are usually underestimated:** T-66, reading the blueprint's unread half,
  because it may change rules already built on; and T-67, drawing the phone screens, because nothing downstream is
  trustworthy without them.

## What has to be true before code starts (the design's list, and where each stands)

| # | Precondition | Status 2026-10-21 |
|---|---|---|
| 1 | The Apple Critical Alerts entitlement applied for | Applied (T-01); not yet granted |
| 2 | BR-WRK-045 recorded as superseded, with a change request | Done (`CR-187-BRC10`) |
| 3 | OQ-272 closed — Archivo ratified | (a) ruled; (b) open |
| 4 | The native type ramp written into the UI standard | Done (B14 rule 45) |
| 5 | Every ruling from this conversation in the decision log | Done (T-05) |
| 6 | A ruling on whether analytics may identify an individual technician | **Ruled 2026-10-21: yes, it may** (`12-security.md` §6) |
