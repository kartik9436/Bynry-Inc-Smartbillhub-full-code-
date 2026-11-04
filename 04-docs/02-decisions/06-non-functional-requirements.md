# B6 — Non-Functional Requirements

> **Part B — human/finance judgment.** Drafted from the prototype as a starting point. Every line marked **PLACEHOLDER** must be confirmed by a human before it is authoritative. Nothing here is extracted fact unless it cites the UI.


> No NFR numbers exist in the design. Values below are **CONFIRMED as indicative defaults (2026-08-07)** — treat as planning targets, **not hard limits**. Refine with ops as real data arrives.

| NFR | Indicative default | Note |
|---|---|---|
| Accounts per tenant | **up to 40,000** — the ICP ceiling (T5), indicative, **not** a hard cap | PO ruling 2026-09-06; tiers T7 ≤3,000 · T6 3–10K · T5 10–40K in scope, T4/T3 later. Pricing tiers (Starter/Growth/Scale) are commercial, not technical ceilings; design must not hard-limit |
| Tenants (platform) | **1,000 (PO capacity scenario, 2026-08-08)** — planning target, not a cap | capacity math §above |
| Peak load | monthly bill-run windows per cycle; end-of-month payment spikes | product |
| Bill-run batch target | full cycle (~1,100 accts) rated+invoiced in < 5 min (indicative) | eng |
| Financial data retention | 7 years (typical US utility/tax) | finance/legal |
| Meter-read retention | 3–7 yrs (reprice/audit) | product/regulatory |
| Audit-log retention | 7 years | legal |
| RPO | 1 hour | ops |
| RTO | 4 hours | ops |
| Backups | daily full + PITR (WAL) | ops |
| Uptime target | 99.9% | product |
| Data residency | US | product/legal |
| Concurrency (staff) | **10–20 staff/tenant maximum** at up to 40,000 accounts; do not architect a hard ceiling | PO ruling 2026-09-06, verbatim: *"Upto 40K utilities we are sesing 10 to 20 staff memeber maximum"*. **Read *"1–2 staff/tenant"* until that date.** Portal concurrency is a separate, platform-level figure — `NFR-38` |

**Design rule:** connection/account counts are **indicative for capacity planning only** — no table, index, or code path may enforce a maximum account count per tenant.

### The customer profile these numbers describe (PO ruling 2026-09-06)

**SMARTBillHub's ideal customer is a NORTH AMERICAN utility of up to 40,000 accounts, run by at
most 10–20 staff.** The PO thinks in tier names and uses them in conversation, so they are
recorded here as vocabulary a lane can look up:

| Tier | Accounts | Status |
|---|---|---|
| **T7** | up to 3,000 | **IN SCOPE NOW** |
| **T6** | 3,000 – 10,000 | **IN SCOPE NOW** |
| **T5** | 10,000 – 40,000 | **IN SCOPE NOW** |
| **T4** | 40,000 – 80,000 | later, *"once we get critical mass"* |
| **T3** | 80,000 – 160,000 | later |

Verbatim: *"Curently our focus is T7, T6 T5 utilities in North america … we dont have to wory
about T4 and T3 right now; If we keep the architecture flexible we will able to later make the
changes"*. Full ruling and consequences: `12-governance/02-decision-log.md`, 2026-09-06,
*"THE ICP, CORRECTED THE SAME HOUR"*.

⚠ **THE OLD PROFILE — *"under 3,000 connections, 1–2 staff"* — WAS NOT WRONG ABOUT
CONNECTIONS, IT WAS THE BOTTOM TIER.** T7 is still in scope; the ceiling moved **3,000 →
40,000**. The **staff** half was false and is now **10–20**, ruled.

⚠ **T4/T3 REQUIRE NO BUILDING AND ONE DISCIPLINE, WHICH MAKES THREE EXISTING RULES
LOAD-BEARING RATHER THAN TIDY.** The PO's entire requirement for those tiers is *"keep the
architecture flexible"*, and **`NFR-5` (no hard per-tenant caps), `NFR-3` (universal server
pagination, no unbounded lists) and the design rule immediately above ARE that flexibility.**
The standing instruction is therefore a negative one: **nobody may add a per-tenant cap, an
unpaginated list, or an account maximum that would have to be removed when T4 arrives.**

