# EP-AUD-01 — The platform audit-write contract (one table, one write path, every module a writer-by-contract)

**Module:** audit · **Wave:** W0 (every W0 story already cites its audit row — the store + write path must exist first) · **Screens:** S61 (the store this epic feeds; headless otherwise) · **Status:** draft

## Scope
**In:** the **`audit_log` table** exactly per B2 §audit — append-only, RLS FORCE, monthly-partitioned (NFR-24/28), `tenant_id` deliberately not FK-constrained (survives tenant purge); the **event-code catalog** — platform-seeded, code-defined, dotted `entity.action` grammar as used across the authored corpus, each code mapped to one S61 action-type class (create/update/status/money/approval/auth — A1 S61 addendum); NOT tenant-extensible (extensibility unratified — see pack report); the **payload standard** — who/when/tenant/entity/action/before→after diff, PII-masked per BR-CUS-045 (audit payloads are MED class, pii-inventory); the **audit-write service** — the sole write path (B1 boundary), single lightweight INSERT, callable from async jobs (NFR-4), never fan-out, never a provider call. Tamper posture = **plain append-only + RLS** (B2 DDL comment + A1 S61 "no edit/delete anywhere"); no hash chain — no ratified doc supports one, none is invented here.
**Out:** every upstream WRITER story — tenancy settings audit (BR-TEN-016), billing/payments/ledger money rows (BR-BIL/PAY/LED packs), premises/asset audit (BR-MET-048, BR-AST-011/012/019), identity audit rows (BR-IDN-019/027) — **contracts consumed, not re-authored**; the viewer (EP-AUD-02); retention/archival (EP-AUD-03); exact DDL, partition mechanics, write-guarantee mechanics (sync-in-transaction vs guaranteed outbox) = **Eng-Lead 🔒** (B2 addenda pattern).

## Capability matrix (list screens only — B9 conformance)
No list screens in this epic (a table + a catalog + a service). S61's matrix row lives in EP-AUD-02.

## Stories

---
id: US-AUD-001
epic: EP-AUD-01
module: audit
screens: [S61]
wave: 0
status: draft
blocked_by: []
depends_on: []
journeys: [J5, J6]
rules: [BR-AUD-002, BR-AUD-007, BR-AUD-012, BR-AUD-015]
golden_tests: []
finance_calc: none
---
### US-AUD-001 — `audit_log`: the append-only, RLS-forced, monthly-partitioned trail table

