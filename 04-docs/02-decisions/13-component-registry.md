# B13 — Component Registry & BUILD CHECKPOINT (PO-directed 2026-08-09)

> PO: *"I will first build a list of all frontend and backend components and mark what is available and what is not available, make it as check point and then move to the build."*
> This document + **13a** (the per-screen map) form the **checkpoint the PO reviews before any feature code is written**. Status cells flip to ✅ only when a component merges through the G1–G12 gates — so this file is also the live build tracker, updated in the same PR that lands each component.
> **Legend — Status:** ✅ available (built, gate-passed) · 🟡 partially available (exists as reference/library base; our wiring to build) · ⬜ not available (to build) · 🔒 sensitive path — **as amended by PO 2026-08-09: AI authors it implementing signed law; file flagged HUMAN-REVIEW-PENDING + human-review-ledger row (G7); human ratifies later**. **Source:** `library` = adopted off-the-shelf base + our thin config · `custom` = written by us · `generated` = produced by a tool from a contract.

## 1 · Frontend shared components (`src/components/` — ONE implementation each, B8; LAW 0 applies)

| ID | Component | What it does | Governed by | Source | Status | Wave |
|---|---|---|---|---|---|---|
| FE-01 | AppShell | Sidebar/topbar, bell, global search, tenant context, route frame | BR-SHL-001..009 | custom | ✅ 2026-08-09 (US-SHL-001..004 shell; accessibleModules per BR-SHL-025) | W0 |
| FE-02 | DataTable | THE one table: server pagination/sort/filter, capability row, saved column sets, **expandable rows** | IS-2..5 · BR-SHL-010..015 · B14 rules 12/20 | library (TanStack Table) + custom | ✅ 2026-08-09 (US-SHL-006/007; vitest 31 green, gates 10-PASS; page sizes 50–1000 default 50) · **AMENDED 2026-08-23 (CR-029 RC-W3-T0) — `config.renderExpanded?: (row) => ReactNode` adds a disclosure capability: an expander column, one `aria-expanded` button per row named for its identity value ("Expand PRM-001"), and Expand-all/Collapse-all in that column's header cell. Absent = the capability does not exist (BR-SHL-010) and the markup is BYTE-IDENTICAL to before, asserted against `src/components/__fixtures__/DataTable.baseline.html`. Interactive proof in `DataTable.dom.test.tsx` (jsdom); vitest 122 files / 2100 green** | W0 |
| FE-03 | FilterBar | Declarative filter chips feeding DataTable/report params | IS-4 | custom | ✅ 2026-08-09 (US-SHL-007; chips + URL grammar) | W0 |
| FE-04 | ConfirmDialog | THE one destructive-action confirm with consequence messaging | IS-6 | custom | ✅ 2026-08-09 (composes ModalShell+WorkingButton; consequence verb never OK) | W0 |
| FE-05 | FormModal | Standard modal form frame (zod schema, server-error rendering) | IS-1 · B8 forms | custom | ✅ 2026-08-09 (US-SHL-009; ModalShell + field kit + zod + envelope errors) | W0 |
| FE-06 | WizardFrame | Multi-step wizard with review-before-commit step (bill run, imports, onboarding) | A18 · BR-BIL run pattern | custom | ✅ 2026-08-09 (US-SHL-010; single-flight commit, rail, failed-retry) | W0 |
| FE-07 | StateFrame | Loading skeleton / empty / error / permission-denied — identical everywhere | IS-7 · A18 | custom | ✅ 2026-08-09 (US-SHL-011; gates 9-PASS, vitest 14/14, tsc+eslint clean) | W0 |
| FE-08 | Toast | One toast system (every Settings modal fires one, A1 addendum) | A18 | custom | ✅ 2026-08-09 (US-SHL-012; FIFO queue + aria-live, TC-1..6 green) | W0 |
| FE-09 | KPIStrip | Dashboard/screen-top KPI tiles with date-basis labels | BR-REP-001 · S7/S36 | custom | ✅ 2026-08-09 (basis label type-required) | W0 |
| FE-10 | StatusPill | Status chips bound to semantic tokens (active/invited/overdue/…) | design system §12 | custom | ✅ 2026-08-09 | W0 |
| FE-11 | MoneyCell | Money display: 2dp, currency, never float, regional format | HR-2 · IS-8 | custom | ✅ 2026-08-09 (decimal-string, pad-never-round) | W0 |
| FE-12 | UnitCell | Consumption with explicit unit — never a bare number | HR-3 | custom | ✅ 2026-08-09 (unit required, compile-proven) | W0 |
| FE-13 | DateCell | Dates/timestamps in tenant TZ + regional format | IS-8 | custom | ✅ 2026-08-09 (tenant TZ; calendar dates never shift) | W0 |
| FE-14 | DownloadButton | THE one download control (CSV always, PDF where formatted) | IS-11 · IS-9/10 | custom | ✅ 2026-08-09 (CSV always, XLSX unrequestable) | W0 |
| FE-15 | ImportStager | Staged bulk import UI: upload → validate → preview counts → commit | OQ-044 pattern · BR-MET-012.. | custom | ⬜ | W1 |
| FE-16 | DetailTabs + EntityHeader | Entity page frame: header (name/status/flags banner) + tab set incl. AuditTab | A1 detail screens · BR-AUD | custom | ⬜ | W1 |
| FE-17 | AuditTab | Per-entity audit trail tab (one implementation, every entity) | EP-AUD-02 | custom | ⬜ | W1 |
| FE-18 | SchedulePicker | Cadence/recurrence picker (scheduled reports, plan installments) | S45 · BR-CUS-043 | custom | ⬜ | W4 |
| FE-19 | DocumentViewer | Rendered-document (PDF) preview: bills, notices, receipts | EP-BIL-06 · EP-NOT-03 | custom | ⬜ | W3 |
| FE-20 | Chart | Dashboard chart panels (one charting wrapper) | S7 · EP-REP-05 | library + custom | ⬜ | W5 |
| FE-21 | TemplateDesigner | Designer canvas + variable palette for bill/notice/receipt/contract templates — 13a finding: this repeats across 17 screens; promoted to ONE shared implementation (lifts shared-only coverage to 56/89 rows) | EP-BIL-06 · EP-NOT-02 · A19 | custom | ⬜ | W3 |
| FE-22 | ListPager | B14 rule 16's pagination footer for a list that is **not** the shared `DataTable` — a client-held array inside a wizard step or a read-only ops tab. Same four `table.pager.*` keys and the same `table-pager*` classes as `DataTable`, so every footer in the product is ONE thing. Ships `pageSlice()` beside it so the numbers the footer prints and the rows under it come from one place | B14 rule 16 · DEF-223 | custom | ✅ 2026-08-23 (CR-029 RC-W3-T7) — **added because DEF-223 measured rule 16 broken on FIVE tables at once and the footer was already implemented twice.** Consumers: SET-06.2 premises picker, SET-06.3 meter list, SET-07.2 route picker, S26 Routes, S27 Cycles. `WizardPager` in `RoutesCyclesWizards.tsx` is DELETED, not wrapped. Wizard SUMMARY tables stay exempt, by the rule's own words | W0 |

