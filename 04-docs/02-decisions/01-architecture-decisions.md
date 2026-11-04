# B1 — Architecture Decisions

> **Part B — human/finance judgment.** Drafted from the prototype as a starting point. Every line marked **PLACEHOLDER** must be confirmed by a human before it is authoritative. Nothing here is extracted fact unless it cites the UI.


## Decision: modular monolith (PLACEHOLDER — confirm)
A single deployable Django app organized into the nine modules from the schema, with enforced boundaries — **not** microservices in v1. Rationale: North American utilities of **up to 40,000 accounts** run by **at most 10–20 staff** (tiers T7 ≤3,000 · T6 3–10K · T5 10–40K), and a small engineering team; a monolith is cheapest to build and operate. ⚠ **This rationale read *"1–2-person utilities, < 3,000 connections/tenant"* until 2026-09-06** — see `12-governance/02-decision-log.md`, 2026-09-06, *"THE ICP, CORRECTED THE SAME HOUR"*. **The monolith decision is UNCHANGED by that ruling and none of its named triggers has fired:** a 13× move in the stated account ceiling is a change in tenant SIZE, not in the coupling between modules, and the extraction triggers below are about coupling and independent scaling. ⚠ **What the ruling does add is a standing constraint on this decision: T4 (40–80K) and T3 (80–160K) are deliberately deferred on the single condition that the architecture stays flexible, so no module may acquire a per-tenant account cap or an unpaginated list that would have to be removed to reach them** (`NFR-5`, `NFR-3`). Extract a module to its own service only on a **named trigger** (below).

## The nine modules (own their tables; see B2)
tenancy · identity · metering · rating · billing · payments · ledger · customers · notifications (+ audit as cross-cutting).

## Boundary rules (PLACEHOLDER — confirm/adjust)
1. A module owns its tables; **no other module writes them**. Cross-module reads go through a service function, not direct ORM reach-in.
2. Cross-module foreign keys are the reviewed "interface" set flagged with ⚠ in B2 §2.
3. Money posting flows one way: billing/payments → **ledger**. Nothing writes journal lines except the ledger module's posting service.
4. Rating is a **pure** module (inputs: reads + tariff version; output: priced lines); no side effects, so it stays unit-testable against B5 golden tests.

## Extraction triggers (when a module leaves the monolith) — PLACEHOLDER
- **rating/billing**: a bill run for the largest tenant exceeds the batch window (target in B6).
- **notifications**: send volume needs independent scaling / third-party rate limits dominate.
- **metering ingest**: AMI feeds arrive continuously rather than as periodic CSV.
Until a trigger fires, keep it in-process.

## Open
- Async jobs (billing run, imports, reconcile) need a worker (Celery/RQ?) — PLACEHOLDER, choose queue.
- Read models for multi-entity screens (A11): materialized views vs query services — PLACEHOLDER.

## Technology Decision Register (PO-directed documentation, 2026-08-08)
Status note: the monolith/boundary sections above marked "PLACEHOLDER — confirm" are **CONFIRMED AS-BUILT** — the entire ratified documentation set (14 modules, module-owned tables, cross-module FKs as the reviewed interface set, build waves W0–W8) is constructed on them; extraction triggers stay advisory for ops.