**1 · Details** — As the platform, I want the `audit_log` table stood up exactly per B2 §audit — `id uuidv7 · tenant_id (NOT NULL, deliberately not FK-constrained: the trail must survive tenant purge) · actor_user_id (null = system job) · action · entity_type · entity_id · before/after jsonb · created_at`, PK `(tenant_id, created_at, id)`, `PARTITION BY RANGE (created_at)` monthly (NFR-24/28), index `ix_audit_entity (tenant_id, entity_type, entity_id, created_at)` for entity-tab lookups, RLS ENABLE+FORCE per the B2 §3 template — append-only with **no UPDATE/DELETE path anywhere** (B2 DDL comment; A1 S61 "no edit/delete anywhere"), block-mutation trigger per the B2 §3 immutability-trigger family, so that every module's audit rows from W0 day one land in one queryable, isolated, scale-ready store (B6 capacity: 115M rows/yr platform, 346M/3yr, largest tenant 8.6M — partitioning is NFR-24 law, "No exceptions"). Partition pre-create rides the same scheduled pattern as `meter_reads` (B2 §5: 3 months ahead). **Upstream writers (tenancy, identity, metering, assets, billing, payments, ledger, notifications, customers) are contracts consumed — their stories already cite their rows; nothing here re-authors them.** Exact DDL/trigger/partition mechanics = Eng-Lead 🔒. Entry: migration + scheduled partition job. Exit: table live, US-AUD-003 writes into it.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AUD-002 | `audit_log` is append-only: no UPDATE or DELETE path exists anywhere (UI, API, service, trigger-enforced); corrections/annotations are NEW rows. | CONFIRMED — B2 §audit DDL comment ("append-only, no update/delete") + A1 S61 addendum |
| BR-AUD-007 | RLS FORCE on `audit_log`; every audit read/write executes under `app.tenant_id`; no cross-tenant queryset exists. | CONFIRMED — B2 §3 (audit_log in the RLS apply-list) + NFR-10 + OQ-029 closure (PO Q&A R4) |
| BR-AUD-012 *(table half)* | Monthly range partitions on `created_at`; projected >50M rows/yr ⇒ partitioning is mandatory. | CONFIRMED — NFR-24/28 (B6 capacity math) |
| BR-AUD-015 | `tenant_id` is deliberately NOT FK-constrained — audit rows survive tenant purge; closed-tenant disposition beyond the 7-yr law stays OPEN (data-retention.md; SC-7 pending) and is NOT decided here. | CONFIRMED (DDL fact) — B2 §audit comment; disposition OPEN — data-retention.md + SC battery |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Migration + partition job run Aug 2026 | Table live, partitions `audit_log_2026_08` … `audit_log_2026_11` exist (3 ahead per B2 §5 pattern); RLS ENABLE+FORCE verified in `pg_policies`; `ix_audit_entity` present |
| TC-2 | W0 writer contract: Alex Reed saves Billing defaults (US-TEN-005 fixture, `late_grace_days` 10 → 15) | One row lands via US-AUD-003: tenant_id = Brazos Bend, actor = Alex Reed, action `billing_settings.updated`, before/after jsonb — the BR-TEN-016 contract satisfied by THIS table |
| TC-3 *(immutability — no UPDATE path)* | `UPDATE audit_log SET after = '{}' WHERE id = …` as table owner | Rejected by the append-only trigger (FORCE RLS + immutability family, B2 §3) — no code path or role can mutate a row |
| TC-4 *(negative — no DELETE path)* | `DELETE FROM audit_log WHERE created_at < now()` (any actor, incl. a mis-written cleanup script) | Rejected — deletion never happens in the operational path; partition DETACH by the EP-AUD-03 job is the only way data leaves hot storage |
| TC-5 *(isolation — zero-tolerance)* | Lone Star Ridge session (`app.tenant_id` = LSR) queries `audit_log` while Brazos Bend holds 12,400 rows | Zero Brazos Bend rows returned, ever; automated isolation-suite assertion (release blocker per NFR-10) |
| TC-6 *(negative)* | INSERT with `tenant_id` ≠ `app.tenant_id` (forged cross-tenant write) | Rejected by the RLS WITH CHECK clause — writes are tenant-scoped exactly like reads |
| TC-7 | Tenant purge drill (staging): Brazos Bend tenant row purged | audit_log rows REMAIN queryable by platform ops (not FK-cascaded) — the trail survives per the B2 design comment; further disposition = OPEN (BR-AUD-015), untouched |

**4 · Test Data** — Partitions: `audit_log_2026_08..11`. Brazos Bend (subdomain brazosbend, TZ America/Chicago): 12,400 rows seeded from W0 fixtures — `billing_settings.updated` (Alex Reed, Aug 9 2026 10:42 CT), `premises.created` P-00421 (Dana Whitfield), `invoice.issued` BL-2608-018410. Lone Star Ridge: 210 rows, actor J. Okafor. Volume check fixture: B6 math 72 rows/acct/yr → 40k-acct tenant ≈ 2.9M rows/yr.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Row identity | — | B2 §audit | `audit_log.id` uuidv7; PK (tenant_id, created_at, id) | uuid | system-derived | DB-2 |
| Tenant scope | — | B2 §audit + §3 | `audit_log.tenant_id` NOT NULL, no FK (survives purge) | uuid | system-derived | RLS USING + WITH CHECK |
| Actor | S61 Actor col | B2 §audit | `audit_log.actor_user_id` (null = system job) | uuid | system-derived | resolved to user for display |
| Action / entity refs | S61 | B2 §audit | `.action`, `.entity_type`, `.entity_id` | text/uuid | system-derived | catalog codes only (US-AUD-002) |
| Before/after | S61 drawer | B2 §audit + A1 S61 | `.before`, `.after` jsonb | jsonb | system-derived | payload standard US-AUD-002 |
| When | S61 When col | B2 §audit | `.created_at` timestamptz UTC | ts | system-derived | tenant-TZ render (IS-8) |
| Monthly partitions | — | NFR-24/28 + B2 §5 | RANGE (created_at), pre-create 3 ahead | DDL | system-derived | mechanics Eng-Lead 🔒 |
| Append-only enforcement | — | B2 §audit comment + §3 trigger family | block UPDATE/DELETE trigger | DDL | system-derived | Eng-Lead 🔒 |
| Entity lookup index | entity Audit tabs | B2 §4 | `ix_audit_entity (tenant_id, entity_type, entity_id, created_at)` | index | system-derived | NFR-30 tenant-leading |