## 2 · Frontend infrastructure

| ID | Piece | What it does | Source | Status | Wave |
|---|---|---|---|---|---|
| FI-01 | Typed API client | Generated from the audited A11/OpenAPI schema — no hand-written fetch; handles the full HTTP contract (202 job-polling, 304/ETag, 429 backoff) | generated | ⬜ (after A11 audit) | W0 |
| FI-02 | TanStack Query setup | Server-state caching, invalidation by entity key, no optimistic money updates | library + custom | ⬜ | W0 |
| FI-03 | i18n catalog + switcher | Every string a key; en/es/es-MX/de/hi seed; customer documents stay server-rendered (TD-16) | library + custom | ⬜ | W0 |
| FI-04 | Router + RBAC guards | Route gating by 3-role matrix (UI convenience; server authoritative) | custom | ⬜ | W0 |
| FI-05 | Design tokens | Modernist tokens + semantic status colors | custom | ✅ ported 2026-08-09 — 73 tokens verbatim from `05-prototype/styles.css` → `07-frontend/src/styles/tokens.css` (W0 frontend lane) | W0 |
| FI-06 | Playwright harness | Browser E2E runner for the journey suite | library + custom | ⬜ | W0 |

## 3 · Backend shared components (platform services every module consumes)

| ID | Component | What it does | Governed by | Source | Status | Wave |
|---|---|---|---|---|---|---|
| BE-01 | RLS tenant-context middleware | Sets `app.tenant_id` per request; refuses tenant-table access without it | HR-1 | custom (**policies themselves 🔒**) | ✅ 2026-08-09 (🔒 AI-authored, HUMAN-REVIEW-PENDING, ledger row #1; 15 tests) | W0 |
| BE-02 | Error catalog module | The one exception→envelope mapping (AUTH/VAL/BIZ/SYS + BR refs, full HTTP series) | B12 §3 + r1 | custom | ✅ 2026-08-09 (20 codes, envelope handler, 404-never-403 byte-identical; 29 tests) | W0 |
| BE-03 | Audit writer | The one `audit_log` write contract (every money action, every refusal row) | EP-AUD-01 · HR-7 | custom | ✅ 2026-08-09 (EP-AUD-01 contract + BR-AUD-018 attempt rows; 10 tests) | W0 |
| BE-04 | RBAC decorator | Server-side 3-role enforcement; cross-tenant = 404 never 403 | A4 matrix · B12 r1 | custom | ✅ 2026-08-09 (A4 matrix classes + require_role; 12 tests) | W0 |
| BE-05 | Selector helpers | Pagination/sort/filter/ETag plumbing for every list endpoint | IS-2..5 · B8 layering | custom | ✅ 2026-08-09 (pagination 50–1000 clamp + param grammar; 26 tests; ETag rides lookup endpoints) | W0 |
| BE-06 | Number-series service | Tenant-scoped document numbering (accounts, bills, payments, batches, receipts) | BR-TEN-035 | custom | ✅ 2026-08-09 (BR-TEN-035 grammar, event-time, forward-only; 16 tests, §4 figures verbatim) | W0 |
| BE-07 | Jobs framework | Celery/Redis: idempotent resumable jobs, 202 + `/jobs/{id}` polling | TD-17 · NFR-16 | library + custom | ✅ 2026-08-09 (202+/jobs/{id} contract, scope-keyed idempotent, checkpoint resume; 17 tests) | W0 |
| BE-08 | Search indexer | Global search across FIFTEEN groups — BR-SHL-005 corrected 2026-08-09, amended 2026-09-03 (four → nine) and 2026-09-05 (`CR-073`, nine → fifteen: work orders · templates · parts · workforce · plans · charge codes). Sources live in the owning modules; the order is `core/search.py`'s `GROUP_ORDER` | BR-SHL-005/006 | custom | ✅ 2026-08-09 (per-module sources, ≤5/group, RBAC+RLS; 12 tests) | W0 |
| BE-09 | Bell event writer | ⚠ **RETIRED 2026-09-03 (`DEF-3422`)** — `core/bell.py` and `bell_events` are DELETED. The ✅ below was honest about its own scope and misleading about the product: the closed catalogue and the ten tests were real, and **no sink was ever registered and nothing outside those tests ever called `notify()`**, so the writer could not put anything in anybody's bell and the table held zero rows on every deployment. What the bell actually shows is delivered by notifications (`bulk_summary` → the outbound queue → `in_app.deliver_batch` → the mailbox the shell reads). Superseded, not lost: BR-SHL-026's five events are unchanged. | BR-SHL-026 | custom | ~~✅ 2026-08-09 (5-event closed catalog, advisory sink; 10 tests)~~ → REMOVED 2026-09-03; decision in `12-governance/02-decision-log.md` | W0 (events land with their modules) |
| BE-10 | Partition manager | Time-partitioning on the big five (audit_log first) + pruning jobs | NFR-24..30 (**migration ordering 🔒**) | custom | ✅ 2026-08-09 (🔒 ledger row; audit_log born partitioned, create-ahead+3, no drop API) | W0 |
| BE-11 | OpenAPI schema publisher | drf-spectacular schema, CI-diffed against audited A11 — drift is loud | TD-19 | generated | ✅ 2026-08-09 (spectacular wired, byte-stable export, A11+11b baseline) | W0 |
| BE-12 | Money kernel | Decimal-only NUMERIC(18,6) helpers + currency (**rounding rule itself 🔒**) | HR-2 · B4 | custom | ⬜/🔒 | W1 |
| BE-13 | Staged-import framework | Batch → per-row validate → preview → commit; file+SHA-256 stamp; per-row error report | OQ-044 model · BR-MET/PAY imports | custom | ⬜ | W1 (consumers: assets W1, reads/brownfield W2, lockbox/bank W4) |
| BE-14 | Rating engine core | Tier/TOU/seasonal/demand/capacity computation | B4 ❄ | **🔒 HUMAN** | 🔒 | W3 |
| BE-15 | Estimation engine | Estimated reads + true-up | BR-MET-026..030 | custom | ⬜ | W3 |
| BE-16 | Outbound delivery queue + dispatcher | ALL email/SMS written to table; dispatcher batches (default 500) at provider pace; quiet hours | BR-NOT-005 | custom | ⬜ | W3 |
| BE-17 | Template rendering engine | Server-side documents; template+version+language PINNED at issue forever | BR-BIL-025/026 · TD-16 | custom | ⬜ | W3 |
| BE-18 | Document storage adapter | Bills/receipts/notices/customer files: store, retention, size/type guards | NFR-33..36 · BR-SHL-031 | custom | ⬜ | W3 |
| BE-19 | Idempotency wrapper | Bill runs + inbound webhooks can never double-execute | HR-6 (**keys 🔒**) | custom | ⬜/🔒 | W3 |
| BE-20 | Posting service | The ONLY writer of journal lines; balanced pairs; dimension stamping | HR-5 · BR-LED | **🔒 HUMAN** | 🔒 | W3 contract · W5 consumption |
| BE-21 | Report engine + renderers | Streamed CSV (IS-9) + PDF skeleton (IS-10), 3-day retention | BR-REP · BR-SHL-016 | custom | ⬜ | W5 |
| BE-22 | Accounting export builder | Idempotent period export batches: QBO/Xero/IIF/CSV + export codes | BR-LED-004/017 | custom | ⬜ | W5 |
| BE-23 | Rollup builder | Rollup-on-close read models for heavy aggregates | TD-18 · NFR-26 | custom | ⬜ | W5 |
| BE-24 | Webhook receiver seam | Inbound payment webhooks (`webhook_key` dedupe) | BR-PAY-003 (**keys 🔒**) | custom | ⬜/🔒 | W7 |

## 4 · The gate scripts (G1–G12, B12 r2 — PO agreed 2026-08-09)

| ID | Piece | Status | Wave |
|---|---|---|---|
| GS-01..12 | The twelve merge-blocking gates | ⬜ | **W0 — the FIRST code written, before any feature code exists for them to guard** |

## 5 · What is available TODAY (honest baseline, 2026-08-09)

- ✅ **The documentation corpus** (pre-build certificate) — every packet's raw material: 227 stories, rules, TCs, test data, 300 journeys, frozen money math.
- ✅ **Verification harnesses already running**: trace lint · golden 33/33 · 245-row expectation generator · pairwise/wiring generators — these become parts of G2/G4/G12. ⚠ **Read "golden 33/33" as DOCUMENT self-consistency, which is what it is (DEF-2846, 2026-09-01):** the harness recomputes B4/B5's own figures and imports no application code. The **engine-verified** count is a different, smaller number — 14 of the 61 signed GTs, in `06-backend/tests/golden/` — and on this 2026-08-09 baseline it was zero, because no product code existed yet.
- 🟡 **Prototype** (`05-prototype/UtilityBilling.html`): layouts/copy/tokens as signed REFERENCE — its runtime is never ported (law).
- 🟡 **Library bases** adopted, not yet wired: Django + DRF (TD-19) · Celery/Redis (TD-17) · PostgreSQL 16 · React + TanStack + zod · Playwright.
- ⬜ **Every FE-/FI-/BE-/GS- row above**: no product code exists yet — all to build, in the waves shown.
- **13a** (companion file): the per-screen map proving every screen resolves to these shared parts + configuration.

## 6 · Checkpoint protocol

1. PO reviews B13 + 13a → acknowledges the checkpoint.
2. W0 opens: gate scripts (GS) → A11 conformance audit → FI-01 client generation → FE/BE W0 rows.
3. A status cell flips ✅ only in the same PR where the component merges through the gates; a feature story may not build on a component whose cell is not ✅ (the packet assembler checks this).

## 7 · The native field app's component kit (`field-app/src/components`) and the shared token module (`CR-187-BRC10`, recorded 2026-10-21)

**Source:** decision log 2026-10-21, *"The native field app (React Native) lives in this repo"* (conflicts 2 and 10) and *"Where the field-app design lives in the repo"* (*"token rules into `13-component-registry.md`"*); ADR-013, ADR-014, ADR-016; B14 rules 44 and 45; the design's *Stack* page, *Design tokens*.

### 7.1 · One token source, two renderers

| ID | Piece | What it does | Governed by | Source | Status | Phase |
|---|---|---|---|---|---|---|
| NT-01 | `shared/tokens.ts` (repo root) | **THE one source of design tokens for both apps** — a plain TypeScript object of colours, the spacing scale, radii, the two type ramps and the touch figures. The web reads it through `tokens.css` / the Tailwind theme; the native kit imports it directly. **Nothing in a native screen names a colour or a number directly.** | decision log 2026-10-21 conflict 2 · ADR-013 · B14 rules 44, 45 | custom | ⬜ — not on the branch at 2026-10-21 (`ls shared` finds nothing) | field-app Phase 1 (T-06) |
| NT-02 | Token drift test | Fails when a value in `shared/tokens.ts` differs from `07-frontend/src/styles/tokens.css`. **Until the web reads the module, this test is the only thing keeping the two the same** — the web tokens are not rewritten in the same change (conflict 2). It must print how many tokens it compared, so a test that read nothing cannot pass (law 7). | conflict 2 · law 7 | custom | ⬜ | with NT-01 |

**Renderers.** The web renders the tokens as CSS custom properties and Tailwind utilities (B14 rule 21). The native kit renders them as React Native style objects. **Two renderers of one set of values — never two sets of values.** Two design systems in one product is the repository's own named *"most expensive recurring fault"* (ADR-013). NativeWind may sit on top in the native app, but **never with its default theme**, whose own docs say it is not designed for native devices (design *Stack* page).

**What the token module holds, from the design** (the design's figures; where they meet a web token, the drift test decides and a mismatch is a defect, not a choice):
- **Colours:** `brand` `#ec3013` — the mark, the active nav indicator, section labels; **never** a button fill with white text (4.20:1). `brand-action` `#e12e13` — every primary button, 4.56:1 with white (rule R100, PO ruled). `text` `#201e1d` · `text-muted` `#605d5d` · page `#f3f2f2` / surface `#eae9e9` · card `#ffffff` / border `#d7d3d3` · success `#0f6e3a` / `#e6f4ec` · warning `#e08a1e` / `#fdf0d8` · danger `#e0341a` / `#fde4df` · info `#1d4ea8` / `#e6eefb`.
- **Spacing — seven values only:** 4 · 8 · 12 · 16 · 20 · 24 · 32. 6, 10, 14, 18 and 22 do not exist (B14 rule 44).
- **Radius:** 4 chip · 6 button · 8 card · 22 pill.
- **Three themes** from the one set: Light (default) · Dark · Sunlight (pure white, black text, 2–3px borders, one size up) — ADR-014.

### 7.2 · B14 rule 45's figures — what every native component is held to

| Figure | Value | Web equivalent |
|---|---|---|
| Screen title | **22** | 32 (rule 40) |
| Section head | **17** | 20–25 |
| Body | **15** | 15 |
| Label | **13** | 13 |
| Micro | **12** | 11 |
| Primary action | **56pt** | — |
| Any interactive control (floor) | **48pt** | — (desk 44pt, reversed) |
| Icon-only button | **48pt** | — |
| Most-tapped control (e.g. a quantity stepper) | **56pt** | — |
| Clear space between adjacent targets | **8pt** | — |

Font: Archivo, bundled (ADR-015). Scope: `field-app/` only; nothing on the web changes. **Rule 45 is UNENFORCED until the kit's own tests assert 22/17/15/13/12 and 56/48/8** — those tests are part of NK-01, not a follow-up.

### 7.3 · The native kit

| ID | Piece | What it does | Governed by | Source | Status | Phase |
|---|---|---|---|---|---|---|
| NK-01 | Native component kit, `field-app/src/components/` | The field app's ONE implementation of each UI piece. **Same component names and the same props as the web kit in `07-frontend/src/components/`** (`Button`, `Chip`, `StatusPill`, `MoneyCell`, `UnitCell`, `DateCell`, `StateFrame`, `Toast`, `ConfirmDialog`, `CountBadge`, `BuildVersion` …) where the web kit has one; a **different rendering** (React Native views, not DOM). A native-only piece (a stepper, a camera capture strip, the sync chip) is named once here and nowhere else. The per-screen list is `04-docs/05-modules/18-field-app/09-component-inventory.md`. | conflict 10 · B14 rules 43, 44, 45 · ADR-016 | custom | ⬜ — `field-app/src/` holds only `App.tsx` at 2026-10-21 | field-app Phase 1 (T-07) |

**Rules the native kit carries over unchanged:** money is read-only in the app and displayed at 2 decimals, a unit price up to 4 (CLAUDE.md hard rule 2; `MoneyCell`'s decimal-string contract, never float); a quantity always carries its unit (hard rule 3, `UnitCell`); no database id is ever a visible value (B14 rule 31); a destructive act is in the danger tier (B14); a piece of UI is a component, never inline code in a screen (B14 rule 43). **Same name, same props** is what lets a reader of one kit read the other — a native `MoneyCell` that took a number where the web one takes a decimal string would be two components wearing one name.
