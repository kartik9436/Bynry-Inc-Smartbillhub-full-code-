# EP-NOT-01 — The platform outbound queue & dispatcher (every message queues; nothing sends inline)

**Module:** notifications · **Wave:** W3 (billing/payments queue-writers depend on this pack) · **Screens:** S8 (Settings → Notifications tab = dispatch home per BR-TEN-041), queue surfaces on S30/S35 (owner-module views) · **Status:** draft (BR-NOT-001..005 all CONFIRMED — PO 2026-08-08)

## Scope
**In:** the **platform-wide `outbound_messages` table** + the sanctioned queue-write path — EVERY email, SMS and print/PDF message from ANY module is written to the queue first, never sent inline (BR-NOT-005, B2 r12 #16); the **dispatcher service** — tenant-config batches (default 500), provider pacing, statuses `queued→sent→delivered|failed|bounced`, retry ×3 with backoff, idempotent dispatch (BR-NOT-005, NFR-1, TD-8); **channel routing + provider adapter seam** — print/PDF live v1, email dispatch deferred → W6 (OQ-073 closed), SMS dispatch deferred → v1.1 Twilio seam (BR-PAY-017, NFR-21); the **Settings → Notifications dispatch-home config** — batch size, channel activation, provider status, A15 opt-toggles (BR-TEN-041 upgrade #8).
**Out:** billing's per-bill queue rows + per-run S30 delivery dashboard (US-BIL-023/024 — billing owns its rows; the table + dispatcher live HERE) · payments' notice/receipt/plan-notice row writes (US-PAY-014/015/018/025) · template content + rendering (EP-NOT-02) · provider connect UIs — BYO mailbox / ESP / Twilio / print vendor (integrations module, B7 + A15 addendum) · exact DDL, dedupe keys, dispatcher mechanics (Eng-Lead 🔒 — B2 r12 #17).

## Capability matrix (list screens only — B9 conformance)
No list screens in this epic (services + a config panel). The platform queue LIST (dispatch-home dashboard) is specified in EP-NOT-04's matrix; billing's per-run S30 list is in EP-BIL-06's matrix.

## Stories

---
id: US-NOT-001
epic: EP-NOT-01
module: notifications
screens: [S8, S30, S35]
wave: 3
status: draft
blocked_by: []
depends_on: [US-BIL-023, US-PAY-014, US-PAY-018, US-PAY-025]
journeys: [J2, J4]
rules: [BR-NOT-005, BR-BIL-016]
golden_tests: []
finance_calc: none
---
### US-NOT-001 — `outbound_messages`: the platform-wide queue table + the only send path

**1 · Details** — As the system, I want ONE platform-wide outbound table (`outbound_messages`, B2 r12 #16) that every module writes to for every email, SMS and print/PDF message — bills (US-BIL-023), receipts (US-PAY-025, r12 #4), collection + plan notices (US-PAY-014/015/018), credit/plan-change/statement messages (A15 matrix), future staff mail — **never sent inline** (BR-NOT-005, PO volume ruling). Each row carries: source module + source ref (invoice / payment / notice / plan / report), template code + pinned version ref (BR-BIL-026 pattern), channel, recipient-address snapshot, status `queued`, dispatch-not-before timestamp, batch id (null until dispatched), attempts, provider response. Module writers INSERT via the reviewed interface (r12 #16 — the PO-approved exception to B1, like cross-module FKs); **only the dispatcher service sends** (US-NOT-002). Queue-write is idempotent: re-emitting the same source event never duplicates rows (dedupe key mechanics Eng-Lead 🔒, r12 #17). Entry: any module's send-triggering event. Exit: rows rest `queued` for the dispatcher.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-NOT-005 | EVERY email/text from ANY module is WRITTEN TO THE OUTBOUND TABLE first — never sent inline; dispatcher on top. | CONFIRMED — PO explicit ruling, 2026-08-08 ("volume challenge") |
| BR-NOT-005 (schema) | `outbound_messages` is PLATFORM-WIDE: one table for email + SMS + print across ALL modules; module writers insert; ONLY the dispatcher sends. | CONFIRMED — B2 r12 #16 (PO-approved) |
| BR-BIL-016 *(generalized)* | One delivery record per document per channel; statuses queued→sent→delivered/failed/bounced — BR-NOT-005 generalizes this contract to the platform. | CONFIRMED — PO A-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Run 07-A issues 1,124 bills (US-BIL-023 contract) | 142 pdf_print + 982 email rows land `queued` with source=billing/invoice refs + pinned template version; issue returns immediately — zero sends |
| TC-2 | Payment PMT-2608-0455 clears $247.30 (US-PAY-025 contract) | One receipt row per active channel, status `queued`, source=payments/payment ref, template code `receipt` (r12 #4) |
| TC-3 | Plan reminder −3d fires for ACC-1310 (US-PAY-018 contract) | Queue row written + `notice_history` appended by the writer; row rests `queued` |
| TC-4 *(negative)* | A code path calls a provider adapter directly at trigger time (bypassing the queue) | Forbidden — the queue is the only send path (BR-NOT-005); adapters accept batches only from the dispatcher |
| TC-5 *(negative)* | The clearing event for PMT-2608-0455 is re-emitted (job retry) | No duplicate receipt row — idempotent queue-write on source ref × channel (mechanics Eng-Lead 🔒) |
| TC-6 *(isolation)* | Lone Star Ridge queue query | Its rows only; Brazos Bend's 1,124-bill rows invisible (RLS FORCE) |

**4 · Test Data** — Brazos Bend: run 07-A → 142 print + 982 email rows (US-BIL-023 §4 fixture); receipt fixture PMT-2608-0455 $247.30 cleared Aug 9 2026; plan fixture ACC-1310 reminder due Aug 12. Re-emit fixture: duplicate clearing event same payment id. Isolation: Lone Star Ridge, 210-bill run W-01.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Queue row (recipient × channel) | — | BR-NOT-005 | `outbound_messages` (r12 #16; r10 #8 contract) | rows | system-derived | one per document/message per channel |
| Source module + ref | — | r12 #16 ("across ALL modules") | source_type + source_id columns (invoice/payment/notice/plan/report) | enum/uuid | system-derived | required |
| Template code + version ref | — | BR-BIL-026 pattern (A19 addendum b) | template ref pinned on the row | text/int | system-derived | renders pinned version at dispatch |
| Recipient snapshot | — | A15 (recipient column) + BR-TEN-017 stamping principle | address/phone snapshot at queue time | text | system-derived | issued messages never re-resolve |
| Status | S30/S35 surfaces | BR-BIL-016/BR-NOT-005 | status enum queued\|sent\|delivered\|failed\|bounced | enum | system-derived | starts `queued` |
| Dispatch-not-before | — | US-BIL-023 §5 (send-now vs scheduled) | timestamp on the row | ts | user-input (upstream) | dispatcher honors |
| Attempts / batch id / provider response | — | BR-BIL-016 (r10 #8) | counters + batch ref + provider payload | int/uuid/jsonb | system-derived | written by dispatcher only |
| Queue-write dedupe | — | CLAUDE.md #6 principle + r12 #17 | unique key on source ref × channel — Eng-Lead 🔒 | — | system-derived | no duplicate rows |

**6 · Acceptance**
- Given any send-triggering event in any module, Then a queue row exists and nothing has been sent inline.
- Given a re-emitted source event, Then no duplicate row exists.
- Given a queue row, Then it carries source refs, template version ref, recipient snapshot and status `queued`.
- Given tenants, Then queue rows never cross (RLS).

**7 · Finance Calculation** — N/A — no money math (the queue moves documents, never money). Ref: BS-23, PE-14.

**8 · Open Questions** — None.

---
id: US-NOT-002
epic: EP-NOT-01
module: notifications
screens: [S8, S30]
wave: 3
status: draft
blocked_by: []
depends_on: [US-NOT-001, US-BIL-023]
journeys: [J2, J4]
rules: [BR-NOT-005, BR-BIL-016]
golden_tests: []
finance_calc: none
---
### US-NOT-002 — The dispatcher: tenant-config batches, provider pacing, retry ×3, idempotent dispatch

**1 · Details** — As the system, I want a **dispatcher service** on top of `outbound_messages` that drains `queued` rows per tenant in **tenant-config batches (default 500, seeded)** and hands each batch to the channel's provider adapter **at the provider's pace** — because ESP/Twilio cannot absorb platform-speed bulk generation (BR-NOT-005; NFR-1: generation speed and sending speed decoupled). Statuses progress `queued → sent → delivered | failed | bounced` (forward-only; the re-queue ACTION in US-NOT-013/US-BIL-024 is the only reset). Failures **retry ×3 with backoff**, then rest at `failed` with the provider error stored. Dispatch is **idempotent**: a crashed or re-run dispatcher never double-sends a row (batch-id + status-transition guards; exact mechanics Eng-Lead 🔒, r12 #17). The dispatcher honors `dispatch-not-before` (scheduled sends, US-BIL-023) and held/suppressed markers (bad-address paper suppression, US-NOT-014/BR-PAY-018). Entry: scheduled job per tenant. Exit: batches sent, statuses advanced, dashboard truth (EP-NOT-04).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-NOT-005 | Dispatcher sends in tenant-config batches at the provider's pace; statuses queued→sent→delivered/failed/bounced; retry ×3 backoff. | CONFIRMED — PO explicit ruling, 2026-08-08 |
| BR-BIL-016 | Batch default 500 (tenant-config); mass sends are never synchronous. | CONFIRMED — PO A-7, 2026-08-08 |
| NFR-1 | All outbound written to the queue, dispatched in tenant-config batches at provider pace — generation and sending decoupled. | CONFIRMED — B6 (BR-NOT-005) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(batch pacing — the rule's reason to exist)* | 10,000 rows queued in one generation burst (bulk notice run) | Dispatched as 20 sequential batches of 500, each handed to the adapter at provider pace — NEVER one burst; batch id stamped per row; generation completed long before sending did |
| TC-2 | Tenant batch size changed to 200 (US-NOT-004) | Next dispatch cycle honors 200 — config, not constant (pairs US-BIL-023 TC-5) |
| TC-3 | Provider timeout on 6 rows | Retry ×3 with backoff (attempts counter + next-attempt time); after the 3rd failure status `failed` + provider error stored (US-BIL-023 TC-4 pair) |
| TC-4 | Dispatcher crashes mid-batch and re-runs | No row sent twice — idempotent dispatch via batch/status guards; unsent remainder picked up cleanly |
| TC-5 *(negative)* | Direct status write `sent → queued` outside the re-queue action | Rejected — forward-only lifecycle; re-queue (US-NOT-013/US-BIL-024) is the only reset |
| TC-6 *(negative)* | Row with dispatch-not-before = Sep 1 in an Aug 9 cycle | Skipped — not selected until its time |
| TC-7 *(isolation)* | Two tenants queued simultaneously | Per-tenant batches; Lone Star Ridge rows never enter a Brazos Bend batch or provider session (RLS + per-tenant dispatch) |

**4 · Test Data** — Brazos Bend: 10,000-row fixture (bulk reminder generation), batch size 500 seeded → 20 batches; changed-to-200 fixture. Failure fixture: 6 rows, provider timeout, backoff ×3 → failed. Crash fixture: kill after batch 7 of 20, re-run. Scheduled fixture: dispatch-not-before Sep 1 2026. Isolation: Lone Star Ridge 210 rows same cycle.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Batch size | S8 Notifications tab | BR-BIL-016 ("tenant-config, default 500") + BR-TEN-041 | tenant dispatch setting (r12 #16 "batch size/cadence tenant-config") | int | reference-data | seeded 500 |
| Batch id per handoff | — | BR-BIL-016 (r10 #8) | `outbound_messages.batch_id` family | uuid | system-derived | stamped at dispatch |
| Status transitions | S30 / S8 | BR-NOT-005 | status enum, forward-only | enum | system-derived | reset only via re-queue action |
| Attempts + backoff schedule | — | BR-NOT-005 ("retry ×3 backoff") | attempts (≤3) + next-attempt time | int/ts | system-derived | ×3 then failed |
| Provider response/error | S30 failures list | r10 #8 | provider response column | jsonb/text | integration | stored on failure + success ref |
| Idempotent-dispatch guard | — | CLAUDE.md #6 principle + BR-NOT-005 | batch/status transition guards — Eng-Lead 🔒 (r12 #17) | — | system-derived | no double-send |
| Held-row skip | — | BR-PAY-018 (suppression) | held marker respected (US-NOT-014) | flag | system-derived | held rows never selected |

**6 · Acceptance**
- Given 10,000 queued rows, Then dispatch happens in tenant-config batches at provider pace and never as one burst.
- Given failures, Then retry ×3 with backoff, then `failed` with the provider error visible.
- Given a dispatcher re-run, Then no message is ever sent twice.
- Given tenants, Then batches, configs and provider sessions never cross.

**7 · Finance Calculation** — N/A — no money math. Ref: BS-23, PE-15.

**8 · Open Questions** — None.

---
id: US-NOT-003
epic: EP-NOT-01
module: notifications
screens: [S8]
wave: 3
status: draft
blocked_by: []
depends_on: [US-NOT-002]
journeys: [J2]
rules: [BR-NOT-005, BR-BIL-016, BR-PAY-017]
golden_tests: []
finance_calc: none
---
### US-NOT-003 — Channel routing + provider adapter seam (print/PDF live v1 · email **deferred → W6** · SMS **deferred → v1.1**)

**1 · Details** — **Deferred-wave note: queue rows + rendering for ALL channels are v1; only the SEND adapters defer — email dispatch activates at W6 (OQ-073 closed), SMS dispatch at v1.1 behind the Twilio seam (BR-PAY-017, NFR-21).** As the system, I want the dispatcher to route each row to its channel adapter behind ONE provider seam (TD-8): **print/PDF** — live v1: batch PDF generation + print/certified-mail vendor seam (Lob, B7); **email** — rows written from day one, dispatch inactive until W6; at activation, send through the tenant's connected mailbox (Google/M365 OAuth or SMTP — A15 addendum: BYO, never a shared sender) for small tenants, or the tenant's transactional ESP integration for 6k–10k volume (OQ-074 closed); **SMS** — rows written, dispatch inactive until v1.1 (Twilio seam); SMS requires opt-in (A15). v1 sends NO staff auth emails (NFR-14/BR-IDN-021). No provider is hardcoded into business logic (B7 design rule). Entry: dispatcher batch per channel. Exit: sent via the active adapter, or resting `queued` with the deferred-channel marker.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-NOT-005 | Provider adapters (BYO mailbox, transactional ESP, Twilio) behind one seam; dispatcher sends at the provider's pace. | CONFIRMED — PO ruling + B2 r12 #16 |
| BR-BIL-016 (email timing) | Print/PDF v1; customer email ships W6 with notifications — queue architecture stands; rows written from day one. | CONFIRMED — OQ-073 CLOSED (PO F-round) |
| BR-BIL-016 (volume) | BYO mailbox for small tenants; transactional ESP as the tenant's integration for volume. | CONFIRMED — OQ-074 CLOSED (PO F-round) |
| BR-PAY-017 (channel timing) | Email + SMS text-to-pay ride the delivery queue WHEN their channels land (email W6, SMS Twilio seam). | CONFIRMED — PO PA-6, 2026-08-08 |
| A15 addendum | All customer email through the tenant's connected mailbox — sent FROM the utility's own address. | CONFIRMED — 2026-08-07 addendum |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Print batch (142 rows) dispatched v1 | **RE-SCOPED 2026-08-15 by PO ruling — see the note under this table.** Batch rendered from pinned template versions (US-NOT-006); the cycle reaches the provider boundary and REPORTS the adapter absent **by name** (`apps.integrations.services.dispatch_outbound_batch`); nothing is sent, nothing is lost, rows keep their place `queued`. ~~print-vendor seam invoked; rows → sent → delivered~~ — unsatisfiable in this release BY DECISION |
| TC-2 | Email rows pre-W6 | Persist `queued` with the deferred-channel marker; NO mailbox/ESP call ever attempted (US-BIL-023 TC-3 pair); rows never lost |
| TC-3 | SMS rows pre-v1.1 | Persist `queued` with the v1.1 marker; no Twilio call; opt-in flag carried for activation day |
| TC-4 | W6 email activation | Dispatcher drains deferred email rows **in tenant-config batches** (pacing rule holds on the backlog) via the tenant's connected mailbox or ESP per its config |
| TC-5 *(negative)* | Email channel activated but tenant has no connected mailbox/ESP | Rows stay `queued`; config-missing surfaced on the dispatch home (US-NOT-004) — no crash, no loss, no fallback shared sender |
| TC-6 *(negative)* | Staff temp-password email queued in v1 | No such writer exists — v1 sends no staff auth emails (NFR-14); row rejected at the write path |
| TC-7 *(isolation)* | Two tenants' email dispatch at W6 | Each sends exclusively from its OWN connected mailbox; credentials and rows never cross |

> **⚠ TC-1 SUPERSESSION — Product Owner ruling, 2026-08-15 (recorded here per hard-won law 10).** *Issuing a bill does NOT mean the customer receives one.* **Delivery is OUT of this release, by decision** — no provider adapter exists or is coming on ANY channel, print included, and the chain ends at a **rendered document**. Two consequences bind every lane touching this epic: **(1)** the two parked provider seams in `10-scripts/gates/seam_known_gaps.txt` (`dispatch_outbound_batch`, `provider_connection_status`) are **ACCEPTED, not owed** — a dispatch cycle reporting the adapter absent is CORRECT OUTPUT, never a defect, and nobody is to build or fake one to make a test green; **(2)** TC-1's original expectation (*"print-vendor seam invoked; rows → sent → delivered"*) is unsatisfiable **by ruling** and is re-scoped above rather than left failing. The test keeps its name — `test_us_not_003_tc1__print_is_the_one_channel_v1_activates` in `06-backend/tests/test_us_not_003_channel_routing.py` — so the story's test mapping still resolves, and its docstring carries this supersession. The half of TC-1 that IS now satisfied is the rendering half: rows are rendered from **pinned template versions**, which US-NOT-006's store made possible on the same day.

**4 · Test Data** — Brazos Bend: 142-row print batch (run 07-A); 982 deferred email rows; 47 SMS reminder rows (opt-in subset). W6 fixture: Brazos Bend = ESP tenant (6k+ volume path), Lone Star Ridge = BYO Google-OAuth mailbox (billing@lonestarridge.example). No-mailbox fixture: Lone Star Ridge disconnects its mailbox mid-cycle. Channels enum: pdf_print (active) · email (deferred → W6) · sms (deferred → v1.1).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Channel | — | r12 #16 (email + SMS + print) | `outbound_messages.channel` | enum | system-derived | pdf_print\|email\|sms |
| Channel activation flags | S8 Notifications tab | OQ-073/074 closures + BR-TEN-041 | channel-config flags (US-BIL-023 §5 pattern) | flag | reference-data | email W6 · sms v1.1 |
| Provider adapter binding | — | TD-8 + B7 design rule | per-tenant provider config (integrations-owned read) | config | integration | no hardcoded provider |
| BYO mailbox send-from | — | A15 addendum (BYO email) | tenant mailbox connection (integrations-owned; secrets encrypted per B7 addendum) | config | integration | tenant's own address only |
| SMS opt-in | — | A15 ("SMS requires opt-in") | customer opt-in preference (customers-owned read) | boolean | reference-data | no opt-in → no SMS row dispatch |
| Deferred-channel marker | S8 badges | OQ-073 closure | marker on rows/config | flag | reference-data | rows written, not dispatched |

**6 · Acceptance**
- Given v1, Then print/PDF dispatches and email/SMS rows persist queued with deferred markers — zero provider calls before their rails.
- Given W6/v1.1 activation, Then the backlog drains in tenant-config batches through the tenant's OWN provider config.
- Given missing provider config, Then rows wait visibly — never lost, never sent via a shared sender.
- Given tenants, Then mailboxes, credentials and rows never cross.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None (OQ-073/074 closed; activation is roadmap, not a question).

---
id: US-NOT-004
epic: EP-NOT-01
module: notifications
screens: [S8]
wave: 3
status: draft
blocked_by: []
depends_on: [US-NOT-002, US-TEN-010]
journeys: [J2]
rules: [BR-NOT-005, BR-TEN-041]
golden_tests: []
finance_calc: none
---
### US-NOT-004 — Settings → Notifications tab: the delivery/dispatch home (config)

**1 · Details** — As a System Admin, I want the Settings → Notifications tab (S8 tab 7, A1 addendum) to be the platform's **delivery/dispatch home** (BR-TEN-041 upgrade #8): **batch size** (default 500, editable), **channel activation** status (print live · email W6 badge · SMS v1.1 badge), **provider status** (connected mailbox / ESP / Twilio / print vendor — read from integrations config), and the A15 opt-**toggles** the spec defines (receipt on record-payment "(opt)", credit-notice email "(opt)", bookkeeper emails "(opt)", lockbox receipts "(opt)") — so that dispatch behavior is tenant-configured in one place, never code-constant. Edits are audited; the dashboard half of the dispatch home (queue counts, failures, re-queue) is US-NOT-013. Entry: Settings → Notifications. Exit: config consumed by US-NOT-002/003.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-TEN-041 (#8) | Notifications tab = delivery/dispatch home: batch size 500, channel activation, provider status. | CONFIRMED — PO settings audit, 2026-08-08 |
| BR-NOT-005 | Batch size/cadence are tenant-config (r12 #16). | CONFIRMED — PO ruling, 2026-08-08 |
| A15 matrix | Optional sends marked "(opt)": receipt, credit notice, bookkeeper reconcile/QB-sync copies, lockbox receipts. | CONFIRMED — A15 (EXPLICIT rows) |
| A1 addendum | S8 tab 7 "Notifications — customer + staff toggles". | CONFIRMED — A1 Settings rework |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex (Admin) edits batch size 500 → 200 | Saved + audited; next dispatch cycle honors 200 (US-NOT-002 TC-2 pair) |
| TC-2 | Channel panel pre-W6 | print: Active · email: "Ships W6" badge + rows-queued count · SMS: "v1.1" badge — read-only status, honest about deferral |
| TC-3 | Provider status readout | Connected mailbox (Google OAuth, billing@brazosbend.example) shown Connected; Twilio Not connected; states read from integrations config — no connect UI here (integrations owns it) |
| TC-4 | Receipt toggle per A15 "(opt)" | Toggle governs the default of the S35 "Send receipts" election (US-PAY-025 surface); BR-PAY-024 auto-queue itself is law and stays on |
| TC-5 *(negative)* | Priya (Billing Clerk) attempts a batch-size edit | Absent/disabled + server-rejected — Settings config is Admin-gated (A1: Settings screens = System Admin) |
| TC-6 *(negative)* | Batch size set to 0 | Rejected — dispatch requires a positive batch size; validation message, config unchanged |
| TC-7 *(isolation)* | Lone Star Ridge dispatch home | Its own batch size (500 seeded), its own provider status; Brazos Bend config invisible (RLS) |

**4 · Test Data** — Brazos Bend: batch 500 → 200 edit; mailbox connected (Google OAuth); ESP connected (volume tenant); Twilio not connected. Toggles: receipts ON, credit-notice email ON, bookkeeper copies OFF. Actors: Alex Reed (Admin), Priya Menon (negative). Isolation: Lone Star Ridge seeded defaults.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Batch size | S8 Notifications | BR-TEN-041 + BR-BIL-016 | tenant dispatch setting (r12 #16) | int | user-input | > 0; seeded 500 |
| Channel activation display | S8 Notifications | BR-TEN-041 + OQ-073/074 closures | channel-config flags (US-NOT-003) | flag | reference-data | W6/v1.1 badges until active |
| Provider status | S8 Notifications | BR-TEN-041 ("provider status") | read-model over integrations connections (B7) | status | computed-display | read-only here |
| A15 opt-toggles | S8 Notifications | A15 "(opt)" rows + A1 tab 7 | tenant notification settings rows | boolean | user-input | defaults for the send-time elections |
| Config audit | — | CLAUDE.md principle (settings audited — BR-TEN-016 family) | `audit_log` `notification_settings.updated` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given the dispatch home, Then batch size, channel activation, provider status and A15 opt-toggles are visible and tenant-scoped.
- Given a batch-size edit, Then the next dispatch honors it and the edit is audited.
- Given a non-admin, Then config edits are rejected server-side.
- Given deferral, Then email/SMS states are honestly badged W6/v1.1 with their queued-row counts.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None (full staff-toggle catalog beyond A15's "(opt)" rows = candidate note in the pack report, not decided here).
