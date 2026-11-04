# EP-REP-05 — Dashboards: S7 KPIs + panels, ops chips on S7 + S32 (no new screen v1)

**Module:** reports · **Wave:** W5 · **Screens:** S7 (+ S32 chip/label consumption) · **Status:** draft (BR-REP-001..018 CONFIRMED; formula rules RQ-1..9 ratified)

## Scope
**In:** the **S7 SCREEN ITSELF — the route, the page and its honest tiles (US-REP-019, added 2026-08-16 from DEF-129)**, which is the half nothing owned: US-SHL-001 owned the chrome, US-REP-016 owned the W5 figures, and the SCREEN between them was nobody's, so `/{tenant}/dashboard` fell through the router's catch-all and the first thing a user saw after every sign-in was the literal string "SMARTBillHub — W0 scaffold" · the **S7 main dashboard content** (KPI strip + panels per prototype + the A14 §Dashboard widget set) with EVERY formula ruled — collection % (BR-REP-009), DSO (BR-REP-011), active accounts (BR-REP-012), Cash today = CLEARING (BR-REP-010), billing status ← bill_runs, exceptions ← S31.3, write-offs YTD ← approved write_offs, capture intents excluded (A14 item 10) — and every money widget **basis-labeled** (BR-REP-001) · the **five RQ-7 ops chips on S7 + S32** (delivery health · pending billing · returned mail · corrections pending · tie-out drift — BR-REP-015, no new screen v1) · the **S32 reports-law conformance layer** (BR-REP-010 label pair, BR-REP-014 purpose rule, BR-REP-016 dunning-stage naming).
**Out:** the S7 shell chrome/nav (US-SHL-001) · the S32 panel render itself (US-PAY-005 — payments-owned; this epic binds labels/formulas/chips onto it) · S36 KPI strip (US-LED-007) · tie-out computation (US-LED-004) · queue re-queue operation (US-NOT-013) · KPI drill-down screens (A1: lightly stubbed — routes go to owning modules).
**Tables:** read-models only (BR-REP-002); rollup reads per NFR-26 at closed periods.

## Capability matrix (list screens only — B9 conformance)
*(S7 is a dashboard — KPI strip + panels, no IS-2 list; S32 rows live in the payments pack. No capability rows here.)*

## Stories

---
id: US-REP-016
epic: EP-REP-05
module: reports
screens: [S7]
wave: 5
status: draft
blocked_by: []
depends_on: [US-SHL-001, US-LED-007, US-PAY-005, US-BIL-005, US-CUS-001]
journeys: [J2, J5]
rules: [BR-REP-001, BR-REP-002, BR-REP-009, BR-REP-010, BR-REP-011, BR-REP-012]
golden_tests: []
finance_calc: confirmed
---
### US-REP-016 — S7 dashboard: ruled KPI formulas, basis-labeled widgets, ruled panel sources

**1 · Details** — As staff landing on S7 (prototype: greeting + cycle countdown + Import reads / Run billing actions), I want the dashboard computed ONLY from read-models (BR-REP-002; rollups per NFR-26 for closed periods): **KPI strip** (prototype) — **AR outstanding** (dimension-derived AR, POSTING basis) · **Unbilled reads** (committed-unbilled `meter_reads` count + pending routes) · **Failed payments** (failed read-model + needs-retry count) · **MTD revenue** (POSTING basis) · **Active connections** (= Active + Marked disconnect + Vacation hold; Pending activation + Closed excluded — BR-REP-012; shown against the subscription band per prototype "of 1,000 plan · Growth"). **A14 widget set**: **Cash today = CLEARING basis** (BR-REP-010) · **billing status ← `bill_runs` states** and **exceptions-to-action ← S31.3 cases** (A14 item 10) · **recent activity** (event read-model) · **AR aging panel** (same derivation as US-REP-005 — Σ = AR KPI) · **Service mix MTD** (revenue by service dimension; live service set, BR-REP-006) · **To do** (route-outs to owning modules). Collections figures where shown: collection % per BR-REP-009, DSO per BR-REP-011, BILL-purpose only (BR-REP-014), write-offs separate, **capture intents shown as "autopay scheduled" and EXCLUDED from cash/collected** (A14 item 10 / BR-PAY-015). **Every money widget header labels its basis** (BR-REP-001). Entry: sign-in / sidebar. Exit: drill routes to owning modules.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-REP-010 | S7 "Cash today" = CLEARING. | CONFIRMED — PO RQ-2, 2026-08-08 |
| BR-REP-012 | Active-accounts KPI = Active + Marked disconnect + Vacation hold; Pending activation + Closed excluded. | CONFIRMED — PO RQ-4, 2026-08-08 |
| BR-REP-009 / BR-REP-011 *(consumed)* | Collection % and DSO formulas wherever they render. | CONFIRMED — PO RQ-1 / RQ-3 |
| A14 item 10 | Billing status ← bill_runs; exceptions ← S31.3; write-offs YTD ← approved write_offs; intents = "autopay scheduled", excluded from cash/collected. | CONFIRMED — reports audit 2026-08-08 |
| BR-REP-001 | Every money widget labels its basis. | CONFIRMED — PO ruling 2026-08-08 |
| BR-REP-002 / NFR-26 *(consumed)* | Read-models only; closed periods read rollups. | CONFIRMED — audit / NFR-26 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | LE-1 month figures | AR outstanding = **152.32** (dimension-derived, = S36/US-LED-007); MTD revenue foots to the posting-basis billed figure **553.69**; AR aging panel Σ = the AR KPI |
| TC-2 | Cash today vs Today total | S7 Cash today counts CLEARED-today money (BR-REP-010); a payment posted today but uncleared appears in S32 "Today total" (posting) and NOT in S7 Cash today — the ruled divergence renders |
| TC-3 | Active connections | Fixture: 1,240 Active + 18 Marked disconnect + 6 Vacation hold + 30 Pending + 200 Closed → KPI **1,264**; band context from the subscription read-model |
| TC-4 | Billing status + exceptions + activity | Billing widget states = `bill_runs` lifecycle; exceptions count = open S31.3 cases; recent activity rows tie to their source events; To-do routes out |
| TC-5 *(basis label)* | Every money widget | "posting basis" / "clearing basis" on each money header (AR, MTD revenue, Cash today, aging, service mix) — any unlabeled money widget = FAIL (BR-REP-001) |
| TC-6 *(negative)* | Open capture intents + pending write-off | Intents render only as "autopay scheduled", excluded from Cash today/collected; an unapproved write-off changes nothing (approved-only per A14 item 10) |
| TC-7 *(isolation)* | Lone Star Ridge S7 | Its figures only (RLS); Brazos Bend numbers never leak |

