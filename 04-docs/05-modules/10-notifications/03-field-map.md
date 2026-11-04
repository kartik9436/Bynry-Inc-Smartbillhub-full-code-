# notifications — Field Map

One row per field. Origin: user-input | system-derived | reference-data | integration | computed-display. Rows cite A2 § or "prototype-extracted"; underivable = GAP (candidate OQ in the pack report — routed to the Product Owner by the orchestrator).
Consolidated from US-NOT-001..015 §5 (2026-08-09); verified against B2 r10 #8, r12 #4/#7/#8/#9/#16, r14 #5. Exact DDL/keys = Eng-Lead 🔒 (r12 #17).

## 1. The platform queue + dispatcher (EP-NOT-01)
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Queue row (recipient × channel) | — | US-NOT-001 §5 · BR-NOT-005 | `outbound_messages` (r12 #16; r10 #8 contract) | rows | system-derived | one per document/message per channel | mapped |
| Source module + ref | — | US-NOT-001 §5 · r12 #16 | source_type + source_id (invoice/payment/notice/plan/report) | enum/uuid | system-derived | required | mapped |
| Template code + pinned version ref | — | US-NOT-001 §5 · BR-BIL-026 (A19 addendum b) | template ref on the row | text/int | system-derived | renders pinned version at dispatch | mapped |
| Recipient snapshot | — | US-NOT-001 §5 · A15 + BR-TEN-017 | address/phone snapshot at queue time | text | system-derived | never re-resolved | mapped |
| Status lifecycle | S8/S30 | US-NOT-001/002 §5 · BR-NOT-005 | status queued\|sent\|delivered\|failed\|bounced | enum | system-derived | forward-only; re-queue = only reset | mapped |
| Dispatch-not-before | — | US-NOT-001 §5 · US-BIL-023 (send-now vs scheduled) | timestamp on the row | ts | user-input (upstream) | dispatcher honors | mapped |
| Batch size | S8 Notifications | US-NOT-002/004 §5 · BR-BIL-016 + BR-TEN-041 | tenant dispatch setting (r12 #16) | int | reference-data / user-input | > 0; seeded 500 | mapped |
| Batch id / attempts / backoff | — | US-NOT-002 §5 · BR-NOT-005 (r10 #8) | batch ref + attempts (≤3) + next-attempt time | uuid/int/ts | system-derived | ×3 then failed | mapped |
| Provider response/error | S8/S30 failures | US-NOT-002 §5 · r10 #8 | provider response column | jsonb/text | integration | stored on failure + success ref | mapped |
| Queue-write dedupe + dispatch guards | — | US-NOT-001/002 §5 · CLAUDE.md #6 principle | unique keys + transition guards — **Eng-Lead 🔒** (r12 #17) | — | system-derived | no dup rows, no double-send | mapped 🔒 |
| Channel | — | US-NOT-003 §5 · r12 #16 | `outbound_messages.channel` | enum | system-derived | pdf_print\|email\|sms | mapped |
| Channel activation flags (email W6 · SMS v1.1) | S8 badges | US-NOT-003/004 §5 · OQ-073/074 closures + BR-PAY-017 | channel-config flags (US-BIL-023 pattern) | flag | reference-data | rows written, not dispatched before rails | mapped |
| Provider adapter binding / BYO mailbox / ESP / Twilio | — | US-NOT-003 §5 · TD-8 + B7 + A15 addendum | per-tenant provider config (integrations-owned read; secrets encrypted) | config | integration | tenant's own address only; no hardcoded provider | mapped |
| SMS opt-in | — | US-NOT-003 §5 · A15 | customer opt-in preference (customers-owned read; family of r12 #14 D-8) | boolean | reference-data | no opt-in → no SMS dispatch | mapped (see N-7) |
| Provider status readout | S8 Notifications | US-NOT-004 §5 · BR-TEN-041 | read-model over integrations connections | status | computed-display | read-only here | mapped |
| A15 opt-toggles (receipt/credit/bookkeeper/lockbox) | S8 Notifications | US-NOT-004 §5 · A15 "(opt)" rows + A1 tab 7 | tenant notification settings rows | boolean | user-input | defaults for send-time elections | mapped (see N-5) |
| Config audit | — | US-NOT-004 §5 · BR-TEN-016 family | `audit_log` `notification_settings.updated` | jsonb | system-derived | append-only | mapped |

## 2. Templates & rendering (EP-NOT-02)
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Template registry (group, channel, category) | S8 card | US-NOT-006 §5 · A19 r8 (16) + BR-NOT-004 (+4) + BR-BIL-025 | `notification_templates` + r8 designer extension — **Eng-Lead 🔒** (see N-6) | rows | user-input | groups per A19/S67 | mapped 🔒 |
| Version rows draft\|published\|archived | designers | US-NOT-006 §5 · BR-BIL-026 + A19 rule 6 | append-only version rows (r10 #4 pattern for all classes) | rows | user-input | edit = new row; one published | mapped |
| Effective date (contracts) | S67 | US-NOT-006/012 §5 · BR-NOT-002 | effective_from on contract versions | date | user-input | generation picks version in effect | mapped |
| Publish action (Admin-gated) | S8 | US-NOT-006 §5 · BR-BIL-027 | status transition | enum | user-input | server-enforced role | mapped |
| Pin refs / audit-lock | — | US-NOT-006 §5 · BR-BIL-027 + BR-NOT-002 | pinned-by refs (invoices, outbound rows, signed contracts) | — | system-derived | delete blocked while pinned | mapped |
| Account template override | resolution | US-NOT-006 §5 · BR-BIL-025 + r12 #14 (D-4) | `accounts.template_override_id` (customers-owned read) | uuid | reference-data | override → category default | mapped |
| Merge-variable catalog per type | S94–S106 palette | US-NOT-005 §5 · A19 token lists + addendum | typed catalog per template class | list | reference-data | out-of-catalog tokens rejected (PROPOSED validation) | mapped |
| Money/date rendering | artifacts | US-NOT-005 §5 · A19 header | 2dp at display (CLAUDE.md #2); tenant Regional formats | text | computed-display | never hardcoded | mapped |
| Identity stamp | artifacts | US-NOT-005 §5 · BR-TEN-017 | identity at render; issued docs keep theirs | text | system-derived | never re-rendered | mapped |
| Statement "nothing is due" line | statement classes | US-NOT-005/008 §5 · A19 rule 1 | mandatory class content | text | reference-data | save-blocked without it | mapped |
| Disconnect regulatory footer + certified block | S94 | US-NOT-007 §5 · A19 §2 + r8 row | mandatory blocks on the disconnect class | text | reference-data | non-removable | mapped |
| Dunning stage banners / day numbers | S95 | US-NOT-007 §5 · BR-REP-016 | render from tenant cadence config (S70; r14 #5 keys) | ints | reference-data | seeded 7/14/30 | mapped |
| Receipt content set | S96 | US-NOT-007 §5 · A19 r8 receipt row | receipt token catalog | tokens | reference-data | no due date/usage/rates | mapped |
| Email subject + preheader + body | S97–S102 | US-NOT-008 §5 · A19 r8 email table | email version rows | text | user-input | subject required | mapped |
| Past-due tone variants (3) | past-due designer | US-NOT-008 §5 · A19 r8 + BR-PAY-035 | tone-variant bodies | text | user-input | 3 tones, no free text | mapped |
| SMS body + live segment counter | S103–S106 | US-NOT-008 §5 · A19 rule 5 | SMS version rows; counter computed | text/int | user-input / computed-display | 160-char segment math live | mapped |
| STOP opt-out / URGENT lead / autopay-skip | S103–S106 | US-NOT-008 §5 · A19 r8 SMS table + rule 3 | class content requirements + render-context flag | text/flag | reference-data | disconnect SMS supplements the letter | mapped |
| Send-test | designers | US-NOT-008 §5 · A19 addendum + OQ-073 closure | v1 preview; W6 via connected mailbox | pdf/html | computed-display / integration | no provider call pre-W6 | mapped |
| Test-print | S94–S96 | US-NOT-007 §5 · BR-BIL-027 | rendered preview only | pdf | computed-display | no delivery row, no money event | mapped |
| Template audit | — | US-NOT-006 §5 · A19 rule 6 + CLAUDE.md #7 | `audit_log` `template.saved/published/archived` | jsonb | system-derived | append-only | mapped |

## 3. Notices, receipts & contracts (EP-NOT-03)
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Notice request (tier + accounts) | S22/S34/S35 | US-NOT-009 §5 · prototype-extracted (owner modals) | service params from trigger owners | enum/uuid | user-input (upstream) | tier ∈ 3 | mapped |
| Reconnect fee token | letters | US-NOT-009 §5 · BR-BIL-007 via BR-CUS-039 | tenant charge-code read | numeric USD | reference-data | display-only; missing = error, never defaulted | mapped |
| Certified-mail forcing + certified number | final tier | US-NOT-009 §5 · BR-CUS-039 + A19 §2/r8 | channel constraint + provider response (r10 #8) | flag/text | system-derived / integration | server-enforced | mapped |
| Medical-hold exclusion | — | US-NOT-009 §5 · A15 + BR-CUS-039 | account flag read (customers-owned) → refuse + skip record | boolean | reference-data | hard block | mapped |
| notice_history append (send AND skip) | S21/S34 | US-NOT-009/010 §5 · r12 #7 + J4 step 2 | `notice_history` append-only | rows | system-derived | every send and every skip | mapped |
| Tone select + tone→tier mapping | S35 | US-NOT-010 §5 · BR-PAY-035 | fixed mapping friendly=due+3 · firm=10-day · final=5-day/48h | enum/map | user-input / reference-data | free text does not exist | mapped (see N-2) |
| Ladder step context | — | US-NOT-010 §5 · BR-PAY-017 | collection state read (r12 #7, payments-owned) | enum | system-derived | payments advances it | mapped |
| Receipt queue row + render | S33/S35 | US-NOT-011 §5 · BR-PAY-024 + r12 #4 | `outbound_messages` (payment ref, template `receipt`) + S96 render | rows/pdf | system-derived | clearing-triggered only (BR-PAY-021) | mapped |
| Receipt re-send | S35/S33 | US-NOT-011 §5 · BR-PAY-024 | new queue rows, audited | rows | user-input | never edits; not a money event | mapped |
| Plan-notice rows (reminder −3d / missed +1d / void) | — | US-NOT-011 §5 · BR-PAY-016 + r12 #9 | `outbound_messages` + `notice_history` (written by US-PAY-018) | rows | system-derived | queue-write upstream | mapped |
| Plan-notice BODY | — | US-NOT-011 §5 | **GAP** — no template class in the A19 16-set; dispatch holds on missing published template | — | — | content never invented | **GAP — N-1, MINTED as OQ-207 on 2026-08-15** |
| Contract types (4) + category variants + default | S67 | US-NOT-012 §5 · BR-NOT-001/004 + BR-TEN-040 | contract registry + variant rows | rows | reference-data / user-input | fallback mandatory | mapped |
| A19 §3 blocks (plan agreement) | S67 ① | US-NOT-012 §5 · A19 §3 + addendum c | template body: terms/schedule/conditions/signature | text | user-input | no countersign block | mapped |
| Variant resolution by category | — | US-NOT-012 §5 · BR-NOT-001 | account consumer-category read (customers-owned) | enum | reference-data | category → variant → default | mapped |
| E-sign envelope + signed doc | S24.3 | US-NOT-012 §5 · BR-CUS-044 | DocuSign seam (⚠ B7); signed pdf → account documents | event/pdf | integration | signature alone activates | mapped |
| Signed-contract version ref | — | US-NOT-012 §5 · BR-NOT-002 | permanent template+version reference | uuid/int | system-derived | never re-rendered | mapped |

## 4. Delivery ops (EP-NOT-04)
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Platform counts type × channel × status | S8 dashboard | US-NOT-013 §5 · BR-NOT-005 + BR-TEN-041 | computed over `outbound_messages` | counts | computed-display | ties to rows | mapped |
| Failures/bounces list | S8 dashboard | US-NOT-013 §5 · BR-NOT-005 | rows failed\|bounced + provider response | rows | computed-display | error text shown | mapped |
| Re-queue (row/bulk) + audit | S8 dashboard | US-NOT-013 §5 · BR-NOT-005 | status reset → queued; `audit_log` `delivery.requeued` | enum/jsonb | user-input / system-derived | IS-6 confirm; held rows excluded; never bypasses batching | mapped |
| Mark returned (single/bulk) | S30 rows / S35 / S8 | US-NOT-014 §5 · BR-PAY-018 | delivery-return events (r12 #8) + row return state | rows | user-input | paper rows only; idempotent | mapped |
| Bounced status (W6) | — | US-NOT-014 §5 · BR-NOT-005 + r10 #8 | status = bounced + provider payload | enum/jsonb | integration | webhook-driven | mapped |
| Delivery-return event → bad_address | S21/S32/S34 | US-NOT-014 §5 · BR-PAY-018 | consumed by payments (`accounts.bad_address`, r12 #8) — notifications EMITS only | event | system-derived | B1: no cross-module write | mapped |
| Held marker + release on verify | — | US-NOT-014 §5 · BR-PAY-018 | held flag on paper rows; drop on verification event | flag | system-derived | rows kept; audited | mapped |
| Suppression config | S8/S70 | US-NOT-014 §5 · BR-PAY-018 + r14 #5 | `suppress_paper_on_bad_address` tenant setting | boolean | reference-data | tenant-set | mapped |
| Health + returned-mail read-models | S46 (reports-owned) | US-NOT-015 §5 · BR-REP-007 | service-function reads over queue + return events | counts/rows | computed-display | B1 boundary; ties to rows | mapped |
| Scheduled-report email rows (W6) | S45 | US-NOT-015 §5 · BR-REP-017 + A15 | `outbound_messages` (source=report, file ref, recipients) | rows | system-derived | deferred marker pre-W6 | mapped |
| Bookkeeper email rows (W6) | S43/S36 | US-NOT-015 §5 · BR-LED-020 + A15 "(opt)" | `outbound_messages` (source=ledger) | rows | system-derived | toggle-gated | mapped |

## 5. Discrepancies & residuals (verified vs B2 r10/r12/r14 — 2026-08-09)
| # | Where | Finding | Disposition |
|---|---|---|---|
| N-1 | US-NOT-011 | **Plan-notice template content**: BR-PAY-016 confirms the three plan notices + queue + history, but the A19 r8 16-template set contains no plan-notice class — bodies/subjects unspecified anywhere | **MINTED 2026-08-15 as OQ-207** (W3 delivery-core lane). It sat as a *"candidate OQ"* for six days with no live id, which meant no lawful way to refuse by name — G8 rejects a stub citing an unknown OQ. `apps/notifications/rendering.render` now refuses the three `plan_notice_*` classes quoting this reason; dispatch holds safely and content is never invented |
| N-2 | US-NOT-010 | Manual tone "firm/final" resolves to the 10-day / 5-day/48h steps (BR-PAY-035) — whether the rendered BODY at those steps is the dunning stage or the regulated disconnect notice is precise in the engine (regulated steps → disconnect class) but the S35 modal wording needs PO confirm | Candidate OQ (pack report) — mapping itself ratified |
| N-3 | US-NOT-002/003 | **Quiet hours / localization**: A15 lists both as UNKNOWN; no B-doc rules them; dispatcher paces but has no time-of-day constraint | Candidate OQ (pack report) |
| N-4 | US-NOT-009 / US-CUS-015 | **Door-hanger** delivery election (S22, A15 disconnect row) is not a queue channel in r12 #16 (email+SMS+print only); A6 marks the field task INFERRED | Candidate OQ (pack report) — v1 stories route letter/SMS only; door-hanger = field-ops surface |
| N-5 | US-NOT-004 | S8 tab 7 says "customer + **staff** toggles"; only A15's "(opt)" rows are derivable — full staff-toggle catalog unspecified (v1 sends no staff auth emails, NFR-14) | Candidate OQ (pack report) — pack builds the derivable set only |
| N-6 | US-NOT-006 / overview | Base B2 `notification_templates` (code/channel/subject/body) predates the r8 designers (versions, preheader, options, effective_from) and base `notifications` predates r12 #16 `outbound_messages` — column/table disposition unresolved in the addenda | **BOTH HALVES DISPOSED — CLOSED 2026-08-15.** The `notifications` half was made on 2026-08-11 in `apps/notifications/models.py`: **`outbound_messages` REPLACES the base `notifications` table, which is not built.** The `notification_templates` half is made in `apps/notifications/migrations/0005_w3_notification_templates.py`: the base four columns are **SPLIT** — `code`/`channel` stay on the registry row, which gains the r8 designers' `category` and `language` axes (BR-NOT-001/BR-NOT-006), while **`subject`/`body` move ONTO THE VERSION ROWS** (`notification_template_versions`), because BR-BIL-026 makes every edit a new version and a body on the parent is a body with no version number to pin; `deleted_at` is **dropped** (a soft-delete column on rows that can never be deleted is a second, weaker word for `archived`). ⚠ The registry holds the notifications-owned classes only — **S91–S93 (bill/statement) are billing's** and B2 r10 #4 gives them `bill_templates` + `bill_template_versions`; `template_service.register` refuses them by name |
| N-8 | US-NOT-005 / US-NOT-008 / US-NOT-012 | **Thirteen template classes have ratified CONTENT and no merge-variable catalog.** A19 §1/§2/§3 write tokens in braces for the printable classes; the r8 revision describes the six EMAIL and four SMS bodies in prose with real example subjects and **not one token**, and BR-NOT-004 confirms four contract TYPES while A19 gives blocks for one (the payment-plan agreement, §3). US-NOT-005 makes the palette the catalog and TC-5 makes an out-of-catalog token a save refusal — so a class with no catalog cannot be validated, previewed or rendered at all | **MINTED 2026-08-15 as OQ-206** (W3 delivery-core lane). Found while building the catalogs: seven classes are catalogued from signed tokens and thirteen are registered in `apps/notifications/catalogs.CLASSES_WITHOUT_CATALOG` with their reason, where the renderer refuses them by name rather than inventing a variable vocabulary for a customer-facing document |
| N-7 | US-NOT-003 | SMS opt-in storage: A15 requires opt-in; customers-owned preference family (r12 #14 D-8 anchored paperless only) | Eng-Lead/customers anchoring at DDL — behavior ratified |
