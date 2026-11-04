# EP-BIL-01 — The bill run (five phases — prepare · calculate · breaks · summary+gate · release — over the six S31 wizard steps: select → check → exceptions → totals → confirm → send)

**Module:** billing · **Wave:** W3 · **Screens:** S30 (entry + Past billing runs tab), S31, S31.2, S31.3 · **Status:** draft (BR-BIL-001..029 all CONFIRMED — session closed 2026-08-08; **five-phase run model added 2026-08-11 — BR-BIL-050..062**)

## Scope
**In:** the bulk cycle run per the ratified pipeline (pre-session model §6, session-closed r2): idempotent run creation (BR-BIL-005), the S31.2 "Check what we found" preview — Consumers · Plans · Reads · Balances · Credits · **Overcharges** (guardrail BR-BIL-029) — the S31.3 exception step with the per-case missing-service choice (BR-BIL-015), draft bills with the confirmed draft powers (BR-BIL-023), issue (numbering BR-BIL-022, due date BR-BIL-024, immutability BR-BIL-004, GL stamp BR-BIL-010, posting handoff BR-BIL-011, template pin BR-BIL-026, delivery-queue write BR-BIL-016), and the held-account **Pending-billing queue + catch-up sub-runs** (BR-BIL-015, model r1.3). Status-class behavior at assembly (BR-CUS-055, OQ-064 closed seed) including mid-cycle Vacation-hold proration (BR-BIL-028). **Plus (2026-08-10, PO modularity request):** the run's INTERNAL SHAPE — the seven-stage pipeline with exactly one input contract and one output contract per stage, stated as rules so it can be tested rather than described (BR-BIL-037/039/040, US-BIL-029).
**Plus (2026-08-11, PO five-phase ruling):** the run's OPERATING SHAPE — **1 prepare · 2 calculate · 3 breaks · 4 summary + gate · 5 release** (BR-BIL-050). This RECONCILES onto the six S31 wizard steps already scoped above; it does not replace them (mapping table below). Five things the six steps did not carry, each now in scope: (a) the calculation is a **BACKGROUND BATCH** the clerk is not held at, with a run status the screen polls and a resumable partial state (BR-BIL-051/052) — the epic previously implied a synchronous "continue"; (b) a **BREAKS** list the moment calculation finishes — what failed, why, and per row *fix-and-retry now* or *mark for later* (BR-BIL-053) — with the over-guardrail draft moved here as a post-calculation exception carrying required actions rather than a pre-block (BR-BIL-054, refining where BR-BIL-029 surfaces, not what it computes); (c) a consolidated pre-release **SUMMARY carrying CONSUMPTION and category breakdowns** (BR-BIL-056/057) — the epic had per-tab counts only. ⚠ **This clause said "frozen at confirm rather than recomputed later" and that half is SUPERSEDED (PO 2026-08-11, option B): the SCREEN RECALCULATES LIVE.** The `bill_run_releases` row is still written at confirm and never rewritten — it is the append-only authorisation record (hard rule 4) — but re-opening the run shows what those bills total TODAY. Stored row and screen answer different questions on purpose; (d) a **RELEASE GATE that enumerates** compliance + email/text/autopay mandate confirmations, each recorded as its own fact (BR-BIL-058/059) — the epic said only "confirm"; (e) **BULK actions wherever a clerk would otherwise work account-by-account**, one `bulk_action_id` shared across the rows one click produced while each account keeps its own row (BR-BIL-060). Also in scope from the same ruling: a **partial run issues the clean bills and holds the rest** in the pending queue for a catch-up sub-run (BR-BIL-055) · **base-only billing is a RECORDED staff opt-in/opt-out at prepare time**, not a consequence of the status class (BR-BIL-061) · a first bill with **no prior read** prices at the plan's minimum for the category, prorated, with no usage line (BR-BIL-062 — OQ-102 CLOSED).
**Out:** rating math itself (EP-RAT-05 🔒 engine — billing calls it with assembled inputs) · estimation math (EP-MET-05 — invoked, not owned) · invoice/GL anatomy details (EP-BIL-02) · non-cycle bill types (EP-BIL-03) · corrections (EP-BIL-04) · delivery execution + dashboard (EP-BIL-06) · payment allocation execution (payments, BR-PAY-010 — the run only previews auto-apply) · ledger write execution (ledger posting service 🔒, W5) · the **refactor-invariance contract** over GT-1..61 and the two terminal stages (EP-BIL-02, US-BIL-030) · the rule-type plugin interfaces the priced stages resolve through (EP-RAT-05, US-RAT-015).
**Tables (B2 + r10):** `bill_runs` (+ status lifecycle, `parent_run_id` + scope, r10 #7), `bill_run_exclusions`, `bill_run_decisions` (the recorded staff choices + `bulk_action_id`, BR-BIL-060/061), `bill_run_releases` (the summary AS IT STOOD AT SIGN-OFF — written once, never rewritten — plus the four gate confirmations, BR-BIL-056/058; the SCREEN recalculates live per the 2026-08-11 option-B ruling, the ROW does not), `invoices`, `invoice_lines`. Reads/plans/accounts/balances via service functions only (B1).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S30 · Past billing runs tab | batch #, cycle | cycle, status (draft/issued/sent), ran-by | ran_at desc | ran_at, cycle, customers, total | Batch · Cycle · Ran by · Ran at · Customers · Total · Unresolved · Status / +period, parent run (IS-5 chooser) | View run (→ its wizard state read-only) | — | CSV (IS-9) |
| S30 · Pending-billing queue (KPI chip → list) | account #, customer | reason held, age band, cycle | age desc | age, account, period | Account · Customer · Period · Service(s) blocked · Reason held · Age · Escalation / +held-by (IS-5) | Open account · Resolve (→ catch-up scope) | Start catch-up sub-run (selected) | CSV (IS-9) |

*(S31/S31.2/S31.3 wizard-embedded tables follow IS-2/3/5 inside the wizard; they are not standalone list screens.)*

## The five phases over the six wizard steps (PO ruling 2026-08-11 — BR-BIL-050)

The PO described the run they want in one message. It is the same run this epic already specified — the mapping below is a RECONCILIATION, and the "what is new" column is the whole of what changed. Nothing here renumbers a wizard step, a stage or a story.

| Phase | The PO's words (verbatim) | S31 wizard steps | Stages run (BR-BIL-037) | What the phase leaves behind | What is NEW vs the six steps |
|---|---|---|---|---|---|
| **1 · PREPARE** | *"we build the data first for billing show all that data on screen for user so that all the decisions are made on screen and recorded, in case any data should be changed, he is able to do it"* | 1 Pick the cycle (US-BIL-001) · 2 Check what we found, S31.2 (US-BIL-002) · 3 Review customers, S31.3 (US-BIL-003) | 1–5 as PREVIEW; stage 6 not run (BR-BIL-039) | `bill_runs` row · `bill_run_decisions` rows incl. `base_only_billing` · `bill_run_exclusions` for holds | base-only billing is an opt-in/opt-out DECISION here (BR-BIL-061); every decision surface carries a BULK action (BR-BIL-060) |
| **2 · CALCULATE** | *"once all billing data exceptions, decisions are made, then run the billing in batch process in background"* | the transition INTO step 4 — the clerk is not held at the screen | 1–6 per account; stage 7 NOT reached | draft `invoices` + `invoice_lines` — no number, no GL stamp, no ledger, nothing immutable (BR-BIL-004) | the calculation is a BACKGROUND BATCH with a polled status and a resumable partial state (BR-BIL-051/052) — the epic implied synchronous |
| **3 · BREAKS** | *"once billing is complete show immediately bills that are break and why; allow user to retry immediately by fixing the issue or mark for later"* | a panel on step 4, ahead of the totals | none; a retry re-runs 1–6 for that account only | retried drafts, or `bill_run_exclusions` rows for *mark for later* | the break list itself (BR-BIL-053); the over-guardrail draft surfaces HERE with its required actions rather than as a pre-block (BR-BIL-054); a partial run issues the clean and holds the rest (BR-BIL-055) |
| **4 · SUMMARY + GATE** | *"then show the billing summary in how many accounts, how many bills generated, how much consumption and how much bill amount and various categories; take final confirm from user, compliance confirmation, emails, text mandates, auto pay mandates"* | 4 See the totals (US-BIL-004) · 5 Confirm & sign off (US-BIL-005) | none | ONE `bill_run_releases` row: the summary AS IT STOOD AT SIGN-OFF (written once, never rewritten — the append-only authorisation record), the four confirmations each recorded separately, who and when. **The SCREEN is not that row: it recalculates live on every viewing (BR-BIL-056, PO 2026-08-11 option B)** | CONSUMPTION + category breakdowns (BR-BIL-056/057) — the epic had per-tab counts only; the gate ENUMERATES its confirmations (BR-BIL-058/059) — the epic said only "confirm" |
| **5 · RELEASE** | *"and then release the bills and run the batches in background for downstream jobs"* | 6 Send them out (US-BIL-005) | 7 emits the balanced handoff, at issue | issued immutable invoices (numbers, due dates, GL stamps, template pins) · posting handoff · delivery-queue rows · `released_at` set | issue and every downstream job run as BACKGROUND batches too — the gate returns the clerk to S30, it does not hold them (BR-BIL-051) |

**Three axes, and none of them renumbers another.** The **seven stages** are the computation (BR-BIL-037). The **six S31 wizard steps** are the UI over it — the prototype's own stepper labels: Pick the cycle · Check what we found · Review customers · See the totals · Confirm & sign off · Send them out. The **five phases** are the operating model the PO described: what the clerk is doing, when the machine is working, and where the two review points are. *(US-BIL-029 §1 previously wrote "the five S31 wizard steps"; the wizard has six, and "five" now names the phases — corrected in that story below.)*

**Two review points, not one** (PO answer 2, same ruling): phase 1 reviews the INPUTS before anything is calculated; phase 3+4 review the OUTPUTS before anything is issued. A run that has been calculated has still billed nobody.

## ⚠ AMENDED 2026-09-30 — THE BULK BILL RUN REDESIGN (applies to US-BIL-036 … US-BIL-041; amends US-BIL-001 TC-4, TC-8)

**Sources, read in this order:** the change list `../14-bulk-bill-run-changes.md` (rows 1–43) · the build plan `../15-bulk-bill-run-build-plan.md` (R/D/B/A/DB/F/T/E/C, 82 tasks, PO-approved) · the 2026-09-30 rows of `12-governance/02-decision-log.md` · the rules `BR-BIL-1050` (the Scope refusal and warning list — written by the bulk Scope lane) and `BR-BIL-1051`–`1055`, and the amended `BR-BIL-005`, `1043` (stamped by the Scope lane), `1040`, `1041`, `070`, `1025`, `034` and `BR-RAT-007` (`../02-business-rules.md`) · the drawing images `05-prototype/bulk-bill-run-2026-09-30/` (index `README.md`, inventory `inventory.md`) · the defects `DEF-BIL-8200`–`DEF-BIL-8215`. **Build the screen from the IMAGES, not from this text** (B14 rules 42 and 44). A figure drawn in the mock-up is an ILLUSTRATION (rule 37): the figures these stories assert are the `BBR` fixture's below.

**What the PO said, verbatim, 2026-09-30:** *"im good with thsi - Screens to capture: 36 states, each at 2 screen widths = 72 images … + 82 tasks you mentioned; please start and ensure between step 1 and 2 for given account you runs allc heck sand dont stop at first problem"* · *"why two screens - this is not correct"* · *"what if we have warnings or rufusals on step 1 how you will show them that is not coming out"* · *"we have 7 or 8 categories and in each we ahve multiple tags … how are you going to allow user to see one tag accounts at a time, and allow user to fix the issues"* · *"on step 2 also you did not talk about payment ralted issues"* · *"at what step actual bills will be calculated bwtween 2 and 3"* · *"first screen units vacant units ect thos thing does not match"* · *"then the accounts are not bill or theya re on hold or ecluded in this run - we need to show them as a list or somthing and allow to run ran them later"* · *"you have see on this screen but it dones not go anywhere - dont you need screen for that"*.

**What it supersedes in this epic:** the six-step S31 wizard (*Pick the cycle · Check what we found · Review customers · See the totals · Confirm & sign off · Send them out*) becomes **four steps — Scope · Check · Sign off · Send** — with bills calculated between Check and Sign off (BR-BIL-050's five phases are unchanged: prepare = Scope + Check, calculate = the Calculating panel, breaks + summary + gate = Sign off, release = Send). `BillRunWizard.tsx` is deleted and Bills › Run opens the one screen (`DEF-BIL-8200`). US-BIL-001…006 stay as the history of the engine they describe; where they contradict a story below, the story below is current. It is MAINTENANCE (a live screen redrawn end to end), borrowing Build's drawing step.

### The shared fixture — `BBR` (every story below and journey `J72` use it)

Tenant **Brazos Bend Utilities** (`brazos-bend`); isolation tenant **Lone Star Ridge WSC**. Actors **Priya Menon** (Billing Clerk), **Alex Reed** (System Admin), **Jo Park** (view-only). Clock **Thu 1 Oct 2026, 09:00**.

* **Cycle 3 · Riverside** — monthly, reads start day 1 (5 days to complete), bill day **1st**, **21 days to pay**, 2 routes, usual template **Standard bill · v4** (published); also **Winter insert · draft** (never published). Previous runs: **BR-0231 Aug 1 – Aug 31, 2026**, *Sent* by J. Ortiz, 10 bills, $1,482.60; **BR-0229 Sep 1 – Sep 30, 2026, Cancelled** (a draft cancelled on Sep 29 — it must NOT count for continuity).
* **12 units, 10 accounts to bill (9 regular, 1 master):**

| Account | Who / unit | What is true of it this period |
|---|---|---|
| `AC-2026-00101` | Maria Alvarez · 1408 Elm St · Unit A | clean — water W-2001 (Aug 31 **482.0**, Sep 30 **492.0** kgal), electric E-3001 |
| `AC-2026-00102` | Omar Haddad · 1408 Elm St · Unit B | clean |
| `AC-2026-00103` | Priya Natarajan · 1410 Elm St · Unit A | **no reading** on W-2003 this period (a DECISION) |
| `AC-2026-00104` | Luis Alvarez · 1410 Elm St · Unit B | **no plan** on its unit (BLOCKS; fixable inline — plan *Residential Standard*) |
| `AC-2026-00105` | Grace Okafor · 1412 Elm St · Unit A | **no plan AND a disputed reading on W-2005 AND a bounced $85.00 payment of Sep 20 not reversed** — the PO's worked example (three tags) |
| `AC-2026-00106` | Tom Becker · 1412 Elm St · Unit B | metering returns its electric consumption **with no unit** |
| `AC-2026-00107` | Hannah Lee · 1414 Elm St · Unit A | **$120.00 payment posted Oct 1, after the check cut-off** (a DECISION) |
| `AC-2026-00108` | Diego Ramos · 1414 Elm St · Unit B | electric has **no base charge defined or bound** (WARNING — bills $0.00 base) |
| `AC-2026-00109` | Sara Cohen · 1416 Elm St · Unit A | clean — the clerk will **Leave out** |
| `AC-2026-00110` | Elm St Apartments (master) · covers 1418 Elm St Units A and B | clean |
| — | 1416 Elm St · Unit B | **vacant, nobody to bill** — last account moved out Aug 12; water connected |
| (service) | gas at 1408 Elm St · Unit A (`AC-2026-00101`) | gas **connected with no gas meter** — the one *Missing meter* on Scope (a WARNING; not billed, the rest of the account bills) |

* **Water price:** $3.25/kgal version in force **until Sep 30**, **$3.50/kgal from Oct 1, 2026**; base **BASE-W $8.00**. So `AC-2026-00101`'s 10.0 kgal is **$32.50 + $8.00 = $40.50** (at the bill date's version it would be $35.00 + $8.00 = $43.00).
* **Expected Check (before any fix):** ready **5** (`00101`, `00102`, `00108`, `00109`, `00110`) · need a decision **2** (`00103`, `00107`) · blocked **3** (`00104`, `00105`, `00106`) · warnings: base $0.00 on `00108`; nobody to bill 1 unit and missing meter 1 on Scope.

### Open items — NOT chosen here

| # | Item | Meanwhile |
|---|---|---|
| **OI-B1** | ✅ **CLOSED 2026-09-30 — option C: SAVE and RE-CHECK ON CHANGE** (PO: *"this is correct - C · Save results, and automatically re-check an account when its plan, reading, meter or payment changes"*; decision log "OQ-843 RE-RULED"). The text below is the question as it stood. **A saved Check versus `OQ-843`'s RECOMPUTE ruling.** The plan (B9, DB1) keeps the Check's results in a store with progress and resume; `OQ-843` was closed *RECOMPUTE* with *"A lane may not reopen this by proposing a cache"*. The PO approved the plan; the collision itself was not put in words (`DEF-BIL-8208`). | US-BIL-037 asserts that a fix is SEEN on re-check (the reason RECOMPUTE was ruled) and that progress survives leaving; it does not assert where the results live |
| **OI-B2** | **Payment facts with no source.** Each payment tag is read through the payments seam; which of the nine facts payments can answer today is not yet measured (plan Open). | US-BIL-037 TC-10 asserts the tags whose fact exists; a tag with no source is a deliberate absence, filed, never a guess |
| **OI-B3** | **"Leave for next cycle" loses no usage** — relies on BR-BIL-1039 (the next run opens at the last billed read). | US-BIL-041 TC-6 proves it on the fixture |

## Stories

---
id: US-BIL-001
epic: EP-BIL-01
module: billing
screens: [S30, S31]
wave: 3
status: draft
blocked_by: []
depends_on: [US-MET-006, US-CUS-001]
journeys: [J2, J24]
rules: [BR-BIL-005, BR-BIL-021, BR-BIL-024, BR-BIL-050]
golden_tests: []
finance_calc: none
---
### US-BIL-001 — Run selection: cycle + period, idempotent run creation

**1 · Details** — As a Billing Clerk, I want to start a billing run by picking a cycle and billing period (S31 step 1: cycle select with read window + customer count, bill date, derived due date), and have the system refuse a second identical run — showing who ran the original, when, and a link — so that a cycle is never double-billed (BR-BIL-005). Entry: S30 "Start a billing run". Exit: a `bill_runs` row in draft status → step 2 (US-BIL-002). Due date is display-derived at this step: bill date + the cycle's due-days (BR-BIL-024); the prototype's step-1 "Statement template" select is superseded by category-default template assignment (BR-BIL-025 — no single-template pick per run). Prototype service chips scope which services bill this run; a service left unchecked is an explicit scope choice recorded on the run, never a silent skip (model §2). Identical re-runs for held accounts go through catch-up sub-runs (US-BIL-006), never a colliding re-run. **Phase 1 of five (BR-BIL-050) starts here:** the run row created at this step is what every later phase hangs off, and its `status` is the PHASE the run is in — the value the screen polls once phase 2 goes to background (BR-BIL-051), and the value that tells a returning clerk whether a run is still calculating, waiting at the gate, or released.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-050 | The run is FIVE PHASES — prepare · calculate · breaks · summary+gate · release — mapped onto these six wizard steps (epic §Phase map); `bill_runs.status` carries the phase, so the run is resumable and inspectable from S30 at any point. | CONFIRMED — PO 2026-08-11 (the five-phase description, verbatim in the epic §Phase map) |
| BR-BIL-005 | Bill runs are idempotent — unique (tenant, cycle, period) key blocks an identical re-run; blocked attempt shows who/when/link (model §6 step 1, OQ-044 closure pattern). Key mechanics = human-owned 🔒 (CLAUDE.md #6). | CONFIRMED — B2 `bill_runs` UNIQUE (tenant_id, idempotency_key), CLAUDE.md #6 |
| BR-BIL-024 | Due date = bill date + the cycle's due-days; bill-delivery-day preference stays DROPPED (BR-CUS-060). **WHICH bill date is BR-BIL-070's answer (PO 2026-08-11): the one the clerk typed in step 1, the cycle's only when nobody typed one.** ⚠ The derivation in `apps/billing/issue._due_terms_for` still reads the cycle — REPORTED, one read, the issue lane's | CONFIRMED — PO Lane B-5, 2026-08-08 · input named PO 2026-08-11 |
| BR-BIL-070 | **The bill date a clerk types in step 1 is STORED (`bill_runs.bill_date`) and USED — it IS the run's SERVICE date, so it decides which tariff version prices every bill in the run (BR-RAT-007).** PO verbatim *"A Store what they type and use it"*. NULL = nobody typed one → the cycle's date; neither present → the findings pass REFUSES (422 / BR-BIL-024) rather than reaching for a clock (BR-TEN-043 / G6). Never part of the BR-BIL-005 idempotency key. | CONFIRMED — PO 2026-08-11 (OQ-122 option A) |
| BR-BIL-021 | Cycle due-days and all run-relevant knobs are tenant config, seeded, nothing hardcoded. | CONFIRMED — PO Lane B-2, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Priya starts a run: Cycle 07-A · Jul 1–31 · bill date Aug 1 | `bill_runs` row status draft, period 2026-07-01..2026-07-31; due date renders Aug 22 (Aug 1 + 21 due-days, tenant setting); audit `bill_run.created` |
| TC-2 | Alex attempts Cycle 07-A · Jul 1–31 again | Blocked by the idempotency key; message names Priya, the run timestamp, and links the original run (BR-BIL-005) — no second row |
| TC-3 | Priya starts Cycle 07-A · Aug 1–31 | Allowed — different period, new key; both runs listed on S30 Past billing runs |
| TC-4 ⚠ **SUPERSEDED 2026-09-30** (PO: *"which servcies to be billed in unit /account is decied at run time -so this filter is of now use"* — BR-BIL-1043 superseded for new runs; replaced by US-BIL-036 TC-9) | Run scoped to Electric+Water+Sewer only (Gas chip off) | Scope stored on the run; gas services excluded by explicit scope, recorded — not reported as missing-read exceptions |
| TC-5 *(negative)* | Forged POST with period_end < period_start, or a cycle id from another tenant | 422 / not-found; no `bill_runs` row |
| TC-6 *(isolation)* | J. Okafor (Lone Star Ridge) lists cycles and past runs | Sees only Lone Star Ridge cycles/runs (RLS); a Brazos Bend run id in the URL 404s |
| TC-8 *(the typed bill date is real — BR-BIL-070)* ⚠ **PRICING HALF SUPERSEDED 2026-09-30** (PO: *"this si correct"* to *"The period end: $3.25"* — BR-BIL-1055): the typed date still decides the due date (24 Aug); the tariff version is the one in force at the PERIOD END, not 2 Aug — replaced by US-BIL-038 TC-2 | Cycle 08-A is dated **1 Aug**; Priya types bill date **3 Aug**; a tariff version is effective **2 Aug** | The run's SERVICE date is **3 Aug**, so every bill prices against the 2-Aug version — not the one in force on 1 Aug — and the due date is **24 Aug** (3 Aug + 21 due-days), not 22 Aug. Leaving the field empty stores NULL and the run prices at the cycle's 1 Aug, the behaviour before the ruling. A second run over the same cycle and period is still refused however different its bill date (BR-BIL-005 gains no fourth key term). ⚠ The due-date half is NOT yet built — `issue._due_terms_for` still reads the cycle — so today this case reaches 3-Aug pricing and 22-Aug due |
| TC-7 *(phase resumability)* | Priya creates run 07-A, leaves the wizard, and re-opens it from S30 Past billing runs a day later | The run re-opens at the phase its `status` names — still phase 1, at step 1 — with the cycle, period, bill date and service scope as saved; no second `bill_runs` row, no lost decisions (BR-BIL-050) |

**4 · Test Data** — Tenant **Brazos Bend MUD** (workbook §1 fixture): Cycle 07-A, read window Jul 1–5, 1,124 customers, due-days 21; period Jul 1–31, 2026; bill date Aug 1, 2026 → due Aug 22, 2026. Actors: Priya Menon (Billing Clerk), Alex Reed (System Admin). Second run: Aug 1–31. Isolation: J. Okafor, Lone Star Ridge Co-op, cycle W-01.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Billing cycle | S31 step 1 | prototype-extracted (cycle select w/ window + count) | `bill_runs.cycle_id` (⚠ tenancy/metering FK, BR-MET-009 cycle) | uuid | user-input | tenant's active cycles only |
| Period start/end | S31 step 1 | model §6 step 1 | `bill_runs.period_start/period_end` | date | user-input | end ≥ start; feeds idempotency key |
| Bill date | S31 step 1 | prototype-extracted ("Bill date (shows on statement)") · **BR-BIL-070 (PO 2026-08-11, OQ-122)** | **`bill_runs.bill_date` at CREATE** (nullable — NULL means nobody typed one and the cycle's date is used), then `invoices.service_date` at issue; drives tariff-version selection either way. This cell used to name `invoices.service_date` alone, which is why the field had nowhere to live between create and issue and was silently discarded | date | user-input | optional; absent/null/"" all mean "nobody typed one"; a PRESENT value must be ISO — defaults to today |
| Due date (derived) | S31 step 1/5 | BR-BIL-024 | `invoices.due_date` at issue = bill date + cycle due-days | date | system-derived | never user-typed |
| Services scope | S31 step 1 | prototype-extracted (service chips) | run scope (r10 #7 `bill_runs` scope) | enum[] | user-input | subset of tenant-enabled services |
| Idempotency key | — | BR-BIL-005 | `bill_runs.idempotency_key` UNIQUE (tenant, key) — mechanics 🔒 Eng-Lead | text | system-derived | duplicate → block with who/when/link |
| Run status = the phase | S31 stepper · S30 | BR-BIL-050/051 | `bill_runs.status` (RUN_STATUSES, r10 #7) | enum | system-derived | one value at a time; the screen polls it through phase 2; a returning clerk re-enters at the phase it names |
| Run audit | — | CLAUDE.md #7 | `audit_log` `bill_run.created` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a cycle + period, When the run is created, Then a draft `bill_runs` row exists with the derived due date shown, And the action is audited.
- Given an identical (tenant, cycle, period), Then creation is refused with who/when/link and no row is written.
- Given a different period or cycle, Then a new run creates normally.
- Given a cross-tenant session, Then cycles and runs never leak.

**7 · Finance Calculation** — N/A (no amounts computed at selection; due-date arithmetic per BR-BIL-024: Aug 1 + 21 = Aug 22, 2026).

**8 · Open Questions** — None.

---
id: US-BIL-002
epic: EP-BIL-01
module: billing
screens: [S31.2]
wave: 3
status: draft
blocked_by: []
depends_on: [US-BIL-001, US-CUS-006, US-MET-010, US-MET-011, US-MET-014, US-RAT-012, US-RAT-013]
journeys: [J2, J24]
rules: [BR-BIL-001, BR-BIL-002, BR-BIL-008, BR-BIL-028, BR-BIL-029, BR-BIL-061, BR-BIL-062]
golden_tests: [GT-8]
finance_calc: confirmed
---
### US-BIL-002 — Step 2 "Check what we found": six preview tabs incl. the overcharge guardrail

**1 · Details** — As a Billing Clerk, I want the run to assemble every input per account and show me six review tabs before anything commits (S31.2, model §6 step 2): **Consumers** (billable count by status behavior class per BR-CUS-055/OQ-064 seed — Vacation-hold/Suspended accounts listed as base-only, incl. mid-cycle hold starts per BR-BIL-028), **Plans** (accounts missing plans/snapshots), **Reads** (completeness % per BR-MET-049 with Missing/Estimated/High/Low/Days/Factor sub-tabs, read-less services skipped per the workbook fixture), **Balances** (prior balances + late-fee candidates per BR-BIL-001/002/008), **Credits** (unallocated credits that will auto-apply per BR-PAY-010), and **Overcharges** (drafts above the tenant guardrail % of trailing average, BR-BIL-029) — ⚠ **STALE ON THIS TAB, `DEF-2706`, 2026-08-31: THE SIXTH TAB IS *CHARGES TO ADD*, NOT THE GUARDRAIL.** A16's glossary reads *"Over charges | extra items to add in a billing run"*, `04-docs/README` §111 reads *"nested tabs: All / Late payment fees / Service charges — apply/waive actions"*, and r10 line 4256 draws precisely that. Two concepts share one name and this line took the other one. **BR-BIL-029's guardrail is not lost — BR-BIL-054 already moved it to phase 3**, where it is surfaced after calculation with its three actions, and that is the only place it belongs. Built as charges-to-add by CR-051 task 15; TC-4 below still describes the guardrail and is stale in the same way — so that everything is visible before anything is billed (a missing input is an exception, never a silent skip, model §2). Entry: US-BIL-001 continue. Exit: step 3 (S31.3). The KPI strip totals each tab (prototype layout).

**This is the "build the data first and show all that data on screen" half of phase 1 (BR-BIL-050).** Two things the tabs must carry that the six-tab list above did not say. **(a) Base-only accounts are a CHOICE, shown here and decided here.** BR-CUS-055 says what such an account CAN be billed (base charges, no usage); whether THIS run bills them is the staff's call at prepare time — PO 2026-08-11, verbatim: *"this is decision user make hence during pre billing process, you have to give option to user to opt in or opt out of this decision"*. The Consumers tab therefore shows the base-only cohort with its count and the run's current opt-in state, and the toggle writes a recorded decision (case `base_only_billing`, US-BIL-003 §5) rather than silently following the status class (BR-BIL-061). **(b) An account with NO PRIOR READ is not a missing-read exception.** A first bill has no prior read by definition; the Reads tab must not list it under Missing, and it prices per BR-BIL-062 — the plan's minimum for the account's consumer category, prorated on calendar days, with NO usage line and no estimated read created (OQ-102 CLOSED 2026-08-11). Treating it as missing would send a brand-new customer to the pending queue on their first cycle. Consumption shown on these tabs is also the SOURCE of the phase-4 consumption summary (BR-BIL-056) — same measured quantities, same explicit units (CLAUDE.md #3), aggregated rather than re-measured.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-029 | Overcharge guardrail: any draft bill above tenant-set % (default 200%) of the account's trailing average is flagged in the run preview before issue. | CONFIRMED — PO Lane B-10, 2026-08-08 |
| BR-BIL-001 / BR-BIL-008 | Late-fee candidates computed as max($5, 1.5% × overdue portion); grace from due date, tenant-defined days (default 5, 0–30). Preview only lists candidates; application is a step-3/draft decision. | CONFIRMED — B4 §Late fee + PO Q&A R6 (OQ-005) |
| BR-BIL-002 | Grace mode = calendar OR business days (tenant setting) — both modes evaluated in the candidate computation (WE-15 d/e). | CONFIRMED — B4 §Late fee (B4.1) |
| BR-BIL-028 | Mid-cycle Vacation-hold start: usage lines bill through the day before the hold (interim read); base charges and flat services continue the full month (billable-base-only class). | CONFIRMED — PO Lane B-9, 2026-08-08 |
| BR-CUS-055 *(consumed)* | Status behavior classes drive inclusion: billable / billable_base_only / non_billable / terminal; seed per OQ-064 closure (Marked disconnect = billable). | CONFIRMED — PO OQ-064 closure (r9 #7) |
| BR-BIL-061 | Whether this run bills the base-only cohort is a STAFF opt-in/opt-out at prepare time, shown on the Consumers tab and RECORDED as a decision — never a silent consequence of the status class. | CONFIRMED — PO 2026-08-11 (*"this is decision user make…opt in or opt out"*) |
| BR-BIL-062 | First bill with no prior read: the plan's minimum for the account's consumer category, prorated on calendar days (B4.3), NO usage line and no estimated read. Not a missing-read exception. | CONFIRMED — PO 2026-08-11, OQ-102 CLOSED → (c) |
| BR-MET-049 / BR-PAY-010 *(consumed)* | Reads tab = plan-required channel-set completeness; Credits tab = unallocated credits in allocation order. | CONFIRMED — metering/payments rules, cited not restated |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Run 07-A assembles | Consumers 1,124 (21 excluded by class: Pending=non_billable, Closed=terminal); Vacation-hold rows show class billable_base_only |
| TC-2 | Reads tab | Completeness per BR-MET-049 across required channels; Broadband/Trash (read-less) never counted missing (workbook fixture: "completeness gate skips read-less services"); estimates labeled with method + consecutive count (US-MET-014 contract) |
| TC-3 | Balances tab, ACC-1042 prior balance $45.00 past grace | Late-fee candidate max(5, 1.5% × 45.00) = **$5.00** floor (WE-15b); overdue $400 fixture shows **$6.00** (WE-15a); partial-payment fixture: bill 247.87, paid 200 by due date → fee base = 47.87 overdue portion only → $5.00 (WE-15c); business-days tenant mode: due Fri Jul 17 → fee from Jul 24 (WE-15e, BR-BIL-002) |
| TC-4 | Overcharges tab | ACC-3020 draft at 312% of trailing average > 200% guardrail → flagged for review; account at 180% not flagged; tenant guardrail edited to 150% → 180% account now flags (config, not constant) |
| TC-5 | Vacation hold starting Jul 16 on ACC-1077 | Consumers tab marks the split; draft (step 4) prices usage through Jul 15 + full-month bases = WE-12 figures (§7) |
| TC-6 *(negative)* | Account with no plan snapshot as of service date | Listed under Plans as an exception; the account cannot silently reach drafts (model §2) |
| TC-7 *(isolation)* | Lone Star Ridge run preview | Assembles only Lone Star Ridge accounts/reads/balances; Brazos Bend trailing averages never feed its guardrail (RLS) |
| TC-8 | Consumers tab, base-only cohort (the Vacation-hold + Suspended accounts of TC-1/TC-5) | The cohort is shown with its own count and the run's current opt-in state; the toggle is a staff choice with no pre-committed default, and flipping it writes a `base_only_billing` decision row naming who/when (BR-BIL-061). The status class is NOT the decision — a run that opts OUT excludes them and says so on screen |
| TC-9 *(negative — the class is not the choice)* | Run started, base-only opt-in never touched, clerk continues to step 3 | Step blocks (or the cohort is listed unresolved) until the choice is made — a base-only account is never billed or skipped by default. No `invoices` row exists either way at this phase |
| TC-10 | ACC-1520, moved in Jul 12, no prior read of any kind; run 07-A | Reads tab does NOT list it under Missing and no estimated read is created (BR-BIL-062). It prices at the plan's configured minimum for its consumer category, prorated on calendar days from the move-in day (B4.3), with NO usage line. The PO's own OQ-102 worked example is the 30-day shape — move-in on the 12th → **19 of 30 days**. The minimum itself is tenant configuration (BR-RAT-028 / B4 §minimum bill), never a constant in code, so the amount is engine-computed and no figure is fixed here |
| TC-11 *(consumption feeds phase 4)* | Consumption shown on the Reads/Consumers tabs for the run | Every quantity carries its explicit unit (CLAUDE.md #3) and is the SAME measured quantity the phase-4 summary aggregates (BR-BIL-056) — the summary sums this, it does not re-measure |

**4 · Test Data** — Brazos Bend run 07-A (US-BIL-001 TC-1). ACC-1042 (WE-1 fixture: prior balance $45.00 past grace). Late-fee fixtures per WE-15: $400 overdue → 6.00; $45 → 5.00; partial 47.87 → 5.00; grace: due Jul 20 + 5 calendar → fee from Jul 26 (payment Jul 25 = no fee); business-days variant due Fri Jul 17 → fee from Jul 24. Guardrail: ACC-3020 (Ridge-Coffee-shaped: water 26.24 kgal vs 8.40 kgal trailing avg = 312%); ACC-3021 at 180%. Vacation hold ACC-1077, hold starts Jul 16 (WE-12). Credits: ACC-1090 −$42.20 unallocated. Base-only cohort: ACC-1077 (Vacation hold) + ACC-1602 (Suspended) — opt-in state per run, no default. No-prior-read first bill: **ACC-1520**, Residential Standard, moved in Jul 12, 2026, no read of any kind before the run → prorated on calendar days per B4.3 (the PO's own OQ-102 example is the 30-day shape: move-in on the 12th = **19 of 30 days**); amount = the tenant's configured plan minimum for the residential category × the proration, **engine-computed** (00-e2e-design.md §5) — no figure is fixed in this epic. Isolation: Lone Star Ridge run W-01.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Consumers tab rows (account, class, plan, services) | S31.2 | prototype-extracted + BR-CUS-055 | read-model over `accounts` + snapshot (`account_plan_assignments`) via service fn (B1) | rows | computed-display | class from status lookup seed (OQ-064) |  ⚠ **`account_plan_assignments` is SUPERSEDED (PO 2026-08-11)** — no account-side plan table is built; the plan lives once on `units.rate_plan_id` and the account derives it. See BR-CUS-029.
| Reads completeness / flag sub-tabs | S31.2 | prototype-extracted + BR-MET-049 | read-model over `meter_reads` (channel set) via service fn | rows/% | computed-display | read-less services excluded |
| Prior balance + late-fee candidate | S31.2 Balances | BR-BIL-001/002/008 | computed: overdue portion from open invoices/buckets; candidate never written until applied | numeric(18,6) USD | computed-display | §7 formula; grace mode per tenant `late_grace_mode` |
| Grace mode + days settings | S66 | BR-BIL-002/008 | tenant settings `late_grace_mode` (calendar\|business) + `late_grace_days` (B4 schema note) | enum/int | reference-data | seeded: calendar, 5; range 0–30 |
| Unallocated credits | S31.2 Credits | BR-PAY-010 | read-model over payments/credits via service fn | numeric(18,6) USD | computed-display | allocation-order preview |
| Overcharge flag | S31.2 Overcharges | BR-BIL-029 | computed: draft total vs trailing average × tenant `overcharge_guardrail_pct` (r10 #6) | % | computed-display | default 200%, tenant-set |
| Guardrail % setting | S66 | BR-BIL-021/029 | tenant billing settings `overcharge_guardrail_pct` (r10 #6) | numeric | reference-data | seeded 200 |
| Base-only cohort + opt-in state | S31.2 Consumers | BR-BIL-061 | count = read-model over `accounts` by status class (BR-CUS-055); the CHOICE = `bill_run_decisions` case `base_only_billing`, choice include\|exclude | rows + enum | user-input | no default; required before step 3; recorded with actor + when |
| No-prior-read first bill | S31.2 Reads/Consumers | BR-BIL-062 · OQ-102 | flagged on the assembly as `first_bill_no_read`; drives `invoices.bill_type` = `first` (r10 #12) at draft; never a Missing-read row | flag | system-derived | account has no read of any kind before the period; minimum + proration from tenant config, never a constant |
| Consumption per service (unit-carrying) | S31.2 | model §2 · CLAUDE.md #3 | read-model over `meter_reads` — the SAME quantities phase 4 aggregates (BR-BIL-056) | numeric(18,6) + unit | computed-display | unit always explicit; never re-measured downstream |
| KPI strip | S31.2 | prototype-extracted | computed over the six tabs | counts/$ | computed-display | totals tie to tabs |

**6 · Acceptance**
- Given a created run, Then all six tabs render with counts that tie to the KPI strip, and every missing input appears as an exception in its tab — never a silent skip.
- Given the WE-15 fixtures, Then late-fee candidates equal §7 exactly, computed on the overdue portion only, honoring the tenant's calendar/business grace mode.
- Given a draft above the tenant guardrail %, Then it is flagged in Overcharges before issue; changing the tenant % changes the flag set.
- Given a Vacation hold starting mid-cycle, Then the preview classes the account base-only from the hold date per BR-BIL-028.
- Given the base-only cohort, Then the run cannot proceed on the status class alone — a staff opt-in/opt-out is shown, taken and recorded with who and when (BR-BIL-061).
- Given an account with no prior read of any kind, Then it is never a Missing-read row and never gets an estimated read; it prices at the plan's configured minimum for its category, prorated on calendar days, with no usage line (BR-BIL-062).

**7 · Finance Calculation** — CONFIRMED (BR-BIL-001/002/008 + BR-BIL-029; workbook figures verbatim).
`late_fee_candidate = max(5.00, 0.015 × overdue_portion)`, grace from due date (tenant days/mode). Worked (WE-15): (a) 400 → **6.00** · (b) 45 → **5.00** · (c) overdue portion 47.87 → **5.00** · (d) due Jul 20 + 5 cal → applies from Jul 26 · (e) business-days mode (BR-BIL-002), due Fri Jul 17 → from Jul 24 · (f) waiver manual only (BR-BIL-003).
`overcharge_flag = draft_total > (guardrail_pct ÷ 100) × trailing_average` — fixture 312% > 200% → flag.
Vacation-hold split (WE-12): TOU 13.20 + 13.30 + 14.40 · water 12.40 · sewer 4.96 · full-month bases 12 + 8 + 18 → taxable **96.26** → tax **9.10** → total **105.36**. GT ref: **GT-8**.

**8 · Open Questions** — None.

---
id: US-BIL-003
epic: EP-BIL-01
module: billing
screens: [S31.3]
wave: 3
status: draft
blocked_by: []
depends_on: [US-BIL-002, US-MET-014, US-MET-015]
journeys: [J2, J24]
rules: [BR-BIL-003, BR-BIL-006, BR-BIL-007, BR-BIL-015, BR-BIL-060, BR-BIL-061]
golden_tests: [GT-9]
finance_calc: confirmed
---
### US-BIL-003 — Step 3 exceptions: per-case tables, bulk actions, the missing-service choice

**1 · Details** — As a Billing Clerk, I want every account that needs a decision grouped in per-case tables with bulk actions (S31.3 — prototype categories: used-a-lot-more, no usage, estimated, owes-a-lot, way past due, late fee due, extra charges), and for an account missing a read on ONE service I want an explicit per-case choice — **estimate / hold account / bill without the service** — so that no exception resolves silently (BR-BIL-015). Estimate prices per the tenant estimation defaults (BR-BIL-006, engine = US-MET-014); **hold** sends the account to the Pending-billing queue (US-BIL-006); **bill-without-service** issues the other services and leaves the missing one for a catch-up sub-run. Late-fee rows apply/waive per case — first-time waiver is always a manual staff decision (BR-BIL-003); extra-charge rows come from tenant charge codes only (BR-BIL-007). Entry: US-BIL-002 continue. Exit: step 4 drafts (US-BIL-004); "Accept everything & continue" applies the defaults shown per row.

**Bulk is not a convenience here; it is the difference between a usable step and an unusable one (BR-BIL-060).** PO 2026-08-11, verbatim: *"if there are 500 or 1000 or 5000 bills to be generated and 1000 bills has late fees, it is impossible for user to do this manually account by account; its time consuming."* So EVERY case table on this step carries a bulk action over the current selection — apply/waive late fees, estimate, hold, bill-without-service, add a charge code, include/exclude the base-only cohort (BR-BIL-061) — with the selection count and, where money is involved, the selection total shown before the click. **Both halves of a bulk action have to survive in the record.** Each account still gets its OWN `bill_run_decisions` row, because that account's bill changed and a dispute months later is about that one account; the rows produced by one click share a `bulk_action_id`, which answers the different question — *was this considered individually, or was it one of a thousand?* One row cannot carry both facts, so there are N rows and one id.

**"All the decisions are made on screen and recorded" (PO 2026-08-11) is this step's contract.** Every choice on S31.3 writes a decision row with case, choice, reason where the rule demands one (a waiver always does, BR-BIL-003), the amount or quantity it was worth with its unit, and who decided. Changing one's mind appends a NEW row pointing at the one it supersedes — the trail is evidence, and evidence that can be edited is not evidence. Phase 1 ends when no case table has an unresolved row.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-015 | Missing-service read at run time: per-case staff choice (estimate / hold account / bill-without-service); held accounts enter the Pending-billing queue and are billed via catch-up SUB-RUNS. | CONFIRMED — PO A-6 option (a) + process, 2026-08-08 |
| BR-BIL-006 | Estimation = trailing-3-cycle daily average × period days; true-up by register arithmetic at next actual, current-period rates (defaults tenant-changeable per BR-MET-026/027). | CONFIRMED — A10 · OQ-003 CLOSED (PO R6) |
| BR-BIL-003 | First-time late-fee waiver is a manual staff decision, never automatic. | CONFIRMED — B4 §Late fee |
| BR-BIL-007 | NSF/reconnect/etc. are tenant-configured charge codes, never hardcoded (UI $30/$45 are samples). | CONFIRMED — B4 §NSF |
| BR-BIL-060 | Every per-case table carries a BULK action over the selection; one click writes N per-account decision rows sharing one `bulk_action_id`; selection count (and money total where applicable) shown before the click. | CONFIRMED — PO 2026-08-11 (*"impossible for user to do this manually account by account"*) |
| BR-BIL-061 | Base-only billing is a recorded staff opt-in/opt-out; it appears here as a bulk-able decision like any other, not as a status-class consequence. | CONFIRMED — PO 2026-08-11 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | ACC-1201 missing its gas read; electric+water present | Row offers exactly three dispositions (BR-BIL-015); default none pre-committed |
| TC-2 | Disposition = Estimate | Estimated read row created via the metering estimation service (US-MET-014 contract), labeled estimated; draft prices it — gas 42 ccf × 1.15 = **$48.30** line labeled "estimated" (WE-13) |
| TC-3 | Disposition = Hold account | ACC-1201 excluded from drafts, lands in the Pending-billing queue with reason "gas read missing", age 0 (US-BIL-006); the rest of the run proceeds |
| TC-4 | Disposition = Bill without the service | Draft carries electric+water lines only; the gas gap is recorded on the run for catch-up scope — never silently forgotten |
| TC-5 | Late-fee tab: ACC-3015 first-time late | Staff picks "Waive (first-time)" per case → no fee line, waiver audited; bulk "Apply all" never auto-waives (BR-BIL-003) |
| TC-6 *(negative)* | Staff tries to add a free-typed amount in the extra-charges tab | Impossible — rows reference tenant charge codes only (BR-BIL-007/020); no free-amount input exists |
| TC-7 *(negative)* | Continue with an unresolved missing-service row and no disposition | Step blocks listing the unresolved rows — an exception cannot pass unresolved (model §2/§6) |
| TC-8 *(isolation)* | Lone Star Ridge exceptions | Only its own accounts/charge codes; Brazos Bend TAMPER/CONN codes invisible |
| TC-9 *(bulk — the scale the PO named)* | Late-fee tab lists the run's candidates; Priya selects all and clicks "Apply late fee" once | Exactly one row per selected account in `bill_run_decisions` (case `late_fee`, choice `apply`, decided_by Priya), **all sharing one `bulk_action_id`**; the confirm dialog showed the selection count and the total fee before the click; one query returns "the accounts this bulk action touched" (BR-BIL-060) |
| TC-10 *(bulk never launders a manual-only rule)* | Same selection, clerk chooses bulk "Waive" | Refused for the first-time-waiver path — a waiver is a per-case manual decision with a reason (BR-BIL-003); bulk APPLY is allowed, bulk WAIVE is not, and the screen says which and why |
| TC-11 *(one click, N rows, both facts kept)* | ACC-3015's bill is disputed two months later | Its own decision row answers "what was decided, by whom, when, for how much"; its `bulk_action_id` answers "was this considered individually or was it one of a thousand" — neither fact is inferred from the other |
| TC-12 *(changing your mind is an append)* | Priya applies a fee to ACC-3015 in bulk, then waives it individually with a reason | Two rows: the bulk row now carries `superseded_by` → the waiver row; the original is NOT updated or deleted; the current decision is a query, not a guess; both are audited |
| TC-13 | Base-only cohort decided in bulk (include) | One decision row per base-only account, case `base_only_billing`, choice `include`, one shared `bulk_action_id` (BR-BIL-061/060); the drafts phase bills base charges only for those accounts per BR-CUS-055 |

**4 · Test Data** — Run 07-A. ACC-1201 (Residential Standard + Gas add-on): gas read missing, trailing-3 gas history → estimate 42 ccf (WE-13); electric/water reads committed. Late-fee tab per US-BIL-002 §4 fixtures; ACC-3015 first-time late. Extra charges: ACC-1310 NSF $30.00, ACC-1288 RECONN $45.00 (Brazos Bend charge codes, workbook §1). **Bulk fixture (BR-BIL-060):** the run's late-fee candidate set selected in one action — candidate count and Σ fee **engine-computed** from the WE-15 rule over the fixture's overdue accounts (00-e2e-design.md §5), never a constant typed here; the PO's stated scale is *"500 or 1000 or 5000 bills… 1000 bills has late fees"*, which is the volume the screen must survive, not a fixture figure. Base-only bulk fixture: ACC-1077 + ACC-1602. Actors: Priya Menon; approver n/a (no money writes at this step). Isolation: Lone Star Ridge, code set LATE/NSF only.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Case tables + counts | S31.3 | prototype-extracted (7 case categories) | computed over run assembly | rows | computed-display | categories per prototype; counts tie to S31.2 |
| Missing-service disposition | S31.3 | BR-BIL-015 | run exception record: chosen action + actor + when (r10 #7 run scope/exclusions) | enum(estimate\|hold\|bill_without) | user-input | required before continue |
| Estimate trigger | S31.3 | BR-BIL-006 | via metering estimation service (B1 — metering writes the read) | — | user-input | labeled estimated; cap per BR-MET-027 |
| Hold → queue entry | S31.3 | BR-BIL-015 | Pending-billing queue row (US-BIL-006 target) | row | system-derived | reason + age tracked |
| Late-fee apply/waive | S31.3 | BR-BIL-001/003 | applied → draft fee line (LATE charge code); waived → audited waiver, no line | enum | user-input | waiver manual, per case |
| Extra-charge rows | S31.3 | BR-BIL-007 | pending `charges`-referenced draft lines (`invoice_lines.charge_id`) | uuid + amount | reference-data | tenant charge codes only |
| Decision record (every choice on this step) | S31.3 | BR-BIL-015/003/007 + PO 2026-08-11 | `bill_run_decisions` (run, account, service, case, choice, reason, amount+unit, decided_by, created_at) | row | user-input | append-only; reason REQUIRED where the rule demands it (waiver, BR-BIL-003) |
| Bulk actions | S31.3 | prototype-extracted + IS-6 + BR-BIL-060 | same writes as per-row, batched — N rows, never one summary row | — | user-input | selection count + $ total shown before the click |
| `bulk_action_id` | S31.3 | BR-BIL-060 | `bill_run_decisions.bulk_action_id` — one uuid across the rows one click produced | uuid | system-derived | NULL = decided on that account alone; never reused across clicks |
| Supersede link | S31.3 | PO 2026-08-11 (*"recorded"*) | `bill_run_decisions.superseded_by` → self | uuid | system-derived | a changed mind APPENDS; the original row is never updated or deleted |
| Base-only opt-in/opt-out | S31.3 (+ shown S31.2) | BR-BIL-061 | `bill_run_decisions` case `base_only_billing`, choice include\|exclude | enum | user-input | no default; bulk-able; required before phase 2 |

**6 · Acceptance**
- Given a missing-service account, Then exactly the three BR-BIL-015 dispositions are offered and the run cannot continue while any such row is unresolved.
- Given Estimate, Then the read is created by the metering service, labeled, and priced per WE-13; given Hold, the account enters the queue; given Bill-without, the gap is recorded for catch-up.
- Given late-fee rows, Then apply/waive is per-case, waivers are audited, and nothing waives automatically.
- Given extra charges, Then only tenant charge codes can produce lines.
- Given any case table, Then a bulk action exists over the selection, shows its count and money total first, and writes one decision row PER ACCOUNT sharing one `bulk_action_id` (BR-BIL-060) — with bulk waive still refused, because a waiver is manual (BR-BIL-003).
- Given a reversed decision, Then a new row supersedes the old and neither is edited or removed.

**7 · Finance Calculation** — CONFIRMED (BR-BIL-006, workbook verbatim): estimate qty = trailing-3 daily avg × period days (quantity from US-MET-014); priced at current rates. Worked (WE-13): gas estimate 42 ccf × $1.15 = **$48.30**, line labeled "estimated"; next actual shows 95 ccf across 2 months → true-up qty 95 − 42 = **53 ccf** billed at the then-current period's rates = **$60.95** — register arithmetic, no reversal of the July bill. GT ref: **GT-9**.

**8 · Open Questions** — None.

---
id: US-BIL-004
epic: EP-BIL-01
module: billing
screens: [S31]
wave: 3
status: draft
blocked_by: []
depends_on: [US-BIL-002, US-BIL-003, US-RAT-008, US-RAT-012, US-RAT-013]
journeys: [J2, J24]
rules: [BR-BIL-004, BR-BIL-023, BR-BIL-029, BR-BIL-051, BR-BIL-052, BR-BIL-053, BR-BIL-054, BR-BIL-055]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-004 — Calculate in the background, show the breaks, then the draft bills with the confirmed draft powers (exclude · re-rate · add charge line — never edit computed)

**1 · Details** — As a Billing Clerk, I want full draft bills per account — every line, KPI totals, overcharge flags carried from step 2 — with exactly three powers (BR-BIL-023): **exclude an account** (reason required, recorded in `bill_run_exclusions`), **re-rate after a fix** (e.g. a read was corrected — the draft recomputes through the engine), and **add a charge-code line**; computed amounts are NEVER hand-editable, and drafts are discardable free — immutability starts at issue (BR-BIL-004). So that I can fix real problems without ever typing money. Entry: S31 step 4 (prototype "See the totals" + sample bill preview). Exit: step 5 confirm → issue (US-BIL-005), all-remaining or a selected subset (BR-BIL-023).

**Phase 2 — the calculation is a BACKGROUND BATCH (BR-BIL-051).** PO 2026-08-11, verbatim: *"once all billing data exceptions, decisions are made, then run the billing in batch process in background"*. Continuing from step 3 SUBMITS the run; it does not hold the clerk at the screen while 1,124 accounts price. The run's `status` says it is calculating, the screen polls it and shows progress, and closing the browser does not lose or corrupt the work — a clerk who comes back re-enters at the phase the status names (BR-BIL-050). Per account the batch runs stages 1–6 (BR-BIL-037); **stage 7 is not reached**, because nothing is issued in this phase: the batch's whole output is DRAFT invoices and lines, with no number, no GL stamp, no ledger effect and nothing immutable (BR-BIL-004). The batch is per-account restartable and idempotent within a run, so a partial completion is resumable rather than restartable-from-zero (BR-BIL-052).

**Phase 3 — the breaks, immediately, with the reason and two ways out (BR-BIL-053).** PO, verbatim: *"once billing is complete show immediately bills that are break and why; allow user to retry immediately by fixing the issue or mark for later"*. The moment the batch finishes, and BEFORE the totals, the step shows every account that did not produce a draft: the account, the stage that failed and the staff-readable reason it carries (BR-BIL-040 — a stage failure names its stage). Two actions per row, and bulk over the selection (BR-BIL-060): **fix and retry now**, which re-runs stages 1–6 for that account alone and moves it into the draft set if it succeeds; or **mark for later**, which writes a `bill_run_exclusions` row so the account lands in the Pending-billing queue for a catch-up sub-run (US-BIL-006, BR-BIL-034). **A break never blocks the run (BR-BIL-055):** PO answer 1 to the partial-run question — issue the clean ones, hold the rest. The rest of the batch is unaffected by any one account's failure, and no partial bill is ever created for a broken one (BR-BIL-040).

**Post-calculation exceptions live here too, not before the calculation (BR-BIL-054).** PO on the unexpectedly-large bill, verbatim: *"this is an exception, mark it and show exception high consumption cases, after billing process and let user take the action on it; you have to show this list and required actions"*. The over-guardrail draft (BR-BIL-029) is therefore surfaced in this phase as an exception list with its required actions — release it knowingly, exclude it, or send it back for a read check — rather than as a pre-block that stops the batch. **This refines WHERE BR-BIL-029 surfaces, not WHAT it computes:** the guardrail arithmetic, its tenant % and its "flagged before issue" guarantee are unchanged. The S31.2 Overcharges tab still previews the candidates from the assembled inputs; the flag on a real calculated draft is a phase-3 exception carrying actions.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-023 | Draft powers: exclude account (reason required) · re-rate after a fix · add charge-code line; computed amounts NEVER hand-editable; issue = all remaining or selected subset. | CONFIRMED — PO Lane B-4, 2026-08-08 |
| BR-BIL-004 | Issued invoices/lines are immutable; drafts are free to discard — nothing money-bearing exists until issue. | CONFIRMED — B2 §billing, CLAUDE.md #4 |
| BR-BIL-029 | Overcharge flags remain visible on flagged drafts until resolved or knowingly issued. | CONFIRMED — PO Lane B-10, 2026-08-08 |
| BR-BIL-051 | The calculation runs as a BACKGROUND BATCH: continuing from step 3 submits it, the clerk is not held at the screen, the run's status carries progress, and stage 7 is not reached — nothing money-bearing exists when the batch ends. | CONFIRMED — PO 2026-08-11 (*"run the billing in batch process in background"*) |
| BR-BIL-052 | Batch mechanics: per-account, restartable and idempotent within the run; a partial completion is resumable; one account's failure never rolls back another's draft. | PROPOSED — derived from BR-BIL-051 + BR-BIL-005 + BR-BIL-039 purity (re-rate replays with no cleanup) |
| BR-BIL-053 | The BREAKS list is shown the moment the batch finishes and before the totals: account · failing stage · staff-readable reason · two actions (fix-and-retry now / mark for later), bulk-able. | CONFIRMED — PO 2026-08-11 (*"show immediately bills that are break and why…retry immediately by fixing the issue or mark for later"*) |
| BR-BIL-054 | Post-calculation exceptions (the over-guardrail draft) are surfaced AFTER calculation with their required actions — never a pre-block. Refines where BR-BIL-029 surfaces; its arithmetic and guarantee are unchanged. | CONFIRMED — PO 2026-08-11 (*"this is an exception…after billing process…show this list and required actions"*) |
| BR-BIL-055 | A partial run ISSUES the clean bills and HOLDS the rest in the Pending-billing queue for a catch-up sub-run; a break never blocks the run. | CONFIRMED — PO 2026-08-11 answer 1 (partial run → A) · consistent with BR-BIL-015/034 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Run WE-1 fixture (ACC-1042) through to drafts | Draft shows **15 lines**, current charges **$247.87**, total due **$292.87** (WE-1); KPI totals include it |
| TC-2 | Exclude ACC-3020 (overcharge under investigation) | Reason required; `bill_run_exclusions` row (account, reason, who/when); KPI counts drop by one; draft discarded free |
| TC-3 | Gas read on ACC-1201 corrected in metering; clerk hits Re-rate | Draft recomputes through the rating engine; new totals replace old; no hand edit anywhere |
| TC-4 | Add charge-code line RECONN $45.00 to ACC-1288's draft | Line references the charge code (own GL); amount comes from the code definition, not typing |
| TC-5 *(negative)* | Attempt to edit a computed line amount (API PATCH on a draft usage line) | Rejected — computed amounts are never hand-editable (BR-BIL-023); only the three powers mutate drafts |
| TC-6 *(negative)* | Discard the whole draft set, then re-enter step 4 | Drafts regenerate from the same run; no invoice/ledger/audit-money artifacts existed from the discarded set (BR-BIL-004) |
| TC-7 *(isolation)* | Lone Star Ridge drafts | Its exclusions/lines write only its rows; Brazos Bend drafts invisible (RLS) |
| TC-8 *(phase 2 — background)* | Priya continues from step 3 on run 07-A and immediately closes the browser | The batch keeps running; `bill_runs.status` reports calculating with progress; re-opening the run from S30 shows the same run at the phase it reached — no second batch is started and no draft is duplicated (BR-BIL-051/052) |
| TC-9 *(phase 2 — nothing money-bearing)* | Inspect the database the instant the batch completes | Draft `invoices` + `invoice_lines` only: `invoice_no` NULL, `gl_account_id` NULL, `issued_at` NULL, zero `journal_lines`, zero delivery rows. Stage 7 was never reached (BR-BIL-051, BR-BIL-004) |
| TC-10 *(phase 2 — resumable, not restartable-from-zero)* | The batch is killed after 400 of 1,124 accounts and resumed | The 400 drafts are kept and not recomputed twice; the remaining 724 complete; totals equal a clean run's totals to the digit (BR-BIL-052) |
| TC-11 *(phase 3 — the break list)* | Batch completes; 3 accounts produced no draft | The step shows them BEFORE the totals: account, the failing STAGE by name, and the staff-readable reason (BR-BIL-040/053). No partial invoice exists for any of the three |
| TC-12 *(phase 3 — fix and retry now)* | ACC-1201's read is corrected in metering; Priya clicks Retry on its break row | Stages 1–6 re-run for that account ALONE; it joins the draft set; the other drafts are untouched; the break row closes with its resolution recorded |
| TC-13 *(phase 3 — mark for later, and the run still issues)* | Priya marks the remaining 2 breaks "for later" and continues | Two `bill_run_exclusions` rows → Pending-billing queue (US-BIL-006); the run proceeds to phase 4 with 1,122 drafts — the clean bills issue, the held ones wait for a catch-up sub-run (BR-BIL-055) |
| TC-14 *(phase 3 — the big bill is an exception, not a gate)* | ACC-3020's calculated draft lands at 312% of trailing average | The batch does NOT stop and the draft DOES exist; it appears in the phase-3 exception list with its required actions (release knowingly · exclude · send back for a read check) and the flag stays visible on the draft until one is taken (BR-BIL-054, BR-BIL-029 unchanged) |
| TC-15 *(negative — a break is never a silent skip)* | An account fails stage 2 and nobody acts on its break row | Phase 4 cannot be entered with unresolved break rows; the run names them. There is no path in which an account silently produces no bill and no queue row (BR-BIL-053, model §2) |
| TC-16 *(phase 3 — 2026-08-12, OQ-146: a tax authority with no liability account)* | A **$117** bill's tax cannot post anywhere because the authority the tenant added has no 2200-series account | The **RUN REPORTS IT** as a break naming the authority (PO 2026-08-12, *"let the run report it"*) and **the other accounts in the run continue** — the tenant is NOT blocked at configuration time from adding the authority, because that would stop a utility part-way through setting itself up. The bill itself still does not issue (BR-BIL-010's atomic stamp), which is what makes this a break row rather than a silent mis-post |

**4 · Test Data** — Run 07-A drafts: ACC-1042 = WE-1 (15 lines, 247.87/292.87). ACC-3020 excluded, reason "overcharge 312% — investigating leak". ACC-1288 + RECONN $45.00. Vacation-hold draft ACC-1077 = WE-12 (total $105.36). Sample KPI strip: customers to bill 1,123 (after 1 exclusion). **Phase 2/3 fixtures:** batch of 1,124 accounts, killed after 400 and resumed (TC-10); three break rows — ACC-1201 (stage 2, gas read missing), ACC-1455 (stage 1, no plan in force at service date), ACC-1710 (stage 6, pinned template variable unresolvable) — ACC-1201 retried after the Aug 9 read correction, the other two marked for later → 2 queue rows and 1,122 drafts (TC-11..13). Post-calculation exception: ACC-3020 at 312% (US-BIL-002 §4 fixture) with its required actions. Actors: Priya Menon. Isolation: Lone Star Ridge run W-01 drafts.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Draft invoice + lines | S31 step 4 | model §6 step 4 | `invoices` (status draft) + `invoice_lines` — no GL stamp yet (stamp at issue, BR-BIL-010) | rows | system-derived (engine) | amounts rounded per B4.4 at finalization |
| Exclude action | S31 step 4 | BR-BIL-023 | `bill_run_exclusions` (account, reason, who/when — r10 #7) | row | user-input | reason required |
| Re-rate action | S31 step 4 | BR-BIL-023 | draft regeneration via rating engine call (B1) | — | user-input | audited |
| Added charge line | S31 step 4 | BR-BIL-023 + BR-BIL-007 | `invoice_lines.charge_id` → `charges` | uuid | reference-data | tenant charge codes only |
| Overcharge flag on draft | S31 step 4 | BR-BIL-029 | carried from step-2 computation | flag | computed-display | visible until resolved/issued |
| Batch progress | S31 step 4 (polled) | BR-BIL-051 | `bill_runs.status` + counts over the draft set (accounts done / total) — no separate progress table | enum + counts | system-derived | poll, never block; survives the browser closing |
| Break row (account · stage · reason) | S31 step 4, ahead of the totals | BR-BIL-053 · BR-BIL-040 | run exception rows (r10 #7 scope/exclusions family), carrying the failing stage name | rows | system-derived | never a silent skip; no partial invoice for a broken account |
| Break action: retry now | S31 step 4 | BR-BIL-053 | re-runs stages 1–6 for that account only; the break row closes with its resolution | — | user-input | audited; bulk-able (BR-BIL-060) |
| Break action: mark for later | S31 step 4 | BR-BIL-053 · BR-BIL-055 | `bill_run_exclusions` row → Pending-billing queue (US-BIL-006) | row | user-input | reason carried from the break; bulk-able |
| Post-calculation exception + required action | S31 step 4 | BR-BIL-054 | the flagged DRAFT + a `bill_run_decisions` row (case `overcharge`, choice release\|hold) | row | user-input | shown after calculation, never a pre-block; flag visible until acted on |
| KPI totals + sample preview | S31 step 4 | prototype-extracted | computed over drafts | $/counts | computed-display | ties to draft set |

**6 · Acceptance**
- Given the WE-1 fixture, Then the draft reproduces the workbook exactly (15 lines, 247.87, 292.87).
- Given the three powers, Then exclude requires a reason and writes the exclusions row, re-rate recomputes through the engine, add-line references a charge code — and no other mutation path exists.
- Given a discarded draft set, Then nothing money-bearing persists.
- Given issue, Then all-remaining or a selected subset proceeds (executed in US-BIL-005).
- Given the continue from step 3, Then the calculation is submitted as a background batch, the clerk is released from the screen, progress is readable from the run's status, and nothing money-bearing exists when it ends (BR-BIL-051).
- Given a killed batch, Then resuming completes the remainder without recomputing or duplicating what was already drafted, and the totals match a clean run (BR-BIL-052).
- Given accounts that produced no draft, Then they are listed with their failing stage and reason before the totals, each offering retry-now or mark-for-later, and the run still issues the clean bills (BR-BIL-053/055).
- Given an over-guardrail draft, Then it exists, it is listed as a post-calculation exception with required actions, and it never pre-blocked the batch (BR-BIL-054).

**7 · Finance Calculation** — CONFIRMED (engine math is rating's 🔒; billing asserts totals): draft total = Σ line amounts, each rounded half-up 2dp at finalization (B4.4). Worked (WE-1): taxable 221.90 → tax 20.97 → current **247.87** → + prior balance 45.00 = **292.87**. Vacation-hold draft (WE-12): **105.36**. Refs: BS-16 (draft powers), BS-1.

**8 · Open Questions** — None.

---
id: US-BIL-005
epic: EP-BIL-01
module: billing
screens: [S31, S30]
wave: 3
status: draft
blocked_by: []
depends_on: [US-BIL-004, US-BIL-007, US-BIL-009, US-BIL-021, US-TEN-012]
journeys: [J2, J5, J24]
rules: [BR-BIL-004, BR-BIL-010, BR-BIL-011, BR-BIL-016, BR-BIL-022, BR-BIL-024, BR-BIL-026, BR-BIL-056, BR-BIL-057, BR-BIL-058, BR-BIL-059]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-005 — Summary, release gate, then issue: freeze invoices, stamp GL + template, hand off posting, queue delivery

**1 · Details** — As a Billing Clerk (with the step-5 sign-off recorded), I want Issue to atomically per bill: **verify** the invoice number the DRAFT already carries (allocated at draft creation from the tenant series `BL-{YYMM}-{seq}` — BR-BIL-022 source/format, **BR-BIL-063** timing, PO ruling 2026-08-11; issue mints NOTHING and refuses a numberless draft — this sentence said "mint the invoice number" and contradicted §5's own field-map row), set due date (BR-BIL-024), freeze the invoice + lines as immutable (BR-BIL-004), stamp each line's GL account from the mapping (BR-BIL-010) and the template + version (BR-BIL-026), emit the balanced-posting handoff to the ledger posting service (BR-BIL-011 — billing writes NO journal lines. ⚠ **AMENDED 2026-08-11:** this read *"until W5 the call is stubbed at the boundary"* and it is no longer stubbed — `apps/billing/posting_seam.post_bill_issue` calls `apps.ledger.posting.post` INSIDE the issue transaction, so a bill and its journal entry commit together and a posting refusal leaves a discardable DRAFT), write one delivery record per bill per channel to the outbound queue (BR-BIL-016 — mass sends never synchronous), and write `audit_log` — so that the J2 step-8 contract holds: invoice status=issued, immutable, taxable flags set, due_date set. Issue covers all remaining drafts or a selected subset (BR-BIL-023). Entry: S31 step 5 confirm → step 6. Exit: S30 shows the issued bills; the run closes when all drafts are issued or excluded.

**Phase 4 — the summary the clerk actually approves (BR-BIL-056).** PO 2026-08-11, verbatim: *"then show the billing summary in how many accounts, how many bills generated, how much consumption and how much bill amount and various categories"*. The epic previously carried per-tab counts; this is one consolidated panel across the whole run, and it carries **consumption** — which no earlier count did. Four figures are named by the PO and are therefore required: **accounts** in the run · **bills** generated · **consumption**, per service, each with its explicit unit (CLAUDE.md #3 — never a bare number, and never summed across different units) · **bill amount**, with its currency (CLAUDE.md #2). Plus **category breakdowns** (BR-BIL-057 — the axes are derived, not yet ruled).

**⚠ REVERSED 2026-08-11 — THE SUMMARY SCREEN RECALCULATES LIVE (PO ruling, option B).** The paragraph above used to end with *"the summary is FROZEN as shown, not recomputed later … the authorisation was given against THESE figures"*. It is not frozen. Put to the PO in plain English with the worked figure — *"You approve 480 bills, $52,847.19. Two bills are voided next week. The screen still says 480 / $52,847.19, because that's what you approved"*, against **A** keep frozen · **B** recalculate live · **C** show both — **the PO chose B**. Re-opening the run after those two voids shows **478** and the smaller total. **Two things this does NOT change.** (1) The `bill_run_releases` row is still written at confirm and is still never rewritten: it is the append-only authorisation record and hard rule 4 forbids touching it. The ruling governs what the SCREEN DISPLAYS, not what is stored. (2) The four PO-named figures, their explicit units and currency, and the tie-out to the bills they are computed from all stand. **So the shape is: the ROW keeps what was shown at sign-off; the SCREEN shows the live figures — two true answers to two different questions.** The consequence a later reader must know: after this ruling the screen no longer answers *"what did I authorise?"*, and only the stored row does. ⚠ **Not settled:** the PO's example fixes the VOID case only; whether a correction's rebill (a new invoice, EP-BIL-04) joins the recalculated set was never asked, and must be surfaced rather than chosen (BR-BIL-056).

**Phase 4 — the release gate enumerates its confirmations (BR-BIL-058).** PO, verbatim: *"take final confirm from user, compliance confirmation, emails, text mandates, auto pay mandates and then release the bills"*. Not one undifferentiated tick: **compliance**, **email mandate**, **text/SMS mandate**, **autopay mandate** and the **final confirm** are each shown separately and each recorded separately, because a release that went out without the compliance check is a different event from one that did, and only separate facts can say which happened. Each is shown against the coverage it attests — how many accounts hold that mandate, and how many do not (BR-BIL-059). **A missing email address is normal, not an exception, and never blocks release** (BR-BIL-036: print is the primary channel and the floor). Release is REFUSED while any confirmation is untaken; the gate is the last point at which nothing has been billed.

**Phase 4 and phase 5 are TWO ENDPOINTS, and the split is what makes TC-13 possible (added 2026-08-15, DEF-116).** Until that date the wizard could reach a `201 draft` run and stop: neither route existed, and its own step-5 and step-6 panels named what was missing by rule and by path. Both are mounted now. **`POST /billing/runs/{id}/release`** is phase 4 — it records BR-BIL-058's five confirmations with who and when, writes one `bill_run_releases` row, and **issues nothing**. **`POST /billing/runs/{id}/issue`** is phase 5 — it issues every remaining draft and stamps `released_at` only once that pass returns. **Why not one call:** a crash between the two leaves exactly the authorised-but-unreleased state TC-13 requires a resume to CONTINUE rather than re-authorise, and that state can only exist because they are two events. **Both are idempotent and the rules differ:** a repeated Confirm returns the authorisation that already exists (a second row would be a second signature for one act, and the table is append-only); a repeated Send returns the release already stamped, while `issue_run` underneath it finds no remaining drafts. Issue with NO release row is refused — TC-14. **The event times are the CALLER's** (`confirmed_at`, `issued_at`, both required and both offset-bearing): BR-TEN-043 puts them there, and refusing to invent a time was never a reason not to accept one. **What the routes cannot do, and say so on every response:** one template pin serves the whole run where BR-BIL-025 resolves per account; the stored summary is the server's own recomputation at confirm time, not the payload the screen showed, so nothing binds a signature to figures that may have moved since the clerk read them; and the pass is INLINE, so the clerk IS held — the route answers 201 with the finished result rather than 11b's contracted 202, because a 202 would promise an asynchrony this deployment does not keep.

**Phase 5 — release runs in the background too (BR-BIL-051).** PO, verbatim: *"and then release the bills and run the batches in background for downstream jobs"*. Confirming does not hold the clerk while 1,122 bills mint numbers, stamp GL accounts, freeze, render and queue: it returns them to S30, where the run's status reports the release progressing, and the downstream jobs (document render + store, print batch, delivery queue, posting handoff) run as background batches. The `released_at` stamp closes the loop — a crash between the gate and the finish leaves an authorised-but-unreleased row, which a resume must recognise rather than asking for authorisation a second time.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-022 | Bill numbers from the tenant number series, default `BL-{YYMM}-{seq}`, format tenant-adjustable in Numbering settings. | CONFIRMED — PO Lane B-3, 2026-08-08 |
| BR-BIL-004 | No UPDATE/DELETE on issued invoices/lines ever — corrections are credit notes/rebills (EP-BIL-04). | CONFIRMED — B2 §billing, CLAUDE.md #4 |
| BR-BIL-010 | GL account resolved from the Finance mapping and stamped onto each line at issue — later mapping edits never re-map history. | CONFIRMED — PO Billing A-1 option (a), 2026-08-08 |
| BR-BIL-011 | One bill = one document + N GL-coded lines + one balanced JE (DR AR / CR per-GL buckets); posting service is the sole writer. | CONFIRMED — PO directive 2026-08-08 · B1/B2 |
| BR-BIL-026 | Template + version pinned on the bill at issue. | CONFIRMED — PO Lane B-7, 2026-08-08 |
| BR-BIL-016 | Issue writes one delivery record per bill per channel to the queue (dispatcher = US-BIL-023). | CONFIRMED — PO A-7, 2026-08-08 |
| BR-BIL-024 | Due date = bill date + cycle due-days. | CONFIRMED — PO Lane B-5, 2026-08-08 |
| BR-BIL-056 | The pre-release SUMMARY carries accounts · bills generated · consumption per service WITH its unit · bill amount with currency · category breakdowns. ⚠ The **"FROZEN as shown, never recomputed"** half is SUPERSEDED — **the screen RECALCULATES LIVE**; the `bill_run_releases` row is still written once at confirm and never rewritten (hard rule 4). | CONFIRMED (the figures) — PO 2026-08-11 (*"how many accounts, how many bills generated, how much consumption and how much bill amount and various categories"*) · **frozen half SUPERSEDED — PO 2026-08-11, option B** (shown: *"You approve 480 bills, $52,847.19. Two bills are voided next week. The screen still says 480 / $52,847.19"* → live now reads 478) |
| BR-BIL-057 | The category axes of the summary. | PROPOSED — the PO said *"various categories"* without enumerating them; seed derived from what the run already knows (service · consumer category · bill type · status class · delivery channel · exception state). Needs a PO ruling before the axes are fixed |
| BR-BIL-058 | The release gate is FIVE separate facts — compliance · email mandate · text mandate · autopay mandate · final confirm — each shown and RECORDED separately; release is refused while any is untaken. | CONFIRMED — PO 2026-08-11 (*"take final confirm from user, compliance confirmation, emails, text mandates, auto pay mandates"*) |
| BR-BIL-059 | Each confirmation is shown against its coverage count, and a missing email/SMS mandate never blocks release — print is the floor (BR-BIL-036). | PROPOSED — derived from BR-BIL-058 + BR-BIL-036 (*"an account with NO email address is normal, not an exception"*) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Issue the WE-1 draft (ACC-1042) | The `BL-2608-018410`-pattern number the draft already carried is UNCHANGED by issue (BR-BIL-063); status issued; due date = bill date + 21; 15 immutable lines each with `gl_account_id` stamped; `template_id`+`template_version` pinned; posting handoff = §7 exactly; one delivery record per channel queued; `audit_log` `invoice.issued` |
| TC-2 | Issue a selected subset (100 of 1,123) | Exactly those 100 issue; the rest stay draft; run remains open for the remainder (BR-BIL-023) |
| TC-3 | Mapping edited AFTER issue (4100 → 4101 for Electric) | Already-issued lines keep 4100 forever; only future issues stamp 4101 (BR-BIL-010) |
| TC-4 | Posting handoff consumed (W5) | One balanced JE per bill: DR AR = current charges; CR per-GL buckets sum from lines; J5 trial balance ties |
| TC-5 *(negative)* | UPDATE/DELETE attempted on an issued invoice or line; a billing code path attempts to INSERT `journal_lines` | Both rejected — immutability triggers (B2 §3) + sole-writer boundary (CLAUDE.md #5); audit intact |
| TC-6 *(negative)* | Issue re-triggered for the same drafts (double-click/retry) | Idempotent — no duplicate invoices/numbers/queue rows (run-scoped guard 🔒 Eng-Lead) |
| TC-7 *(isolation)* | Lone Star Ridge issue | Its number series, mapping, queue rows only; a Brazos Bend draft id in the request 404s (RLS) |
| TC-8 *(phase 4 — the summary)* | Run 07-A reaches the gate with 1,122 drafts | One panel shows: accounts in the run · bills generated · **consumption per service, each with its unit** (electric kWh, water kgal, gas ccf — never summed across units) · bill amount with currency · the category breakdowns. Every figure TIES to the draft set: amount = Σ draft totals, consumption per service = Σ the same measured quantities S31.2 showed (BR-BIL-056) |
| TC-9 *(phase 4 — the screen recalculates, the record does not)* | Confirm the gate at 480 bills / $52,847.19; two months later one bill is corrected and another voided; re-open the run from S30 | **Two assertions, and they differ on purpose.** (a) The SCREEN shows the LIVE figures: the voided bill leaves the set, so the panel reads **479** and the correspondingly smaller total — the PO ruled option B on 2026-08-11. (b) The `bill_run_releases` ROW still reads **480 / $52,847.19**, unchanged and unrewritten: it is the append-only authorisation record and is now the ONLY answer to "what did I authorise" (BR-BIL-056 · hard rule 4). ⚠ **AMENDED 2026-08-11 — that edge is RULED and this TC must now say so.** It read "whether its rebill joins the recalculated set is the unruled edge named in BR-BIL-056"; the PO closed OQ-111 the same day: *"A Replacement counts (panel = what these customers owe now)"* (BR-BIL-064). So the CORRECTED bill is not left out — the panel must show it at its REPLACEMENT's current figure, which on the PO's own worked case is **$104.20** where the run issued **$117.01**. ~~**Unbuildable today and therefore asserted as a REFUSAL, not as a figure:** no column reaches the rebill (`invoices.corrects_invoice_id` does not exist — EP-BIL-04 §5; OQ-120), so `apps/billing/release.summary_for` raises a `BillingRuleError` naming that column for any run holding a corrected bill, and assertion (a) above therefore holds only for a run whose corrections are absent.~~ ⚠ **AMENDED 2026-08-12 — THE SHAPE IS RULED (OQ-120 CLOSED): the link is carried on the NEW bill.** PO verbatim: *"Nod to add the link on the new bill"* — the replacement points back at what it replaces, because the original is immutable and must not gain a column after issue (BR-BIL-004). So the refusal above is now a SCHEMA gap, not an unruled edge: the column is still unbuilt, and when it lands it lands on the rebill. The half that IS built: a REBILL carrying this run's `bill_run` counts like any other bill. ~~A credit note with no replacement (class C) is a separate unruled case, OQ-121~~ ⚠ **RULED 2026-08-12 (OQ-121 CLOSED): *"no rebill , Count it like a replacement"*** — a class-C credit note with **no** replacement bill still moves this panel; on GT-6's shape a **$247.30** invoice with a **$25.00** goodwill credit shows **$222.30** as **1 bill, 1 account**, with GROSS and CREDIT travelling beside the net (BR-BIL-064) |
| TC-10 *(phase 4 — the gate is five facts)* | Priya ticks compliance, email and autopay but not the text mandate, and presses release | Refused, naming the untaken confirmation. Release proceeds only with all five; the stored record shows each as its own value, so "which ones did they confirm" is answerable — never one undifferentiated tick (BR-BIL-058) |
| TC-11 *(phase 4 — no email is normal)* | 68 of the 1,122 accounts have no email address | The email confirmation is shown against that coverage ("1,054 of 1,122"); the 68 do NOT block release, still bill, still render and still dispatch by print (BR-BIL-059, BR-BIL-036). The count is stored as it stood at confirm, not recounted later |
| TC-12 *(phase 5 — release is background)* | Priya confirms and immediately navigates to S30 | The release proceeds without her; the run's status reports progress; issue, document render, print batch, delivery queue and the posting handoff all run as background jobs; `released_at` is stamped when they finish (BR-BIL-051) |
| TC-13 *(negative — a crash between gate and finish)* | The process dies after the gate is recorded and before release completes | The release row exists with `released_at` NULL — authorised but not released. Resume continues the downstream jobs and does NOT ask for authorisation a second time; no bill is issued twice (BR-BIL-058, BR-BIL-005) |
| TC-14 *(negative — the gate cannot be bypassed)* | Forged POST straight to issue with no release record for the run | Refused — issue requires a recorded release with all five confirmations for the run and the scope being issued; no invoice is minted, no delivery row is written (BR-BIL-058) |
| TC-15 *(phase 4 — 2026-08-12, OQ-121)* | Run 07-A holds one class-C correction: a **$247.30** bill with a **$25.00** goodwill credit and NO rebill | The panel counts it **like a replacement** at **$222.30** — 1 bill, 1 account — so a corrected account is not invisible to the person signing off. The credit-note column is read as a **MAGNITUDE per row** with the direction applied once: a signed sum reads **$272.30**, which is DEF-085 |
| TC-16 *(negative — 2026-08-12, OQ-152: a GL bucket below zero)* | A draft whose lines make one GL bucket sum BELOW ZERO reaches issue (reachable today: a discount is a negative charge rule, BR-RAT-045/OQ-055) | **The bill REFUSES to issue** (PO 2026-08-12, *"refuse the bill"*). It does **not** post a debit of the absolute value to the other side: a negative bucket means the bill's own lines contradict each other, and issuing it would put a figure in the books that no line explains. It surfaces as a phase-3 break row like any other stage failure (BR-BIL-040/053), so the rest of the run issues |
| TC-17 *(the two routes exist — DEF-116, 2026-08-15)* | A clerk drives S31 to step 5, confirms all five, and presses Send | `POST /billing/runs/{id}/release` answers **201** with the authorisation row (`released_at` null — nothing is billed yet) and `POST /billing/runs/{id}/issue` answers **201** with the drafts issued and `released_at` stamped. **Both paths are asserted REACHABLE through the real root URLconf AND over real HTTP**, where 401 means the route exists and asked for a session: a 404 is what both answered until this date, and is what the wizard was rendering *"no endpoint is contracted"* from |
| TC-18 *(idempotency — a double-clicked Confirm and a double-clicked Send)* | Press Confirm twice, then Send twice | Confirm answers **200 `created:false`** the second time with the SAME release id and **one** `bill_run_releases` row exists — a second row would be a second signature for one act. Send answers **200 `created:false`** the second time, **one** invoice exists, and its `issued_at` has NOT moved even though the second call named a different moment: the stamp is on an immutable row (CLAUDE.md rule 6, hard rule 4) |
| TC-19 *(negative — a naive event time)* | Send with `issued_at: "2026-07-03T09:41"` (no offset) | **422 VAL-002 naming `issued_at`.** That string is a different instant in Houston than in Chennai and it lands on an immutable row; it is refused rather than assumed UTC (BR-TEN-043, BR-TEN-020) |
| TC-20 *(the bill prints its total — BR-BIL-035, DEF-116)* | An account with one unpaid **45.00** bill is billed **247.87** and the run is released | The issued bill's locked instance carries previous balance **45.00**, payments & credits **0.00**, current charges **247.87** and total due **292.87**, and all four PRINT on the rendered document — asserted on the page, not only in the payload, because a stamp the renderer cannot read still leaves the customer holding a dash. The OQ-117 run problem is gone for that bill |
| TC-21 *(negative — the arrears cannot be read)* | The same run on a deployment where payments publishes nothing | Previous balance, payments & credits and total due stamp as **NULL** and the page prints `—`; the run reports the bill by name (OQ-117, *"issue and report it"*). **They are never 0.00**: zero says the customer owes nothing from before, and this bill would be telling somebody in arrears that they are square |

**4 · Test Data** — WE-1 issue: ACC-1042, current 247.87, prior 45.00, total due 292.87; number series `BL-{YYMM}-{seq}` → `BL-2608-018410` (B2 sample format); bill date Aug 1 → due Aug 22, 2026. GL stamps per WE-1: 4100/4105/4110/4115/4120/4130/4150/2200–2203/4200; AR 1200. Channels queued: pdf_print (v1) + email (record written, dispatch deferred W6 per OQ-073). Subset fixture: 100 selected. **Phase 4/5 fixtures:** the gate for run 07-A after phase 3 — 1,122 drafts from 1,124 accounts (2 marked for later, US-BIL-004 §4); summary totals **engine-computed** from that draft set (00-e2e-design.md §5) — amount = Σ draft totals, consumption per service = Σ the measured quantities (WE-1's own account contributes electric 120 + 200 + 380 kWh and water 8 kgal), so no aggregate figure is fixed in this epic; mandate coverage fixture: **68 accounts with no email address**, the remainder emailable (BR-BIL-059/036). Actors: Priya Menon (ran), Alex Reed (sign-off). Isolation: Lone Star Ridge, series `LSR-{YYMM}-{seq}`.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Invoice number | S31/S30 | BR-BIL-022 (source/format) · **BR-BIL-063** (timing) | `invoices.invoice_no` (tenant `number_series`, BR-TEN-035) | text | system-derived | unique per tenant; **allocated when the DRAFT is created** (PO ruling 2026-08-11 — was "at issue only", which BR-BIL-022 never said); an unused number is lost |
| Status → issued + issued_at | S31 | BR-BIL-004 | `invoices.status`, `invoices.issued_at` | enum/ts | system-derived | one-way; immutable after |
| Due date | S31/S30 | BR-BIL-024 | `invoices.due_date` | date | system-derived | bill date + cycle due-days |
| GL stamp per line | — | BR-BIL-010 | `invoice_lines.gl_account_id` (r10 #1) | uuid | system-derived | resolved from mapping at issue; frozen |
| Template pin | — | BR-BIL-026 | `invoices.template_id` + `.template_version` (r10 #3) | uuid/int | system-derived | category default or account override (BR-BIL-025) |
| Bill type | — | r10 #12 | `invoices.bill_type` = `cycle` | enum | system-derived | cycle\|first\|final\|rebill\|backbill\|penalty |
| Posting handoff | — (service contract) | BR-BIL-011 | consumed by ledger posting service 🔒 (journal_entries source invoice) — billing writes none | rows | system-derived | balanced by construction: DR AR = Σ CR buckets |
| Delivery queue rows | — | BR-BIL-016 | outbound delivery queue (r10 #8): bill × channel, status queued | rows | system-derived | one per bill per channel |
| Summary (the STORED record — what was shown at sign-off) | S31 step 5 | BR-BIL-056 · hard rule 4 | `bill_run_releases.summary` jsonb — `{accounts, bills, consumption:[{service, quantity, unit}], amount, by_category:[…], delivery:{…}, autopay:{…}, compliance:[…]}` | jsonb | system-derived | written once at confirm; **never updated and never deleted** — an append-only authorisation record. It is NOT what the screen renders (see the next row) |
| Summary (the SCREEN — recalculated live) | S31 step 5 · S30 re-open | BR-BIL-056 (PO 2026-08-11, option B) | **no column — a query over the run's current bill set**; same shape as the stored payload | jsonb-shaped read model | computed-display | recomputed on every viewing: a voided bill leaves the figures. ⚠ **AMENDED 2026-08-11:** a correction's rebill DOES join the set (BR-BIL-064, PO ruling on OQ-111 — *"A Replacement counts (panel = what these customers owe now)"*), and the superseded original is shown at that replacement's figure. ⚠ **AMENDED 2026-08-12 (OQ-120 + OQ-121 CLOSED):** the chain link is carried **on the NEW bill** (*"Nod to add the link on the new bill"*) rather than as `invoices.corrects_invoice_id` on the original, and a **credit note with no rebill counts like a replacement** (*"no rebill , Count it like a replacement"* — GT-6's $222.30, 1 bill / 1 account). The column is still unbuilt, so the computation REFUSES for a run holding a corrected bill — a SCHEMA gap now, not an unruled edge. ~~**Built since 2026-08-11: `apps/billing/release.summary_for` computes this row; still no endpoint and no screen**~~ ⚠ **BOTH LANDED 2026-08-31 (DEF-2853).** `GET /billing/runs/{id}/summary` serves it and S31 steps 4 and 5 draw it — the four PO-named figures, the derivable category axes and BR-BIL-059's mandate coverage. The struck sentence is kept because a reader who greps for it must find out what happened to it. **The absence had stood for twenty days and both suites were green over it:** the backend tests called `summary_for` directly and the frontend test asserted the *"Not worked out"* placeholder, so the missing figures were ASSERTED GREEN |
| Summary headline figures (stored) | S31 step 5 | BR-BIL-056 | `bill_run_releases.account_count` · `.bill_count` · `.total_amount` numeric(18,6) · `.currency` CHAR(3) | int/numeric | system-derived | pulled out as columns so the auditor's question needs no JSON parse; ties to the draft set as it stood at confirm — and after the option-B ruling these columns are the ONLY answer to *"what did I authorise?"* |
| Consumption per service | S31 step 5 | BR-BIL-056 · CLAUDE.md #3 | inside `summary.consumption` (stored) and in the live read model | numeric + unit | computed-display | never a bare number; never summed across different units — in the stored row and on the recalculated screen alike |
| Category breakdowns | S31 step 5 | BR-BIL-057 | inside `summary.by_category` — tenant-shaped, which is why it is jsonb and not a column per category | jsonb | computed-display | **axes PROPOSED** — the PO said "various categories" without enumerating; a run built before the ruling stubs the axis set |
| Gate confirmations | S31 step 5 | BR-BIL-058 | `bill_run_releases.compliance_confirmed` · `.email_mandate_confirmed` · `.sms_mandate_confirmed` · `.autopay_mandate_confirmed` (+ the final confirm = the row's existence, with `confirmed_by` + `confirmed_at`) | bool ×4 | user-input | each its own fact; release refused while any is false |
| Mandate coverage counts | S31 step 5 | BR-BIL-059 | inside `summary.delivery` / `summary.autopay` — counts as they stood at confirm | counts | computed-display | a zero-email account never blocks release (BR-BIL-036) |
| Release completion | S30 | BR-BIL-051 | `bill_run_releases.released_at` — NULL = authorised but not yet released | ts | system-derived | a resume recognises NULL and never re-asks for authorisation |
| Issue audit | — | CLAUDE.md #7 | `audit_log` `invoice.issued` per bill + `bill_run.issued` + `bill_run.released` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given issue of the WE-1 draft, Then number, due date, immutability, per-line GL stamps, template pin, posting handoff, delivery rows and audit all exist exactly as §7/TC-1 — the J2 step-8 contract is satisfied.
- Given a later mapping or template edit, Then issued history never changes.
- Given a subset issue, Then only the selection freezes and the run stays open for the rest.
- Given a retry, a direct ledger write, or a cross-tenant request, Then nothing duplicates, nothing bypasses the posting service, nothing leaks.
- Given the gate, Then one consolidated summary shows accounts, bills, consumption per service with its unit, amount with currency and the category breakdowns, and every figure ties to the bill set it is computed from (BR-BIL-056).
- Given confirmation, Then the figures shown are stored as shown in `bill_run_releases` and that row is never updated or deleted, and the five confirmations are stored as five separate facts with who and when (BR-BIL-056/058 · hard rule 4).
- Given the run is re-opened after a bill is voided, Then the SCREEN shows the live figures — not the stored ones — because the PO ruled option B on 2026-08-11 ("recalculate live"); the stored row is unchanged and remains the only answer to *"what did I authorise?"* (BR-BIL-056).
- Given any untaken confirmation, Then release is refused; given accounts with no email, Then release is not refused (BR-BIL-058/059).
- Given release, Then the clerk is returned to S30 while issue and every downstream job run as background batches, and a crash before completion leaves an authorised-but-unreleased record that resumes without re-asking (BR-BIL-051).

**7 · Finance Calculation** — CONFIRMED (WE-1, workbook verbatim). Posting handoff per bill: `DR AR = current charges; CR per-GL buckets = Σ stamped lines per GL`. Worked (WE-1/BS-1): DR 1200 AR **247.87** · CR 4100 **88.60** · 4105 **12.00** · 4110 **39.50** · 4115 **8.00** · 4120 **15.80** · 4130 **18.00** · 4150 **40.00** · 2200–2203 **20.97** · 4200 **5.00** — balanced (prior balance 45.00 is already in AR from its own bill; total due 292.87 is presentation, not posting). Ref: BS-1.

**8 · Open Questions** — None.

---
id: US-BIL-006
epic: EP-BIL-01
module: billing
screens: [S30, S31]
wave: 3
status: draft
blocked_by: []
depends_on: [US-BIL-003, US-BIL-005]
journeys: [J2, J24]
rules: [BR-BIL-005, BR-BIL-015, BR-BIL-055]
golden_tests: []
finance_calc: none
---
### US-BIL-006 — Pending-billing queue + catch-up sub-runs (hold ≠ forget)

**1 · Details** — As a Billing Clerk, I want every held account in a **Pending-billing queue** — billing landing KPI chip, aging shown, escalation after tenant-config days — and when the blocker clears (read arrives / estimate accepted) I want to launch a **catch-up sub-run**: a child of the original run (`parent_run_id`), same period, scoped to the held accounts only, with idempotency key = parent key + scope so it never collides with the original, flowing drafts→issue like any run — so that nothing silently stays unbilled (BR-BIL-015, model r1.3). Entry: S30 KPI chip → queue list; queue bulk action "Start catch-up sub-run" → S31 in sub-run mode. Exit: held accounts billed; queue rows closed with resolution recorded.

**Two doors into this queue, and the second one is new (BR-BIL-055).** The original door is a phase-1 HOLD decision (BR-BIL-015 — the read is missing and staff choose to hold). The second is a phase-3 **"mark for later"** on a break row: the calculation ran and this account produced no draft, and rather than block the run the clerk defers it (US-BIL-004, PO answer 1 to the partial-run question — *issue the clean ones, hold the rest*). Both write the same `bill_run_exclusions` row and both leave through the same catch-up sub-run; the difference is only the reason recorded and the phase it came from, which the queue shows so a clerk can tell "we never calculated this" from "we calculated it and it broke". Partial runs are therefore the NORMAL case, not a failure mode: a run that issues 1,122 of 1,124 bills and queues 2 is a run that worked.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-015 | Held accounts enter the Pending-billing queue (KPI chip, aging, escalation) and are billed via catch-up SUB-RUNS (parent-linked, scope-keyed idempotency — never a colliding re-run). | CONFIRMED — PO A-6 + r1.3 process, 2026-08-08 |
| BR-BIL-005 | Sub-run idempotency: key = parent key + scope; the original run's key is never re-used; mechanics 🔒 Eng-Lead. | CONFIRMED — PO A-6/r1.3 + CLAUDE.md #6 |
| BR-BIL-015 (escalation) | Queue ages out to escalation after tenant-config days — surfaced, never auto-billed. | CONFIRMED — r1.3 "ages out to escalation (config days)" |
| BR-BIL-055 | A phase-3 "mark for later" is the second door into this queue: the run issues the clean bills and holds the rest; the queue row records which phase it came from. | CONFIRMED — PO 2026-08-11 answer 1 (partial run → A) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | ACC-1201 held in US-BIL-003 TC-3 | Queue row: account, period Jul 1–31, blocked service Gas, reason, age counting from hold; S30 KPI chip count +1 |
| TC-2 | Gas read for ACC-1201 arrives Aug 9; clerk starts catch-up for the 3 resolved holds | Child `bill_runs` row: `parent_run_id` = run 07-A, same period, scope = the 3 accounts; drafts→issue normal; invoices carry the original period |
| TC-3 | Catch-up completes | Queue rows closed with resolution + link to the child run; KPI chip decrements; audit trail complete |
| TC-4 | Age exceeds the tenant escalation days (fixture 14) | Row flagged escalated; appears in the escalation filter — still requires staff action, never auto-bills |
| TC-5 *(negative)* | Second catch-up attempted for the same parent + same scope | Blocked by the scope-keyed idempotency (who/when/link shown); a catch-up for a DIFFERENT held subset is allowed |
| TC-6 *(negative)* | Catch-up attempted including an account never held on that run | Rejected — sub-run scope must be a subset of the parent's held set |
| TC-7 *(isolation)* | Lone Star Ridge queue + sub-runs | Own rows only; Brazos Bend parent run ids unusable (RLS) |
| TC-8 *(the second door)* | ACC-1455 and ACC-1710 are marked "for later" on their phase-3 break rows (US-BIL-004 TC-13) | Two queue rows appear carrying the break's failing stage and reason, marked as phase-3 origin — distinguishable from a phase-1 hold; the run still issues its other 1,122 bills (BR-BIL-055); the catch-up path is identical from here |
| TC-9 *(a partial run is not a failed run)* | Run 07-A completes with 1,122 issued and 2 queued | The run's own status reads completed, not failed; S30 shows 1,122 issued bills and a queue count of 2; nothing about the 2 is presented as an error in the issued bills' totals |

**4 · Test Data** — Parent run 07-A (Brazos Bend). Held: ACC-1201 (gas missing), ACC-1455 (access flagged), ACC-1710 (unit locked) — 3 rows, held Aug 1. Read arrives Aug 9 → catch-up CU-07-A-1 issuing 3 bills for Jul 1–31. Escalation setting 14 days; ACC-1455 hits day 15 → escalated. Actors: Priya Menon. Isolation: Lone Star Ridge queue (1 row).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Queue row (account, period, reason, age) | S30 queue | BR-BIL-015/r1.3 | held-account queue rows on the run scope (r10 #7) | rows | system-derived | age = days since hold |
| KPI chip | S30 | r1.3 "billing landing KPI chip" | computed count over open queue rows | int | computed-display | ties to list |
| Escalation flag | S30 queue | r1.3 | computed: age > tenant escalation days (BR-BIL-021 config family) | flag | computed-display | tenant-set days |
| Catch-up sub-run | S31 | BR-BIL-015 | `bill_runs.parent_run_id` + scope (r10 #7); idempotency key = parent + scope 🔒 | row | user-input | scope ⊆ parent held set |
| Resolution linkage | S30 queue | r1.3 | queue row closed with child-run link | uuid | system-derived | audited |
| Queue-entry origin (phase 1 hold \| phase 3 mark-for-later) | S30 queue | BR-BIL-055 | `bill_run_exclusions.reason_code` + detail (r10 #13 reference data) | enum + text | system-derived | shown in the list so "never calculated" reads differently from "calculated and broke" |

**6 · Acceptance**
- Given a hold, Then the queue row + KPI chip appear with aging, and escalation flags at the tenant threshold without auto-billing.
- Given a cleared blocker, Then a catch-up sub-run (parent-linked, same period, held-scope only) drafts and issues like any run.
- Given a duplicate catch-up for the same scope, Then it is blocked with who/when/link; a different held subset is allowed.
- Given tenant isolation, Then queues and sub-runs never cross.

**7 · Finance Calculation** — N/A (catch-up bills price identically to the parent run's period; money math per US-BIL-004/005 and WE fixtures).

**8 · Open Questions** — None.

---
id: US-BIL-029
epic: EP-BIL-01
module: billing
screens: [S31, S31.2, S31.3]
wave: 3
status: draft
blocked_by: []
depends_on: [US-BIL-001, US-BIL-002, US-BIL-003, US-BIL-004, US-BIL-005, US-RAT-012, US-RAT-013, US-RAT-015]
journeys: [J2, J24]
rules: [BR-BIL-037, BR-BIL-039, BR-BIL-040, BR-BIL-011, BR-BIL-023, BR-BIL-033, BR-BIL-050, BR-BIL-051]
golden_tests: [GT-1, GT-8, GT-10]
finance_calc: confirmed
---
### US-BIL-029 — The bill-run pipeline: seven stages, one contract each, no stage reaching around another

**1 · Details** — As the Eng Lead answering the PO's *"how do we write billing code modular, maintainable"*, I want the run expressed as **seven narrow stages in one fixed order**, each with exactly one input contract and one output contract (BR-BIL-037): **1 resolve-subscription** → `SubscriptionContext` · **2 measure-consumption** → `MeasuredUsage` · **3 price-usage** → `PricedLines` · **4 apply-charges** → `ChargedLines` · **5 compute-tax** → `TaxedLines` · **6 assemble-document** → the stamped `bill_payload` + rendered document · **7 post-to-ledger** → the balanced handoff. So that each stage is independently testable with a fixture and no database, a change lands in one stage instead of in a 900-line function, and the boundaries are asserted by a test rather than described in a comment (hard-won law 1).

What this story is **not**: it is not new arithmetic. Every figure stays exactly where it was ratified — stages 3·4·5 are the rating engine's (🔒 EP-RAT-05/06, US-RAT-012/013/014) and this story only fixes their edges; stage 7 **emits** and never writes, because the ledger posting service is the sole writer of journal lines (BR-BIL-011, CLAUDE.md #5). **Three axes that are easy to conflate and must not be** (corrected 2026-08-11 — this sentence previously said "the five S31 wizard steps", and the wizard has SIX): the **seven stages are the computation** (this story); the **six S31 wizard steps are the UI over it** — the prototype's own stepper: Pick the cycle · Check what we found · Review customers · See the totals · Confirm & sign off · Send them out; and the **five phases are the operating model the PO ruled on 2026-08-11** — prepare · calculate · breaks · summary+gate · release (BR-BIL-050, epic §Phase map). None of the three renumbers another. Where the stages sit on the phases: stages **1–5 run twice** — once in phase 1 as the S31.2 preview with stage 6 not run (BR-BIL-039), and again inside the phase-2 background batch; **stage 6** runs in the phase-2 batch, producing the draft document instance; **stage 7 is reached only in phase 5**, at issue, because it emits the posting handoff and nothing before release may touch the ledger (BR-BIL-011). The refactor-invariance contract over GT-1..61 lives with the terminal stages in US-BIL-030.

Stage boundaries, each derived from an existing ruling: stage 1 assembles per the model §2 input contract (status class BR-CUS-055, plan snapshot as of service date, tariff version in force BR-RAT-007, tax rules + exemption, charge rules, capacity rows); stage 2 gates read completeness (BR-MET-049) and UoM (BR-RAT-038); stage 4 applies the minimum-bill adjustment **then** charges (BR-RAT-028's order, unchanged), which is why tax is its own stage 5 and never earlier (B4.2); stage 6 renders **before** issue, because a failed render refuses the issue (BR-BIL-033).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-037 | Seven named stages in one fixed total order, one input and one output contract each; a stage receives its predecessor's output and nothing else; only the orchestrator knows the sequence; ownership 1·2·6·7 billing, 3·4·5 rating 🔒, 7 emits only. | PROPOSED — derived from billing model §2/§3/§6 + B1 boundaries + BR-BIL-010/011/030/033 + EP-RAT-05 scope |
| BR-BIL-039 | Stages 1–5 are pure (no writes, no external calls, no clock); only stage 6 writes; stage 7 emits the handoff and writes no journal lines. Re-rate replays stages 2–6 with no compensating cleanup; the S31.2 preview is stages 1–5 with stage 6 not run. | PROPOSED — derived from BR-BIL-004/011/023 + US-RAT-012 TC-8 + CLAUDE.md #4/#5 |
| BR-BIL-040 | A stage failure is a typed exception naming the stage, surfaced in the S31.2/S31.3 tab that owns that stage's inputs; the run cannot continue past an unresolved one. Never a silent skip, never a partial bill. | PROPOSED — derived from billing model §2 + BR-BIL-015/033 + US-BIL-007 TC-5 |
| BR-BIL-011 | One bill = one document + N GL-coded lines + one balanced JE; the posting service is the sole writer — which is why stage 7 emits rather than writes. | CONFIRMED — PO directive 2026-08-08 · B1/B2 |
| BR-BIL-023 | Draft powers include **re-rate after a fix** — the operation BR-BIL-039's purity makes safe to repeat. | CONFIRMED — PO Lane B-4, 2026-08-08 |
| BR-BIL-033 | Render before issue; a failed render refuses the issue — stage 6 is a precondition of issuing, not a consequence of it. | CONFIRMED — PO 2026-08-10 (OQ-089) |
| BR-BIL-050 | Stages ≠ wizard steps ≠ phases: seven stages (computation) · six wizard steps (UI) · five phases (operating model). Stages 1–5 run in phase 1 (preview) and again in the phase-2 batch; stage 6 in phase 2; stage 7 only in phase 5. | CONFIRMED — PO 2026-08-11 five-phase ruling (epic §Phase map) |
| BR-BIL-051 | The phase-2 batch is where stages 1–6 execute in the background; nothing in it is synchronous with the clerk and nothing in it reaches stage 7. | CONFIRMED — PO 2026-08-11 (*"run the billing in batch process in background"*) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(end to end)* | WE-1 (ACC-1042, Jul 1–31) run through all seven stages | Each stage's output equals §7's line exactly: stage 3 → **221.90** of usage/base/capacity lines · stage 4 → + late fee 5.00 = **226.90** · stage 5 → + tax 20.97 = **247.87** · stage 6 → payload total due **292.87** · stage 7 → DR AR 247.87 = Σ CR buckets. The 15 lines match US-BIL-007 TC-1 |
| TC-2 *(stage isolation)* | Stage 3 called directly with a hand-built `MeasuredUsage` and tariff config, no bill run and no database | Reproduces GT-2 (**13.74** usage + 12.00 base) — every stage is unit-testable from a fixture alone (BR-BIL-039 purity) |
| TC-3 *(import-graph guard)* | Architecture test over the stage modules; then a patch making stage 4 import stage 3's internals or query `meter_reads` directly | Baseline passes; the patch **fails** naming the stage and the illegal import. Proven RED first against a deliberately-violating branch (hard-won law 7) |
| TC-4 *(the order is data, not folklore)* | Test asserts the orchestrator's stage sequence constant | Equals the BR-BIL-037 list exactly, in order; no stage calls another stage; removing a stage from the constant fails the test rather than silently skipping work |
| TC-5 *(negative — purity)* | An INSERT/UPDATE, an HTTP call, or `datetime.now()` introduced anywhere in stages 1–5 | Purity property test fails naming the stage (extends US-RAT-012 TC-8 to the whole front of the pipeline) |
| TC-6 *(re-rate replay)* | ACC-1201's gas read is corrected; clerk hits Re-rate (BR-BIL-023) | Stages 2–6 replay; no compensating delete or cleanup is needed anywhere; no ledger effect, because stage 7 is not reached until issue; the new draft replaces the old |
| TC-7 *(negative — named failure)* | Stage 2 cannot complete for ACC-1201 (gas read missing) | A typed exception carrying account + stage + reason lands in the **Reads** tab of S31.2 and the missing-service choice of S31.3 (BR-BIL-015); the run cannot continue past it; the account never reaches stage 3 |
| TC-8 *(negative — no partial bill)* | Stage 6 render fails for one account mid-issue (template variable unresolvable) | That bill does **not** issue (BR-BIL-033); nothing immutable is created for it; the rest of the batch is unaffected; the failure names stage 6 |
| TC-9 *(negative — stage 7 writes nothing)* | Stage 7 code path attempts `INSERT INTO journal_lines` | Rejected — sole-writer boundary (BR-BIL-011, CLAUDE.md #5); the handoff persists unposted until W5 exactly as US-BIL-009 specifies |
| TC-10 *(isolation)* | Brazos Bend and Lone Star Ridge runs execute in the same process | The tenant travels on `SubscriptionContext` from stage 1; a stage cannot be invoked without `app.tenant_id` set (probe test), and a stage that received one tenant's context can never resolve the other's tariff version (RLS) |
| TC-11 *(the three axes are asserted, not described)* | Test over the orchestrator's stage sequence constant, the wizard's step list and the phase map | Seven stages, SIX wizard steps, five phases; the phase→stage assignment equals BR-BIL-050 exactly (1–5 preview in phase 1 · 1–6 in the phase-2 batch · 7 in phase 5). Renaming or renumbering any one of the three fails the test rather than silently drifting — hard-won law 1, and this test exists because the epic itself once said "five wizard steps" |
| TC-12 *(negative — stage 7 cannot be pulled forward)* | The phase-2 batch is made to call stage 7 | Rejected: the batch's contract ends at stage 6, and phase 2 leaves nothing money-bearing (BR-BIL-051, US-BIL-004 TC-9). A ledger effect before the release gate is authorised is the failure this boundary exists to prevent |

**4 · Test Data** — **WE-1** (Brazos Bend, ACC-1042, Residential Standard, Jul 1–31, 2026): 15 lines — electric TOU 26.40 + 28.00 + 34.20, electric base 12.00, water tiers 20.00 + 19.50, water base 8.00, sewer 15.80, trash 18.00, solar capacity 40.00 (Σ **221.90**), late fee 5.00, taxes 13.87 + 2.22 + 4.44 + 0.44 (Σ **20.97**) → current **247.87**, prior 45.00, total due **292.87**; GL stamps 4100/4105/4110/4115/4120/4130/4150/2200–2203/4200, AR 1200. Stage-2 failure fixture: **ACC-1201** gas read missing (US-BIL-003 §4). Stage-6 failure fixture: an account whose pinned template references an unresolvable variable. Re-rate fixture: ACC-1201 gas read corrected Aug 9. Isolation: **Lone Star Ridge** run W-01. Actors: Priya Menon (ran), Alex Reed (sign-off).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `SubscriptionContext` (stage 1 out) | S31.2 Consumers/Plans | model §2 assembly contract | read-model over `accounts` + plan snapshot + `tariff_versions` + `plan_tax_rules` + `plan_charge_rules` + `account_capacities` via service fns (B1) — **no writes** | frozen contract object | system-derived | tenant id present; plan snapshot as of service date; missing → stage-1 exception (Plans tab) |
| `MeasuredUsage` (stage 2 out) | S31.2 Reads | BR-MET-049 + BR-RAT-038 | read-model over `meter_reads` per channel (`consumption`, `unit`, estimated flag, read ids) | numeric(18,6) + explicit unit | system-derived | unit required (CLAUDE.md #3); completeness + UoM gates |
| `PricedLines` (stage 3 out) | S31.2 | US-RAT-012/014 | line candidates → later `invoice_lines` (usage/base/capacity, `tariff_version_id`, `taxable`) | numeric(18,6) | system-derived | unrounded; rounding at finalization (B4.4) |
| `ChargedLines` (stage 4 out) | S31.2/S31.3 | US-RAT-013 + BR-BIL-001/007/023 | + minimum-bill adjustment, then charge-code lines (`charge_id`), then late-fee line | numeric(18,6) | system-derived | minimum before charges; charge codes only, never typed amounts |
| `TaxedLines` (stage 5 out) | S31.2 | US-BIL-008 · B4.2 | + one line per tax authority; `invoices.tax_total` | numeric(18,6) | system-derived | base = taxable lines only; exempt ⇒ zero |
| Document instance (stage 6 out) | S31 step 4/5 | BR-BIL-030/031/033/035 | `invoices.bill_payload` + `payload_version`; `template_id`+`template_version` pinned | jsonb | system-derived | renders before issue or the issue is refused |
| Posting handoff (stage 7 out) | — (service contract) | BR-BIL-011 · US-BIL-009 | consumed by the ledger posting service 🔒 — billing writes no journal lines | rows | system-derived | DR AR = Σ CR buckets by construction |
| Stage sequence constant | — | BR-BIL-037 | code-only ordered list; **no table** | — | system-derived | asserted by TC-4 |
| Phase → stage map | S31 stepper | BR-BIL-050/051 | code-only; the run's PHASE is `bill_runs.status`, the stage list is the constant above — **two values, never one** | — | system-derived | asserted by TC-11; seven ≠ six ≠ five |
| Stage exception record | S31.2/S31.3 | BR-BIL-040 | run exception rows (r10 #7 scope/exclusions family) | rows | system-derived | carries account + stage + reason; blocks continue |

**6 · Acceptance**
- **Given** the WE-1 fixture, **when** it flows through all seven stages, **then** every stage boundary carries the §7 figures and the issued bill is identical to US-BIL-005/US-BIL-007 today.
- **Given** any single stage, **then** it can be executed from a fixture with no database and no other stage present.
- **Given** a patch that makes one stage import another's internals or re-read another's tables, **then** the architecture test fails naming the stage — and it was proven to fail before it was trusted to pass.
- **Given** a corrected read and Re-rate, **then** stages 2–6 replay with no cleanup and no ledger effect.
- **Given** a stage failure, **then** it surfaces named, in the tab that owns that stage's inputs, and nothing partial is ever issued.
- **Given** two tenants in one process, **then** no stage can run without a tenant context and no context ever crosses.
- **Given** the three axes, **then** a test asserts seven stages, six wizard steps and five phases with the BR-BIL-050 phase→stage assignment — and stage 7 cannot execute before phase 5.

**7 · Finance Calculation** — **CONFIRMED (WE-1/BS-1, workbook verbatim — the pipeline restates the ratified figures, it does not compute new ones).**
Stage-by-stage trace of WE-1: **stage 3** Σ usage + base + capacity = 88.60 + 12.00 + 39.50 + 8.00 + 15.80 + 18.00 + 40.00 = **221.90** (all taxable) → **stage 4** + late fee `max(5.00, 0.015 × 45.00)` = **5.00** (not taxable) ⇒ subtotal **226.90** → **stage 5** tax `0.0825 × 221.90` split by authority = 13.87 + 2.22 + 4.44 + 0.44 = **20.97** ⇒ current charges **247.87** → **stage 6** payload: current 247.87 + prior balance 45.00 = total due **292.87** → **stage 7** handoff DR 1200 AR **247.87** / CR 4100 88.60 · 4105 12.00 · 4110 39.50 · 4115 8.00 · 4120 15.80 · 4130 18.00 · 4150 40.00 · 2200–2203 20.97 · 4200 5.00 — balanced. GT refs: **GT-1** (flat line arithmetic), **GT-8** (the late-fee stage-4 rule), **GT-10** (the stage-5 base excluding fees). Ref: BS-1.

**8 · Open Questions** — None. *(The stage list is derived entirely from existing rulings — model §2/§3/§6 and BR-BIL-010/011/015/028/033 — so it needs no new decision; if the PO wants the boundaries drawn elsewhere, that is an amendment to BR-BIL-037, not an open question this story is waiting on.)*

---
id: US-BIL-036
epic: EP-BIL-01
module: billing
screens: [S31]
wave: 3
status: ready            # 2026-09-30: the bulk bill run redesign (epic §AMENDED 2026-09-30) — ready to build, not blocked
blocked_by: []
depends_on: [US-BIL-001, US-BIL-006, US-MET-006, US-CUS-001]
journeys: [J72]
rules: [BR-BIL-005, BR-BIL-1043, BR-BIL-1041, BR-BIL-1050, BR-BIL-1051, BR-BIL-1025, BR-BIL-024]
golden_tests: []
finance_calc: none
---
### US-BIL-036 — Scope: choose what to bill, see every refusal and warning at once, one screen

**1 · Details** — As a Billing Clerk, I want step 1 **Scope** to ask only what the run is — **run name, cycle, period start and end, bill date, days to pay, bill template** — and to show me, before I start, what the cycle holds and every reason the run cannot start or should give me pause, all at once and each on its field, so that I never meet a run-level problem one at a time or after the accounts have been checked (BR-BIL-1050; changes rows 9–19, 30–35, 43). There is ONE bill-run screen: **Bills › Run** opens it and the six-step `BillRunWizard` is gone (`DEF-BIL-8200`). Below *What to bill*: **Cycle details** (open), **This run covers** (open — units in cycle, accounts to bill, regular, master, meters, sub-meters, behind the meter, missing meter; *Last run* under the three account cards only — row 30), **Previous runs** (closed; run no. + name, period, bills, value, run by, status, newest first, *All runs*), each collapsible with a one-line summary. The side card **Run to start** repeats the choices, the utility's services as `ServiceChips`, the counts, the last run and *Follows on* (Continuous / Gap / Overlap). **There is no services filter** (BR-BIL-005 re-affirmed; `DEF-BIL-8201`), **no standing answers** (they are on Check — BR-BIL-1040), and **no "Continue anyway" tick** for a gap (BR-BIL-1051). *See units* opens the **Nobody to bill** panel (units) and *See services* the **Missing meter** panel. Images `01`–`08`.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-1050 | Scope checks the run, never an account; every refusal and every warning at once, each on its field; the ruled list (changes row 43) | CONFIRMED — PO 2026-09-30 |
| BR-BIL-1051 | Continuity against the cycle's real last run (cancelled ignored): overlap refuses naming the run; gap warns, no tick | CONFIRMED — PO 2026-09-30 (row 35 supersedes row 17's tick) |
| BR-BIL-005 / 1043 | The key is cycle + period with no services term for new runs; existing keys unchanged 🔒 | CONFIRMED / SUPERSEDED for new runs — PO 2026-09-30 |
| BR-BIL-1041 | Template required and published for a new bulk run | AMENDED 2026-09-30 |
| BR-BIL-1025 | A vacant unit with nobody to bill is a warning only | AMENDED 2026-09-30 — *"only warning- i agree"* |

**3 · Test Cases** (fixture `BBR`)
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Priya opens **Billing › Bills › Run** | The four-step screen opens at Scope (rail **Scope · Check · Sign off · Send**); `/billing/run` renders it and no route renders `BillRunWizard` (door test by ADDRESS, law 2) |
| TC-2 | Cycle 3 · Riverside, **Sep 1 – Sep 30, 2026**, bill date **Oct 1**, days to pay **21**, template **Standard bill · v4**, run name **September 2026 · Riverside** | *Continuous — Follows run BR-0231 (Aug 1 – Aug 31). 30 days.*; due **Oct 22, 2026**; This run covers **12 units · 10 accounts · 9 regular · 1 master**; *Last run 10* under Accounts to bill; **no** last-run figure under Units or Meters; amber box **2 warnings. You can still start.** — *Units — 1 unit has nobody to bill.* and *Meters — 1 service has no meter. Not billed.*; **Start checking** enabled |
| TC-3 | Continuity ignores the cancelled BR-0229 (Sep 1 – Sep 30) | Still *Continuous*; no overlap is reported against a cancelled run |
| TC-4 *(overlap)* | After TC-2 created **BR-0232** (Sep 1 – Sep 30), Priya starts another run for **Sep 15 – Oct 14** | Red box **Fix 1 thing to start.** — *Period start — Sep 15 – Sep 30 already billed.* with link **Open BR-0232**; Period start red with the same message; side card *Follows on* **Overlap**; Start disabled with *Fix 1 thing first.*; no row written |
| TC-5 *(gap)* | Period **Oct 10 – Nov 9** (last run ends Sep 30) | Amber *Period start — Oct 1 – Oct 9 not billed by any run.*; **no tick box anywhere**; Start enabled; side card *Follows on* **Gap** |
| TC-6 *(every refusal at once)* | Run name empty · period end **Aug 20** · bill date empty on a cycle with no bill day · days to pay **-3** · template **Winter insert · draft** | ONE response and ONE red box listing all five, each field red with its own message (*Enter a run name.* · *Ends before it starts.* · *Cycle has no bill day. Enter one.* · *Enter whole days, zero or more.* · *Not published. Publish it first.*); each line's field name focuses its field; side card *To fix 5*; Start disabled; `POST /billing/runs` answers `field_errors` with five entries and writes no row |
| TC-7 *(new refusal)* | Bill date **Sep 25** for period Sep 1 – Sep 30 | Refused on *Bill date* (bill date before the period ends); no row |
| TC-8 *(warnings, all at once)* | Period Sep 1 – **Oct 15**, bill date **Oct 20**, days to pay **30**, template **Large print · v2** (published, not the cycle's usual) | Amber box lists: period 45 days / cycle monthly / ends after today · not the cycle's bill day (1st) · changed from the cycle's 21 · not the cycle's usual template · nobody to bill · no meter; Start **enabled** |
| TC-9 *(no services filter)* | Inspect Scope and the create request | No service checkboxes; the create body has no `scope_services`; the run's key is `<cycle>|2026-09-01|2026-09-30`; a pre-2026-09-30 run keyed `…|scope|water` is untouched (replaces US-BIL-001 TC-4) |
| TC-10 *(no run-number series)* | Tenant with no run-number series | A WARNING *Run number — No number series yet. Numbered when set up.*; Start enabled (BR-BIL-1050, not a refusal) |
| TC-11 *(duplicate)* | A second run for Cycle 3, Sep 1 – Sep 30 after TC-2's run exists | Refused: who (Priya Menon), when, link to the run; no second row (BR-BIL-005) |
| TC-12 *(panels)* | Collapse all three panels; press *See units*; press *See services* | Headers keep their summaries; **Nobody to bill** panel: *1416 Elm St · Unit B · Water · Moved out Aug 12 · Add account ↗*; **Missing meter** panel: *1408 Elm St · Unit A · Gas · AC-2026-00101 · Fit a meter ↗*; each ↗ opens the named screen in a new tab with the unit filled in |
| TC-13 *(module down)* | Meter Reads not answering while Scope loads its counts | Refusal names *Meter Reads*; the typed form is kept |
| TC-14 *(permission)* | Jo Park (view-only) opens Scope | Refused: not allowed to run bills; no create control works; `POST /billing/runs` → 403 |
| TC-15 *(isolation)* | Lone Star Ridge's clerk asks the scope preview for Brazos Bend's cycle id | 404; nothing of Brazos Bend's counted |

**4 · Test Data** — `BBR` (epic §AMENDED 2026-09-30).

**5 · Data Fields / Mapping**
| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Run name | Scope | row 14 | `bill_runs.label` (required going forward — plan DB2) | text | user-input | non-blank |
| Cycle / period / bill date / days to pay | Scope | BR-BIL-005, 024, 070 | `bill_runs.cycle_id`, `period_start/end`, `bill_date`, `due_days` | uuid/date/int | user-input | BR-BIL-1050 list |
| Bill template | Scope | BR-BIL-1041 | `bill_runs.template_id` | uuid | user-input | tenant's, published |
| Idempotency key 🔒 | — | BR-BIL-005 | `bill_runs.idempotency_key` | text | system-derived | no services term for new runs |
| Scope preview counts | Scope | rows 15, 30 | read (plan A2) | ints | system-derived | tenant-scoped |

**6 · Acceptance**
- Given any set of run-level problems, Then all of them show at once, each on its field, and Start is disabled only by refusals.
- Given a gap, Then Start stays enabled and nothing asks for a tick.
- Given an overlap with a non-cancelled run, Then it is refused naming and linking that run.
- Given Bills › Run, Then exactly one bill-run screen is reachable.

**7 · Finance Calculation** — N/A (due date only: Oct 1 + 21 = Oct 22, 2026).

**8 · Open Questions** — None.

---
id: US-BIL-037
epic: EP-BIL-01
module: billing
screens: [S31.2]
wave: 3
status: ready
blocked_by: []
depends_on: [US-BIL-036, US-BIL-002, US-BIL-003, US-MET-010, US-RAT-012, US-PAY-001]
journeys: [J72]
rules: [BR-BIL-1052, BR-BIL-1053, BR-BIL-1040, BR-BIL-015, BR-BIL-1025, BR-BIL-1054]
golden_tests: []
finance_calc: none

> ⚠ **AMENDED 2026-09-30, after this story was written — the PO's later rulings of the same day (decision log; `14-bulk-bill-run-changes.md` rows 44–46). Build to these; the test cases below are extended, not replaced.**
> 1. **Saved, re-checked on change** (OQ-843 re-ruled, option C): results are saved per account with *Checked at*; a change to an account's plan, reading, meter or payment re-checks that account only; *Check again* is a backstop.
> 2. **No check stops an account.** A disputed reading is a tag (*Disputed reading*: Hold until resolved / Bill on an estimate) and every other check still runs.
> 3. **Nothing is fixed automatically.** Every former "auto" answer is a clerk decision with a SUGGESTED answer pre-selected; the account stays under *Need a decision* until accepted.
> 4. **Seven tag buckets, each fixable from the tag:** Reading has no unit (suggest the meter's unit) · Possible rollover (99,950 → 00,120 on 5 digits = 170) · Meter swapped (bill both parts) · Plan not published (last published version) · No price for a service (bill the others, hold it) · No charge for customer type (base $0.00) · Price changed mid-period (period-end price, or split). Each row: found, suggestion, fix (inline via the owning module, or a fix link then Re-check), Hold.
> 5. **Decisions with defaults:** no multiplier → Hold (or Bill with 1) · city limits unknown → Hold (or inside / outside) · no price in force → latest earlier version / Hold · no plan → customer type's default plan / Hold · time-of-use unmatched → flat-rate total / Hold · reading down (not a rollover) → Estimate / Hold.
> 6. **Stays blocked (that account or service only):** no unit · master coverage (OQ-334/335) · no size · pricing conflict. **Utility-wide:** Meter Reads down · currency not set.
>
> **Added test cases:** TC-A1 six accounts blocked on an unpublished plan; the plan is published; only those six re-check and turn ready. TC-A2 an account with a disputed reading AND no plan AND a bounced payment shows three tags. TC-A3 a reading with no unit on a kgal meter is listed under *Reading has no unit* with suggestion kgal, and no bill uses it until accepted. TC-A4 99,950 → 00,120 on a 5-digit dial suggests 170; accepting prices 170. TC-A5 no multiplier defaults to Hold; "Bill with 1" prices ×1.
---
### US-BIL-037 — Check: every check on every account, problems by category and tag, fixed here or answered for all

**1 · Details** — As a Billing Clerk, I want step 2 **Check** to run every check on every account in the background — never stopping an account at its first problem and never stopping the run for one account — and to show me the problems **one tag at a time**, grouped by category, with the accounts for that tag in a paginated table, so that I can answer a whole tag at once, fix a blocking fact on the row, or open the screen that owns it, and re-check (BR-BIL-1052; changes rows 20–26, 36, 38, 41). Layout (images `09`–`23`): progress *Checking accounts — n of N* (you can leave and come back); then five tiles (problem types · blocked · need a decision · warnings · ready) that filter; a left list — **Ready to bill** first, then nine categories (**Payments & balances · Readings · Meter history · Plans & rates · Accounts & units · Master accounts · Assets & connections · Billing period · Setup**) with their tags and counts, *Find a problem*, *Show N passed checks*; the right pane shows ONE tag: name, severity, count, meaning, where it is fixed, *Find account*, the action bar (decision: **Answer for all N** pre-selected from Billing settings, per-row override, **Apply to N selected**; blocking: inline fix or *Open <screen> ↗* and **Re-check N accounts**; warning: *Bills anyway*), and the table (account · unit · service · **Also has** chips · decision / fix). Clicking an account opens **Fix account** listing EVERY problem on it with its fix and **Re-check account**. A utility-wide stop names what and who, gives a support reference and keeps the run. Every fact the clerk can supply here is WRITTEN BY ITS OWNING MODULE (reading → Meter Reads, plan → Accounts, size/count → Assets, city limits → Premises) — billing writes none of them (plan B14).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-1052 | Every check on every account; per-account savepoint; any error blocks that account; unitless reading = that account's problem | CONFIRMED — PO 2026-09-30 |
| BR-BIL-1053 | Payments & balances: five decisions, four warnings, read through the payments seam | CONFIRMED — PO 2026-09-30 |
| BR-BIL-1040 | Standing answers chosen at Check per tag, pre-selected from S66, stored on the run | AMENDED 2026-09-30 |
| BR-BIL-015 | A per-row override is a `bill_run_decisions` row; the trail stays append-only | CONFIRMED |
| BR-BIL-1025 | Nobody to bill is a warning, never a block | AMENDED 2026-09-30 |

**3 · Test Cases** (fixture `BBR`, after US-BIL-036 TC-2 started the run)
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(never stops at the first problem — the PO's example)* | Check finishes | `AC-2026-00105` carries **three** tags — *No plan* (blocks), *Disputed reading* (blocks), *Bounced payment* (decision); its Fix account panel lists 3 problems; its row in each tag shows the other two under *Also has* |
| TC-2 *(one account never stops the run — law 14)* | Check with `AC-2026-00106`'s electric reading arriving with no unit | `00106` is **blocked** under a Readings tag naming the missing unit; every other account is checked; tiles **ready 5 · need a decision 2 · blocked 3**; proved on PostgreSQL, and the same test with the savepoint removed fails with `InFailedSqlTransaction` |
| TC-3 *(any error)* | Inject a plain `RuntimeError` for `00102` only (test double) | `00102` blocked with a support reference; the other nine checked; the run kept |
| TC-4 *(three accounts, middle broken)* | Accounts `00101`, `00106`, `00102` only | 2 ready, 1 blocked (plan T1) |
| TC-5 *(background + progress)* | Start Check; leave the page; come back | Progress *n of 10* then results; leaving did not stop it; a second Start while running does not start a second pass |
| TC-6 *(a fix is seen — the reason OQ-843 was ruled RECOMPUTE)* | Fix `00104` inline: choose plan **Residential Standard** → Save | The plan is written by Accounts' own service (no billing write — G78-style boundary test); the row reads **Fixed · re-checked** and `00104` moves to Ready (ready 6, blocked 2) |
| TC-7 *(fix elsewhere)* | Tag *Disputed reading*: **Open Meter Reads ↗**, resolve the dispute there, then **Re-check 1 account** | Only the named account is re-checked (`calculate_run(only_accounts=…)` pattern); `00105` still blocked by *No plan* until that is fixed too |
| TC-8 *(answer for all)* | Tag *No reading* (1 account): Answer for all = **Estimate** (pre-selected from S66 `run_default_missing_read`) | The run stores `case_defaults.missing_read = estimate`; `00103` counts toward the priced total |
| TC-9 *(override + apply to selected)* | On a tag with 2+ rows, select one, choose **Hold**, **Apply to 1 selected** | One `bill_run_decisions` row for that account; the rest follow the tag's answer |
| TC-10 *(payments)* | Tag *Paid after cut-off*: `00107`, $120.00 posted Oct 1 | Answers **Apply to this bill** / **Next bill**; default the first; *Bounced payment* on `00105` offers *Reverse, add fee* / *Reverse, no fee* / *Hold*; a payment tag whose fact has no source today is ABSENT and filed (OI-B2), not shown with a guessed count |
| TC-11 *(warnings on findings)* | Tag *Base charge $0.00* | `00108` listed as a WARNING (*No base charge for Electric.*); it stays Ready (`DEF-BIL-8210`) |
| TC-12 *(labels)* | Any account raising one of the ten codes with no label today (e.g. `billing_continuity`, `rating_refused_to_price`) | A clerk label from the taxonomy, never the unmapped fallback; a unit test fails on any code without a label (`DEF-BIL-8209`) |
| TC-13 *(filters)* | Press the **Blocked accounts** tile; type *meter* in Find a problem; tick *Show N passed checks* | Only blocking tags listed; search narrows tags and, if the open tag is hidden, the pane opens the first shown; passed tags show ✓ |
| TC-14 *(Ready to bill)* | Open **Ready to bill**; filter **Master**; **Leave out** `00109` then **Put back**, then Leave out again | List paginated and searchable; *1 left out* pill; `00109` joins Not in this run with reason **left out by clerk** (US-BIL-041) |
| TC-15 *(module down)* | Meter Reads not answering at Check | *Meter Reads isn't answering. No account was checked.* + *Try again* + a support reference; the run saved |
| TC-16 *(scale — plan T2)* | 40,000 accounts on PostgreSQL | The Check completes as a background job; no web request exceeds the 60-second worker limit; the time is recorded |
| TC-17 *(isolation)* | Lone Star Ridge reads Brazos Bend's run findings | 404 |

**4 · Test Data** — `BBR`; TC-3 uses a test double; TC-16 the 40,000-account scale seed (plan T2).

**5 · Data Fields / Mapping**
| Field | Screen | Source | DB target | Type | Origin | Validation |
|---|---|---|---|---|---|---|
| Finding | Check | plan B10, DB1 | findings store: run, account, tag, severity, detail, fixed-at (tenant-scoped, RLS FORCE) | rows | system-derived | one row per account per problem |
| Tag taxonomy | Check | plan B10 | code-only map: code → category · tag · severity · fix screen | — | system-derived | every engine code mapped |
| Standing answer | Check | BR-BIL-1040 | `bill_runs.case_defaults` | jsonb | user-input | `decisions.CHOICES_BY_CASE` |
| Per-row decision | Check | BR-BIL-015 | `bill_run_decisions` | row | user-input | append-only |
| Left out | Check | BR-BIL-1054 | Pending billing, reason *left out by clerk* (plan DB3) | row | user-input | a ready account only |

**6 · Acceptance**
- Given an account with several problems, Then all are shown, each under its tag, in one pass.
- Given any failure on one account, Then only that account is blocked and the run goes on.
- Given a fix on the row or elsewhere, Then a re-check of the named accounts shows it.

**7 · Finance Calculation** — N/A (Check prices nothing).

**8 · Open Questions** — OI-B1 (saved results vs `OQ-843`), OI-B2 (payment facts with no source) — epic §AMENDED 2026-09-30.

---
id: US-BIL-038
epic: EP-BIL-01
module: billing
screens: [S31]
wave: 3
status: ready
blocked_by: []
depends_on: [US-BIL-037, US-BIL-004, US-RAT-012]
journeys: [J72]
rules: [BR-BIL-050, BR-BIL-051, BR-BIL-052, BR-BIL-1055, BR-RAT-007, BR-RAT-114]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-038 — Calculate: draft bills between Check and Sign off, priced at the period end

**1 · Details** — As a Billing Clerk, I want pressing **Price N accounts** on Check to calculate draft bills in the background with a progress panel (*Calculating bills — n of N · Draft bills only. Nothing is sent. One failure doesn't stop the rest.*), then open Sign off on the drafts — and I want every bill priced at the rate version **in force at the period end**, the same as a one-time bill (BR-BIL-1055; changes rows 29, 39; image `24`). PO: *"at what step actual bills will be calculated bwtween 2 and 3"* — answered: between them.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-1055 🔒💰 | Version in force at PERIOD END, bulk and one-time alike | CONFIRMED — PO 2026-09-30 *"this si correct"* |
| BR-BIL-051/052 | Background, per-account, restartable | CONFIRMED |
| BR-RAT-114 | A boundary inside the period still splits | CONFIRMED |

**3 · Test Cases** (`BBR`, after US-BIL-037 TC-6 and TC-8)
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Press **Price 7 accounts** | Progress panel; Sign off opens on **7** drafts (`00101`, `00102`, `00103`, `00104`, `00107`, `00108`, `00110`); blocked and left-out accounts get no draft |
| TC-2 *(price at period end — replaces US-BIL-001 TC-8's pricing half)* | `00101` water 10.0 kgal, period ends Sep 30, bill date Oct 1 | Usage **$32.50** at $3.25 + base **$8.00** = **$40.50**; NOT $43.00; the line names the Sep-30 version |
| TC-3 *(one failure)* | A draft fails for `00102` (template cannot render its address) | `00102` goes to *Failed to draft* with its reason and **Retry**; the other 6 drafts stand |
| TC-4 *(resume)* | Kill the worker at 3 of 7 | Resumes at 4; no account drafted twice |
| TC-5 *(one-time agrees)* | The same period and account billed as an Interim one-time bill | The same $3.25 version |
| TC-6 *(scale — plan T2)* | 40,000 accounts on PostgreSQL | Completes as a job; no request past 60 s |

**4 · Test Data** — `BBR`.

**5 · Data Fields / Mapping** — draft `invoices` + `invoice_lines` (no number, BR-BIL-004); job progress (plan A7).

**6 · Acceptance** — Given a price change the day after the period ends, Then the bill uses the old price; Given one failed draft, Then the rest are drafted.

**7 · Finance Calculation** — **CONFIRMED (PO 2026-09-30):** 10.0 kgal × $3.25 = $32.50; + BASE-W $8.00 = **$40.50** (the ruled figure pattern: $3.25 until Oct 1, $3.50 after; period ends Sep 30 → $3.25).

**8 · Open Questions** — None.

---
id: US-BIL-039
epic: EP-BIL-01
module: billing
screens: [S31]
wave: 3
status: ready
blocked_by: []
depends_on: [US-BIL-038, US-BIL-005]
journeys: [J72]
rules: [BR-BIL-056, BR-BIL-057, BR-BIL-058, BR-BIL-059, BR-BIL-1054, BR-BIL-1025]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-039 — Sign off: a summary that adds up to Scope's figures, usage and charges, payments, and what is not in this run

**1 · Details** — As a Billing Clerk, I want **Sign off** to show a summary whose every line adds back to the figures Scope showed me, then usage and charges per service, payments and balances, by customer type, the **Not in this run** list and the warnings, and to sign off with five confirmations (changes rows 37, 40, 42; images `25`–`31`). Sections, each collapsible: **Run summary** (bills of accounts to bill · this run's charges · payments applied · amount due) · **Who is billed** (accounts to bill → billed regular · master + not billed blocked · held · nothing to bill · left out; units in cycle → billed own account · through a master + not billed account not billed · nothing to bill · nobody to bill) · **Usage and charges** (service chip · bills · usage with unit · usage charges · base charges · total, then taxes, late fees, reconnection fees, credits and adjustments, this run's charges) · **Payments and balances** (previous balance − payments applied − credits applied + this run's charges = amount due; how it will be paid) · **By customer type** (closed) · **Not in this run** (after By customer type) · warnings, one line each with a link. **Every *See* on Who is billed opens Not in this run with that filter pressed — no side panel** (row 42); *See breaks* opens the **Failed to draft** panel. Confirmations: *Bills follow our rules and rates* · *E-mail customers have agreed to e-bills* · *SMS customers have agreed to texts* · *Autopay customers will be charged on the due date* · *I checked the totals*; **Sign off** enabled only when all five are ticked.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-056/057 | One consolidated summary; its category axes | CONFIRMED |
| BR-BIL-058/059 | The release gate's separate confirmations | CONFIRMED |
| BR-BIL-1054 | Not in this run; every See filters it | CONFIRMED — PO 2026-09-30 |

**3 · Test Cases** (`BBR`, after US-BIL-038 TC-1)
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(accounts reconcile)* | Who is billed · Accounts | **Accounts to bill 10** (step 1) = billed **7** (regular 6 · master 1) + not billed **3** (blocked 2 — `00105`, `00106` · left out 1 — `00109`) |
| TC-2 *(units reconcile)* | Who is billed · Units | **Units in cycle 12** (step 1) = billed **8** (own account 6 · through a master 2) + not billed **4** (account not billed 3 · nobody to bill 1) |
| TC-3 *(See filters, no panel)* | Press *See* on Blocked, then on Nobody to bill | Not in this run scrolls into view with **Blocked 2** pressed, then **Nobody to bill 1** pressed (a UNIT row, *Add account ↗*); no side panel opens |
| TC-4 *(usage and charges)* | Usage and charges | One row per service with its chip; water usage in **kgal** with its own total; the services subtotal plus taxes, fees and credits equals **This run's charges** equals the sum of the 7 drafts |
| TC-5 *(payments)* | Payments and balances | previous balance − payments − credits + this run's charges = amount due, to the cent; *How it will be paid* rows add back to amount due; `00107`'s $120.00 appears in payments applied (TC-10 of US-BIL-037 answered *Apply to this bill*) |
| TC-6 *(warnings link back)* | Warning *1 bill: Electric base $0.00. See* | Opens Check on the *Base charge $0.00* tag |
| TC-7 *(failed to draft)* | After US-BIL-038 TC-3 | *See breaks* opens **Failed to draft** (account · what failed · fix in ↗ · **Retry**); Retry drafts it and the summary moves |
| TC-8 *(gate)* | Tick four of five | Sign off disabled; the fifth enables it; one `bill_run_releases` row on Sign off with each confirmation recorded separately |
| TC-9 *(every link goes somewhere — plan T7)* | Click every link and button on the step | Each opens a list, a tag, a panel or a named screen in a new tab; the test fails on one that changes nothing |

**4 · Test Data** — `BBR`.

**5 · Data Fields / Mapping** — sign-off summary read (plan A8/B19); `bill_run_releases` (BR-BIL-056/058).

**6 · Acceptance** — Given Scope's figures, Then every Who-is-billed line adds back to them; Given any See, Then Not in this run opens filtered.

**7 · Finance Calculation** — the summary restates the drafts; the reconciliations above are the arithmetic (10 = 7 + 3; 12 = 8 + 4).

**8 · Open Questions** — None.

---
id: US-BIL-040
epic: EP-BIL-01
module: billing
screens: [S31]
wave: 3
status: ready
blocked_by: []
depends_on: [US-BIL-039, US-BIL-005]
journeys: [J72]
rules: [BR-BIL-004, BR-BIL-055, BR-BIL-1054, BR-BIL-034]
golden_tests: []
finance_calc: none
---
### US-BIL-040 — Send: one acknowledged send, one failure breaks one bill, the run's leftovers go to Pending billing

**1 · Details** — As a Billing Clerk, I want **Send** to show the run, its total, delivery split, autopay count, template and warnings, *Final once sent. Changes need a credit note.*, and a tick *I checked the totals* that unlocks **Send N bills**; then a *Sending — n of N* progress; then **Sent** — bills sent, total, due, delivery queued, meter reads locked, bills not sent named with *See breaks*, **View run**, **Print paper bills** — and below it the **Not in this run** list now *in Pending billing* (changes rows 8, 40; images `32`–`35`). One bill's failure breaks only that bill (row 8, built).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-004 | Issued bills are immutable | CONFIRMED |
| BR-BIL-055 | A partial run issues the clean bills and holds the rest | CONFIRMED |
| BR-BIL-034 / 1054 | At Send every account not in this run enters Pending billing, a left-out one with reason *left out by clerk* | CONFIRMED / 2026-09-30 |

**3 · Test Cases** (`BBR`, after US-BIL-039 TC-8)
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Send step, unticked | **Send 7 bills** disabled; `POST …/send` without the acknowledgement refused |
| TC-2 | Tick, press Send twice quickly | One issue pass: 7 invoices, 7 numbers, 7 balanced journal entries, 7 delivery rows, one audit row per send |
| TC-3 *(one breaks)* | `00102`'s GL account missing for trash at issue | **6 bills sent**; *1 bill not sent. AC-2026-00102: GL account missing for trash. See breaks*; the 6 are issued |
| TC-4 *(pending)* | After Send | Pending billing holds `00105` and `00106` (their blocking reasons) and `00109` with reason **left out by clerk**; Not in this run reads *… in Pending billing* with *0 days* waiting |
| TC-5 *(isolation)* | Lone Star Ridge posts Send for Brazos Bend's run | 404 |

**4 · Test Data** — `BBR`.

**5 · Data Fields / Mapping** — issue (US-BIL-005); Pending billing rows (BR-BIL-034, plan DB3 reason).

**6 · Acceptance** — Given the acknowledgement, Then exactly one issue pass runs; Given a failed bill, Then only it is not sent.

**7 · Finance Calculation** — N/A (issue restates drafts).

**8 · Open Questions** — None.

---
id: US-BIL-041
epic: EP-BIL-01
module: billing
screens: [S31, S30]
wave: 3
status: ready
blocked_by: []
depends_on: [US-BIL-040, US-BIL-006]
journeys: [J72]
rules: [BR-BIL-1054, BR-BIL-015, BR-BIL-034, BR-BIL-005, BR-BIL-1039]
golden_tests: []
finance_calc: none
---
### US-BIL-041 — Not in this run and catch-up: every account left out is listed on the run, and billed later from it

**1 · Details** — As a Billing Clerk, I want every account the run did not bill — blocked, held by a decision, nothing to bill, left out by me — and every unit with nobody to bill, listed on the run with its reason, filterable by group and selectable, so that I can fix and re-check before sending, and after sending start a **catch-up run** for the ones now ready or **leave them for the next cycle** (BR-BIL-1054; changes rows 40–42; images `29`, `35`, `36`). PO: *"then the accounts are not bill or theya re on hold or ecluded in this run - we need to show them as a list or somthing and allow to run ran them later"*. On Sign off: filters **All · Blocked · Held · Nothing to bill · Nobody to bill** (+ *Left out*), header counts accounts and units apart, **Fix and re-check N** / *Fix in Check* per row, *When you send, these go to Pending billing.* After Send: **Start catch-up run for N** (a child run of this run, same period, through Check · Sign off · Send — `pending.create_catch_up_run`, `POST …/catch-up`, `bill_runs.parent_run_id`), **Leave for next cycle**, **Open Pending billing**.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-1054 | Not in this run; left out by clerk; catch-up; leave for next cycle | CONFIRMED — PO 2026-09-30 |
| BR-BIL-015 / 005 | Catch-up = child run, key = parent key + scope (accounts) — never a colliding re-run 🔒 | CONFIRMED |
| BR-BIL-1039 | The next run opens at the last billed read | CONFIRMED |

**3 · Test Cases** (`BBR`)
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(on Sign off)* | Open Not in this run | Header **3 accounts · 1 unit**; rows `00105` Blocked *No plan* (+2 more problems), `00106` Blocked *reading with no unit*, `00109` *Left out by clerk*, and the unit 1416 Elm St · Unit B *Nobody to bill* with no checkbox and *Add account ↗* |
| TC-2 *(fix in Check)* | *Fix in Check* on `00105` | Check opens on `00105`'s first tag with its Fix account panel |
| TC-3 *(catch-up)* | After Send, fix `00105`'s plan, disputed read and bounced payment; select `00105` and `00109`; **Start catch-up run for 2** | A child run **BR-xxxx-A** of this run, Sep 1 – Sep 30, `parent_run_id` set, key = parent key + those accounts; it goes through Check · Sign off · Send and bills exactly 2; a second press starts no second child for the same accounts |
| TC-4 *(catch-up refuses a still-blocked account)* | Include `00106` (still unitless) | `00106` is checked in the child run and blocked there; the other accounts bill |
| TC-5 *(leave for next cycle)* | Select `00106`, **Leave for next cycle** | It stays in Pending billing marked for the next cycle; the October run for Cycle 3 includes it |
| TC-6 *(no usage lost — OI-B3)* | `00106` left for next cycle, then the Oct 1 – Oct 31 run with its unit fixed | Its bill covers usage from its LAST BILLED read (Aug 31) through Oct 31 — Sep's usage is not lost and not billed twice (BR-BIL-1039) |
| TC-7 *(put back before send)* | On Check, **Put back** `00109` before pricing | It leaves Not in this run and is priced |

**4 · Test Data** — `BBR`.

**5 · Data Fields / Mapping** — Pending billing (`PendingQueuePage.tsx`, BR-BIL-034), reason *left out by clerk* (plan DB3); child run (`bill_runs.parent_run_id`).

**6 · Acceptance** — Given an account not billed, Then it is on the run's list with its reason and reaches Pending billing at Send; Given a catch-up, Then it is a child run through all steps.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — OI-B3 (proved by TC-6).
