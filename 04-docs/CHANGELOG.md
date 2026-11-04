# Handoff Changelog

Anything reworked after the initial 2026-08-07 export. Newest first. Whenever the design changes, `05-prototype/` is re-exported alongside `/docs` so they stay in sync.

## 2026-09-03 — 2.129.0 · the Integrations tab draws a grid (CR-069 wave A)

The first wave of the integration substrate is built, and it is the first thing
in this change request a person can look at.

**What a clerk sees.** Settings → Integrations used to hold one dashed box
saying that accounting, payment, meter and email connections *"arrive with the
Integrations feature"* and that no connection could be made there yet. It now
draws **seventeen provider cards**, each reading *Not set up* on a fresh
utility, with a kicker that says in three words what the connection is for and
which way it runs — *EMAIL · WE SEND*, *BANKING · WE COLLECT*, *PAYMENTS · THEY
SEND*. A card with more than one operation lists them and carries **no summary
word of its own**, because *"three of three running"* is a claim about a thing
that is not a thing.

**What is underneath.** Five tables — the connection, its versioned credential,
the record of every attempt, the foreign name for one of our things, and a
consent row nothing writes yet. Row-level security is enabled and forced on all
five and on both year partitions of the run table, checked against a live
PostgreSQL rather than against a comment. No credential material sits on the
connection, so the table the grid and the audit trail read is safe to select
from. A credential is versioned rather than updated and the database itself
refuses a second active one. Seventeen provider manifests and a registry that
refuses to let the application start if a manifest omits how an operation
finishes.

**Proved rather than asserted:** 44 tests on SQLite, 5 on real PostgreSQL 16
(the isolation probe, the one-active-credential guard and the append-only
trigger — none of which SQLite can express), 7 front-end tests each shown to
fail before it passed, three new gates each carrying a self-sabotage, and a
browser walkthrough clicked against the running product at 1440 wide.

**Deliberately absent:** the action button. The wireframe draws one on every
card and nothing behind it can honour a press until wave B. A button wired to
nothing is the failure this repository paid for four times in one day.

Eleven catalogues gain twenty-seven lines each, written in each language rather
than translated from English (B14 rule 35, ruled today), and lose the sentence
that is no longer true.

## 2026-09-03 — the Work module documented into `16-work/` (CR-070)

`04-docs/05-modules/16-work/` — written from *SMARTBillHub Work Module Blueprint, read of
2.128.2 / 47108051*, sections 1–14 read (to card `WM-35`); **§15–§21 unread** because the
PDF (16.3 MB) is over the download cap and the text reader stopped inside §14. Every row
built from an unread section says so.

**What is in it:** 10 epics, **54 user stories** in the canonical eight-section format,
**57 business rules** (`BR-WRK-001`–`057`) plus the signed rules Work inherits, cited
never restated, **352 test cases** (132 negative, 53 tenant-isolation), 53 sets of
concrete test data, a field map of 25 card-named tables plus 9 the wireframes need and 28
changed columns across four existing tables (two of them NOT built), **94 endpoints**
against `CR-070`'s *"roughly 30"* (the reason is at the foot of `07-endpoints.md`), and
**8 end-to-end journeys** reserved as `J60`–`J67`. Screens `Work-001`–`Work-033`. Eight
open questions registered as `OQ-WRK-1490`–`1497`.

**Three Product Owner rulings of the day, written where they land:** *"it will become the
module itself"* (work is the eleventh code module) · *"Use Work-nnn - code for this"* (the
screen series) · ***"Dont add Tax on work order - for now"*** — so `WM-46` is not built,
`Work-031` is not drawn, and the work-order report totals **`$138.42`** with no tax line
where the wireframe drew `$149.84`.

**What step 0 found, all recorded in `01-overview.md` §4 rather than fixed silently:** the
blueprint's headline says thirty-eight specifications over forty-nine cards · `CR-070` §9
says nine screens are drawn as `WS-01`–`09` when the nine that exist are `WS-01`–`06` and
`WS-18`–`20` · nineteen `CR-070` §8 rows carry a title that is not the card's · `CR-070`
§11 sends a lane to `WM-24` for the offline queue, which is `WM-36` · `CR-070` §3 counts
one changed table where there are four · `CR-070` §10 names `17-work/` where `16` is next ·
`CR-070` §6 says raise four questions where one (`OQ-376`) is already open · two wireframes
contradict their own cards on stock levels and on lapsed certifications. Ten defect rows,
`DEF-WRK-3542`–`3551`.