**6 · Acceptance**
- Given the migration, Then audit_log exists monthly-partitioned with RLS FORCE and the entity index, and W0 writers' rows land in it.
- Given any UPDATE or DELETE attempt by any role, Then it is rejected — no mutation path exists.
- Given two tenants, Then neither can read or write the other's rows (zero-tolerance suite passes).
- Given a tenant purge drill, Then that tenant's audit rows survive.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.

---
id: US-AUD-002
epic: EP-AUD-01
module: audit
screens: [S61]
wave: 0
status: draft
blocked_by: []
depends_on: [US-AUD-001, US-TEN-010]
journeys: []
rules: [BR-AUD-003, BR-AUD-004, BR-AUD-005, BR-AUD-006]
golden_tests: []
finance_calc: none
---
### US-AUD-002 — Event-code catalog (seeded-only) + the payload standard (who/when/tenant/entity/before→after, PII-masked)

**1 · Details** — As the platform, I want ONE payload standard for every audit row — **who** (`actor_user_id`; null = system job with the job named in the payload) · **when** (`created_at` UTC, rendered tenant-TZ per IS-8) · **tenant** (`tenant_id`) · **entity** (`entity_type` + `entity_id`) · **action** (a catalog code) · **before→after** (jsonb: changed fields only for updates; full snapshot for creates; before-only for terminal actions) — and one **event-code catalog**: platform-seeded, code-defined (like the reports canned registry — no tenant table), in the dotted `entity.action` grammar the authored corpus already uses (`invoice.issued`, `journal.posted`, `premises.created`, `budget.enrolled`, `delivery.requeued`, `notification_settings.updated`, `meter_reads.partition_archived`…), each code mapped to exactly ONE S61 action-type class — `create | update | status | money | approval | auth` (A1 S61 filter vocabulary) — and to its owning module (the S61 module filter derives from this mapping, B2 §1 ownership). **Tenant-extensible event codes are NOT ratified** (B2 has no audit event-code lookup — `action` is text; BR-TEN-036's extensible-vocabulary list excludes audit codes) — the catalog ships **seeded-only**; extensibility = candidate OQ (pack report). **PII rule:** masked-display fields enter payloads in their MASKED form (`DL ****4218`, DOB `MM/****`); HIGH-class plaintext (full gov-ID — never stored anywhere, DOB, EIN, TOTP) never enters a payload — audit payloads are MED class (pii-inventory) precisely because no HIGH plaintext is in them (BR-CUS-045/NFR-13: "full values never leave the server" — nor enter the trail). US-TEN-010's reference-data discipline (seeded vocabularies, is_system governance) is the pattern consumed; audit codes are stricter (no tenant rows at all). **A1 S61's drawer also shows request metadata + a Source (UI/API/job) column — B2 anchors NO column for these; GAP AUD-D2, anchoring = Eng-Lead batch; nothing invented here.** Entry: writer calls with (code, entity, payload). Exit: standard-shaped row via US-AUD-003.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AUD-003 | Payload standard: who (actor_user_id; null = system job) · when (created_at UTC) · tenant · entity (type+id) · action code · before/after jsonb (changed-fields diff on update; snapshot on create; before-only on terminal). | CONFIRMED — B2 §audit columns + A1 S61 addendum (drawer: "full before/after values, JSON diff view"); diff-scope convention PROPOSED (corpus §5 usage) |
| BR-AUD-004 | Every event code maps to exactly one action-type class: create / update / status / money / approval / auth — the S61 filter vocabulary. | CONFIRMED — A1 S61 addendum (filter bar) |
| BR-AUD-005 | Event codes are a PLATFORM-SEEDED, code-defined catalog in the dotted `entity.action` grammar; seeded-only — tenant extensibility is unratified (no B2 lookup table; not in the BR-TEN-036 list). | PROPOSED — derived from corpus §5 tables (EP-TEN/BIL/LED/MET/AST/NOT) + B2 §audit `action text`; extensibility = candidate OQ |
| BR-AUD-006 | Masked-display fields are stored in payloads in MASKED form; HIGH-class plaintext never enters a payload; audit payloads are MED class. | CONFIRMED — BR-CUS-045 (PO closure batch 2026-08-08) + NFR-13 (OQ-016 closure) + pii-inventory audit-payload row (PO sweep 2026-08-08) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex Reed edits Billing defaults `late_grace_days` 10 → 15 | Row: actor Alex Reed, action `billing_settings.updated` (class `update`, module tenancy), before `{"late_grace_days":10}` after `{"late_grace_days":15}` — changed fields only (BR-TEN-016 shape) |
| TC-2 | Bill run 08-A issues BL-2608-018410 by the async job | Row: actor NULL + job named in payload (`bill_run:08-A`), action `invoice.issued` (class `money`), full issue snapshot — the CLAUDE.md #7 row |
| TC-3 | Contact DOB corrected on account A-10432 | before `{"dob":"06/****"}` after `{"dob":"11/****"}` — masked forms ONLY (BR-CUS-045); automated payload scan for HIGH-class patterns (9-digit ids, full DOBs, EIN) finds zero across the fixture corpus |
| TC-4 *(negative)* | Writer submits action code `stuff.happened` (not in the catalog) | Rejected at the write service — catalog codes only; the error names the catalog; no row written |
| TC-5 *(negative)* | Tenant admin looks for an "add audit event type" surface; API attempt to insert a tenant event code | No such surface exists; API rejected — seeded-only (BR-AUD-005); extensibility awaits ratification, never improvised |
| TC-6 *(immutability)* | Attempt to "reclassify" TC-2's row from class `money` via any path | No mutation path exists (BR-AUD-002); classification is a catalog property of the CODE, resolved at read time — rows never edited |
| TC-7 *(isolation)* | Same catalog, two tenants | Catalog is platform code (no tenant rows to leak); each tenant's ROWS remain RLS-scoped (US-AUD-001 TC-5) |
| TC-8 | J6 chain: `correction.approved` (approval) → `credit_note.issued` (money) → `journal.posted` (money) on CC-2608-007 | Each row carries its class + entity refs so S61's action-type filter reconstructs the corrections trail (J6) |

**4 · Test Data** — Catalog fixture (seed excerpt): `billing_settings.updated`/update/tenancy · `invoice.issued`/money/billing · `invoice.voided`/money/billing · `payment.recorded`/money/payments · `journal.posted`/money/ledger · `correction.approved`/approval/billing · `premises.created`/create/metering · `asset.retired`/status/assets · `security_policy.updated`/auth/identity · `period.closed`/status/tenancy · `report.exported`/update/reports · `meter_reads.partition_archived`/status/metering. Payload fixtures per TC-1..3 above; PII scan corpus = 12,400 Brazos Bend rows.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Event code | S61 Action col | corpus grammar + B2 §audit | `audit_log.action` (text; catalog-validated at the service) | text | system-derived | catalog member; dotted grammar |
| Action-type class | S61 filter | A1 S61 addendum | catalog property of the code (code-defined registry, no tenant table) | enum ×6 | reference-data | exactly one class per code |
| Module mapping | S61 module filter | A1 S61 + B2 §1 ownership | catalog property (entity_type → owning module) | text | reference-data | B2 module map |
| Before/after diff | S61 drawer | B2 §audit + A1 S61 | `.before`/`.after` jsonb per the standard | jsonb | system-derived | changed-fields on update |
| System-actor convention | S61 Actor col | B2 §audit (`actor_user_id` nullable) | NULL actor + job name in payload | uuid/text | system-derived | never a fake user |
| PII masking in payloads | S61 drawer | BR-CUS-045 + NFR-13 + pii-inventory | masked forms in jsonb; HIGH plaintext never present | text | system-derived | automated pattern scan |
| Source (UI/API/job) + request metadata | S61 Source col + drawer | A1 S61 addendum | **GAP — no B2 column (AUD-D2)**; anchoring = Eng-Lead batch, DDL 🔒 | — | system-derived | renders when anchored; not invented |

**6 · Acceptance**
- Given any write, Then the row carries who/when/tenant/entity/code/before→after per the standard, and the code resolves to one class + one module.
- Given a non-catalog code or a tenant-minted code, Then the write is rejected — the catalog is seeded-only.
- Given payloads across the fixture corpus, Then zero HIGH-class plaintext appears — masked forms only.
- Given the J6 fixture, Then the corrections chain is reconstructable by class + entity filters alone.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None (event-code extensibility + Source/request-metadata anchoring = candidate-OQ notes in the pack report; SC battery untouched).

---
id: US-AUD-003
epic: EP-AUD-01
module: audit
screens: [S61]
wave: 0
status: draft
blocked_by: []
depends_on: [US-AUD-001, US-AUD-002]
journeys: [J5, J6]
rules: [BR-AUD-001, BR-AUD-008, BR-AUD-011]
golden_tests: []
finance_calc: none
---
### US-AUD-003 — The audit-write service: sole write path, lightweight INSERT, async-safe, never a bottleneck

**1 · Details** — As the platform, I want ONE **audit-write service function** as the only path into `audit_log` — B1's boundary made concrete: no other module writes this module's table; writer modules CALL the service (the ledger-posting / outbound-queue interface pattern) — accepting (event code, entity ref, before/after payload, actor context) and performing a **single lightweight INSERT**: no fan-out, no notifications, no provider calls, no derived writes — so the audit write never becomes the reason a bill run or payment posting slows (B6: audit_log is the #3 growth table; NFR-24/28/30 absorb the volume; the service stays callable from async jobs per NFR-4). **The guarantee is law, the mechanics are not mine:** hard rule 7 says every money action WRITES audit_log — the row must exist whenever the action stands; whether that is same-transaction INSERT or a guaranteed-outbox pattern = **Eng-Lead 🔒** (like r12 #17 dispatcher mechanics). Fire-and-forget-with-loss is NOT an option under rule 7 — that much the law does determine. IS-6 binds the UI side: every destructive/money action = modal → explicit confirm → toast → audit row. **Upstream writers are contracts consumed, not depends_on:** BR-TEN-016 (every Settings write), BR-MET-048 (every premises/unit change), BR-AST-011/012 (every asset create/edit), BR-LED-015 (every finance action), BR-BIL/PAY rows, BR-IDN-019/027, BR-TEN-038 (close auto-forward audit note — J5), the J6 correction chain — their stories already name their rows; this story is the callee they all share. Entry: any writer's event. Exit: standard row in audit_log.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AUD-001 | Every money action writes an `audit_log` row; every destructive/money UI action ends modal → confirm → toast → audit row. | CONFIRMED — CLAUDE.md/B8 hard rule 7 + NFR-18 + B9 IS-6 |
| BR-AUD-008 | The audit-write service is the SOLE write path (B1: no other module writes this module's tables — writers call the service); single INSERT, no fan-out, async-callable; write-guarantee mechanics Eng-Lead 🔒. | CONFIRMED — B1 boundary + module overview; mechanics 🔒 |
| BR-AUD-011 | Settings/provisioning/reference-data writes are audited with before/after; an atomic per-tab save = ONE audit row. | CONFIRMED — BR-TEN-016 (PO R2-B3) + BR-TEN-024 (PO R2-B6), consolidated |
| BR-TEN-038 *(consumed)* | Closed-period money events auto-post to the earliest open period WITH audit note; reopen is audit-logged. | CONFIRMED — PO Q&A R6 (OQ-033 closure) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Run 07-A issues 1,124 bills (US-BIL-023 fixture) | 1,124 `invoice.issued` rows + 1 `bill_run.issued` row via the service; run duration budget unaffected beyond the INSERTs (bill-run target < 5 min stands, B6) — no fan-out occurred |
| TC-2 | J5 close: July 2026 closed; a correction dated Jul 28 arrives Aug 7 | `period.closed` row (Finance actor) + the BR-TEN-038 auto-forward audit note row on the posting — the J5 handoff trail complete |
| TC-3 | J6 chain on CC-2608-007 | `correction.approved` → `credit_note.issued` → `journal.posted` → `payment.reapplied` rows, each entity-linked — the corrections trail (J6) assembled entirely by service calls from four modules |
| TC-4 *(negative — sole path)* | A module performs a direct ORM/SQL INSERT into audit_log, bypassing the service | Forbidden — B1 boundary; migration/code-review guard (trace-lint pattern) rejects it; the service is the only sanctioned interface |
| TC-5 *(negative)* | Money action commits but the audit write fails (fault injection) | The pair never diverges silently: per rule 7 the row must exist whenever the action stands — the Eng-Lead 🔒 mechanism (same-txn or guaranteed outbox) makes divergence impossible or loudly failing; test asserts NO silent action-without-row outcome |
| TC-6 *(immutability)* | Service invoked with an "amend previous row" intent | No such API exists — the service only INSERTs; corrections are new rows (BR-AUD-002) |
| TC-7 *(isolation)* | Concurrent writers: Brazos Bend run 07-A + Lone Star Ridge run W-01 | Each row lands under its caller's `app.tenant_id`; WITH CHECK blocks any cross-tenant write; counts reconcile per tenant exactly |
| TC-8 | Atomic Settings tab save (BR-TEN-024): 4 fields changed in one save | ONE audit row with a 4-field before/after diff — not four rows (BR-AUD-011) |

**4 · Test Data** — Run 07-A: 1,124 bills, Aug 9 2026 (US-BIL-023 §4 fixture). Close fixture: July 2026 closed Aug 5 by Finance (Nora Patel); late-dated correction Jul 28→Aug 7 (LE-9 pattern). J6 fixture: CC-2608-007 → CN-2608-0031 → reversing JE → PMT-2608-0455 reapply ($247.30). Settings fixture: Billing-defaults tab, 4 fields, Alex Reed. Fault fixture: injected INSERT failure on `invoice.issued`. Isolation: LSR run W-01, 210 bills.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Service call (code, entity, payload, actor) | — | B1 boundary + BR-AUD-003 | INSERT into `audit_log` via service fn | call | system-derived | catalog + payload standard enforced |
| Money-action coverage | all money screens | CLAUDE.md #7 + NFR-18 + IS-6 | one row per money action | rows | system-derived | no silent money action |
| Settings coverage | S8 tabs | BR-TEN-016/024 | one row per atomic tab save | rows | system-derived | before/after diff |
| Close/auto-forward note | S56 | BR-TEN-038 | `period.closed` + auto-forward audit note rows | rows | system-derived | J5 trail |
| Correction chain | S30/S31.3/S56 | BR-BIL-014 + BR-LED-003 + BR-PAY-031 | entity-linked rows per step | rows | system-derived | J6 trail |
| Write-guarantee mechanism | — | rule 7 (guarantee) | same-txn vs guaranteed outbox — **Eng-Lead 🔒** | — | system-derived | no silent loss, no silent divergence |
| No-fan-out constraint | — | NFR-4 posture + BR-NOT-005 contrast | single INSERT; sends belong to the outbound queue, never here | — | system-derived | service does one thing |

**6 · Acceptance**
- Given any money action in any module, Then exactly the contracted audit rows exist, written through the service, and the action's latency budget is unharmed.
- Given a bypass attempt, Then it is rejected — the service is the only write path.
- Given fault injection, Then no silent action-without-row divergence is possible.
- Given the J5 and J6 fixtures, Then their complete trails exist as entity-linked rows.

**7 · Finance Calculation** — N/A — no money math (the trail records money actions; it computes nothing).

**8 · Open Questions** — None (write-guarantee mechanics = Eng-Lead 🔒, not a product question).

---
id: US-AUD-010
epic: EP-AUD-01
module: audit
screens: [S61, S21]
wave: 0
status: draft
blocked_by: []
depends_on: [US-AUD-001, US-AUD-003]
journeys: [J-RBS-3]
rules: [BR-AUD-002, BR-AUD-003, BR-AUD-007, BR-AUD-019, BR-RBS-015]
golden_tests: []
finance_calc: none
---
### US-AUD-010 — An automated action can say what it is: a named, versioned actor that is not a person

**1 · Details** — As a **clerk answering a customer who is disputing a charge**, I want the account
history to tell me **which automation made it and which version of that automation**, so that I can
look the thing up and answer properly — instead of reading a blank I cannot tell from a bug, or a
colleague's name against something they never did.

⚠ **THIS STORY IS NOT A DECISION. THE DECISION WAS ALREADY MADE.** `BR-RBS-015` rules it in one
sentence — *the runbook is the audit actor, named and versioned; it never borrows a user identity* —
and CLAUDE.md hard rule 7 makes the audit row non-negotiable on every money action. What was missing
is that **the platform could not express an actor that is not a person**: spec B1's *"an automated
action currently has no name"*. `audit_log` recorded one kind of actor, a user id, and a NULL that
means *a system job* (`BR-AUD-003`) — so a bill run, an import, a retention sweep and a runbook all
wrote the same blank, and **every automation in the product was indistinguishable from every other**.
This story is the companion build the runbooks execution plan names as task `L1`; it lands in the
AUDIT module because that is where the trail lives, and nothing about it is Runbooks' code.

**Worked, because that is what makes it a defect rather than a tidy-up.** The returned-payments
runbook applies a **$25 fee to 43 accounts overnight — $1,075 charged while nobody is at the
office.** Six weeks later a customer rings about theirs and a clerk opens the account history. Before
this story she saw one of two things and **both are wrong**: a **blank actor**, indistinguishable
from a bill run, an import or a bug, so she can tell the customer nothing — or **a staff member's
name**, because the automation borrowed the login of whoever set it up, putting a real person against
43 fees they did not apply and did not know about. It must read **"Returned payments, version 4"**.

**What is built:** three nullable columns on `audit_log` (`actor_kind`, `actor_label`,
`actor_version`), an `AutomationActor` the one writer accepts, a CHECK that refuses a named actor
carrying a user id, the read payload, the `f.actor=automation` filter value, and the two screens that
draw an actor — S61 and every per-entity Audit tab, the account history among them.

Entry: any automation writing through `core.audit`. Exit: the row names itself on screen.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AUD-019 | An actor that is NOT a person is named and versioned, and carries no user id; name and version are two fields, never one stored sentence. | CONFIRMED — the behaviour is `BR-RBS-015`'s; this is the capability |
| BR-RBS-015 *(consumed)* | The runbook is the audit actor, named and versioned; it never borrows a user identity. | CONFIRMED (PO) — **the platform gap it waited on is closed by this story** |
| BR-AUD-002 *(consumed)* | Append-only: no UPDATE or DELETE path exists anywhere. | CONFIRMED — **why the three columns are NULLABLE and nothing is backfilled**: a backfill here is not undesirable, it is forbidden, and the 0001 trigger would refuse it |
| BR-AUD-003 *(consumed)* | `actor_user_id` NULL = a system job, named in the payload. | CONFIRMED — **narrowed, not superseded**: NULL *and no name* still means an unnamed system job, and every row written before this story reads exactly as it did |
| BR-AUD-007 *(consumed)* | Tenant-scoped only; RLS FORCE. | CONFIRMED — a named row is scoped like every other row |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-RBS-12 | The returned-payments runbook, version 4, applies the $25 fee | The audit row's actor reads `{kind: runbook, name: "Returned payments", version: "4"}`; `actor_user_id` is NULL; **no id appears in the payload at all** (B14 rule 31) |
| TC-1 | `money_action()` is handed an `AutomationActor` | It is routed as an automation, not silently resolved to a blank by the `getattr(actor, "id")` line — the defect arriving through its own fix |
| TC-2 *(negative)* | A caller supplies BOTH a user id and an automation | Refused LOUDLY at the writer, naming `BR-RBS-015` — never resolved by preferring one |
| TC-3 *(negative)* | An automation with an empty name, or an unknown kind | Refused at CONSTRUCTION, so no call site can hold a half-formed one |
| TC-4 *(regression)* | A person's row and an unnamed system job's row | Byte-identical to before: `{id, name}` and `null`. US-AUD-004 TC-1's ratified key set does not move |
| TC-5 | `f.actor=system` and `f.actor=automation` | `system` returns the UNNAMED job only; `automation` returns the named runbook. **Without the narrowing, `system` would answer "every automation" and put the indistinguishability back one filter along** |
| TC-6 | The entity-scoped read behind the account history | Carries the same actor payload the viewer does (BR-AUD-010 — one audit surface) |
| TC-7 | Blue Mesa reads `f.actor=automation` while Silver Creek holds the row | 0 rows — the app-filter half of BR-AUD-007 |
| TC-8 *(live Postgres)* | The same read under FORCE ROW LEVEL SECURITY | 0 for Blue Mesa, 1 for Silver Creek. **SKIPPED on sqlite, and the skip says so** — a skip is not a pass |
| TC-9 *(live Postgres)* | A direct INSERT naming an actor AND a user id | The table's CHECK refuses it — `BR-RBS-015` at the last line of defence, so a future writer cannot reintroduce the borrowed login |
| TC-10 | A row written in the pre-story shape | All three columns NULL and unchanged — nothing was backfilled (BR-AUD-002) |

**4 · Test Data** — The worked scenario's own actor: `Returned payments`, version `4`, kind `runbook`,
action `payment.fee_applied`, `after {"fee": "25.0000"}`. Tenants: Silver Creek (holder) and Blue Mesa
(the reader that must see nothing). Users: Alex Reed (System Admin, signed in while the runbook row is
read — so a test that accidentally rendered a login would fail on his name being present).

⚠ **`TC-RBS-12` WAS SHOWN RED FIRST, AGAINST THE PLATFORM AS IT STOOD**, at the pinned tip
`a10eae00`, in a throwaway file written only in the vocabulary that existed that day. Both halves
failed, which is the gap in two sentences: the runbook could not name itself, so the row came back
blank; and the only way to make it non-blank was to hand it a staff login, which the platform accepted
without a word. CLAUDE.md hard-won law 7.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `actor_kind` | S61 · Audit tabs | BR-AUD-019 | `audit_log.actor_kind` | text, null | system-derived | one of `runbook` \| `job` \| `import` \| `integration`, refused at construction |
| `actor_label` | S61 · Audit tabs | BR-AUD-019 · BR-RBS-015 | `audit_log.actor_label` | text, null | system-derived | non-empty when a kind is set (writer + CHECK) |
| `actor_version` | S61 · Audit tabs | BR-AUD-019 | `audit_log.actor_version` | text, null | system-derived | optional — a version nobody established is not invented |
| The sentence a clerk reads | S61 · S21 History | B14 rules 31, 35 | — (composed) | — | derived | composed in the READER's language from name + version; never stored |

**6 · Acceptance**
- Given the returned-payments runbook applies its fee, When a clerk opens that account's history,
  Then the actor reads **"Returned payments, version 4"** — not blank, and not a staff member's name.
- Given any automation writes a row, Then no user id is on it, and neither the writer nor the table
  will accept one.
- Given every audit row written before this story, Then it reads exactly as it did.

**7 · Finance Calculation** — N/A — the trail records money actions; it computes nothing.

**8 · Open Questions** — None. ⚠ **AND ONE IS DELIBERATELY NOT MINTED:** the behaviour was ruled by
`BR-RBS-015` on the PO's own authority, so putting it back to them would be CLAUDE.md hard-won law 13
(*"asking again is a bug in us"*). ⚠ **A RETENTION CAVEAT THAT IS NOT THIS STORY'S:** `OQ-1340`
asks whether an audit row recording a replaced value is exempt from retention pruning, and it is OPEN
— so **nothing here describes any audit path as a permanent record**. This story adds no retention
behaviour and takes none away. (CLAUDE.md hard rule 4 cited that question as `OQ-1330` until 2026-09-14, when
`DEF-GOV-5229` corrected it on the PO's ruling; `OQ-1330` is a different, real question.)
