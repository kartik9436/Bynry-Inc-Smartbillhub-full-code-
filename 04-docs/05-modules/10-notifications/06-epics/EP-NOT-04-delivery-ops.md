# EP-NOT-04 — Delivery operations: dashboard, bounces & returned mail, report feeds

**Module:** notifications · **Wave:** W4 (US-NOT-015 = W5 with reports/finance) · **Screens:** S8 (Notifications tab dashboard half), S30/S35 (owner surfaces), S43/S45 (W6 email consumers) · **Status:** draft (BR-NOT-005, BR-PAY-018, BR-REP-007/017, BR-LED-020, BR-TEN-041 all CONFIRMED)

## Scope
**In:** the **platform delivery dashboard** on the dispatch home — counts by type × channel × status across ALL message types, failures/bounces list, re-queue action (BR-NOT-005 "per-run dashboard + re-queue"; BR-TEN-041); **bounce + returned-mail handling** — queue statuses and delivery-return events feeding the bad-address flow (BR-PAY-018 — payments consumes); **queue read-models for reports** (delivery-queue health + returned-mail, BR-REP-007) and the **W6 email consumers** (scheduled-report email BR-REP-017, bookkeeper-copy email BR-LED-020).
**Out:** billing's per-run S30 dashboard (US-BIL-024 — stays billing-owned; both read the same queue rows) · setting/clearing `accounts.bad_address` + needs-attention queue + account banner (payments/customers — US-PAY-016) · report definitions/scheduling UI (reports module) · dispatch mechanics (EP-NOT-01).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S8 · Notifications tab — platform queue list | recipient, account, message ref | type (bill/receipt/notice/plan/contract/report), channel, status (queued/sent/delivered/failed/bounced), date range | failed+bounced first, then queued_at | status, channel, type, queued_at, attempts | Type · Account · Channel · Status · Attempts · Last error · Batch / +provider ref, source module (IS-5) | View message · Re-queue · Mark returned (paper) | Re-queue selected · Mark returned selected | CSV (IS-9) |

## Stories

---
id: US-NOT-013
epic: EP-NOT-04
module: notifications
screens: [S8, S30]
wave: 4
status: draft
blocked_by: []
depends_on: [US-NOT-002, US-BIL-024]
journeys: [J2]
rules: [BR-NOT-005, BR-TEN-041]
golden_tests: []
finance_calc: none
---
### US-NOT-013 — The platform delivery dashboard + re-queue (dispatch home)

**1 · Details** — As a System Admin, I want the dashboard half of Settings → Notifications (BR-TEN-041: the delivery/dispatch home) showing the WHOLE platform's outbound traffic — bills, receipts, collection/plan notices, contracts, (W6) report + bookkeeper emails — as **counts by type × channel × status**, a **failures/bounces list** with provider errors, and a **re-queue** action (row + bulk) resetting rows to `queued` for the next batch (BR-NOT-005 "per-run dashboard + re-queue"). Billing's per-run S30 dashboard (US-BIL-024) remains the run-scoped view; this is the cross-module one — same rows, wider lens. Re-queue is an audited delivery event, never a money event; deferred channels (email W6 / SMS v1.1) show their queued backlogs with badges (US-BIL-024 TC-1 pattern). Entry: Settings → Notifications. Exit: rows re-queued for US-NOT-002.

