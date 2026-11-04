# EP-AUD-02 — S61 audit viewer + per-entity Audit tabs (one store, many windows, zero cross-tenant rows)

**Module:** audit · **Wave:** W1 (needs US-SHL-006 table core + real W0 rows; S8 Security's "View audit log →" target goes live here) · **Screens:** S61 (owned) · windows on S21 / premises + unit detail / S50 (owning modules render; audit provides the read service) · S28/S29 compliance-stamp surfaces (referenced) · **Status:** draft

## Scope
**In:** the **S61 audit-log viewer** per the A1 addendum (PM design for OQ-029, provisional layout; tenant-scoped-only = PO-CONFIRMED): filter bar (date range · actor · module · entity type/id · action type), IS-2/3/4/5-conformant table (When · Actor · Action · Entity linked · Summary · Source), row → **detail drawer** (JSON diff, request metadata, related approval ref), read-only for **System Admin + Executive**, entries from S8 Security and entity-tab "full log" links; the **entity-scoped read service** behind every per-entity Audit tab (account S21 — rendered by US-CUS-011; premises/unit — BR-MET-045/048 tabs; asset S50 — US-AST-006; template/JE audit rows surface through their packs' cited rows) — **windows into the same store, never copies**; **CSV export** under IS-9/IS-11 + BR-SHL-016 guards, itself audited; **compliance-stamp views** for import batches (reads BR-MET-017 · payments BR-PAY-023 · assets BR-AST-023 · accounts BR-CUS-051) — stamps render read-only, audit rows link to their batch.
**Out:** the owning modules' tab RENDERING stories (US-CUS-011, US-AST-006, EP-MET-01 — already authored; not re-authored here) · the write path (EP-AUD-01) · archive search + report feed (EP-AUD-03) · Source-column/request-metadata storage anchoring (GAP AUD-D2, Eng-Lead batch) · security-event catalog expansion (SC-3 — PENDING, not decided).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S61 Audit log viewer | — (no free-text search in the A1 S61 design; the entity type/id filter is the lookup path) | date range · actor (user select) · module · entity type/id · action type (create/update/status/money/approval/auth) — AND-combined, URL-persisted (IS-4) | When desc (newest first — corpus precedent, US-CUS-011 TC-5) | When · Actor · Action · Entity | 6 default (When · Actor · Action · Entity · Summary · Source) / + Entity type · Event code raw (IS-5, BR-SHL-027 persisted) | open detail drawer (read-only — no mutating action exists) | — (none; read-only screen, no multi-select) | CSV (IS-9/IS-11 under BR-SHL-016; export itself audited) |

## Stories

---
id: US-AUD-004
epic: EP-AUD-02
module: audit
screens: [S61, S8]
wave: 1
status: draft
blocked_by: []
depends_on: [US-AUD-001, US-AUD-003, US-SHL-006]
journeys: [J6]
rules: [BR-AUD-007, BR-AUD-009, BR-AUD-002, BR-AUD-013]
golden_tests: []
finance_calc: none
---
### US-AUD-004 — S61: the tenant-scoped audit-log viewer (filter bar, table, roles)

**1 · Details** — As a System Admin or Executive, I want the S61 viewer (A1 addendum, PM design for OQ-029) — filter bar **date range · actor (user select) · module · entity type/id · action type (create/update/status/money/approval/auth)**, table **When (tenant TZ per Regional/IS-8) · Actor · Action · Entity (linked to its detail screen) · Summary (one-line before → after) · Source (UI/API/job — renders when its storage anchor lands, AUD-D2)** — server-paginated on the shared table core (US-SHL-006; IS-2/3/4/5), newest-first, hot-window default with the archive path in US-AUD-008 (BR-AUD-013), so that "who did what, before/after" is answerable in one place. **Read-only:** no edit, no delete, no row mutation — the screen has no such affordance and the store has no such path (BR-AUD-002). **Roles:** System Admin + Executive (A1); others are denied server-side (UI gating convenience, A4). **Tenant-scoped ONLY — the zero-tolerance case:** the viewer shows the current tenant's rows exclusively; RLS-enforced; **no cross-tenant view even for support** (OQ-029 closure, PO Q&A R4). Entry: S8 Security "View audit log →" (US-IDN-010 TC-10 target) · entity Audit tab "full log" links (US-AUD-005). Exit: row → drawer (US-AUD-005), export (US-AUD-006). Module filter resolves via the catalog's entity→module mapping (US-AUD-002).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AUD-009 | S61: read-only; System Admin + Executive; filter bar (date range/actor/module/entity/action type); columns When · Actor · Action · Entity · Summary · Source; row → drawer; CSV export; entries from S8 Security + Audit-tab full-log links. | CONFIRMED — A1 S61 addendum (PM design for OQ-029; layout provisional per A1) |
| BR-AUD-007 | Tenant-scoped-only: current tenant's rows exclusively; RLS-enforced; no cross-tenant view even for support. | CONFIRMED — OQ-029 closure (PO Q&A R4) + B2 §3 + NFR-10 |
| BR-AUD-002 *(shared)* | No edit/delete anywhere on the viewer — append-only store. | CONFIRMED — A1 S61 + B2 §audit comment |
| BR-AUD-013 | List queries: server pagination, 2-yr hot-window default, explicit archive search only (US-AUD-008); no unbounded endpoint. | CONFIRMED — NFR-28 ("matches reads pattern") applying BR-MET-055 (PO RD-13) + NFR-3 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex Reed opens S61 from S8 Security | Newest-first rows, 25/page (IS-2), 6 default columns; When renders America/Chicago (IS-8); filter state URL-persisted (IS-4) |
| TC-2 | Filter: action type `money` + date range Aug 1–9 + module billing | Only billing money rows in range (`invoice.issued`, `invoice.voided`…) — AND-combined chips with clear-all (IS-4); the J6 fixture chain surfaces under action type `approval`+`money` |
| TC-3 | Filter: entity type `invoice` + entity id BL-2608-018410; Entity cell clicked | The bill's full trail (issued → corrected chain); Entity link routes to the S30 bill detail |
| TC-4 | Evan Ruiz (Executive) opens S61 | Full read access (A1: System Admin + Executive), no mutating affordance anywhere |
| TC-5 *(negative — role)* | Priya Menon (Billing Clerk) requests S61 by URL and by API | Server-side denied (A4 — UI gating is convenience); permission-denied state per IS-7/A18 |
| TC-6 *(negative)* | Query with date range From > To | Inline validation, no query fired; URL grammar falls back per BR-SHL-011 on hand-edited invalid params |
| TC-7 *(immutability)* | DOM/API probe for any edit/delete/annotate affordance or endpoint on S61 rows | None exists — read-only by construction (BR-AUD-002); PATCH/DELETE on the audit API return 405 |
| TC-8 *(isolation — the zero-tolerance case)* | J. Okafor (Lone Star Ridge admin) opens S61; separately a forged request carries a Brazos Bend entity id | **NEVER another tenant's rows**: LSR sees only LSR rows; the forged query returns empty under RLS — asserted by the isolation suite (release blocker, NFR-10); support has no cross-tenant view either (OQ-029 closure) |

**4 · Test Data** — Brazos Bend: 12,400 rows incl. run 07-A's 1,124 `invoice.issued`, the CC-2608-007 J6 chain, `billing_settings.updated` (Alex Reed Aug 9 10:42 CT), `period.closed` July. Actors: Alex Reed (System Admin), Evan Ruiz (Executive), Priya Menon (Billing Clerk — negative). Lone Star Ridge: 210 rows, J. Okafor. Filters fixture per TC-2/3. TZ: America/Chicago.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Filter bar | S61 | A1 S61 addendum | query over `audit_log` (+ catalog class/module mapping) | mixed | user-input | AND-combined; IS-4 URL state |
| When | S61 | A1 S61 + IS-8 | `audit_log.created_at` → tenant TZ render | ts | computed-display | Regional settings |
| Actor | S61 | A1 S61 | `.actor_user_id` → user display name; NULL → job name from payload | text | computed-display | system actors labeled |
| Action + class | S61 | A1 S61 + US-AUD-002 | `.action` + catalog class | text/enum | computed-display | catalog-resolved |
| Entity (linked) | S61 | A1 S61 | `.entity_type` + `.entity_id` → owning screen route | link | computed-display | tenant-scoped route |
| Summary (one line) | S61 | A1 S61 ("before → after, one line") | derived from `.before`/`.after` | text | computed-display | masked values as stored (BR-AUD-006) |
| Source (UI/API/job) | S61 | A1 S61 addendum | **GAP AUD-D2** — no B2 column; renders when anchored | enum | system-derived | not invented; column present, honest-empty until anchor |
| Role gate | S61 | A1 S61 ("System Admin + Executive") | server-side permission check (A4) | — | reference-data | UI gating convenience only |
| Hot-window scope | S61 | BR-AUD-013 | default query = last 2 yrs of partitions | interval | system-derived | archive via US-AUD-008 only |

**6 · Acceptance**
- Given S61, Then filters, columns, sort, pagination and URL state behave per the capability-matrix row, tenant-TZ rendered.
- Given any role outside System Admin/Executive, Then access is denied server-side.
- Given any mutation probe, Then no edit/delete path exists on screen or API.
- Given any cross-tenant probe, Then zero foreign rows return — ever.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None (Source-column anchoring = candidate-OQ note in the pack report).

---
id: US-AUD-005
epic: EP-AUD-02
module: audit
screens: [S61, S21, S50]
wave: 1
status: draft
blocked_by: []
depends_on: [US-AUD-004]
journeys: [J6]
rules: [BR-AUD-009, BR-AUD-010, BR-AUD-006]
golden_tests: []
finance_calc: none
---
### US-AUD-005 — Detail drawer (JSON diff) + the entity-scoped read service behind every Audit tab

**1 · Details** — As staff tracing a change, I want (a) the **S61 row detail drawer** — full before/after values as a **JSON diff view**, request metadata (renders when anchored — AUD-D2), and the **related approval reference** where the payload carries one (correction approval BR-BIL-014, refund approval BR-PAY-014, void approval r12 #14) — and (b) the **entity-scoped read service** that every per-entity Audit tab consumes: `audit_for_entity(entity_type, entity_id)` over `ix_audit_entity`, newest-first, read-only — the **account S21 Audit tab** (rendered by US-CUS-011), **premises + unit detail Audit tabs** (BR-MET-045/048), **asset S50 Audit tab** (BR-AST-019/US-AST-006), and template/JE audit visibility where their packs cite rows (BR-BIL-027 pinned-version locks, BR-LED-015 journal rows) — so that every tab is a **window into the ONE store**, never a per-module copy, and each tab's **"full log" link** opens S61 pre-filtered to that entity (A1 S61 entry note). Owning modules render their tabs (their stories stand; nothing re-authored); this story owns the service + drawer. Masked payload values render exactly as stored (BR-AUD-006 — the drawer never unmasks; full values never left the server, BR-CUS-045). Entry: S61 row click · entity tab load. Exit: drawer closed / S61 pre-filtered.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AUD-009 *(drawer half)* | Row → detail drawer: full before/after (JSON diff), request metadata, related approval/OQ reference if any. | CONFIRMED — A1 S61 addendum |
| BR-AUD-010 | Per-entity Audit tabs are read-only WINDOWS into audit_log scoped to the entity, served by the audit read service; each links to S61 pre-filtered ("full log"). | CONFIRMED — BR-MET-045/048 (PO PU-14/16/17) + BR-AST-019 (PO R4-B10) + A1 S61 entry note (Account detail → Audit tab "full log" link) |
| BR-AUD-006 *(shared)* | Drawer renders masked values exactly as stored; no unmask path exists. | CONFIRMED — BR-CUS-045 + NFR-13 + pii-inventory |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Drawer on `billing_settings.updated` (Alex Reed) | JSON diff highlights `late_grace_days` 10 → 15 only; actor/when/entity header; no other fields shown as changed |
| TC-2 | Drawer on `correction.approved` (CC-2608-007) | Related approval reference renders (approver, case link) from the payload — the J6 trail drills to its approval in one click |
| TC-3 | Account A-10432 Audit tab (S21, rendered by US-CUS-011) | Account-scoped rows newest-first via the entity service (`ix_audit_entity` path); "full log" opens S61 pre-filtered entity_type=account, entity_id=A-10432 (URL state per IS-4) |
| TC-4 | Asset M-4021 S50 Audit tab · premises P-00421 tab | Same service, asset-/premises-scoped (BR-AST-019, BR-MET-048); rows identical to S61 filtered — one store, zero copies (count equality asserted) |
| TC-5 | Drawer on the DOB-correction row | before `06/****` → after `11/****` — masked forms only; response body scan confirms no unmasked value crossed the wire (BR-CUS-045) |
| TC-6 *(negative)* | Drawer on a row whose entity was hard-deleted (unused charge code, IS-1 delete) | Drawer renders fully from the audit payload; Entity link degrades to a labeled non-link — history never 404s |
| TC-7 *(immutability)* | Probe the drawer + entity service for annotate/redact/edit endpoints | None exist — windows are read-only (BR-AUD-010); the service exposes no write |
| TC-8 *(isolation)* | J. Okafor calls the entity service with Brazos Bend's A-10432 | Empty under RLS — entity-scoped reads are tenant-scoped first (US-CUS-011 TC-8 pair; zero-tolerance) |

**4 · Test Data** — Rows: `billing_settings.updated` (4-field and 1-field variants), CC-2608-007 chain w/ approver Nora Patel, DOB correction on A-10432, `asset.updated` M-4021 (multiplier 1.0 → 40.0, BR-AST-012 fixture), `premises.created` P-00421. Deleted-entity fixture: charge code "Gate remote fee" hard-deleted at used_by=0 (BR-TEN-034), its `charge.deleted` row remains. Isolation: J. Okafor / LSR.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| JSON diff view | S61 drawer | A1 S61 ("full before/after values, JSON diff view") | render of `.before`/`.after` | jsonb render | computed-display | changed keys highlighted |
| Request metadata | S61 drawer | A1 S61 | **GAP AUD-D2** — renders when anchored | — | system-derived | honest-empty until anchor |
| Related approval ref | S61 drawer | A1 S61 + BR-BIL-014/BR-PAY-014/r12 #14 | payload-carried approval refs → linked | link | computed-display | when present |
| Entity read service | S21/S50/premises/unit tabs | BR-AUD-010 + B2 §4 `ix_audit_entity` | `audit_for_entity()` service fn (read-only) | rows | system-derived | tenant-scoped; newest-first |
| "Full log" link | every Audit tab | A1 S61 entry note | S61 route pre-filtered (IS-4 URL grammar) | link | computed-display | entity filter pre-set |
| Deleted-entity render | S61 drawer | IS-1 + append-only trail | payload-only render, non-link entity label | text | computed-display | never 404 |

**6 · Acceptance**
- Given a row, Then the drawer shows the full JSON diff with masked values as stored and any approval reference linked.
- Given any entity Audit tab, Then its rows equal S61 filtered to that entity — one store, and its full-log link lands pre-filtered.
- Given a deleted entity, Then its history still renders from payloads.
- Given cross-tenant or write probes, Then empty results and no write endpoints.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.

---
id: US-AUD-006
epic: EP-AUD-02
module: audit
screens: [S61, S29]
wave: 1
status: draft
blocked_by: []
depends_on: [US-AUD-004]
journeys: [J6]
rules: [BR-AUD-014, BR-AUD-016, BR-AUD-001]
golden_tests: []
finance_calc: none
---
### US-AUD-006 — CSV export under BR-SHL-016 guards (itself audited) + compliance-stamp views for import batches

**1 · Details** — As a System Admin producing evidence (dispute, PUC inquiry, SOC 2 walkthrough), I want **S61 CSV export** per the A1 addendum ("Export CSV (IS-9)") executed through the shell export path (BR-SHL-016 contract, US-SHL-008 consumed): server-streamed under the caller's RLS context, **50,000-row cap** ("Narrow your filters to export"), current filters + visible columns (IS-9/IS-5), IS-11 CSV contract (UTF-8, one snake_case header row, ISO dates, tenant-TZ timestamps w/ offset, filename `{tenant}_{report}_{period}_{basis}_{generated}.csv` — basis segment `event-time` since no money basis applies) — and **every audit export writes its own audit row** (`audit.exported`: who, filter state, row count — BR-SHL-016's money-export audit applies a fortiori: audit payloads contain money actions). And I want the **compliance-stamp views**: audit rows for import-batch commits link to their batch's stamp — reads (BR-MET-017: batch no, source, file+SHA-256, uploaded_by/at, session+IP, certification — S28 step 5/S29 block), payments (BR-PAY-023: file+SHA-256, file+tags idempotency), assets (BR-AST-023: batch + audit), accounts (BR-CUS-051 staging) — stamps render **read-only in their owning surfaces** (owning modules' stories stand); S61's window shows the batch audit row + a link to the stamp; import source files are WRITE-ONCE, 7-yr (NFR-35). Entry: S61 Export · batch audit row → stamp link. Exit: file streamed; stamp viewed at its owner.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AUD-014 | S61 export: CSV per IS-9/IS-11 under BR-SHL-016 (streamed under RLS, 50k cap, filters + visible columns); every audit export writes its own audit row. | CONFIRMED — A1 S61 ("Export CSV (IS-9)") + IS-11 (PO 2026-08-08) + BR-SHL-016 (PO R1 A2); self-audit clause derived from BR-SHL-016's money-export audit (audit rows contain money actions) |
| BR-AUD-016 | Import-batch compliance stamps (reads/payments/assets/accounts) render read-only at their owners; batch audit rows link to them; import source files WRITE-ONCE 7-yr. | CONFIRMED — BR-MET-017 + BR-PAY-023 (PO Lane B-2) + BR-AST-023 (PO R4-A5) + BR-CUS-051 (PO AC-6) + NFR-35 (DF-4), consolidated |
| BR-AUD-001 *(shared)* | The export action itself is a confirmed, toasted, audited action. | CONFIRMED — B9 IS-6 + CLAUDE.md #7 spirit per BR-SHL-016 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex exports S61 filtered to action type `money`, Aug 2026 (1,131 rows) | Streamed CSV: visible columns only, snake_case single header, tenant-TZ timestamps w/ offset, filename `brazosbend_audit-log_2026-08_event-time_20260809T1655.csv`; masked values exported exactly as stored |
| TC-2 | The export completes | New row `audit.exported` (actor Alex Reed, filter state, row count 1,131) — visible in S61 itself moments later |
| TC-3 | Read-import batch RD-2608-01's `read_batch.committed` row opened | Drawer links to the S29 compliance block: file `brazosbend_reads_08A.csv`, SHA-256 `9f2c…41ab`, uploaded_by Marcus Vega, session+IP, certification — rendered read-only at its metering owner (BR-MET-017) |
| TC-4 | Payment import batch PB-2608-03 audit row | Links to the payments stamp (file+SHA, file+tags idempotency key) — BR-PAY-023 surface; same pattern for assets (BR-AST-023) + accounts (BR-CUS-051) batches |
| TC-5 *(negative)* | Export request matching 68,000 rows | Rejected with "Narrow your filters to export." (BR-SHL-016 50k cap); no partial file |
| TC-6 *(negative)* | Attempt to re-upload/replace RD-2608-01's source file | Blocked — import source files are WRITE-ONCE (NFR-35); the stamp is immutable evidence |
| TC-7 *(immutability)* | Attempt any edit on a stamp field or on the `audit.exported` row | No path exists — stamps read-only at owners; audit rows append-only (BR-AUD-002) |
| TC-8 *(isolation)* | J. Okafor triggers an export while a forged request names Brazos Bend filter params | Export executes under LSR RLS context (BR-SHL-016 — "under the caller's tenant context"); zero Brazos Bend rows in any file |

**4 · Test Data** — Export fixture: 1,131 money rows Aug 2026; oversize fixture 68,000 rows (18 months unfiltered). Batches: RD-2608-01 (`brazosbend_reads_08A.csv`, SHA-256 `9f2c…41ab`, Marcus Vega, Aug 3 2026, session 10.20.4.18) · PB-2608-03 (lockbox CSV, SHA `c81d…0f27`, tags aug-2026+chase) · asset batch AB-2607-02 · account batch ACIB-2606-01. Actors: Alex Reed; J. Okafor (isolation).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Export execution | S61 | A1 S61 + BR-SHL-016 | streamed query under RLS (US-SHL-008 path consumed) | file | computed-display | 50k cap; filters + visible columns |
| CSV contract + filename | file | IS-9/IS-11 | one header row, ISO dates, TZ offsets, `{tenant}_{report}_{period}_{basis}_{generated}.csv` | file | computed-display | basis segment `event-time` |
| Export audit row | S61 | BR-SHL-016 ("money-table exports write audit_log") | `audit_log` `audit.exported` (who/filters/row count) | jsonb | system-derived | append-only |
| Reads stamp link | S61 drawer → S29 | BR-MET-017 | `read_import_batches` stamp fields (metering-owned) | link | computed-display | read-only at owner |
| Payments stamp link | S61 drawer | BR-PAY-023 (r12 #3) | `payment_import_batches` file+SHA + tags | link | computed-display | read-only at owner |
| Assets / accounts stamp links | S61 drawer | BR-AST-023 + BR-CUS-051 (r9 #4) | batch records at owners | link | computed-display | read-only at owner |
| Source-file immutability | — | NFR-35 (DF-4) | write-once object lock, 7-yr | file | integration | no replace path |

**6 · Acceptance**
- Given an export, Then the file honors IS-9/IS-11 + the 50k guard, is streamed under the caller's RLS, and an `audit.exported` row exists.
- Given an import-batch audit row, Then its compliance stamp is one link away, read-only, with its write-once source file.
- Given oversize/replace/edit attempts, Then each is rejected by its guard.
- Given tenants, Then no file ever contains another tenant's rows.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.