| TD | Decision | Source/status |
|---|---|---|
| TD-1 | React + Vite frontend, Modernist design tokens; files named for screens | ground truth (README/CLAUDE.md) |
| TD-2 | Django/Python modular monolith — one app per domain module, module-owned tables, services.py = only write path | B1 + ADR-005, as-built |
| TD-3 | PostgreSQL 16 + Redis | ground truth |
| TD-4 | Tenant isolation = Postgres RLS FORCE + `app.tenant_id` GUC set server-side from subdomain | B3, CLAUDE.md #1 |
| TD-5 | Per-tenant identity (same email = different users per tenant); server-side sessions | BR-IDN-029/B2 r11 (PO), BR-IDN-006 |
| TD-6 | uuidv7 PKs; citext emails; NUMERIC(18,6)+CHAR(3) money; soft-delete deleted_at; lookups-over-enums for tenant-facing vocabularies | B2 + BR-TEN-036 |
| TD-7 | Human-owned 🔒 code paths: RLS policies, rating engine, ledger posting, idempotency keys, money rounding, migration ordering — CODEOWNERS-enforced | CLAUDE.md |
| TD-8 | Platform outbound-message dispatcher service over one queue table (email/SMS/print); provider adapters behind one seam (BYO mailbox / transactional ESP / Twilio / print vendor) | BR-NOT-005 (PO volume ruling) |
| TD-9 | No Stripe tenant-side v1 (Bynry provision-only subscription handling); Plaid/payment rails = W7 | PO OQ-015, BR-PAY-015 |
| TD-10 | Accounting integration = file/API export batches (QBO/Xero/CSV/IIF), idempotent, export codes on chart | BR-LED-004/014 |
| TD-11 | Monorepo; numbered doc tree mirrors module map; docs one wave ahead of build | ADR-001/-005 |
| TD-12 | Governance CI: trace_lint (IDs, statuses, dependencies, journeys) + migration guard + isolation suite as release gates | 10-scripts, HUMAN-GUIDE §8 |
| TD-13 | QA: story TCs → 08-qa automation; Playwright E2E on journeys J1–J6; golden tests = billing-math contract (xfail→must-pass) | HUMAN-GUIDE §5, B5 |
| TD-14 | Docker compose dev (postgres:16 + redis); hosting decision open with ops (09-infra) | README |
| TD-15 | **File/document storage = object storage** (S3-compatible), per-tenant prefix isolation, US region; PostgreSQL stores ONLY metadata + SHA-256 + storage key (generalizing the account_documents pattern into one platform file service); access via app-mediated signed expiring URLs, role- and RLS-gated; server-side encryption; binaries NEVER in the DB | PO document-storage directive 2026-08-08; DF battery for scope choices | 
| TD-16 | **i18n rendering split**: (1) Staff UI strings render CLIENT-side from platform catalogs (one catalog source builds both bundles, NFR-37); language *selection* (tenant default + per-user override) is server-stored settings. (2) Customer DOCUMENTS (bills/notices/receipts/SMS) render SERVER-side, always — batch generation has no browser, and reprint-reproducibility (pinned template+version+language, BR-BIL-026/BR-NOT-006) demands one deterministic renderer. (3) Server-originated messages (validation errors, IS-6 consequence text) emit CODES + parameters; the UI translates — the server stays language-neutral, no translated strings in data. (4) Formats: client-side per locale for screens (IS-8); server-side for documents; CSV stays ISO per IS-11 regardless of language. (5) Tenant-entered reference data is NOT machine-translated — tenants author it in their language; only platform-seeded values ship translated in catalogs | PO localization Q, 2026-08-08 — derives from BR-SHL-030/BR-NOT-006/BR-TEN-042/NFR-37 |
| TD-17 | Async jobs = **Celery on Redis** (already in stack): bill runs, imports, dispatcher, archival, estimation — all idempotent + resumable per NFR-16; scheduled via celery-beat | Eng-Lead 2026-08-08 (closes B1 open item) |
| TD-18 | Read models = **query services first**; heavy aggregates via the NFR-26 rollup-on-close materializations — no ad-hoc materialized views in v1 | Eng-Lead 2026-08-08 (closes B1 open item) |
| TD-19 | API layer = **Django REST Framework (DRF) + drf-spectacular** (PO question 2026-08-09). Why DRF: most mature/boring choice (B8 LAW 0), largest hiring pool for the humans who will read this code, and its auth/pagination/throttling/content-negotiation cover the full HTTP contract (B12 r1 — incl. 429 throttles) out of the box. Usage constrained by B8 layering: serializers do validation/shape ONLY at `api.py`; business logic stays in `services.py`; drf-spectacular emits the OpenAPI schema that generates the typed frontend client — the schema is CI-diffed against audited A11, so contract drift is loud. django-ninja considered (native OpenAPI) — rejected on ecosystem/hiring size | Eng-Lead 2026-08-09 |