**THE SURFACE, ADDED 2026-08-16 (DEF-128) — and what a person can now do.** This story's
dashboard had no endpoint at all until that date: 7,084 lines of notifications engine sat
behind an `api.py` of 72 bytes that no URLconf named, so nothing a customer was ever sent
could be triggered, listed or audited through the product. Four routes serve it now
(A11 Addendum r4): `GET /outbound` (the list, failures first), `GET /outbound/summary`
(the counts), `POST /outbound/{id}/requeue` and `POST /outbound/requeue` (the bulk half
this story's §1 ratifies and 11b §2.13 did not enumerate).

**TWO STATUSES ARE SERVED AS NOT REPORTED, NEVER AS ZERO.** `delivered` and `bounced` are
PROVIDER facts and no provider adapter exists on any channel — delivery is out of this
release by PO ruling (2026-08-15). The summary carries them on `unpopulated_statuses` with
the reason in `problems`, because *"0 delivered of 142 sent"* reads as a delivery failure
when the truth is that nobody is reporting.

**A RE-QUEUE IS A SYSTEM ADMIN'S ACTION AND THE LIST IS EVERYONE'S** — §4's actors read
*"Alex Reed; Priya Menon (view)"* and the dispatch home is a Settings surface (A4: System
Admin Full, Clerk —). Marking post returned is a CLERK's (US-NOT-014 TC-1 has Priya doing
it from S30) and so is the re-send (US-NOT-011 §5 puts it on S35).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-NOT-005 | Per-run dashboard + re-queue are part of the ratified queue model, platform-wide. | CONFIRMED — PO ruling, 2026-08-08 |
| BR-TEN-041 (#8) | Settings → Notifications = the delivery/dispatch home. | CONFIRMED — PO settings audit, 2026-08-08 |
| BR-BIL-016 *(shared)* | The per-RUN view of the same rows is billing's (US-BIL-024) — no duplicate ownership. | CONFIRMED — PO A-7 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dashboard after run 07-A + a receipt day | Counts tie to rows exactly: bills 142 print (136 delivered · 6 failed) + 982 email deferred; receipts 118 print delivered; notices 37; totals per type × channel × status |
| TC-2 | Failures/bounces list | The 6 failed print rows with provider error text, attempts=3, last-attempt time; failed+bounced sorted first (capability row) |
| TC-3 | Re-queue 6 failed rows (bulk) | Status → queued; next dispatcher batch picks them **within normal batch pacing** — a re-queue never bypasses batching (BR-NOT-005); `audit_log` `delivery.requeued` per row |
| TC-4 *(negative)* | Re-queue attempted on a HELD row (bad-address suppression, US-NOT-014) | Rejected with reason — held rows release only via address verification (BR-PAY-018), not re-queue |
| TC-5 *(negative)* | Re-queue via forged row ids from another tenant | Rejected — server-validated scope (RLS; US-BIL-024 TC-5 pattern) |
| TC-6 *(isolation)* | Lone Star Ridge dashboard | Its rows only; counts never include Brazos Bend traffic (RLS) |
| TC-7 *(surface, added 2026-08-16)* | The four routes resolved through the REAL root URLconf and called over real HTTP with no session | Every one answers **401 AUTH-001**, never 404. An `api.py` that exports `urlpatterns` is not an endpoint until `config/urls.py` includes it, and a route the URLconf knows is not reachable until a request survives the middleware, the authentication and the permission class |
| TC-8 *(surface, added 2026-08-16)* | The dashboard summary on a tenant with 6 failed and 4 queued rows | `totals` reads failed **6** / queued **4**, `retry_exhausted` **6**, `queued_by_channel.pdf_print` **4** — and `unpopulated_statuses` names `delivered` and `bounced` with `provider_statuses_never_written` in `problems` |
| TC-9 *(negative, added 2026-08-16)* | A bulk re-queue posted with an EMPTY selection | Refused 422 naming `message_ids`. An empty list is never read as *all*: a bulk action that quietly meant everything would return nine hundred rows to the pool because a checkbox did not register |

**4 · Test Data** — Brazos Bend: run 07-A rows per US-BIL-023 §4 (142/982, 6 failed on provider timeout); 118 receipt rows Aug 9; 37 notice rows (US-NOT-009/010 fixtures); held-row fixture A-11455 paper. Actors: Alex Reed; Priya Menon (view). Isolation: Lone Star Ridge run W-01 + 12 receipts.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Counts type × channel × status | S8 dashboard | BR-NOT-005 + BR-TEN-041 | computed over `outbound_messages` | counts | computed-display | ties to rows |
| Failures/bounces list | S8 dashboard | BR-NOT-005 | rows status failed\|bounced + provider response (r10 #8) | rows | computed-display | error text shown |
| Re-queue (row/bulk) | S8 dashboard | BR-NOT-005 | status reset → queued, audited | enum | user-input | IS-6 confirm; held rows excluded |
| Deferred-channel badges | S8 dashboard | OQ-073 closure pattern | channel-config flags | flag | computed-display | until W6/v1.1 |
| Re-queue audit | — | CLAUDE.md #7 | `audit_log` `delivery.requeued` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given the dispatch home, Then platform-wide counts tie to queue rows and failures show provider errors.
- Given re-queue, Then rows return to queued, dispatch picks them under normal batch pacing, and every action is audited with zero money effect.
- Given held rows, Then re-queue refuses — verification is the only release.
- Given tenants, Then dashboards and re-queues never cross.

**7 · Finance Calculation** — N/A — no money math. Ref: BS-23.

**8 · Open Questions** — None.

---
id: US-NOT-014
epic: EP-NOT-04
module: notifications
screens: [S8, S30, S35]
wave: 4
status: draft
blocked_by: []
depends_on: [US-NOT-002, US-PAY-016]
journeys: [J4]
rules: [BR-PAY-018, BR-NOT-005]
golden_tests: []
finance_calc: none
---
### US-NOT-014 — Bounces + returned mail: queue statuses feeding the bad-address flow; paper suppression honored

**1 · Details** — **Deferred-wave note: email BOUNCE handling activates with email dispatch at W6; the returned-MAIL (paper) path is v1.** As the system, I want delivery failures to feed the ratified bad-address flow (BR-PAY-018) without notifications ever writing another module's tables: **paper** — the "Mark returned" surface (single/bulk, on delivery rows in S30 and from S35 per US-PAY-016) sets the queue row's return state and emits a **delivery-return event** (r12 #8) that payments consumes to set `accounts.bad_address`, the needs-attention queue and the banner; **email (W6)** — provider bounce webhooks set status `bounced` + provider response, feeding the same event stream. While an account is flagged and the tenant's `suppress_paper_on_bad_address` is ON (r14 #5), the dispatcher **holds** new paper rows — written, marked held, never dispatched, never lost — and **releases** them when the address is verified (US-PAY-016 clear). Balances are unaffected throughout; everything is audited. Entry: provider bounce / staff mark-returned. Exit: events to payments; held rows released on verify.

**THE HAND-OFF IS MADE, ADDED 2026-08-16 (DEF-128).** `POST /deliveries/returned` (11b §2.9,
single or bulk) stamps the queue rows and then hands the r12 #8 events to **payments' own
published writer**, so payments sets `accounts.bad_address`, the needs-attention row and the
S21 banner. Until that date `apps/notifications/delivery_ops.mark_returned` emitted the
events and `apps/payments/returned_mail.mark_returned_bulk` consumed them and **nothing
called the second** — both lanes stopped at the B1 boundary correctly and the two halves sat
unconnected. No cross-module write happens: notifications calls, payments writes.

**`returned_on` IS REQUIRED AND IS THE CALLER'S BUSINESS DATE** (BR-TEN-043) — Tuesday's
stack is marked as Tuesday even when it is worked on Wednesday. **Balances are unaffected**
and the response states it (`balances_affected: false`), matching J18's invariance row.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-018 | Returned mail: delivery record marked returned (single/bulk) → bad-address flag → needs-attention + banner → paper suppressed until verified (config); balances unaffected; audited. | CONFIRMED — PO PA-7, 2026-08-08 (r12 #8, PE-16) |
| BR-NOT-005 | Bounced is a first-class queue status; dispatcher owns status writes. | CONFIRMED — PO ruling |
| B1 boundary | Notifications emits events; payments/customers write the account flag — no cross-module write. | CONFIRMED — B1 + r12 #8 ownership |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Priya marks A-11455's bill letter returned (S30 row) | Queue row → returned state + `delivery.returned` audit; delivery-return event emitted; US-PAY-016 consumes → bad_address set, chip + banner (its TCs) |
| TC-2 | Bulk mark-returned, 14 letters | 14 rows + 14 events, one audited bulk action (r12 #8 "bulk-markable") |
| TC-3 | Suppression ON: next disconnect notice for A-11455 | Paper row written with HELD marker — dispatcher skips it (US-NOT-002 TC pair); email/SMS rows unaffected (their own rails); nothing lost (EP-PAY-04 TC-3 contract) |
| TC-4 | Address verified (US-PAY-016 clear) | Held rows released; next batch dispatches them; release audited |
| TC-5 | W6: ESP bounce webhook for a bill email | Row → `bounced` + provider response stored; same event stream feeds the bad-address flow (deferred-wave note) |
| TC-6 *(negative)* | Mark-returned attempted on an email row | Rejected — paper-channel rows only (EP-PAY-04 field map: "paper rows only; idempotent"); marking the same row twice is a no-op |
| TC-7 *(isolation)* | Lone Star Ridge returns | Its rows/events only; Brazos Bend flags untouched (RLS) |
| TC-8 *(surface, added 2026-08-16)* | A-11455's letter marked returned through `POST /deliveries/returned` | The queue row carries `returned_at` on the stated date, its status is UNCHANGED (a returned letter WAS sent), and payments' `bad_address_for(account)` reads **true** — one endpoint, both halves of BR-PAY-018 |
| TC-9 *(idempotency, added 2026-08-16)* | The same envelope marked returned TWICE — the obvious accident on a stack of fourteen | Exactly **one** `delivery_return_events` row. The queue row is idempotent on `returned_at` and payments' table is keyed `UNIQUE (tenant, outbound_message_id)`; the database is the arbiter, not a check in Python that two clerks working one stack would lose |
| TC-10 *(seam, added 2026-08-16)* | The payments consumer unreachable | The rows are still stamped, NO account is flagged, and the response SAYS the letters will keep going to the same address (`returned_mail_consumer_unpublished`) — never a clean success (DEF-075's shape) |

**4 · Test Data** — Brazos Bend: A-11455 returned-mail fixture (EP-PAY-04 §4); bulk fixture 14 letters route R-4; suppression config ON; verify-clears fixture Sep 2 2026; W6 bounce fixture mailbox-full ESP payload. Actors: Priya Menon; system (webhooks). Isolation: Lone Star Ridge A-2214.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Mark returned (single/bulk) | S30 rows / S35 | BR-PAY-018 | delivery-return events (r12 #8) + queue-row return state | rows | user-input | paper rows only; idempotent |
| Bounced status | — | BR-NOT-005 + r10 #8 | `outbound_messages.status` = bounced + provider response | enum/jsonb | integration | W6 webhook-driven |
| Delivery-return event → flag | S21/S32/S34 | BR-PAY-018 | consumed by payments (`accounts.bad_address`, r12 #8) — notifications emits only | event | system-derived | B1: no cross-module write |
| Held marker on paper rows | — | BR-PAY-018 ("suppressed until verified") | held flag on `outbound_messages` paper rows | flag | system-derived | rows kept, dispatcher skips |
| Suppression config | S8/S70 | BR-PAY-018 ("config") + r14 #5 | `suppress_paper_on_bad_address` tenant setting | boolean | reference-data | tenant-set |
| Release on verify | — | BR-PAY-018 | held flag drop on verification event (US-PAY-016) | — | system-derived | audited |
| Return/bounce audit | — | CLAUDE.md #7 + BR-PAY-018 ("audited") | `audit_log` `delivery.returned/bounced/released` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a returned letter, Then the row's return state, the event, and the downstream flag/queue/banner all follow — with balances untouched.
- Given suppression ON, Then paper rows for flagged accounts are written and held, never dispatched, never lost — and release on verification.
- Given a W6 bounce, Then the row goes bounced with the provider payload and feeds the same flow.
- Given tenants, Then events, holds and releases never cross.

**7 · Finance Calculation** — N/A — no money math (BR-PAY-018: balances unaffected). Ref: PE-16.

**8 · Open Questions** — None.

---
id: US-NOT-015
epic: EP-NOT-04
module: notifications
screens: [S8, S45, S43]
wave: 5
status: draft
blocked_by: []
depends_on: [US-NOT-002]
journeys: [J5]
rules: [BR-REP-007, BR-REP-017, BR-LED-020, BR-NOT-005]
golden_tests: []
finance_calc: none
---
### US-NOT-015 — Queue read-models for reports + the W6 email consumers (scheduled reports, bookkeeper copies)

**1 · Details** — **Deferred-wave note: the report/bookkeeper EMAIL sends ship W6 with all email (BR-REP-017, BR-LED-020 — v1 = download); the read-models are v1-with-reports.** As the system, I want the queue exposed to its cross-module consumers per B1 (service-function reads, never direct table access): **read-models** feeding the canned **delivery-queue health** and **returned-mail** reports (BR-REP-007 — counts, failure/bounce rates, retry exhaustion, held rows, per channel/type/period); and the queue accepting the **W6 email writers** — scheduled-report emails to their recipient lists (BR-REP-017; A15 "Scheduled report | email | recipients | report file | overnight") and bookkeeper-copy emails (BR-LED-020; A15 deposit-reconcile + QuickBooks-sync rows, "(opt)" toggles per US-NOT-004) — which ride the queue like every other message (BR-NOT-005), resting `queued`+deferred until W6. Entry: reports/ledger events (W6) + report engine reads. Exit: read-model data to reports; email rows dispatched at W6 in normal batches.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-REP-007 | Delivery-queue health + returned-mail canned reports = read-models over the queue (BR-BIL-016 / BR-PAY-018); scheduled-report email rides the outbound queue. | CONFIRMED — reports audit F-4/5/7..13 |
| BR-REP-017 | Scheduled-report email ships W6 with all email; v1 = PDF download only. | CONFIRMED — PO RQ-9, 2026-08-08 |
| BR-LED-020 | Bookkeeper-copy email ships W6 via the outbound queue (v1 = download). | CONFIRMED — PO L-5 + L-2, 2026-08-08 |
| BR-NOT-005 | These emails are queue rows first, batch-dispatched — no special path. | CONFIRMED — PO ruling |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Health read-model for July 2026 | Counts match `outbound_messages` exactly: sent/delivered/failed/bounced by channel × type, retry-exhausted list, held-row count — the report renders what the rows say |
| TC-2 | Returned-mail read-model | The A-11455 return events + flagged-account linkage surface for the canned report (BR-PAY-018 data, read-only) |
| TC-3 | W6: nightly scheduled report "AR Aging weekly" to 3 recipients | 3 email rows queued with the report file ref; dispatched within normal tenant batches — report mail never bypasses pacing (BR-NOT-005) |
| TC-4 | Bookkeeper reconcile-summary email (toggle ON) | Row queued on reconcile event (A15 row); pre-W6 it rests queued+deferred; toggle OFF (US-NOT-004) → no row |
| TC-5 *(negative)* | Reports module attempts a direct SELECT on `outbound_messages` | Forbidden — B1: cross-module reads via service functions only; the read-model function is the interface |
| TC-6 *(negative)* | Scheduled-report email requested in v1 with expectation of delivery | Row queues deferred; report remains available as download (BR-REP-017 v1) — no false "sent" status ever shown |
| TC-7 *(isolation)* | Lone Star Ridge health report | Its rows only; recipient lists tenant-scoped (RLS) |

**4 · Test Data** — Brazos Bend July 2026: 1,124 bills + 118 receipts + 37 notices → health counts (6 failed, 1 held); returned fixture A-11455; scheduled report "AR Aging weekly" recipients priya@brazosbend.example + 2; bookkeeper fixture books@brazosbend.example (reconcile Aug 31). Isolation: Lone Star Ridge health July (210 rows).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Health read-model | S46 viewer (reports-owned) | BR-REP-007 | service-function read over `outbound_messages` | counts/rows | computed-display | ties to rows |
| Returned-mail read-model | S46 viewer | BR-REP-007 + BR-PAY-018 | read over return events + flags (r12 #8) | rows | computed-display | read-only |
| Scheduled-report email rows | S45 config (reports-owned) | BR-REP-017 + A15 row | `outbound_messages` (source=report, file ref, recipients) | rows | system-derived | W6 dispatch; deferred marker before |
| Bookkeeper email rows | S43/S36 surfaces | BR-LED-020 + A15 "(opt)" rows | `outbound_messages` (source=ledger export/reconcile) | rows | system-derived | toggle-gated (US-NOT-004) |
| Service-function boundary | — | B1 (module overview) | read interface, no direct table access | fn | system-derived | enforced |

**6 · Acceptance**
- Given the health/returned-mail read-models, Then reports render numbers that tie to queue rows exactly, through the service-function boundary only.
- Given W6, Then scheduled-report and bookkeeper emails queue and dispatch in normal batches; before W6 they rest visibly deferred while downloads serve v1.
- Given toggles, Then bookkeeper copies respect the tenant's opt settings.
- Given tenants, Then read-models and recipient lists never cross.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.