⚠ **AND `NFR-3` IS ALREADY BREACHED IN AT LEAST FOUR SHIPPED PLACES THAT CITE THE OLD CEILING
BY NAME AS THEIR JUSTIFICATION** — `GET /outstandings` (*"Unpaginated ON PURPOSE … one row per
DEBTOR at a utility under 3,000 connections"*, and it **sorts in Python rather than SQL**),
`GET /cheques`, the bank-reconciliation batch list and their two front-end mirrors. Each was
correct at T7 and is **13× short of T5**. Filed as `DEF-PAY-4221`.

⚠ **AND ONE CODED NUMBER NOW SITS BELOW THE ICP CEILING — THE ONLY HARD LIMIT THIS RULING
ACTUALLY MEETS (`DEF-BIL-4224`).** `billing/run_jobs.py` sets
`MAX_ACCOUNTS_PER_RUN_DEFAULT = 25_000` and `refuse_if_oversized()` enforces it **at the door,
before any bill is drafted** — so a **40,000-account T5 tenant billing one cycle over all its
accounts is REFUSED**. It is not a wall: the ceiling is operator-configurable
(`BILLING_MAX_ACCOUNTS_PER_RUN`, and `0` switches it off), and `run_jobs.py` already names the
two legitimate ways to shrink a run — scope it to fewer services, or run it per cycle, since
*"a cycle IS the population split"*. **What needs deciding is whether a T5 tenant is expected
to bill in one cycle at all**; at the measured ~170 ms an account, a full-tenant run is roughly
**113 minutes** on a worker with two slots. ⚠ **The test that ratifies 25,000 still passes and
always will, while its stated reason is now inverted:** `test_cr051_tc13`'s docstring argues
*"25,000 is eight times the largest utility this product is for — CLAUDE.md's own first line
says under 3,000 connections"*, and 25,000 is now **0.625×** the largest utility. **A
ratified-figure test asserts the constant and defends it in prose, so the premise can move
without any assertion changing colour.**

⚠ **RULED 2026-09-14 — THE CEILING STAYS AT 25,000 AND THE QUESTION ABOVE IS ANSWERED, SO DO
NOT RE-RAISE IT (`DEF-BIL-4224` CLOSED).** PO verbatim: *"(b) Keep 25,000, fix the stale
comment only - generally utilities will devide them into nilling cycles and hence 25k limit is
good"*. ⚠ **The recommendation put to them was (a), raise the default above 40,000, and it was
WRONG for a reason no measurement in this pass could have reached: a utility divides its
accounts into BILLING CYCLES, so no single run ever covers the whole book.** A 40,000-account
T5 tenant bills, say, four cycles of 10,000, and 25,000 is headroom for the largest cycle
anybody sensibly configures. **So a number being smaller than the ICP's ceiling is not by
itself a breach** — the argument for (a) reasoned from `40,000 > 25,000` without asking whether
one run ever sees 40,000 accounts. **What changed is the COMMENT and nothing else:**
`run_jobs.py` and `test_cr051_tc13`'s docstring now argue from cycles rather than from book
size, the constant and every assertion are untouched, and `NFR-5` stands not breached exactly
as recorded above. ⚠ **A SECOND SITE CARRIES THE SAME RETIRED SENTENCE AND THIS RULING DOES NOT
REACH IT:** `billing/print_set.py`'s `MAX_BILLS_PER_PRINT_SET_DEFAULT`, whose scope can be
*every issued bill* rather than one cycle — filed separately as `DEF-BIL-5235`, still open.

⚠ **`NFR-5` IS NOT BREACHED, AND THAT WAS CHECKED RATHER THAN ASSUMED.** The bill-run ceiling
is a per-RUN operational limit, not a per-tenant account cap. Every use of `max_accounts` on
the `plans` table was read: `tenancy/models.py` calls it a *"commercial tier bound, NEVER
enforced (B6)"*, `tenancy/selectors.py` says the same, and **no code path gates on it** — it
reaches screens and tests only. So the PO's single requirement for T4/T3, that the
architecture stay flexible, is intact.

⚠ **THE PO DEFERRED THE OBVIOUS FOLLOW-UP THEMSELVES, AND IT IS NOT OPEN BUSINESS:** *"I also
understand at large utility process to handle many of these workflow will changes, many more
users will be involev and thing like that - but that is future problem."* Do not re-raise it.

## NFR Register — session harvest (PO-directed documentation, 2026-08-08)
Every NFR that emerged as a RATIFIED rule across the module sessions, consolidated with citations. These are law (unlike the indicative planning table above).

### Volume & throughput
- **NFR-1** All outbound email/SMS written to the platform queue table, dispatched in tenant-config batches (default 500) at provider pace — generation speed and sending speed decoupled (BR-NOT-005; PO: "ESP/Twilio will not send such emails quickly").
- **NFR-2** Bulk imports are STAGED with per-row validation, never direct writes: reads, assets (10,000-row cap), accounts (10,000), payments/lockbox; pattern generation ≤3,000 units/run (BR-MET-038, BR-AST-034, BR-CUS-051, BR-PAY-023).
- **NFR-3** Server pagination universal; NO unbounded list endpoints (BR-MET-055, IS-5); CSV exports server-streamed, >50,000 rows rejected (BR-SHL-016/IS-9).
- **NFR-4** Bill runs + heavy jobs are async with progress + per-item results; catch-up sub-runs never collide (scope-keyed idempotency, BR-BIL-015).
- **NFR-5** No hard per-tenant account/connection caps anywhere (design rule above; connection counts commercial only).

### Data lifecycle & retention
- **NFR-6** Meter reads: 2-year hot window; monthly partitions detach to cold storage via AUTOMATIC scheduled job; 7-year total (BR-MET-055).
- **NFR-7** Financial records, audit log, rate/plan versions: 7 years (B4 R1 confirmation; planning table above).
- **NFR-8** Template versions pinned by any bill are retained FOREVER (undeletable — BR-BIL-026/027).
- **NFR-9** Generated scheduled-report files: 3 days default, tenant-config (IS-11; PO: "anyway we will email them").

### Isolation, security, privacy
- **NFR-10** RLS FORCE on every tenant table; `app.tenant_id` set server-side only; zero-tolerance isolation suite = release blocker (CLAUDE.md #1).
- **NFR-11** Identity is PER-TENANT: same email = separate users per tenant; uniqueness (tenant, email); no cross-tenant SSO v1 (BR-IDN-029, B2 r11).
- **NFR-12** Password policy: min 8 upper+lower+number, no forced expiry, last-5 block; lockout 5 fails → 15 min; sessions idle 60m / absolute 12h / keep-signed-in 30d; IP allowlist w/ self-lockout guard; ALL 2FA v2 (BR-IDN-025/026/020/028).
- **NFR-13** High-sensitivity PII app-layer encrypted (EIN, TOTP secrets), gov-ID tokenized last-4, masked display always; disk encryption for the rest (OQ-016 closure, BR-CUS-045).
- **NFR-14** v1 sends NO staff auth emails (admin temp passwords); customer email W6 via BYO/ESP (BR-IDN-021, OQ-073).

### Financial integrity (the non-negotiables)
- **NFR-15** Append-only: issued invoices/lines, payments (once cleared), journal entries, template versions, opening buckets — corrections are NEW rows (credit note/rebill, reversing entries, supersede chains) (CLAUDE.md #4, BR-BIL-004, BR-PAY-002, BR-LED-003, BR-MET-053).
- **NFR-16** Idempotency everywhere money enters or leaves: bill runs (tenant+cycle+period), payment webhooks (webhook_key), imports (file+tags), accounting exports (recorded batches, re-run blocked) (BR-BIL-005, BR-PAY-003/028, OQ-044, BR-LED-004).
- **NFR-17** Ledger: posting service SOLE writer, balanced pairs, dimension columns; subledger tie-outs rendered live; ANY drift = red flag + RELEASE BLOCKER (B1, BR-LED-001/007).
- **NFR-18** Every money action writes audit_log (CLAUDE.md #7); posting date ≠ clearing date always kept, basis labeled on every KPI/report (BR-PAY-021, BR-REP-001, IS-11).
- **NFR-19** Money = NUMERIC(18,6) + CHAR(3); round half-up 2dp at finalization only; no hand-typed amounts on any bill (CLAUDE.md #2, B4.4, BR-BIL-019/020).

### Interoperability
- **NFR-20** Accounting handover: idempotent summary-JE exports w/ per-account export codes (QBO/Xero/CSV/IIF) + drill-back (BR-LED-004/014). Bank side: BAI2/CSV/OFX/QBO/QFX imports + Plaid seam (A14).
- **NFR-21** All comms providers behind seams: BYO mailbox (small), transactional ESP (volume), Twilio SMS (v1.1), print vendor; no Stripe tenant-side v1 (OQ-074, OQ-015).

### Localization & accessibility
- **NFR-22** Tenant regional formats (currency/number/date/time), timezone-correct timestamps, US market/residency; historical bills never restate on settings change (IS-8, A1 Company addendum).
- **NFR-23** IS-10 accessibility basics; IS-11 download contracts (Excel-safe CSVs).

## Capacity math (PO-directed 2026-08-08) — which tables grow largest, and the rules that follow
Planning mix (PO scenario): 1,000 utilities — 800 × 100 accts · 180 × ~4,000 · 20 × 40,000 = **1.6M accounts platform-wide**; monthly billing; ~2 meters/account; WE-1-shaped bills (~12 lines); manual reads v1.

| Table | rows/acct/yr | platform/yr | 3 years | largest tenant (40k) 3yr |
|---|---|---|---|---|
| **journal_lines** (dimensioned double-entry) | 216 | 346M | **1.04 BILLION** | 26M |
| **invoice_lines** | 144 | 230M | 691M | 17M |
| **audit_log** | 72 | 115M | 346M | 8.6M |
| **outbound_messages** | 48 | 77M | 230M | 5.8M |
| meter_reads (manual; 2-yr hot per BR-MET-055) | 36 | 58M | 173M (hot ≈115M) | 4.3M |
| allocations · payments · invoices | 18/14/12 | 29/22/19M | 86/67/58M | ≤2.2M |
| **All tables, 3 years** | | | **≈2.7B rows** | |

**Findings:** the maximum-row table is NOT notifications/audit/reads — it is **journal_lines** (double-entry with dimensions multiplies every money event ×~18/account/month), with invoice_lines second. All within PostgreSQL 16 capability **only with the rules below**. AMI/interval reads (future integrations) would multiply meter_reads ×30–60 — the partition+archival design absorbs this by construction, but AMI onboarding re-runs this math first (rule NFR-27).

### Rules (NFR-24..30)
- **NFR-24 Partition rule:** any table projected >50M rows/yr platform-wide MUST be partitioned (monthly, tenant-aware strategy = Eng-Lead 🔒) — applies to journal_lines, invoice_lines, audit_log, outbound_messages, meter_reads, integration_run. No exceptions. ⚠ **AMENDED 2026-09-03 (`CR-069` wave A, `BR-INT-039`, B2 Addendum r22): `integration_run` — the integrations module's run record, one row per attempt against an outside system — JOINS the set, YEARLY on `started_at` like the two financial line tables (PO 2026-08-12 ruled the yearly granularity for those; this table takes the same shape for the same reason — at 60,000 accounts email alone writes about 720,000 run rows a year).** It is a NEW table of an approved change, not a projection error in the original five; the original wording (`monthly`) is already SUPERSEDED for `invoice_lines` and `journal_lines` and is not the rule for this one either. `core/partitioning.py` carries it in `REGISTRY` and `ACTIVE_TABLES`, `integrations/0001` creates it partitioned, and G16 ties the three out. Recorded in `12-governance/02-decision-log.md` 2026-09-03.
  - ⚠ **AMENDED 2026-08-12 by PO ruling (OQ-107), verbatim: _"Nod to split both by year"_.** The word **monthly** above is **SUPERSEDED for `journal_lines` and `invoice_lines`**, which are partitioned **BY YEAR**. `audit_log` and `meter_reads` remain **monthly**; `outbound_messages` keeps its ratified PO exemption of 2026-08-11. The option put to the PO was by month — this sentence is why — and they answered by year; at this product's declared ceiling of utilities under 3,000 connections a year of lines is a small partition and there are fewer of them to maintain. **The requirement is amended, not breached**, and `10-scripts/gates/g16_partition_coverage.py` parses this clause, so its wording is load-bearing.
  - ⚠ **THE PARTITION KEY WAS NEVER RULED** — the PO settled granularity, not the column. Both tables range over `created_at`; OQ-193 records why (the alternatives are a NULLABLE column and a book date that lives on another table and is mutable while a draft) and what it costs.
- **NFR-25 Financial tables are NEVER pruned** (journal_lines, invoice_lines, invoices, payments, allocations — 7yr law); older-than-2yr partitions may move to cold storage/cheaper tablespace but stay queryable for reprice/audit/drill-back.
- **NFR-26 Rollup-on-close:** at period close (BR-LED-006), trial-balance/report rollups materialize per (tenant, period, GL, dimensions) — closed periods are immutable so rollups never invalidate; dashboards/reports read rollups, never scan a billion raw lines. Eng-Lead mechanics 🔒.
- **NFR-27 AMI gate:** enabling interval/AMI read ingestion for a tenant requires re-running this capacity math and Eng-Lead sign-off on the partition plan (30–60× read volume).
- **NFR-28 audit_log:** monthly partitions; >2yr partitions to cold storage; 7yr total (matches reads pattern).
- **NFR-29 outbound_messages** (CONFIRMED — PO NL-1/NL-2, 2026-08-08): rendered BODIES prunable after 90 days (tenant-config) — every document REPRODUCIBLE from pinned template version + data (BR-BIL-026); queue/status rows archive after **18 months** (PO). `notice_history` keeps 7yr regardless.
- **NFR-30 Index discipline:** every hot query path uses tenant-leading composite indexes; no cross-tenant scan exists anywhere (RLS + index design together). Eng-Lead 🔒.
Planning-table correction: max observed tenant size for design = **40,000 accounts** (supersedes the "~5,000+" indicative note; still NO hard caps per the design rule).

⚠ **THIS MODEL ALREADY COVERS THE WHOLE OF THE CURRENT ICP — NOTHING NEEDS RE-RUNNING
(2026-09-06).** The ICP ruling of that date sets the ceiling at **40,000 accounts (T5)**, and
**40,000 is exactly the largest tenant this math already models** (`20 × 40,000` in the mix
above). The two numbers are the same, so the projections, the `journal_lines` finding and
`NFR-24`'s partition rule all stand unchanged at the new profile. **This is recorded because
the first reading of that ruling concluded the opposite** — it briefly took the ceiling to be
80–100K and was about to file the re-run as a defect. **A re-run becomes necessary if and only
if T4 (40–80K) or T3 (80–160K) is taken on**, and `NFR-27` already sets the precedent for what
that costs: re-running this capacity math plus **Eng-Lead sign-off** on the partition plan.
Until then there is nothing owed here.

### Document & file storage (PO-directed; DF battery CLOSED 2026-08-08 — all per recommendation)
- **NFR-33 Two document classes:** (1) **GENERATED** (bills, receipts, notices, statements, reports) are REPRODUCIBLE — pinned template version + data re-render byte-equivalent on demand (BR-BIL-026); stored only transiently (report files 3d/IS-11, message bodies 90d/NL-1). (2) **STORED ARTIFACTS** — anything that cannot be re-rendered or is legally executed: e-signed agreements (BR-CUS-044), uploaded exemption certificates (BR-CUS-063), remittance receipts (BR-LED-019), account documents (BR-CUS-036), import source files (compliance stamps BR-MET-017/BR-PAY-023), tenant logos. DF-1 CONFIRMED.
- **NFR-34 Upload guards:** type allowlist (PDF/PNG/JPG/CSV + config) · size cap default 10MB tenant-config (DF-2 CONFIRMED) · ~~malware scan on every upload before acceptance~~ — ⚠⚠ **SUPERSEDED (PO 2026-09-22 / 2026-09-23 → no malware scan on upload).** PO, verbatim, 2026-09-22: *"once you remove the virus check - you will ahveonly two cases verified or rejected in case of rejected show the reason in short to user why it is rejected."* · and 2026-09-23: *"please remove virus scan chek user don't wan't it. we have ask remove it before why you did not remove it?"*. No upload is scanned: the scanner built under `BR-SHL-253` on 2026-09-13 (middleware on every upload, failing closed) was DELETED on 2026-09-23 with its settings, compose service and refusal keys (`DEF-SHL-6347`), because on a host with no scanner it refused every file. The allowlist and the size cap above are the whole upload guard · every upload/view/download of sensitive classes writes audit_log.
- **NFR-35 Legal-instrument class:** e-signed agreements + import source files are **WRITE-ONCE** (immutable object lock), retention 7yr with their financial records (DF-3 CONFIRMED). ⚠ **THE OBJECT-LOCK HALF IS SUSPENDED 2026-10-02 BY `CR-160-BRC10` (PO, verbatim: *"we dont want this to be enabled right now - dont lock it"*): no file is object-locked, legal files included, and no file carries an expiry tag.** The lock stays a setting (`DOCUMENT_STORAGE_OBJECT_LOCK_MODE`, default `NONE`) and applies, when switched on, only to files written after that moment. The product still deletes nothing — the `stored_documents` row stays write-once — but someone with direct access to the storage account could delete or overwrite a file.
- **NFR-36 Volume:** file storage is GB-scale, not row-scale — e-signed ~160k/yr × ~200KB ≈ 32GB/yr + import files ≈ 48GB/yr platform-wide at the B6 planning mix; no per-tenant hard caps (design rule), storage monitored per tenant.
- v1 uploads are STAFF-mediated; **consumer upload portal = v2** (DF-4 CONFIRMED: "in v2 b"). ⚠ **SUPERSEDED FOR THE NEW-SERVICE REQUEST, PO 2026-10-01** (`CR-158-BRC10`; decision log *"CUSTOMERS MAY NOW UPLOAD DOCUMENTS FROM THE PORTAL"*). PO, verbatim: *"you need to allow customer to upload documents and save those document to server for that Utility - and then clark should able to view those document in new request"*. An applicant on the portal's new-service request may attach **PDF, JPG or PNG — the type read from the file's bytes, never the browser's claim — up to 10 MB each and 5 per application**; the files are held on the draft (RLS `FORCE`, `portal/0011`), handed to the document store only when the application is SENT, and opened by the clerk through a route that sends `Content-Disposition`, `nosniff` and a no-script policy. Upload, view and download each write `audit_log`. **Every other portal flow keeps DF-4** — the report's photo (`CWP-006`), the question's photo (`CWP-054`) and the hardship certificate (`CWP-065`) — until it is ruled.
- **NFR-37 Localization extensibility (PO):** adding a language or currency is a DATA change (catalog + template variants + ISO row), never a code change; W0 shell wiring carries i18n from day one.

### Customer portal load — the assumption that changed (PO, 2026-09-03)

⚠ **THE PLANNING TABLE AT THE TOP OF THIS FILE SAYS *"Concurrency: low (1–2 staff/tenant)"*, AND THE PORTAL BREAKS THAT.**
That line was true when every user was a clerk. `CR-068` puts the utility's *customers* on the same
product. PO, verbatim: *"we might have multiple utilities / multiple tenants, their users will login or
use it as guest portal there can be 500 users or 100 users from various tulities using customer portal
in such case our design should allow them to login as per response time we agreed and also it should
not hamper performance of back office user"*.

- **NFR-38 Portal concurrency is a platform figure, not a per-tenant one.** Plan for **500 concurrent
  portal users spread across many tenants** — guests and signed-in customers together — while the back
  office is in use. The old *1–2 staff per tenant* line stays true of STAFF and is no longer the
  platform's concurrency assumption. No hard cap is coded anywhere (NFR-5's design rule still holds).
  ⚠ **AMENDED 2026-09-06 BY THE ICP RULING — THE LAST SENTENCE BUT ONE IS NOW HALF FALSE.** This
  rule correctly separated PORTAL concurrency from STAFF concurrency and left the staff figure at
  *1–2*; the ICP ruling of 2026-09-06 replaces **the staff figure only** with **10–20 staff per
  tenant** at up to 40,000 accounts (PO, verbatim: *"Upto 40K utilities we are sesing 10 to 20 staff
  memeber maximum"*). **`NFR-38` is EXTENDED, not contradicted:** the separation it draws is exactly
  right and is what makes the correction a one-number change; the platform-level 500-concurrent-portal
  -user figure is **untouched**, and `NFR-39`, `NFR-40` and `NFR-41` stand exactly as written.
  ⚠ **What DOES change is that the two figures are now the same order of magnitude**, so *"a portal
  request may never degrade a back-office request"* (`NFR-39`) is protecting a busier back office than
  when it was written — its three named isolations (own queue and worker, own connection budget, own
  rate limits) are unchanged in shape but no longer face a two-person load on the staff side.
- **NFR-39 A portal request may never degrade a back-office request.** The two share a database and a
  process today, which is exactly the risk. **The portal's work is isolated from the staff app's at
  three named places, and each is a build task, not an aspiration:** its own **queue and worker** (the
  pattern `celery-billing` and `celery-integrations` already establish, enforced by G59's clauses), its
  own **connection budget** so a portal traffic spike cannot exhaust the pool the staff app draws from,
  and its own **rate limits** per tenant as well as per address, so one utility's busy day is not
  another utility's outage.
- **NFR-40 Every portal read is bounded before it is written.** No unbounded list, no unindexed filter,
  no query whose cost grows with a tenant's size on a page a customer can refresh: a signed-in customer
  sees their own account, and *their own* is the index. This is NFR-3 and NFR-30 restated where it now
  bites hardest, and a portal endpoint added without its index is the defect this rule exists to catch.
- **NFR-41 The guest surface is the cheapest thing in the product.** It is unauthenticated, so it is
  what a stranger can point traffic at. A guest lookup does one indexed read and no join across a
  tenant's history; the throttle (`BR-CWP-022`, sixty a minute) and the lockout (`BR-CWP-023`) are the
  floor and not the whole answer.

⚠ **THE RESPONSE-TIME TARGET THE RULING REFERS TO DOES NOT EXIST IN THIS REPOSITORY.** The PO's words
are *"as per response time we agreed"*, and a search of B6, the specs and the module folders finds no
agreed figure — no p95, no latency budget, nothing. **It was not invented here, and it is no longer missing.** The PO handed the question back — *"Figure that out and
write it as response time specifications"* — so it is worked out from the customer's side in
**`04-docs/05-modules/15-portal/11-response-times.md`** (`CR-071`), which closes `OQ-CWP-1510`. **NFR-42:** that file
is the portal's latency law — a guest lookup 400 ms at the 95th percentile, the balance screen 600 ms, signing in 900 ms
because a password check must burn real time, a payment's own half 800 ms with the processor's half never silent, all of
it at NFR-38's 500 concurrent users with the back office unaffected. ⚠ **Its figures are OURS by delegation, not a PO
ruling — never cite them as agreed by the PO.**