**One figure this module found for itself:** `WM-47`'s *0.87 h × 48.50 = 42.20* is only
reachable if hours are rounded to two decimals before pricing — at four decimals it is
`42.03`. The rounding point is now a rule (`BR-WRK-051`) in one named function with a test.

⚠ **THE 8 JOURNEY FILES IN `08-qa/01-e2e/journeys/` ARE NOT WRITTEN YET**, and `04-flows.md`
says so in its own header. **The visual pass IS done:** 21 wireframe images (`wireframes/Work-007`…`033.png`, 0.7 MB),
`08-screen-layouts.md` and `09-component-inventory.md`, from the §13 PDF the PO uploaded
(*Screens to build*, 2.3 MB, 30 pages). Governance rows applied the same day: `OQ-WRK-1490`–`1497`,
`DEF-WRK-3542`–`3551`, four decision-log rows, the reservation block released.

## 2026-09-03 — the integration substrate documented into the existing integrations module (CR-069)

`04-docs/05-modules/13-integrations/` gains Part 2 of every file and nine new epics — written from
*The Integration Substrate* (engineering design, baseline `2.109.0`, re-read at `2.120.1`), read to
about page 106 of ~310 because the 32.8 MB file exceeds the 10 MB download cap; the thirty-six
specification cards of `CR-069` §8 cover the unread sections.

**What is in it:** **36 business rules** `BR-INT-018`–`053` (the document's nineteen at their own
numbers, the six principles as `037`–`042`, eleven specification rules `043`–`053`; every one of
`C1`–`C36` mapped to a rule), **9 epics** `EP-INT-05`–`13` holding **34 stories** `US-INT-013`–`046`
in the eight-section format with **~150 test cases** and a test data set each, the **five tables'**
DDL and the seams in the field map, **12 end-to-end journeys** `J48`–`J59` (the table said 9; the
design's own list has eleven and phase 5's exit test is a twelfth) plus legs on `J14`, `J17`, `J19`,
and **31 endpoints** across four edges where the table said *provisional*. Screens `S141`–`S146`.
**Nineteen open questions `OQ-INT-1470`–`1488`** — the first ids to carry a module code under the
PO's ruling of the same day.