**4 · Test Data** — LE-1 (553.69 / 401.37 / 152.32); status-mix fixture (1,240/18/6/30/200); prototype layout values for shape (184,320 strip, service mix, activity feed); intents: 2 open (US-PAY-024 fixture); posted-uncleared payment: PE-10 check posted Aug 8, clears Aug 10. Actors: Alex Reed. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| AR outstanding KPI | S7 | prototype-extracted + BR-LED-016 pattern | dimension-derived AR (journal_lines r13 #1) | numeric(18,6) | computed-display | posting basis, labeled; = tie-out figure |
| Cash today | S7 | A14 §Dashboard + BR-REP-010 | Σ `payments` cleared today | numeric(18,6) | computed-display | clearing basis, labeled |
| MTD revenue | S7 | prototype-extracted | Σ revenue postings MTD | numeric(18,6) | computed-display | posting basis, labeled |
| Unbilled reads | S7 | prototype-extracted | committed-unbilled `meter_reads` count + route states | counts | computed-display | channel rows (r8) |
| Failed payments | S7 | prototype-extracted | `payments` failed read-model | counts | computed-display | ties to S32/S33 |
| Active connections | S7 | prototype-extracted + BR-REP-012 | status lookup classes over `accounts` + subscription band | counts | computed-display | A+MD+VH exactly |
| Billing status / exceptions | S7 | A14 item 10 | `bill_runs` states / S31.3 case read-model | states/counts | computed-display | live states |
| AR aging panel | S7 | prototype-extracted | US-REP-005 derivation | rows | computed-display | Σ = AR KPI |
| Service mix MTD | S7 | prototype-extracted | revenue by `service` dimension | $/rows | computed-display | live services (BR-REP-006) |
| Recent activity / To do | S7 | prototype-extracted | event read-model / route-outs | rows | computed-display | links to owners |

**6 · Acceptance**
- Given the fixtures, Then every KPI/panel derives from its ruled source and foots to the owning surfaces (S36, S32, S34, bill runs) to the cent.
- Given the bases, Then Cash today is clearing, AR/revenue are posting, and every money header says so.
- Given intents/approvals/tenants, Then non-money never counts and nothing crosses.

**7 · Finance Calculation** — CONFIRMED (workbook figures verbatim, formulas ruled): AR **152.32** = 135.90 + 16.42 (LE-1); collection-% rendering per BR-REP-009 = **72.49%** (401.37 ÷ 553.69, US-LED-007 §7 verbatim); DSO per BR-REP-011 = (AR ÷ billed-12-mo) × 365; Active KPI fixture: 1,240 + 18 + 6 = **1,264**.

**8 · Open Questions** — None.

---
id: US-REP-017
epic: EP-REP-05
module: reports
screens: [S7, S32]
wave: 5
status: draft
blocked_by: []
depends_on: [US-REP-016, US-PAY-005, US-NOT-013, US-BIL-006, US-BIL-016, US-LED-004, US-PAY-016]
journeys: [J2, J5]
rules: [BR-REP-015, BR-BIL-015, BR-BIL-014, BR-PAY-018, BR-LED-007, BR-NOT-005]
golden_tests: []
finance_calc: none
---
### US-REP-017 — The five RQ-7 ops chips on S7 + S32 — read-models, deep links, no new screen

**1 · Details** — As staff, I want the **new ops chips living on S7 + S32 — no new screen v1** (BR-REP-015, PO RQ-7): **① Delivery health** — queued/failed/bounced counts over the platform queue (BR-NOT-005), deep link to the US-NOT-013 dispatch dashboard; **② Pending billing** — the BR-BIL-015 held-accounts queue count with aging/escalation state, deep link to the S30 queue (US-BIL-006); **③ Returned mail** — open bad-address needs-attention count (BR-PAY-018; the S32 chip is US-PAY-016's — S7 renders the SAME read-model, one source); **④ Corrections pending** — `correction_cases` awaiting approval count (BR-BIL-014), deep link to the S30 corrections queue; **⑤ Tie-out drift** — the BR-LED-007 drift state (computed by US-LED-004): green/absent when tied, **red flag naming the delta when drifted — release-blocker semantics preserved: never dismissible from a chip**, deep link to the S36 tie-out panel. Every chip count ties to its owning surface exactly (BR-REP-002 — same rows, no second counter). Entry: S7/S32 render. Exit: deep links into owners.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-REP-015 | The five ops chips live on S7 + S32 — no new screen v1. | CONFIRMED — PO RQ-7, 2026-08-08 |
| BR-BIL-015 *(consumed)* | Pending-billing queue: KPI chip, aging, escalation; catch-up sub-runs are billing's. | CONFIRMED — PO A-6 (a) |
| BR-BIL-014 *(consumed)* | Corrections pending = cases before approval (no money yet). | CONFIRMED — PO A-5 + OQ-072 |
| BR-PAY-018 *(consumed)* | Returned-mail needs-attention queue; S32 chip ratified (A1 addendum). | CONFIRMED — PO PA-7 |
| BR-LED-007 *(consumed)* | Drift = red flag + release blocker; only clears via a posted explaining entry. | CONFIRMED — PO LF-7 |
| BR-NOT-005 *(consumed)* | Delivery counts read the platform queue. | CONFIRMED — PO ruling |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Chip placement | All five on S7; the ops set on S32 per BR-REP-015/A1 addendum — and NO new screen exists for them |
| TC-2 | Count fidelity | Each chip = its owner's count exactly: delivery = US-NOT-013 dashboard totals; pending billing = the BR-BIL-015 queue incl. aging/escalated split; corrections = pending `correction_cases`; returned mail = US-PAY-016 queue (S7 and S32 always equal — one read-model) |
| TC-3 | Tie-out drift (LE-7 fixture) | Deposit register 153.50 vs GL 150.00 → chip red naming −3.50 + subledger; links to S36; when the correcting entry posts, the chip clears — no other clear path |
| TC-4 *(negative)* | Attempt to dismiss/acknowledge the drift chip | No dismiss affordance exists (BR-LED-007 release-blocker semantics); other chips clear only by their queues emptying |
| TC-5 *(negative)* | Approved-but-executed correction / re-queued delivery failure | Leaves the pending/failed counts immediately (same rows) — no stale second counter possible (BR-REP-002) |
| TC-6 | Zero states | Empty queues render per A18/IS-7 zero states — never an error, never hidden data |
| TC-7 *(isolation)* | Lone Star Ridge chips | Its queues only (RLS) |

**4 · Test Data** — Queue: 500-batch, 3 failed + 1 bounced (US-NOT-013 fixture). Pending billing: 4 held accounts, 1 escalated (US-BIL-006 fixture). Returned mail: A-11455 Park (US-PAY-016). Corrections: WE-9 case pre-approval. Drift: LE-7 (−3.50). Actors: Alex Reed, Norma Reyes. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Delivery-health chip | S7/S32 | BR-REP-015 + BR-NOT-005 | counts over `outbound_messages` (r12 #16) | counts | computed-display | = US-NOT-013 totals |
| Pending-billing chip | S7/S32 | BR-REP-015 + BR-BIL-015 | held-accounts queue (r10 #7 family) + aging/escalation | counts | computed-display | = S30 queue |
| Returned-mail chip | S7/S32 | A1 addendum + BR-PAY-018 | open bad-address queue (r12 #8) | counts | computed-display | one read-model, both screens |
| Corrections-pending chip | S7/S32 | BR-REP-015 + BR-BIL-014 | `correction_cases` awaiting approval (r10 #9) | counts | computed-display | pending only |
| Tie-out drift chip | S7/S32 | BR-REP-015 + BR-LED-007 | tie-out views (r13 #6, US-LED-004) | state+$ | computed-display | red on drift; no dismiss |
| Deep links | S7/S32 | BR-REP-015 | routes to owning surfaces | — | computed-display | owners act; chips read |

**6 · Acceptance**
- Given the queues, Then five chips render on S7 + S32 with counts equal to their owners and deep links landing on them.
- Given drift, Then the chip is red, undismissable, and clears only through the books.
- Given zero states/tenants, Then A18 renders and nothing crosses.

**7 · Finance Calculation** — N/A (counts + the LE-7 drift delta −3.50 rendered verbatim from the tie-out view).

**8 · Open Questions** — None.

---
id: US-REP-018
epic: EP-REP-05
module: reports
screens: [S32]
wave: 5
status: draft
blocked_by: []
depends_on: [US-PAY-005, US-PAY-013]
journeys: [J4, J5]
rules: [BR-REP-010, BR-REP-014, BR-REP-016, BR-REP-001, BR-REP-011]
golden_tests: []
finance_calc: confirmed
---
### US-REP-018 — S32 conformance layer: the blessed label pair, purpose rule, tenant-cadence dunning names

**1 · Details** — As staff on the payments summary (render owned by US-PAY-005), I want the reports law bound onto S32: **① the blessed basis pair labeled** — "Today total" = **POSTING** · "Method mix MTD" = **CLEARING** (BR-REP-010; extends BR-PAY-021) with both headers carrying their labels (BR-REP-001 — no unlabeled money on S32); **② collections figures** — count **BILL-purpose payments only** (BR-REP-014; deposit/plan-down/prepay as their own lines), DSO per BR-REP-011, write-offs shown separately (BR-REP-009); **③ dunning-stage naming** — wherever "Dunning 1/2/3" (A19 stage vocabulary) renders in collections context, the stages are the **reminder stages of the tenant-config BR-PAY-017 sequence**, and the **day numbers 7/14/30 are SEEDED DEFAULTS of that cadence, never constants** (BR-REP-016): a tenant with an edited cadence sees ITS day numbers. This story adds labels/bindings only — panel data contracts stay with US-PAY-005/US-PAY-013. Entry: S32 render. Exit: a summary tab on which every number's basis and vocabulary is law-conformant.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-REP-010 | S32 "Today total" = posting · "Method mix MTD" = clearing (blessed pair). | CONFIRMED — PO RQ-2, 2026-08-08 |
| BR-REP-014 | Collections KPIs = BILL-purpose only; other purposes separate. | CONFIRMED — PO RQ-6, 2026-08-08 |
| BR-REP-016 | Dunning 1/2/3 = reminder stages of the BR-PAY-017 sequence; 7/14/30 = seeded defaults of the tenant-config cadence. | CONFIRMED — PO RQ-8, 2026-08-08 |
| BR-REP-011 *(consumed)* | DSO tile formula. | CONFIRMED — PO RQ-3 (resolves payments pack P-1) |
| BR-REP-001 | Both labels rendered; nothing unlabeled. | CONFIRMED — PO ruling 2026-08-08 |
| BR-PAY-017 *(consumed)* | The cadence itself (tenant-config ladder) is payments-owned. | CONFIRMED — PO PA-6 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(basis labels)* | S32 render | "Today total" header labeled **posting** · "Method mix MTD" labeled **clearing** (BR-REP-010); a payment posted today/uncleared is IN Today total and OUT of the cleared-based mix — divergence visible, both labeled |
| TC-2 | Collections panel | Owed/collected framings count BILL-purpose only; a deposit-purpose 150.00 renders on its own line, never in collection figures (BR-REP-014); DSO tile = BR-REP-011 formula (P-1 superseded); write-offs separate |
| TC-3 | Dunning naming, default tenant | Stage references render "Dunning 1 · day 7 / Dunning 2 · day 14 / Dunning 3 · day 30" — from the SEEDED cadence config, not constants (BR-REP-016) |
| TC-4 | Dunning naming, edited cadence (10/20/40) | The same surfaces render 10/20/40 — proving no hardcoded day number exists |
| TC-5 *(negative)* | Any S32 money figure without a basis label | FAIL (BR-REP-001) — the conformance suite walks every money element on the tab |
| TC-6 *(isolation)* | Lone Star Ridge S32 | Its cadence config + figures only (RLS) |

**4 · Test Data** — PE-10 day (posted-today set incl. one uncleared check); deposit-purpose 150.00 (WE-6); cadence configs: seeded 7/14/30 and edited 10/20/40 (S70 Collections & notices rules fixture); prototype layout ("$18,420 · 84 payments · avg $219", mix 62/26/9/3). Actors: Priya Menon. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| "Today total" label | S32 | BR-REP-010 | posting-basis label on the US-PAY-005 panel | text | computed-display | required |
| "Method mix MTD" label | S32 | BR-REP-010 | clearing-basis label on the US-PAY-005 panel | text | computed-display | required |
| Collections purpose rule | S32 | BR-REP-014 | BILL-purpose filter over `payments.purpose` (r12 #2) | $/counts | computed-display | other purposes separate lines |
| DSO tile | S32 | BR-REP-011 | formula over AR + billed-12-mo | days | computed-display | posting basis |
| Dunning-stage names | S32 (+notices surfaces) | A19 + BR-REP-016 | tenant cadence config (r14 #5 settings keys / S70) | text+days | reference-data | day numbers from config only |

**6 · Acceptance**
- Given S32, Then the blessed label pair renders and no money element is unlabeled.
- Given purposes, Then only BILL-purpose money enters collections figures and DSO follows its formula.
- Given cadence edits, Then dunning day numbers follow tenant config everywhere; given tenants, nothing crosses.

**7 · Finance Calculation** — CONFIRMED (formulas ruled, figures from workbooks): DSO = (AR ÷ billed last 12 mo) × 365 (BR-REP-011). Collection framing per BR-REP-009/014 worked case: **72.49%** = 401.37 ÷ 553.69 (LE-1, US-LED-007 §7 verbatim — deposit application counted, transfer + prior-period + non-bill purposes excluded).

**8 · Open Questions** — None.

---
id: US-REP-019
epic: EP-REP-05
module: reports
screens: [S7]
wave: 5
status: ready
blocked_by: []
depends_on: [US-SHL-001, US-SHL-011, US-SHL-013, US-SHL-020, US-LED-007, US-PAY-005, US-CUS-001, US-BIL-025]
journeys: [J2, J5]
rules: [BR-REP-001, BR-REP-002, BR-REP-012, BR-REP-024, BR-REP-025, BR-REP-026, BR-REP-027, BR-REP-028, BR-REP-029, BR-REP-030, BR-REP-031, BR-REP-032, BR-REP-033, BR-SHL-001, BR-SHL-011, BR-SHL-012, BR-SHL-020, BR-SHL-023, BR-SHL-044, BR-TEN-022]
golden_tests: []
finance_calc: none
---
### US-REP-019 — S7 exists: the landing screen, and every tile either carries the owner's figure or says it cannot answer

**1 · Details** — As **any staff user, on the first screen I see after every single sign-in**, I want the Dashboard to BE a screen, so that the product does not open on a developer string. This story exists because DEF-129 measured exactly that in a browser on 2026-08-15: `App.tsx` redirected `/{tenant}` to `dashboard`, **no route with that path existed**, the request fell through `path: "*"` to `ModulePlaceholder`, and the content pane rendered the literal `SMARTBillHub — W0 scaffold`. It is the sidebar's FIRST item. **The root cause is hard-won law 8 for the SECOND time** (DEF-006 was the S1 landing page): A1 lists S7, US-SHL-001 owned the chrome AROUND it and US-REP-016 owned the W5 FIGURES inside it, and **the screen between them belonged to nobody**, so it was nobody's to build and nobody's to notice.

**What this story delivers, and its one governing constraint.** S7 renders the prototype's layout (page head + KPI strip + four panels, `05-prototype/UtilityBilling.html` lines 653–711) and **not one figure on it is computed here**. Every number is read from the surface that OWNS it, through a seam resolved BY NAME at call time (`apps/reports/dashboard_seams.py`), and **where the owner publishes no such read the tile REPORTS that it cannot answer, by name — it never renders 0**. That is not caution, it is this product's own history: DEF-104 shipped four surfaces disagreeing about one customer's balance (the account screen said **$0.00** while the ledger held an issued, unpaid **$108.88**), and a zero that means *"I don't know"* is how it reached a browser. A dashboard is the densest collection of money-and-volume claims in the app and therefore the worst possible place to compute a second opinion.

**What renders with a real figure today** (owner → tile): `apps.ledger.reporting.revenue_and_ar` → **AR outstanding** and **Revenue this period** (both POSTING basis, both labeled per BR-REP-001, both carrying the currency the books are denominated in) and the **Service mix** panel (`revenue_by_service`, the same call, so the panel and the KPI cannot disagree). **What reports that it cannot answer, each naming its own gap**: **Unbilled reads** (metering publishes no unbilled-read count), **Failed payments** (payments publishes the fifty most recent failed payments for its own S32 panel — a COUNT over all of them is not published, and a tile reading "50" on a tenant with 80 would be a wrong number, not a partial one), **Active connections** (BR-REP-012's classes — Active + Marked disconnect + Vacation hold — need a status-class count customers does not publish; `accounts_rollup` answers a total, which is a DIFFERENT question), **AR aging** (the ledger returns `aging: null` with its own reason: a journal line carries no due date), and **Recent activity** (there is no event read-model). Each absence is QUANTIFIED where a figure exists to quantify it — the AR-aging panel shows the receivable total the missing bands would have to add up to, the same posture S60 already ships.

**Page head.** Title = a time-free greeting carrying the signed-in user's name (**OQ-220**: the prototype's *"Good morning"* needs three invented boundary hours and a ruling on whose clock). Sub-line = the utility's own current accounting period from `GET /settings/regional` (BR-TEN-022) — the same period S36/S59/S60 head with, so no two screens disagree about which month a figure belongs to; the prototype's cycle countdown is **OQ-221**. Actions = the prototype's two, wired: *Import reads* → S28, *Run billing* → S31. Entry: sign-in, `/{tenant}` index redirect, sidebar item 1. Exit: every tile and panel routes to its owning module.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-REP-024 | **A dashboard tile never computes a figure.** Every KPI and panel on S7 renders the OWNING surface's published figure, or reports by name that it cannot answer — never 0, never a client-side sum, never a second query over another module's tables. | **PROPOSED** — derived from BR-REP-002 (read-models only, never a side-maintained number) + BR-LED-016 + DEF-104 (four surfaces, one balance, $0.00 vs $108.88) + DEF-075 (a `None` means *"this module cannot answer"*, never *"this module has nothing"*). Reported for the daily PO batch; nothing about it is a choice of VALUE, only a refusal to invent one |
| BR-REP-001 *(consumed)* | Every money widget labels its date basis. | CONFIRMED — PO ruling 2026-08-08 |
| BR-REP-002 *(consumed)* | Dashboards are read-models; never a side-maintained number. | CONFIRMED — reports audit 2026-08-08 |
| BR-REP-012 *(consumed)* | Active-accounts KPI = Active + Marked disconnect + Vacation hold. | CONFIRMED — PO RQ-4 — and **not satisfiable today**, so the tile refuses rather than substituting the account total |
| BR-TEN-022 *(consumed)* | The accounting period is COMPUTED from fiscal settings, never stored. | CONFIRMED |
| BR-SHL-044 *(consumed)* | One page header for every screen. | CONFIRMED — PO prototype walk, DEF-021 |
| BR-SHL-020 / BR-SHL-012 *(consumed)* | Plain-language failure; the shared A18 states. | CONFIRMED |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(the defect)* | Sign in as Dana Whitfield and land on `/{tenant}/dashboard` | The content pane renders the S7 page head and KPI strip. **The literal string "SMARTBillHub — W0 scaffold" appears nowhere on the page** — the assertion DEF-129 would have failed |
| TC-2 | The route table | `/{tenant}` redirects to `dashboard` AND a route with path `dashboard` exists; the catch-all `*` is never reached for it |
| TC-3 | LE-1 figures, tenant currency USD | AR outstanding renders **152.32 USD** labeled *posting basis*; Revenue this period foots to **553.69 USD**, same label; both come from ONE `revenue_and_ar` call so they cannot disagree |
| TC-4 *(negative — the whole point)* | Unbilled reads · Failed payments · Active connections, with their owners publishing nothing | Each renders "Not available" WITH its own sentence naming what is missing. **No tile renders 0, "0", "—" alone, or an empty value** |
| TC-5 *(negative)* | AR aging, ledger answering `aging: null` | The panel renders the named reason AND the receivable total the bands would add up to — never an empty four-row table, which would read as *"nothing is overdue"* |
| TC-6 | Every money element on the screen | Carries a currency and a basis label (BR-REP-001, CLAUDE.md rule 2). A money figure without either = FAIL |
| TC-7 | Quick actions and route-outs | *Import reads* lands on S28, *Run billing* on S31, and each To-do row on its owning module — no dead control, no count on any row (OQ-222) |
| TC-8 *(negative)* | `GET /dashboard/summary` unreachable (route absent / 500) | A18 §4 failure in plain language. **No tile falls back to a number** |
| TC-9 *(isolation)* | Lone Star Ridge signs in | Its own figures only (RLS FORCE); Brazos Bend's 152.32 never appears |
| TC-10 *(the escape route)* | The E2E boot helper | `bootApp()` asserts something in the CONTENT pane, not only the chrome — run it against a content pane holding only the scaffold string and it goes RED |

**4 · Test Data** — Brazos Bend (`brazosbend`), the seeded fixture: LE-1's July book — AR **152.32**, billed **553.69**, currency **USD**, trial balance **598.69 = 598.69**. Actor: **Dana Whitfield**, dana@brazosbendutilities.com, System Admin. Isolation: **J. Okafor** at Lone Star Ridge. Unwired owners: metering (no unbilled-read count), customers (no status-class count), payments (a 50-row failed LIST, no count).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | Owner + read (seam, resolved by name) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| AR outstanding | S7 | prototype line 661 · US-REP-016 §5 | `apps.ledger.reporting.revenue_and_ar` → `kpis.still_owed` | numeric(18,6) + CHAR(3) | computed-display | posting basis, labeled; = the S36 figure to the cent |
| Revenue this period | S7 | prototype line 664 | same call → `kpis.billed` | numeric(18,6) + CHAR(3) | computed-display | posting basis, labeled |
| Service mix | S7 | prototype lines 678–685 | same call → `revenue_by_service` | numeric(18,6) + CHAR(3) | computed-display | one call ⇒ cannot disagree with the KPI |
| Accounting period | S7 | BR-TEN-022 | `apps.tenancy.selectors.regional_settings` → `current_period` | dates | reference-data | absent ⇒ the head says so, never a browser month |
| Unbilled reads | S7 | prototype line 662 | **UNWIRED** — metering publishes no such read | count | computed-display | **reports absent + reason** |
| Failed payments | S7 | prototype line 663 | **UNWIRED** — `apps.payments.summary.summary.failed` is a 50-row LIST, not a count | count | computed-display | **reports absent + reason** |
| Active connections | S7 | prototype line 665 · BR-REP-012 | **UNWIRED** — no status-class count published | count | computed-display | **reports absent + reason** |
| AR aging | S7 | prototype lines 690–702 | `revenue_and_ar` → `aging: null` + its own gap row | rows | computed-display | **reports absent, QUANTIFIED by the AR total** |
| Recent activity | S7 | prototype lines 668–676 | **UNWIRED** — no event read-model exists | rows | computed-display | **reports absent + reason** |
| To do | S7 | prototype lines 704–709 · US-REP-016 §1 | route-outs only, no counts (OQ-222) | links | computed-display | every link resolves; no count rendered |

**6 · Acceptance**
- Given a staff user signs in, Then the first screen they see is S7 and the developer scaffold string is nowhere on it.
- Given the ledger's July book, Then AR outstanding reads 152.32 USD and Revenue this period foots to 553.69 USD, each labeled posting basis, both from one call.
- Given an owner that publishes no read, Then that tile says in the user's own language that it cannot answer and names what is missing — and renders no number at all.
- Given another tenant, Then only its own figures render.

**7 · Finance Calculation** — **N/A — and that is the story's central claim.** This screen performs no arithmetic on money of any kind: not a sum, not a percentage, not a difference. Every amount is a decimal string the owning read model computed, rendered through the one `MoneyCell` path (BR-SHL-023) with its currency. The two figures it displays are `revenue_and_ar`'s own, already golden-tied through US-LED-007 §7 (AR **152.32** = 135.90 + 16.42; billed **553.69** = 247.87 + 16.42 + 289.40).

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-220 | Does the greeting change with the time of day, and by whose clock? | The greeting WORDING only — a time-free greeting ships | Product Owner | OPEN — non-blocking |
| OQ-221 | Which cycle does "Cycle 08-A closes in 4 days" name, and to what date? | The countdown line only — the accounting period ships instead | Product Owner | OPEN — non-blocking |
| OQ-222 | What feeds "To do", and may an item carry a count? | The COUNTS only — the route-outs ship | Product Owner | OPEN — non-blocking |

---

## US-REP-019 · AMENDMENT — S7 becomes r10's DSH-01 (CR-012, PO ruling 2026-08-18)

**This amendment does not replace §1–§8 above; it says what CHANGED.** The story
above is still the true account of DEF-129 and of why no figure on this screen is
computed here. What it describes, though, is the screen as built on 2026-08-16 —
five KPI tiles, an amounts-only service mix, an AR panel that refuses, a to-do
panel of three bare links — and the PO has now specified the screen in full.

**The request, verbatim:** *"Next CR on Dashboard - Please fix the dashbaord it
should display like this ; build all services, backend frontend ; you can find UI
details in r10 - - update all 04 doc and user stories br etc"*. The complete
DSH-01 requirements followed in the same session and are recorded word for word
in `12-governance/11-change-requests.md` §CR-012. Nine business rules came out of
them — **BR-REP-025 … BR-REP-033, all CONFIRMED 2026-08-18** — and they are the
normative text; what follows is the delta a lane needs.

### What changed, region by region

**Region 1 · greeting + cycle status.** The greeting is unchanged and still
time-free (**OQ-220** is still open — the requirement writes *"Good morning,
{first name}"* and still does not say what happens at 18:00 or by whose clock).
**The cycle status line is NEW** and closes the selection half of **OQ-221**:
`{weekday} · {month day} · Cycle {code} closes in {n} days`, naming *"the
next-closing active cycle from SET-07 (tie broken by account count)"*, with four
states — normal, *"closes today"*, *"closed — bill run pending"*, and no cycle
configured, which links to Settings → Routes & Cycles (BR-REP-027).

**Region 2 · KPI band.** Unchanged in shape and still display-only — *"KPI cells
do not navigate in v1"* (BR-REP-033). **The MTD-revenue tile's *"against forecast"*
sub-line is a TYPED PER-TENANT MONTHLY TARGET** — OQ-265 was minted by this lane on
2026-08-18 and CLOSED the same day by the PO, who was shown four options against
one fixture and answered **"B"** (BR-REP-034). With a $400,000 target it reads
`86% of $400,000 target`; **with no target typed the tile degrades to the figure
alone**, which is the state every tenant on this deployment is in today and is
therefore the state proved first. The neighbouring *"of N plan"* IS derivable from
the tenant's subscription and is built.

**Region 3 · recent activity.** Was a whole-panel refusal (*"no module publishes
an event read-model"*). **That sentence was true of the operational modules and
was never true of `apps.audit`,** which has published `audit_queryset` /
`audit_page` since the S61 viewer shipped. The panel is now the last 24 hours,
max six rows, newest first, filtered to operator-relevant action classes and to
what the role may see (BR-REP-031). Amounts render `—` on every row, because
`audit_log` carries no money column and reading one out of a stored before/after
diff would be exactly the second opinion BR-REP-024 forbids.

**Region 4 · service mix.** The change the CR is named for. ⚠ **AMENDED BY THE PO
ON 2026-08-19 AFTER SEEING IT BUILT, and the earlier text is kept because it is
what the amendment reverses.** It read: *"Five fixed rows — Electric, Water,
Sewer, Trash, Gas — always, in that order (BR-REP-025)"*. What that costs a
utility that does not sell those five is what the PO saw: **a broadband-and-water
utility met five rows, three permanently empty, and its actual revenue in the
remainder footnote.** The panel now draws **the TENANT'S OWN configured
services, always all of them, in the platform's fixed seed order** (BR-RAT-024's
ten: Electric · Water · Gas · Sewer · Trash · Storm water · Solar · Broadband ·
Thermal/Heat · Battery). The stability reason survives intact — a service list
changes when a utility adds a service, not month to month.

Each row carries a bar **proportional to the LARGEST service, not the total**
(BR-REP-026), and a configured service that billed nothing draws an empty bar and
an em-dash — never `$0.00`. **The remainder survives the amendment**: revenue
that names no service at all (a late fee is charged to an ACCOUNT) has no row to
live in however complete the list is. Both the bar rule and the row-set rule
REVERSE something a lane could re-derive from r10's own markup, and every
reversal is recorded at its BR.

**Region 5 · AR aging + to do.** The aging panel was a refusal quantified by the
AR total; it now draws **five buckets with accounts, amount and share**
(BR-REP-030), because the figure has an owner after all —
`apps.payments.outstandings.outstandings(as_of=…).ageing()` publishes exactly
those five bands, and its bucket comes from the oldest unpaid bill's due date,
which is why **an account on an active payment arrangement already counts in its
TRUE bucket rather than in Current**, as the requirement demands. Shares are
rounded and **need not total 100%** — no fudge row. The to-do panel is max four
items generated by their owning modules with a kind chip (BR-REP-032); *"Assign"*
is still not built, because nothing in this product assigns work to a person
(the remaining half of **OQ-222**).

**Cross-cutting.** Every region **loads, empties and fails independently**
(BR-REP-028) — *"one section failing must not blank the page"* — and every money
and count figure **arrives pre-formatted from the server** (BR-REP-029), which is
in stated tension with BR-SHL-023 and is reported rather than smoothed.

**The endpoint did not move.** The PO's spec names `GET /api/dashboard?tenantId
&asOf`; A11's S7 row contracts `GET /dashboard/summary`, which is a signed
interface. The route is unchanged and gained an optional `asOf` only; the tenant
comes from the request context and never from a query parameter (hard rule 1).
**The rename is UNRESOLVED and is reported, not taken.**

### 3 · Test Cases (added — TC-1..TC-10 above are unchanged)
| TC | Scenario | Expected |
|---|---|---|
| TC-11 *(AMENDED 2026-08-19)* | A tenant that has **enabled Electric, Water, Solar and Battery** and billed Electric and Water only | The service mix draws **four rows, in seed order — Electric, Water, Solar, Battery**. Solar and Battery each render an **em-dash and a zero-width bar** — never absent, never `0.00`. Sewer, Trash and Gas, which this utility does not sell, have **no row at all** |
| TC-11b *(the ruling's own case)* | A **broadband-and-water** utility | Two rows, Water then Broadband (seed order), and nothing in the remainder. Under the superseded five-row rule this tenant met three permanently empty rows and found its own revenue in a footnote |
| TC-11c *(the first of the month)* | A tenant that has billed **nothing at all** this period | Its own service rows are still drawn, each an em-dash — *"always all of them"*. The panel goes EMPTY only when there is nothing to draw at all |
| TC-12 *(negative)* | The books attribute revenue to a service the tenant has since switched off, or to no service at all | The amount is reported as a NAMED remainder and is **not** folded into a service row and **not** dropped — the panel may not foot to less than the period's revenue |
| TC-13 | Electric 238,000 · Water 76,000 · Sewer 28,000 | Bar widths **100 / 32 / 12 / 0 / 0** — a share of the LARGEST, not of the 342,000 total (which would be 70/22/8). Computed on the SERVER; the client renders the integer it was given |
| TC-14 *(AMENDED 2026-08-19)* | Four cycle states, driven by `as_of` against the next-closing active cycle | `closes in {n} days` · `closes today` at n=0 · `closed — bill run pending` past the close · **a plain statement, with NO LINK, when the tenant has no active cycle** (PO: *"no provide any link"* — cycle set-up lives in Settings → Routes & Cycles, CR-006's surface, reachable from the sidebar of every screen). A **draft** cycle is never named |
| TC-15 *(the acceptance criterion most likely to be faked)* | One region's own read raises | That region renders its error with a stable code; **the other five still render their figures** and the page head is intact. Asserted by making a region fail ON PURPOSE, never by asserting the page renders when everything works |
| TC-16 | A brand-new tenant with no billing history | KPIs render `—` with *"No billing history yet"*, and the remaining onboarding steps appear in To do. No region renders a zero |
| TC-17 | Every money and count figure in the payload | Carries a server-formatted `display` string beside the exact decimal. The client performs **no** rounding, grouping, symbol placement or percentage arithmetic — grep the page for `Intl`, `toFixed`, `/ 100` and find none |
| TC-18 | Aging with a mixed book | Five buckets with accounts, amount and share; the shares are rounded and **are allowed not to sum to 100%**; a share of an empty book is **null**, never `0%` |
| TC-19 *(money semantics)* | An account 45 days past due that is on an ACTIVE payment arrangement | It counts in **31–60**, not in Current. The naive implementation does the opposite |
| TC-20 | Recent activity over a busy day | At most **six** rows, all inside the last 24h of `as_of`, newest first, only operator-relevant action classes; a settings edit or a login never appears; every row shows `—` for amount |
| TC-21 *(AMENDED 2026-08-19)* | To do | At most **four** rows, each with its kind chip (`action` / `review` / `draft`) and a link into the owning module; an owner that COUNTED ZERO contributes no row, and **a row whose owner could not count renders the label alone — never a `0`**, because a zero tells the operator nothing needs their attention |
| TC-25 *(added 2026-08-19)* | The three KPI tiles whose owners publish no count | Each reads **"Not counted yet"** — plain language — and the architecture sentence appears in the tile's SUPPORT text. The wording *"reads not received"* must NOT appear: it asserts a fact about the utility's data where the true fact is about our product, so a clerk who has just imported 400 reads would be told something false |
| TC-26 *(added 2026-08-19)* | The Recent-activity panel, on a quiet morning | The panel STATES its window — *"last 24 hours"* — in both its heading and its empty sentence, rendered from the served `window_hours` figure rather than frozen into eleven catalogues |
| TC-27 *(added 2026-08-19)* | A clerk leaves the dashboard and returns within five minutes | No second `GET /dashboard/summary`. `DASHBOARD_STALE_MS` is five minutes — its own constant, not a move of the global default, which governs every operational read in the product |
| TC-22 *(role)* | An Executive (view-only on Reads & Billing runs, A4 addendum) opens S7 | `Import reads` and `Run billing →` are **absent from the DOM** — hidden, not disabled — and every KPI cell renders as text with no link or button anywhere in it |
| TC-23 | A tenant with a monthly revenue target of **$400,000** and MTD billed **$342,700.00** | The MTD-revenue tile's sub-line reads exactly **`86% of $400,000 target`** — 85.675% rounded half-up to a whole number. No bar, no arrow, no delta |
| TC-24 *(the default state, proved FIRST)* | A tenant with **no target typed** — which is every tenant on this deployment | The tile renders **the figure alone**: no sub-line, no percentage, no bar, no up/down delta anywhere in the tile's DOM. Nothing is derived from last month or last year, and **no day-prorated figure appears anywhere in the payload** |

### 8 · Open Questions (amended)
| OQ | Question | Blocks | Status |
|---|---|---|---|
| OQ-220 | Does the greeting change with the time of day, and by whose clock? | The greeting WORDING only | OPEN — non-blocking, unchanged by CR-012 |
| OQ-221 | Which cycle, and to what date? | Nothing — the selection rule is now ruled | **ANSWERED IN PART.** CR-012 names the cycle; the close FIELD (`read_day_to`) is DERIVED from the requirement's own four states and is flagged for confirmation |
| OQ-222 | What feeds "To do", and may an item carry a count? | *"Assign"* only | **ANSWERED IN PART.** CR-012 rules the sources, the kinds, the max of four and the clearing behaviour; what *"Assign"* DOES is still open and the control is not built |
| ~~OQ-265~~ | What is the MTD-revenue tile's denominator? | Nothing | **CLOSED 2026-08-18 → BR-REP-034.** Minted and ruled the same day: a per-tenant monthly target typed in Settings (PO: **"B"**). Untyped ⇒ the figure alone. Day-prorated comparisons are forbidden — the reason is in the BR |

---

## US-REP-019 · AMENDMENT 2 — the dashboard reports over a window the operator CHOOSES (CR-015, PO ruling 2026-08-19)

**This amendment REVERSES a design statement made in this very epic**, and the
reversal is the PO's. §US-REP-019's own text and `apps/reports/dashboard.py`'s
exception (2) both read:

> *"`dashboard_summary()` takes NO arguments: the window is the tenant's computed
> `current_period` (BR-TEN-022), the same one S36/S59/S60 use, so four screens
> cannot disagree about which month a figure belongs to. **A period picker on
> the landing screen would be a control that changes a number nobody asked to
> change.**"*

The PO, 2026-08-19, verbatim:

> *"If we allow this then there is now way user can see previous values and they
> will be confuse what is dashbaord is saying - so we will ahve to allow period
> filter on dashbaord - so user can select the filter ; default filter can be
> last cycle or last 30 days and let user to change the peiod"*

### Why the old posture was wrong about the COST, not about the risk

The risk it named is real and is answered below rather than dismissed. What it
got wrong is what a fixed calendar month costs a real utility, and the case uses
no demo data at all:

> A utility on the **3rd of any month**. Bills went out on the 25th. The
> dashboard shows the calendar month, so it shows **almost nothing** — for the
> first week of every month, forever. Revenue near zero, service mix nearly
> empty. Nothing is broken and the operator cannot tell why the screen looks
> dead.

The demo seed EXPOSED that; it did not cause it (DEF-298's diagnosis was
corrected by the PO for exactly this reason). It is the same fact this repo
recorded on 2026-08-18 and applied only to the forecast sub-line: **billing is
LUMPY by cycle, not daily.**

### What changed

| | Before | After (BR-REP-035 · BR-REP-036) |
|---|---|---|
| The window | the tenant's `current_period`, always | one of **THREE**, chosen by the operator: **last 30 days · this accounting period · last accounting period** ⚠ AMENDED 2026-09-26 (`CR-142-BRC07` `P0.15`) — this cell read *"one of four … last completed cycle"* for a month after `CR-029` `D8①` withdrew that window (PO: *"dont build it"*, `OQ-268` CLOSED-WITHDRAWN) |
| The default | the calendar/accounting month | **the last 30 days** — `dashboard_period.default_option_id` returns `last_30_days`. ⚠ AMENDED 2026-09-26: this read *"the last completed cycle, falling back to the last 30 days"*; the fallback became the default when `CR-029` `D8①` removed the window it fell back from |
| Saying which | nothing on screen said which window | the window is **stated in dates, prominently, above the figures** |
| `as_of` | the period END — `2026-08-31` on the 19th (DEF-299) | the **read moment clamped into the period** |
| `read_on` | did not exist | the day the figures were read; the page HEADER's date and cycle countdown use it |
| No fiscal calendar | every money figure null | the two ACCOUNTING options are withdrawn; the cycle and rolling windows still answer |
| URL | none | `?f.period=<id>` (BR-SHL-011), so a window is shareable and survives a reload |

### The risk the old posture named, and how it is answered

*"A control that changes a number nobody asked to change"* becomes *"a control
that changes a number, and says which number it now is."* The PO's consistency
rule — *"a KPI must agree with its owning module for the same as-of moment"* —
gets HARDER once a user may pick an arbitrary window, because the dashboard can
then differ from Finance **while both are correct**. The answer is not to
forbid the choice; it is to make the window legible without opening anything:
`Showing Aug 12, 2026 – Aug 19, 2026 · Figures as of Aug 19, 2026`, above the
first figure on the page.

### The completed-cycle derivation — A LANE JUDGMENT, NOT A SIGNED RULE (OQ-268)

SET-07 publishes `window_start`, `window_end` (the READ window) and `bill_date`.
Nothing signed says what makes a cycle "completed". This lane derived it and the
derivation is recorded rather than buried:

* **complete ⇔ its `bill_date` is on or before the read moment** — a cycle is
  complete when the work it exists to produce, the bill, has been issued;
* **its window ⇔ `window_start` … `bill_date`**, and NOT `window_start` …
  `window_end`. Cycle 08-B reads 12–16 Aug and bills on the **19th**. A window of
  12–16 Aug reports on the cycle's READS while excluding the cycle's own
  REVENUE, which books on the bill date — the identical dead screen this change
  exists to remove, one week narrower;
* a **draft** or **inactive** cycle is never the window (BR-MET-076), and a
  cycle with no `bill_date` is SKIPPED rather than given a default.

### 3 · Test Cases (added)

| TC | Given | Then |
|---|---|---|
| TC-28 | A tenant whose most recent active cycle billed on 19 Aug, read on 19 Aug | The dashboard opens on **that cycle**, `period` is `window_start … bill_date`, and the picker shows it selected |
| TC-29 | A tenant with **no** cycle, or none that has reached its bill date | The default is **last 30 days** — exactly 30 dates, `as_of - 29 … as_of` — and `no_completed_billing_cycle` states why the cycle option is absent |
| TC-30 *(DEF-299)* | Any window that CONTAINS today | `as_of` is **today**, never the period end. On 2026-08-19 the payload said `2026-08-31`, eleven days in the future |
| TC-31 *(DEF-299)* | A CLOSED window (last period) selected on 19 Aug | `as_of` is the period END (31 Jul) and `read_on` stays **19 Aug**; the page header's date and cycle countdown do not move |
| TC-32 *(negative)* | `?f.period=last_fortnight`, a stale bookmark, or a cycle since retired | The screen FALLS BACK to the default and answers 200. A landing page that 500s on a hand-edited URL is a locked front door (BR-SHL-011) |
| TC-33 *(BR-REP-028)* | Metering's `cycles_list` raises | ⚠ **THE FIRST CLAUSE IS MOOT SINCE `CR-029` `D8①` — there is no `last_cycle` option to disappear** (amended 2026-09-26, `CR-142-BRC07` `P0.15`; `test_cr015_dashboard_period.py:384` already records the amendment and this cell did not). What the case still asserts: the cycle-status region reports its own failure. **The page keeps its money** — the first build of this read the cycles in the page body and blanked the whole landing screen |
| TC-34 *(prominence)* | Any window | The window is spelled out **in dates, above the KPI strip**. A picker a reader must open to learn the window does not satisfy the requirement |
| TC-35 | A tenant with no fiscal calendar | `this_period` and `last_period` are ABSENT from the menu with `fiscal_period_not_configured` beside them — and the KPIs still carry figures, which is the state this reverses |

### 8 · Open Questions (amended)

| OQ | Question | Blocks | Status |
|---|---|---|---|
| OQ-221 | Which cycle, and to what date? | Nothing | **UNCHANGED by CR-015.** The countdown line's cycle selection is BR-REP-027's and is separate from the period vocabulary's completed-cycle rule; they read the same SET-07 rows through the same seam and answer different questions |