## Field app architecture decisions — ADR-006 to ADR-029 (`CR-187-BRC10`, recorded 2026-10-21)

The native field technician app (`field-app/`, React Native) carries its own architecture decisions, one ADR file each in `04-docs/04-adr/`, taken from the *SMART360 Next Field App* design canvas, page *Architecture decisions* (version of 2026-10-21). PO ruling: decision log 2026-10-21, *"Where the field-app design lives in the repo"*. ⚠ **COUNT: TWENTY-FOUR, NOT SIXTEEN OR SEVENTEEN.** The decision log entry says sixteen and the design's own *Work to be done* page (T-63) says seventeen; the *Architecture decisions* page itself reads *"Twenty-four decisions"* and carries AD-01 to AD-24, counted on 2026-10-21. The page grew after the other two counts were written. **ADR number = AD number + 5.**

| ADR | Design id | Decision | Status |
|---|---|---|---|
| ADR-006 | AD-01 | The field app is a cross-platform native app (React Native), not a web app | Accepted — **supersedes `BR-WRK-045`** (SUPERSEDED by `CR-187-BRC10`) |
| ADR-007 | AD-02 | The Work backend is untouched and fully reused | Accepted |
| ADR-008 | AD-03 | Almost no web front-end code ports — the design does | Accepted (corrects an earlier estimate) |
| ADR-009 | AD-04 | One clean line between offline and online | Accepted (R31 PO ruled) |
| ADR-010 | AD-05 | Handset storage is SQLite, not IndexedDB | Accepted; refined by ADR-022 |
| ADR-011 | AD-06 | Esri supplies the map | Accepted — PO 2026-10-04 (`OQ-WRK-12787`) |
| ADR-012 | AD-07 | iOS Critical Alerts need Apple's permission | Accepted and DONE — entitlement granted (PO 2026-10-21) |
| ADR-013 | AD-08 | One UI standard, two type ramps | Accepted — B14 rule 45 RATIFIED |
| ADR-014 | AD-09 | Three themes from one token set | Accepted |
| ADR-015 | AD-10 | Archivo is the font, deliberately | Accepted — PO 2026-10-20; closes `OQ-272` (a) |
| ADR-016 | AD-11 | Built for gloves, not for a desk | Accepted — B14 rule 45 RATIFIED |
| ADR-017 | AD-12 | A drawer, with quick tabs | Accepted in part — bottom bar superseded (R102, ADR-027; `OQ-FLD-12799`) |
| ADR-018 | AD-13 | Pushed screens, not stacked overlays | Accepted |
| ADR-019 | AD-14 | Flat work-order numbers; one status model | Accepted |
| ADR-020 | AD-15 | Asset types stay configurable | Accepted (R15 PO ruled) |
| ADR-021 | AD-16 | The web field app is kept during the build — a hold with a test | Accepted for the build; T-72 (retire or keep) DEFERRED until the native app is built (PO 2026-10-21) |
| ADR-022 | AD-17 | The handset database is SQLite, not a document store | Accepted |
| ADR-023 | AD-18 | Crashlytics for crashes, PostHog for use | Accepted AS AMENDED — Sentry superseded by Crashlytics (PO 2026-10-21) |
| ADR-024 | AD-19 | No customer data and no replay in telemetry; the technician may be named | Accepted AS AMENDED — technician identity allowed (PO 2026-10-21); R69 reversed |
| ADR-025 | AD-20 | Meter reading is a mode of the same app | Accepted (R73 PO ruled) |
| ADR-026 | AD-21 | Two credentials, not one | Accepted as design; **server endpoint does not exist yet**; sign-off OPEN (`OQ-FLD-12798`) |
| ADR-027 | AD-22 | One landing screen above both modes | Accepted as drawn; collision with R102 OPEN (`OQ-FLD-12799`) |
| ADR-028 | AD-23 | The photograph contract: declare with the data, bytes after | Accepted |
| ADR-029 | AD-24 | The tenant is the file, the technician is a column | Accepted (R131–R134 PO ruled); supersedes R114 |