**Not done, and said so:** the journey files in `08-qa/` are not written; B2 is not edited (anchoring
the five tables in the brief is the build lane's first task, `C34`); no code. **The visual pass IS done,
later the same day:** the PO uploaded *The Integrations Surface* (22 pages, 41 frames) and all 41 are saved as
`13-integrations/wireframes/frame-NN-N.png` (0.8 MB) with `08-screen-layouts.md` and `09-component-inventory.md`.

**Also today:** the count table for `CR-070` (the Work module) approved and its folder `16-work/`
opened by a parallel lane; tax on a work order ruled out for now; questions and defects gain a
module segment in their ids.

## 2026-09-03 — the fifteenth documentation module: the customer portal (CR-068)

`04-docs/05-modules/15-portal/` — written from *SMARTBillHub Customer Portal ·
Blueprint, read of 2.125.4*, 163 pages and 26 sections, read in full.

**What is in it:** 12 epics, **74 user stories** in the canonical eight-section format,
**96 business rules** (`BR-CWP-001`–`096`), **608 test cases**, 74 sets of test data, a
field map of 14 new tables and 11 changed columns across 6 existing tables, 82→**98
endpoints** across four edges, and **18 end-to-end journeys** reserved as `J30`–`J47`.
Screens `CWP-001`–`CWP-079`. Nine open questions registered as `OQ-1391`–`OQ-1399`.

**Five things step 0 found, all recorded in `01-overview.md` §8 rather than fixed
silently:**

* The blueprint draws **79** screens; `CR-068` allocated **75** and stopped at `B7`. The
  four phone screens had no numbers at all — the blueprint's own §26 admits they *"were
  never counted"*. They are `CWP-076`–`CWP-079`, and next free ground is `CWP-080`.
* The specification register closes *"Thirty-eight rows, thirty-eight cards"* over a
  table of **56**. Off by eighteen, **inside the one section whose job is listing
  seventeen count errors**. Build from the rows, never the sentence.
* **Five screen titles in `CR-068` §9 are wrong** — `CWP-013`/`014` and
  `CWP-060`/`061`/`062` carry titles lifted from §16's *"where the customer meets it"*
  column, three of them shifted by one. The ids do not move; the titles are corrected.
* Every *"as built"* claim was true at **2.125.4** and the product is at **2.128.2**, so
  **not one of the 56 specification statuses is verified** — which is the blueprint's own
  instruction: *"a status guessed from a change log is worse than no status at all."*
* The endpoint count moved from an estimated 82 to **98**, and the reason is written at
  the foot of `07-endpoints.md`. Not new scope: the signed-in surface needed 71 rather
  than 55, because the blueprint's §17 audit found nineteen things the back office holds
  that reach no screen, and each of those is a read.

**Two figures the blueprint corrected itself on are carried in the corrected form**, so a
lane reading the stories never meets the wrong one: a plan over `$172.20` with `$40.00`
up front is **five** instalments of `$22.03` and a final `$22.05` (its consequence box
said six, contradicting its own table), and `5,900 gallons in two days` against `155
gal/day` is about **nineteen** times usual, not eight.

**One figure this module found for itself.** `US-CWP-062`'s cheaper-option comparison
does not behave the way the blueprint's example implies: five months of an `$18.50`
standing charge is `$92.50` against `$185.00` reconnection plus a `$150.00` deposit, so
stopping is cheaper — but so is twelve months at `$222.00`. **The crossover is 19
months**, so the recommendation must be computed rather than hardcoded.

⚠ **THE 18 JOURNEY FILES IN `08-qa/01-e2e/journeys/` ARE NOT WRITTEN YET.**
`04-flows.md` says so in its own header rather than letting a story's `journeys:`
frontmatter imply a file exists, and `J30`–`J47` are reserved in
`12-governance/14-id-reservations.md` so no sibling lane takes the block.


## 2026-08-16 r10 — new UI bundle: Work, Workflows, expanded Assets (CR-002)

- Stored verbatim at `05-prototype/r10-2026-08-16/` (see its `PROVENANCE.md`).
  **Additive — r9 is untouched and remains the ratified reference**, because all
  seventeen A-series spec documents cite `05-prototype/UtilityBilling.html` by path.
- New `module:'work'` — nine tabs: orders · dispatch · wmap · crews · parts ·
  templates · rules · mobile · perf. Field service management; **no module in the
  map owns it** → `OQ-249`.
- New `module:'workflows'` — a guided runner (`wfKind` = reads · rates · cost ·
  stock) entered from Work.
- **Assets** grown from a stub to seven tabs: meters · sub · **btm** · inventory ·
  lifecycle · imports · map. `btm` (behind-the-meter: solar inverters, EV chargers)
  is new vocabulary.
- New `UI-RULES.md` — twenty conventions declaring themselves binding on every
  screen. **Not audited against the deployed app yet**; see CR-002 §4.
- New `table-tools.js` (the list-table assembly behind UI rules 12–17).
- **r10 IS THE DEFAULT UI REFERENCE** — PO ruling 2026-08-16, *"for this session
  we will be refering to r10 - as default"*. Where r10 and r9 disagree, r10 wins.
- **Docs NOT synced, and that now matters more, not less.** Unlike every entry
  above this one, the A-series has NOT been re-extracted. All seventeen documents
  cite `05-prototype/UtilityBilling.html` by path and describe **r9** screens
  while the default reference is **r10**. Read the design for the screen and the
  spec for the rules; where A1–A17's screen text contradicts r10, r10 is right
  and the spec is stale — file it before building on it.
- **Scope still open (OQ-249).** A reference default is not permission to build
  Work, Workflows or the new Assets tabs.


## 2026-08-07 (post-export reworks)
- **Semantic colors added** to `styles.css` + `theme.json`: success / warning / danger tokens (100/500/700). Status pills (`.pill.ok/.warn/.past/.draft`) are now real design-system classes bound to these — no longer prototype-local hacks. (A12 updated.)
- **accent-2 clarified**: it is a mono-scheme machine stand-in, not a real second role. A12 corrected to match readme/theme.json.
- **Empty/loading/error states** documented as 6 shared patterns (A18) — previously missing.
- **Document templates** specified (A19): printed bill/statement, disconnect notices (3 tiers), payment-plan agreement.
- **Pricing card feature bullets** finalized for Starter/Growth/Scale (A13 addendum).
- **Settings module** rebuilt with full CRUD: Company (+ Regional & Formats + Fiscal), Services & UoM enable/disable, Routes & Cycles config, Lookup-table management (add/edit/deactivate/delete + audit-lock), Users & roles (3 predefined roles + read-only RBAC matrix), Numbering, Notifications, Integrations (all connectable), Security, Billing plan. (A1/A2/A4/A11/A16 updated.)
- **Integrations connectable**: every card has Connect/Manage + a connect modal; connect/test/disconnect endpoints (A11).
- **BYO email**: tenants connect their own mailbox (Google/Microsoft OAuth or SMTP); no shared email engine (A15, B7).
- **User account menu**: profile / change password / 2FA / sign out (A1 S48, A6, A4).
- **Money-math confirmations** (finance): late fee on overdue portion, grace from due date (calendar/business), tax on usage+base only with account-level exemption, calendar-day proration of base+usage, multiplier-before-tiers with per-bill tier reset that scales on short/long periods, round per line item (half-up), NSF/reconnect are samples. (B4/B5/B2 updated.)
- **NFR**: connection counts are indicative (~5,000+), never a hard cap (B6).

## 2026-08-07 (initial export)
- Full /docs tree (A1–A19 spec, B1–B8 decisions, contracts, CLAUDE.md), Postgres schema (B2), runnable 05-prototype/.

## Re-export procedure (every change)
1. Update the .dc.html + the affected /docs files.
2. Re-copy runtime into 05-prototype/: `UtilityBilling.html` (from the reference with local paths), `styles.css`, `_ds_bundle.js`, `support.js`, `ds-base.js`.
3. Bump this changelog.

## 2026-08-07 r2 — Finance requirement mapping build
- Added Finance **General ledger** tab (trial balance + account mapping + premises/period filter + export).
- Added **Manual journal entry** (standard/accrual/reversing) and **Record refund** (outbound check/ACH, status) modals.
- Added **Account ledger** report (by account + **premises** + date range, PDF/CSV) in Reports.
- Reframed multi-entity → **by-premises reporting** (single legal entity; premises = locations).
- Deferred ERP/payroll connectors (revisit later).
- Docs synced: A1, A6, A14, B2. Prototype re-exported.


## 2026-08-07 r3
- Added dedicated **By-premises summary** report (billed/collected/owed per premises, collection %) — separate from Account ledger. Docs A14 synced; prototype re-exported.


## 2026-08-07 r4 — Assets module
- New **Assets** menu (Meters / Sub-meters / Devices) with list, filter, bulk import, single add, CRUD, and a full **detail view** (Overview / Reads / Assignment history / Maintenance & repairs / Audit).
- Lifecycle: inventory → active → needs repair → in repair → active | retired; repair/retire/reassign modals.
- Net metering measured on net meters (rating input; credit math pending finance).
- New lookups: Asset types, Asset statuses.
- Docs synced: A1, A2, A3, A5, A8, A16, B2. Prototype re-exported.


## 2026-08-07 r8 — Templates
- Added **Settings → Templates** (Printable / Email / Text) with an editor (variables, versioning, send-test). Numbering now points here for wording. Docs A1/A13/A15/A19 synced; prototype re-exported.

## 2026-08-07 r9 — Templates in Reference data
- Templates tab removed from the Settings strip; reached via **Reference data → Document & message templates** (back-link returns).
- **Printable templates now open a WYSIWYG document designer** rendering the real bill on paper (letterhead, service/tier breakdown, taxes, totals, usage graph, ways-to-pay, legal block, remittance stub) with a live controls rail (layout, paper size, show/hide blocks, message + footer copy, variables) and Print-test / Download-PDF / Save actions. Email & SMS keep the copy editor.


## 2026-08-07 — template designers built out

- **Templates moved into Reference data.** The standalone Settings → Templates tab was removed; the "Document & message templates" card in Reference data now opens the template list (with a back link).
- **Fixed:** the printable-template modal could not be closed — `closeSettingsModal` was referenced but never defined.
- **All 16 template designers built with distinct content.** Previously the Design/Edit buttons pointed at modals that did not exist, so every template appeared identical. Each now has a true-to-life preview:
  - **Printable (6):** residential bill, commercial bill (PO/tax-ID/per-meter/demand), statement (ledger over range), disconnect notice (3 tiers + PUC rights footer), dunning (3 stages), receipt (single transaction).
  - **Email (6):** bill ready (usage + YoY), payment receipt, past-due reminder (3 tones), plan change (before/after + impact), credit issued (clerk memo as reason), statement email (period summary).
  - **SMS (4):** bill ready (103ch), past-due (138ch), disconnect (156ch, URGENT), payment received (99ch) — each with a phone-bubble preview and live segment counter.
- Every designer lists its own **merge variables** and **per-template options**, and is versioned + audit-logged.
- See `04-docs/01-spec/19-document-templates.md` for the full content spec and the six rules that fall out of it (statement ≠ bill, dunning ≠ disconnect, SMS never stands alone, etc.).


## 2026-08-07 — Billing plan split into Plan / Invoices

- **Settings → Billing plan** now has two tabs.
  - **Plan** — subscription detail, entitlements, included features, payment-method card, next-invoice summary and billing details. Actions: Change plan · Manage payment method · Cancel subscription.
  - **Invoices (14)** — full invoice table (Invoice · Period · Issued · Due · Plan · Amount · Method · Status · Action) with a KPI strip, All/Unpaid/Paid filter, search and Export all. Unpaid rows are highlighted and carry **Pay now**; paid rows carry **Receipt ↓**. History spans a Starter→Growth plan change and an ACH→Visa method change.
- **Manage payment method** is now a real modal (card / ACH / invoice-wire, card fields, billing address, auto-charge toggles) instead of a toast.
- See `04-docs/01-spec/01-screen-inventory.md` (S107–S109) for the full spec, including the rule that Bynry subscription invoices must never mix with customer bills.


## 2026-08-07 — Settings → Company split into two tabs

- **Company profile** — Utility details (legal name, DBA, EIN, state utility ID, mailing address, support phone/email, website), Brand (logo drop, primary colour, bill accent, live letterhead preview), and a new **Remittance** card (remit-to address, payable-to, service hours) that feeds the printed bill stub. Sticky footer: Save / Discard + last-edited stamp.
- **Regional, formats & fiscal calendar** — three cards side by side: **Location & language** (country, state, timezone, language, first day of week), **Formats** (currency, number, date, time + live preview line), and **Fiscal calendar** (FY start, accounting method, close cadence, close-by day, current-period status, lock-closed-periods toggle).
- **Layout fixed.** The old single page stacked three sections down a 2fr/1fr grid, leaving large empty regions. Both tabs now use `repeat(auto-fit, minmax(320px, 1fr))` so cards reflow to fill the viewport at any width.
- Footer note on the regional tab: changing these settings does not restate historical bills.


## 2026-08-08 — onboarding expanded to 5 steps

- **New step 3 · Plan & setup.** Subscription tier (Starter $1,000 / Growth $5,000 / Scale $8,000 per month) and **implementation package** (Self-serve $0 · Guided $5,000 · Standard $9,000 · Full $12,000, one-time) chosen together with a live running-cost bar. Connection count is a **range picker**, advisory only.
- **New step 4 · Review.** Read-only summary of prior steps with per-block **Edit** links, default-sourced values marked `default`, and a due-today / then-monthly panel. **No card at signup** — the 14-day trial starts without payment details.
- **Step 5 · Create login** — mobile now explicitly optional.
- **Dropdowns expanded** — all 50 states + DC + Puerto Rico as a **searchable type-ahead**; 8 US timezones incl. Phoenix, Anchorage, Honolulu, Puerto Rico; billing cycle gains Semi-annual and Annual; bill-on day is 1st–28th plus Last day; tax region derives from the selected state and offers "I'll configure this later".
- **Friction reduced** — web address auto-suggested with a live availability check; step 2 gains **Skip — use defaults**; every step says what can be changed later and where; rate style labelled a *starting default* since utilities often bill differently per service.
- **Deliberately excluded from signup:** legal name, EIN, state utility ID, mailing address, logo, brand colours, remittance address. They live in Settings → Company, prompted by the post-signup checklist.
- Specs updated: `01-screen-inventory.md` (S110–S114 + dropdown coverage), `09-navigation-flows.md` (Flow 1 rewritten with backend handoff points), `13-copy-and-microcopy.md` (implementation package copy).

### Documentation backfill — Assets → Behind the meter

The third Assets tab was renamed from "Devices" to **Behind the meter** and covers net meters, backflow preventers, communication endpoints, PV/solar, battery and EV chargers. Net meters are **billing-relevant**: bidirectional export/import feeds net-metering credits in rating. Lifecycle across all asset types: Inventory/Spare → Installed/Active → Needs repair → In repair → Active, or → Retired (terminal). Assets referenced by issued bills are audit-locked — retire, never hard-delete. Covered in `03-domain-model.md`, `05-state-machines.md` and `08-tariff-spec.md`.
