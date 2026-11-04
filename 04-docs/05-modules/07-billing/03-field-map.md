# billing — Field Map

> Consolidated 2026-08-08 from the §5 "Data fields / Mapping" tables of the 27 authored billing stories (US-BIL-001..027, EP-BIL-01..07). Pure consolidation — every row cites its primary story; fields appearing in multiple stories are deduplicated to the primary story with cross-cites. Every DB target verified against B2 DDL or an addendum item (r5–r11); unverifiable targets are NOT restated as real — they are listed in "Discrepancies for PM review" at the bottom.

Origin vocabulary: user-input | system-derived | reference-data | integration | computed-display.

---

## 1 · Run wizard (S31 · S31.2 · S31.3) + Pending-billing queue — EP-BIL-01

| UI field | Screen | Source | DB column(s) | Type | Origin | Validation/notes |
|---|---|---|---|---|---|---|
| Billing cycle | S31 step 1 | US-BIL-001 §5 · prototype-extracted | `bill_runs.cycle_id` (B2 billing DDL; ⚠ FK `cycles`, metering/tenancy) | uuid | user-input | tenant's active cycles only |
| Period start / end | S31 step 1 | US-BIL-001 §5 · model §6 step 1 | `bill_runs.period_start` / `bill_runs.period_end` (B2) | date | user-input | end ≥ start; feeds idempotency key |
| Bill date | S31 step 1 | US-BIL-001 §5 · prototype-extracted | `invoices.service_date` at issue (B2 — drives tariff-version selection) | date | user-input | defaults to today |
| Due date (derived) | S31 step 1/5, S30 | US-BIL-005 §5 (display also US-BIL-001) · BR-BIL-024 | `invoices.due_date` (B2) | date | system-derived | = bill date + cycle due-days; never user-typed |
| Services scope chips | S31 step 1 | US-BIL-001 §5 · prototype-extracted | `bill_runs` scope (r10 #7) | enum[] | user-input | subset of tenant-enabled services; unchecked = explicit recorded choice, never silent skip |
| Idempotency key | — | US-BIL-001 §5 · BR-BIL-005 | `bill_runs.idempotency_key` UNIQUE (tenant, key) (B2) | text | system-derived | duplicate → block with who/when/link; key mechanics 🔒 Eng-Lead (r10 #15) |
| Consumers tab rows (account, class, plan, services) | S31.2 | US-BIL-002 §5 · prototype + BR-CUS-055 | read-model over `accounts` (B2) + plan-assignment snapshot via service fn (B1) — snapshot table see D-1 | rows | computed-display | class from status-lookup seed (r9 #7, OQ-064) |
| Reads completeness / flag sub-tabs | S31.2 | US-BIL-002 §5 · BR-MET-049 | read-model over `meter_reads` channel set (B2 + r8) via service fn | rows / % | computed-display | read-less services excluded |
| Prior balance + late-fee candidate | S31.2 Balances | US-BIL-002 §5 · BR-BIL-001/002/008 | computed over open `invoices` (B2); candidate never written until applied | numeric(18,6) USD | computed-display | max(5.00, 0.015 × overdue portion); grace per tenant mode |
| Grace mode + days settings | S66 | US-BIL-002 §5 · BR-BIL-002/008 | tenant settings `late_grace_mode` (calendar\|business) + `late_grace_days` (B2 post-design confirmations 2026-08-07) | enum / int | reference-data | seeded calendar, 5; range 0–30 |
| Unallocated credits tab | S31.2 Credits | US-BIL-002 §5 · BR-PAY-010 | read-model over `payments` (B2, type=credit) via service fn | numeric(18,6) USD | computed-display | allocation-order preview only; payments executes |
| Overcharge flag (preview + carried to drafts) | S31.2 / S31 step 4 | US-BIL-002 §5 (also US-BIL-004) · BR-BIL-029 | computed: draft total vs trailing average × tenant `overcharge_guardrail_pct` (r10 #6) | % | computed-display | default 200%; visible until resolved or knowingly issued ⚠ **the basis — bill total or metered consumption — is OQ-1202 (2026-08-31); this cell spells the MONEY reading and BR-BIL-029's own fixture is the consumption one** |
| Guardrail % setting | S66 | US-BIL-002 §5 · BR-BIL-021/029 | tenant billing settings `overcharge_guardrail_pct` (r10 #6) | numeric | reference-data | seeded 200; tenant-set |
| KPI strip / totals + sample preview | S31.2 / S31 step 4 | US-BIL-002 §5 (also US-BIL-004) · prototype-extracted | computed over the six tabs / draft set | counts / $ | computed-display | totals tie to tabs and drafts |
| Exception case tables + counts | S31.3 | US-BIL-003 §5 · prototype-extracted (7 categories) | computed over run assembly | rows | computed-display | counts tie to S31.2 |
| Missing-service disposition | S31.3 | US-BIL-003 §5 · BR-BIL-015 | run exception record: action + actor + when (r10 #7 run scope/exclusions) | enum(estimate\|hold\|bill_without) | user-input | required before continue; no silent resolution |
| Estimate trigger | S31.3 | US-BIL-003 §5 · BR-BIL-006 | via metering estimation service → `meter_reads` (B2; metering-owned write) | — | user-input | labeled estimated; cap per BR-MET-027 |
| Late-fee apply/waive | S31.3 | US-BIL-003 §5 · BR-BIL-001/003 · **BR-BIL-075** | applied → draft fee line `invoice_lines.charge_id` → LATE (B2 `charges`); waived → audited waiver, no line | enum | user-input | waiver manual, per case — never automatic. **IMPLEMENTED 2026-08-26 (BR-BIL-075, closing DEF-719): `apps/billing/decisions.py` writes this column from the tenant's `LATE` code — THIS ROW is where that code was already stated.** ⚠ The code supplies the **GL account only**; the AMOUNT stays BR-BIL-001's ❄️ frozen figure (GT-10's 8.13), never the code's `amount`. |
| Add charge-code line (exceptions + draft power) | S31.3 / S31 step 4 | US-BIL-003 §5 (also US-BIL-004) · BR-BIL-007/023 | `invoice_lines.charge_id` → `charges` (B2; own `charges.gl_account_id`) | uuid + amount | reference-data | tenant charge codes only; amount from the code, never typed |
| Bulk actions | S31.3 | US-BIL-003 §5 · prototype + IS-6 | same writes as per-row, batched | — | user-input | selection count + $ total shown |
| Draft invoice + lines | S31 step 4 (single mode: US-BIL-012) | US-BIL-004 §5 · model §6 step 4 | `invoices` (status draft) + `invoice_lines` (B2) — no GL stamp until issue (BR-BIL-010) | rows | system-derived (engine) | amounts rounded per B4.4 at finalization; computed amounts never hand-editable |
| Exclude action | S31 step 4 | US-BIL-004 §5 · BR-BIL-023 | `bill_run_exclusions` (account, reason, who/when — r10 #7) | row | user-input | reason required |
| Re-rate action | S31 step 4 | US-BIL-004 §5 · BR-BIL-023 | draft regeneration via rating engine call (B1) | — | user-input | audited; no hand edit path |
| Invoice number | S31 / S30 | US-BIL-005 §5 · BR-BIL-022 (source/format) · **BR-BIL-063** (timing) | `invoices.invoice_no` (B2) — minted from the tenant number series (BR-TEN-035; series mechanism see D-2) | text | system-derived | unique per tenant; **allocated when the DRAFT is created** (PO ruling 2026-08-11 — was "at issue only", a timing BR-BIL-022 never stated); an unused number is lost; default `BL-{YYMM}-{seq}` |
| Status → issued + issued_at | S31 | US-BIL-005 §5 · BR-BIL-004 | `invoices.status` + `invoices.issued_at` (B2) | enum / ts | system-derived | one-way; immutable after (B2 §3 triggers) |
| Pending-billing queue row (account, period, reason, age) | S30 queue | US-BIL-006 §5 (created by US-BIL-003 hold disposition) · BR-BIL-015/r1.3 | held-account queue rows on the run scope (r10 #7) | rows | system-derived | age = days since hold; reason tracked |
| Pending-queue KPI chip | S30 | US-BIL-006 §5 · r1.3 | computed count over open queue rows | int | computed-display | ties to list |
| Escalation flag | S30 queue | US-BIL-006 §5 · r1.3 | computed: age > tenant escalation days (setting key see D-7) | flag | computed-display | surfaced, never auto-billed |
| Catch-up sub-run | S31 | US-BIL-006 §5 · BR-BIL-015 | `bill_runs.parent_run_id` + scope (r10 #7); idempotency key = parent + scope 🔒 | row | user-input | scope ⊆ parent held set; same period as parent |
| Queue resolution linkage | S30 queue | US-BIL-006 §5 · r1.3 | queue row closed with child-run link (r10 #7 family) | uuid | system-derived | audited |
| Run / issue audit | — | US-BIL-001/005 §5 · CLAUDE.md #7 | `audit_log` (B2): `bill_run.created`, `invoice.issued`, `bill_run.issued` | jsonb | system-derived | append-only |

*Section rows: 31*

---

## 2 · Bills list + bill detail + void (S30) — EP-BIL-07 + invoice anatomy EP-BIL-02

| UI field | Screen | Source | DB column(s) | Type | Origin | Validation/notes |
|---|---|---|---|---|---|---|
| List row | S30 All bills | US-BIL-025 §5 · prototype-extracted | read-model over `invoices` (+account/customer joins via service fn) (B2) | rows | computed-display | server-side page/sort/filter (IS-2/3/4) |
| Status segments | S30 | US-BIL-025 §5 · prototype + A5 | `invoices.status` (B2 enum draft\|issued\|paid\|void\|corrected) + derived past-due (issued ∧ unpaid ∧ due_date < today) | enum | computed-display | past-due derived, never stored |
| bill_type filter | S30 | US-BIL-025 §5 · r10 #12 | `invoices.bill_type` (r10 #12) | enum | computed-display | 6 values (cycle\|first\|final\|rebill\|backbill\|penalty) |
| Column set (IS-5 chooser) | S30 | US-BIL-025 §5 · IS-5 | per-user preference — shell-owned, BR-SHL-027 pattern (no B2 table; see D-8) | jsonb | user-input | identity column always visible |
| CSV export | S30 | US-BIL-025 §5 · IS-9 | computed file over current filters + visible columns | file | computed-display | money 2dp, UTF-8; empty result = valid CSV with headers |
| Document panel | S30 detail | US-BIL-026 §5 · BR-BIL-026 | render from `invoices.template_id` / `.template_version` (r10 #3) | pdf/html | computed-display | pinned version only, forever |
| Summary box | S30 detail | US-BIL-026 §5 · A19 (model §7) | computed: previous balance − payments/credits received + current charges = total due | numeric(18,6) | computed-display | WE-1: 45.00 − 0.00 + 247.87 = 292.87 |
| Line table (description/qty/unit/unit_price/amount) | S30 detail | US-BIL-007 §5 · model §3 + B2 DDL | `invoice_lines.description/quantity/unit/unit_price/amount` (B2) | numeric(18,6) + text | system-derived (engine) | amount 2dp at finalization (B4.4); unit explicit on usage (CLAUDE.md #3) |
| Taxable flag | S30 detail | US-BIL-007 §5 · B4.2 schema note | `invoice_lines.taxable` (B2 post-design confirmations 2026-08-07) | boolean | system-derived | usage/base/minimum/capacity ✔ · fees/late ✘ · tax rows — |
| GL stamp per line | S30 detail | US-BIL-007 §5 (written at issue per US-BIL-005) · BR-BIL-010 | `invoice_lines.gl_account_id` (r10 #1; FK `ledger_accounts` ⚠ reviewed interface) | uuid | system-derived | resolved from mapping at issue; frozen — later edits never re-map history |
| Service / tariff version / charge refs | — | US-BIL-007 §5 · B2 DDL | `invoice_lines.service` / `.tariff_version_id` / `.charge_id` (B2) | enum / uuid | system-derived | tariff version = in force at service date |
| Line period | — | US-BIL-007 §5 · B2 DDL | `invoice_lines.period_start` / `.period_end` (B2) | date | system-derived | supports back-bill period groups (US-BIL-013) |
| Invoice totals | S30 | US-BIL-007 §5 · B2 DDL | `invoices.subtotal` / `.tax_total` / `.total` (B2) | numeric(18,6) | system-derived | = Σ lines by class |
| Tax line per authority | S30 detail | US-BIL-008 §5 · model §9 + B4.2 | `invoice_lines` (one row per authority; description = authority name; `gl_account_id` = liability GL via `tax_authority_gl_map` r10 #2) | numeric(18,6) USD | system-derived | rounded half-up individually (B4.4) |
| Tax base | — | US-BIL-008 §5 · B4.2 | computed: Σ `invoice_lines.amount` where `taxable` | numeric(18,6) | system-derived | fees/late excluded by flag |
| Exemption flag | S30 / S21 | US-BIL-008 §5 · B4.2 | `accounts.tax_exempt` (+ `.tax_exempt_ref`) (B2 post-design confirmations) — customers-owned read | boolean | reference-data | account-level; when true ALL tax lines vanish; certificate capture = B4 PLACEHOLDER (finance) |
| Authority + rate | S13 / S41 | US-BIL-008 §5 · r6.5 taxes model | `taxes` (jurisdiction, percent, `liability_gl_account_id`, `effective_from/to` — r6.5) — rating-owned read | numeric | reference-data | dated changes only |
| Run / origin link | S30 detail | US-BIL-026 §5 · r10 #7 | `invoices.bill_run_id` (B2) + `bill_runs.parent_run_id` when catch-up (r10 #7) | uuid | computed-display | — |
| Correction chain | S30 detail | US-BIL-026 §5 · BR-BIL-004/014 | `credit_notes.original_invoice_id` (B2) + rebill citation (r10 #9 links) | uuids | computed-display | navigable both directions |
| Delivery history | S30 detail | US-BIL-026 §5 · BR-BIL-016 | outbound delivery queue rows for the bill (r10 #8) | rows | computed-display | per channel |
| Audit trail panel | S30 detail | US-BIL-026 §5 · CLAUDE.md #7 | `audit_log` rows for the invoice (B2) | rows | computed-display | append-only read |
| Void consequence message | S30 void modal | US-BIL-027 §5 · BR-BIL-009 | rendered from the computed reversal preview (entries, balance effect, approval need) | text | computed-display | always before confirm |
| Void status | S30 | US-BIL-027 §5 · A5/r10 lifecycle | `invoices.status = 'void'` (B2 enum; lines untouched) | enum | system-derived | one-way; never a delete (BR-BIL-004) |
| Void window evaluation | — | US-BIL-027 §5 · OQ-012 closure | computed: paid? same open period? → free vs gated path | enum | system-derived | server-side |
| Void approval (gated path) | S30 modal | US-BIL-027 §5 · OQ-012 closure | approval record (Admin/Executive) — no B2/r10 anchor, see D-6 | uuid / ts | user-input | server-enforced role |
| Reversing JE handoff | — | US-BIL-027 §5 · BR-BIL-004/011 | posting service 🔒 → `journal_entries` / `journal_lines` (B2); closed-period → earliest open (BR-TEN-038) | rows | system-derived | balanced; full mirror of the stamped buckets; billing writes none |
| Payment-reversal prerequisite | — | US-BIL-027 §5 · OQ-012 closure | routed to payments (B2 `refunds` / reversal flow; BR-PAY-011 messaging there) | — | user-input | windows ACH 60d / card 120d / check unlimited (NSF) |
| Void audit | — | US-BIL-027 §5 · CLAUDE.md #7 | `audit_log` `invoice.voided` (actor, path, approval) (B2) | jsonb | system-derived | append-only |

*Section rows: 28*

---

## 3 · Account-mapping settings + posting handoff (S56 · S66) — EP-BIL-02

| UI field | Screen | Source | DB column(s) | Type | Origin | Validation/notes |
|---|---|---|---|---|---|---|
| Service → revenue GL (+ usage/base split) | S56 panel | US-BIL-009 §5 · BR-BIL-010 | `service_gl_map` (r10 #2) | uuid(s) | user-input | active tenant chart rows only |
| Tax authority → liability GL | S56 panel | US-BIL-009 §5 · BR-BIL-010 | `tax_authority_gl_map` (r10 #2) | uuid | user-input | one per authority |
| Charge-code GL (read-only echo) | S12 (echo on S56) | US-BIL-009 §5 · BR-BIL-007/010 | `charges.gl_account_id` (B2 DDL) | uuid | reference-data | edited on the charge, not here |
| AR / deposit-liability / opening-clearing / write-off designations | S56 panel | US-BIL-009 §5 · BR-BIL-010/013 | designation rows (r10 #2; write-off also r10 #11) | uuid | user-input | exactly one each |
| Seeded chart | — | US-BIL-009 §5 · B2 O-14 | `ledger_accounts` seed (B2; COA content = O-14, finance + Eng Lead) | rows | reference-data | tenant-editable labels; codes per COA |
| Posting handoff (per bill) | — (service contract) | US-BIL-009 §5 (emitted at issue per US-BIL-005/007) · BR-BIL-011 | consumed by ledger posting service 🔒 → `journal_entries` (source invoice) + `journal_lines` (B2); ⚠ **AMENDED 2026-08-11 — BUILT; nothing is persisted unposted** (this cell read *"persisted unposted until W5"*): `apps/billing/posting_seam.py` emits it inside the issue transaction. Handoff shape + per-invoice guard = Eng-Lead 🔒 (r10 #15) — the guard is `posting_key = invoice\|<invoice id>\|issued` | rows | system-derived | balanced by construction: DR AR = Σ CR per-GL buckets; billing writes NO journal lines (CLAUDE.md #5) |
| Mapping audit | — | US-BIL-009 §5 · CLAUDE.md #7 | `audit_log` `gl_mapping.updated` (B2) | jsonb | system-derived | append-only |

*Section rows: 7*

---

## 4 · Templates + pinning (S8 · S91–S93) — EP-BIL-06 (US-BIL-021/022)

| UI field | Screen | Source | DB column(s) | Type | Origin | Validation/notes |
|---|---|---|---|---|---|---|
| Template + type + category | S8 Templates | US-BIL-021 §5 · A19 types + BR-BIL-025 | `bill_templates` (type, category assignment — r10 #4) | row | user-input | types per A19 (bill/statement/…) |
| Version body + status | S91–S93 | US-BIL-021 §5 · BR-BIL-026 | `bill_template_versions` (append-only; draft\|published\|archived — r10 #4) | rows | user-input | edit = new row; one published per template |
| Publish action | S8 | US-BIL-021 §5 · BR-BIL-027 | version status transition (r10 #4) | enum | user-input | System Admin only, server-enforced |
| Test-print | S91–S93 footer | US-BIL-021 §5 · BR-BIL-027 | rendered preview (no money event, no delivery row) | pdf | computed-display | sample data only; Clerk-allowed |
| Account template override | S21 (customers surface) / issue resolution | US-BIL-021 §5 · BR-BIL-025 | account-level override attribute (customers-owned) — no B2/r9/r10 column, see D-4 | uuid | user-input | overrides category default |
| Audit-lock on pinned versions | — | US-BIL-021 §5 · BR-BIL-027 | delete blocked while pinned (`invoices.template_version` refs — r10 #3/#4) | — | system-derived | archive allowed, delete never |
| Template pin at issue | — | US-BIL-022 §5 (written by US-BIL-005) · BR-BIL-026 | `invoices.template_id` + `.template_version` (r10 #3) | uuid / int | system-derived | written at issue; immutable with the invoice; rebill pins CURRENT version at rebill issue |
| Resolution at issue | — | US-BIL-022 §5 · BR-BIL-025 | account override → category default → template published version | uuid | system-derived | published versions only |
| Reprint action | S30 / S22 Print bill | US-BIL-022 §5 · model §10 | render from the pinned version; optional re-queue via delivery queue (r10 #8, US-BIL-023) | pdf | user-input | audited, never a money event; no "render on latest" option exists |
| Template / reprint audit | — | US-BIL-021/022 §5 · CLAUDE.md #7 | `audit_log` `template.saved/published/archived`, `invoice.reprinted` (B2) | jsonb | system-derived | append-only |

*Section rows: 10*

---

## 5 · Delivery queue + dashboard (S31 step 6 · S30) — EP-BIL-06 (US-BIL-023/024)

| UI field | Screen | Source | DB column(s) | Type | Origin | Validation/notes |
|---|---|---|---|---|---|---|
| Delivery row (bill × channel) | — | US-BIL-023 §5 (written at issue per US-BIL-005) · BR-BIL-016 | outbound delivery queue (r10 #8): invoice, channel, status, attempts, batch id, provider response | rows | system-derived | one per bill per channel at issue; queue is the ONLY delivery path |
| Status lifecycle | S30 dashboard | US-BIL-023 §5 · r1.4 | queue status enum queued\|sent\|delivered\|failed\|bounced (r10 #8) | enum | system-derived | forward-only + re-queue (US-BIL-024) |
| Dispatcher batches | — | US-BIL-023 §5 · BR-BIL-016 | batch id per handoff (r10 #8); size = tenant setting default 500 (setting key see D-7) | int | system-derived | tenant-config, not constant |
| Retry / backoff | — | US-BIL-023 §5 · BR-BIL-016 | attempts counter (≤3) + next-attempt time (r10 #8 family; exact DDL 🔒 r10 #15 — see D-7) | int / ts | system-derived | ×3 then `failed` with provider error stored |
| Send-now vs schedule | S31 step 6 | US-BIL-023 §5 · prototype-extracted | dispatch-not-before timestamp on the run's rows (r10 #8 family — see D-7) | ts | user-input | queue path either way; never synchronous |
| Channel source | — | US-BIL-023 §5 · r1.4 | account delivery preference (customers-owned read; paperless pref = customers PROPOSED-SCHEMA — see D-8) | enum | reference-data | paperless → email, paper → pdf_print |
| Email deferral marker | — | US-BIL-023 §5 · OQ-073 closure | channel config: email dispatch inactive until W6 (setting key see D-7) | flag | reference-data | rows written from day one, not dispatched before W6 |
| Counts by channel × status | S30 dashboard | US-BIL-024 §5 · BR-BIL-016 | computed over the run's queue rows (r10 #8) | counts | computed-display | ties to rows exactly |
| Failures list | S30 dashboard | US-BIL-024 §5 · r1.4 | queue rows status failed/bounced + provider response (r10 #8) | rows | computed-display | error text shown; sortable failed-first |
| Re-queue action | S30 dashboard | US-BIL-024 §5 · BR-BIL-016 | status reset → queued (row/bulk) (r10 #8) | enum | user-input | run-scoped, server-validated; IS-6 confirm |
| Deferred-email badge | S30 dashboard | US-BIL-024 §5 · OQ-073 closure | channel-config flag rendering | flag | computed-display | until W6 activation |
| Delivery audit | — | US-BIL-024 §5 · CLAUDE.md #7 | `audit_log` `delivery.requeued/resent` (B2) | jsonb | system-derived | append-only; re-send renders the pinned version (BR-BIL-026), never a money event |

*Section rows: 12*

---

## 6 · Budget billing (S30 Budget Bills tab · S66) — EP-BIL-05

| UI field | Screen | Source | DB column(s) | Type | Origin | Validation/notes |
|---|---|---|---|---|---|---|
| Eligibility check | S30 Budget tab | US-BIL-018 §5 · BR-BIL-017 | computed: billed-history months ≥ tenant `eligibility_months` + plan budget flag (BR-RAT-043, rating-owned read) | int | computed-display | reason shown when ineligible |
| Level | S30 | US-BIL-018 §5 · BR-BIL-017 | `account_budget_status.level` (r10 #5) | numeric whole $ | system-derived | trailing-12 actuals ÷ 12, rounded whole-$ (tenant rounding setting) |
| Variance balance | S30 tab / bill document | US-BIL-018 §5 (movement per US-BIL-019) · BR-BIL-017 | `account_budget_status.variance_balance` (r10 #5) | numeric(18,6) USD | system-derived | starts 0.00; += level − actual each bill; shown on EVERY bill; append-only derivation |
| Settle-up month | S30 / S66 | US-BIL-018 §5 · BR-BIL-017 | `account_budget_status.settle_up_month` ← tenant setting (r10 #5) | int 1–12 | reference-data | tenant-set |
| **Amount due** | S30 tab / bill document / `GET /invoices/{id}`.summary | BR-BIL-072 (PO 2026-08-11, OQ-140) | `invoices.bill_payload.budget.amount_due` — stamped at draft, frozen with the bill | numeric(18,6) USD | system-derived | **the LEVEL, not `invoices.total`**: actual 292.87 → due 242.00. In the settle-up month the balance moves it (242 − 2.98 = 239.02 · 242 + 40.27 = 282.27). **AMENDED 2026-08-12 (PO, OQ-164): on a FINAL bill it is the LEVEL ONLY — 242.00, not 282.27** — the accumulated variance is settled through the settle-up, never folded into the last level payment. Read via `apps.billing.selectors.amount_due_for`, never recomputed by a client |
| Tenant budget settings | S66/S69 | US-BIL-018 §5 · BR-BIL-017/021 | tenant budget settings rows (r10 #5), BUILT as `apps.tenancy.settings_families.BUDGET_BILLING`: eligibility_months, level_rounding, relevel_drift_pct, relevel_cadence_months, settle_up_month, override_bound_pct, ~~drop_off_missed_payments~~ | numerics | reference-data | seeded defaults = BR-BIL-017 values; nothing hardcoded. ⚠ **`drop_off_missed_payments` IS DEAD CONFIGURATION as of the PO ruling of 2026-08-11** ("nodrop we chase for payments until write off"): the setting still renders on S69 and NOTHING reads it — DEF-063, routed to the tenancy lane |
| Actual charges | S30 detail | US-BIL-019 §5 · BR-BIL-017 | normal `invoices` / `invoice_lines` (B2 — full pricing + GL + tax) | numeric(18,6) | system-derived | identical to non-budget pricing; posting = ACTUALS buckets |
| Level presentation ("amount to pay") | bill document | US-BIL-019 §5 · BR-BIL-017 | template-rendered from `account_budget_status.level` (r10 #5) | numeric $ | computed-display | shown with actual + variance movement (3 columns) |
| Settle-up line | S30 detail | US-BIL-019 §5 · BR-BIL-017 + WE-8 | `invoice_lines` (B2) — non-taxable AR-timing line (collect or credit) | numeric(18,6) | system-derived | tenant settle-up month only; resets balance; never revenue, never taxed |
| Re-level evaluation | system job + S30 row action | US-BIL-020 §5 · BR-BIL-017 | `account_budget_status.level` + `.last_leveled_at` (r10 #5) | numeric $ / ts | system-derived | drift > tenant `relevel_pct`, each `relevel_cadence_months`; cadence gate server-side |
| Level override + reason | S30 row action | US-BIL-020 §5 · OQ-068 closure | `account_budget_status.level_override` + reason (r10 #5) | numeric $ + text | user-input | within ±30% of computed; reason required; audited |
| Off-budget transition | system (payments event) | US-BIL-020 §5 · BR-BIL-017 | `account_budget_status` status → off_budget after tenant `dropoff_missed_count` (status column not enumerated in r10 #5 — see D-5) | enum | system-derived | payments emits missed events (B1); billing never detects payment state |
| Carried variance at drop-off | next bill | US-BIL-020 §5 · BR-BIL-017 | variance balance carried into the next actuals bill | numeric(18,6) | system-derived | never silently dropped |
| Budget audit | — | US-BIL-018/019/020 §5 · CLAUDE.md #7 | `audit_log` `budget.enrolled/settled/releveled/overridden/dropped` (B2) | jsonb | system-derived | old/new + reason; append-only |

*Section rows: 13*

---

## 7 · Corrections (S30 Fix a bill · S8) — EP-BIL-04

| UI field | Screen | Source | DB column(s) | Type | Origin | Validation/notes |
|---|---|---|---|---|---|---|
| Correction case | S30 Fix a bill | US-BIL-015 §5 · BR-BIL-014 | `correction_cases` (reason code, scope, status, approver — r10 #9) | row | user-input | one open case per bill; one in-flight correction per bill |
| Reason code | S30 / S8 Reference data | US-BIL-015/017 §5 · r10 #13 | correction/penalty reason-code lookups (r10 #13, tenant-extensible) | uuid | reference-data | required; seeded six (r1.2); IS-1 audit-lock when used |
| Impact preview | S30 | US-BIL-015 §5 · BR-BIL-014 | computed artifact persisted on the case (r10 #9) — THE approval artifact | jsonb / rows | computed-display | no money-bearing writes before approval |
| Credit note | — | US-BIL-015 §5 · BR-BIL-004 | `credit_notes` (`original_invoice_id`, `amount`) (B2) + full GL reversal handoff (posting 🔒) | numeric(18,6) | system-derived | references original; append-only |
| Rebill | S30 | US-BIL-015 §5 · BR-BIL-014 | new `invoices` row `bill_type=rebill` (r10 #12) + lines with own GL stamps (r10 #1) | rows | system-derived | current template version pinned at rebill issue (r10 #3); cites the original |
| Re-allocation plan | S30 preview | US-BIL-015 §5 · BR-BIL-014 + BR-PAY-010 | plan emitted to payments (execution payments-owned; B2 `allocations`) | rows | system-derived | overpayment → carried credit |
| Approval / gate record | S30 | US-BIL-015/017 §5 · BR-BIL-014 + OQ-072 | `correction_cases.status/approver` + timestamp (r10 #9) — one gate, three consumers (corrections, back-bill, penalty) | uuid / ts | user-input | v1: System Admin only, server-enforced |
| Bulk scope | S30 | US-BIL-016 §5 · BR-BIL-014 (bulk) | `correction_cases.scope` — run/cycle/plan/service/date-range (r10 #9) | jsonb | user-input | resolves to a concrete bill set at preview; approval binds the reviewed set |
| Per-bill preview rows | S30 | US-BIL-016 §5 · r1.2 | bulk-correction run rows with per-bill computed impact (r10 #9) | rows | computed-display | the approval artifact for bulk |
| Execution job + progress | S30 | US-BIL-016 §5 · r1.2 | staged job state on the case; per-bill status queued\|done\|failed(reason) (r10 #9) | enum | system-derived | idempotent, resumable; succeeded bills never re-execute |
| Per-bill artifacts | — | US-BIL-016 §5 · US-BIL-015 mechanics | `credit_notes` + rebill `invoices` per succeeded bill (B2) | rows | system-derived | exactly one set per bill per case |
| Result summary | S30 | US-BIL-016 §5 · r1.2 | computed over per-bill results ("N succeeded · N failed") | counts | computed-display | always shown |
| Consequence messaging | S30 modal | US-BIL-017 §5 · BR-BIL-009 | rendered from the persisted impact preview | text | computed-display | before confirm, always |
| Approval threshold setting | S66 | US-BIL-017 §5 · BR-BIL-021 + OQ-072 | tenant billing settings `correction approval config` (r10 #6) | numeric USD | reference-data | stored; INERT in v1 (v2 activation) |
| Gate audit | — | US-BIL-017 §5 · CLAUDE.md #7 | `audit_log` `correction.approved/rejected` (B2) | jsonb | system-derived | append-only |

*Section rows: 15*

---

## 8 · Special bill types: first · final · ad-hoc · back-bill · penalty (S30 One-time tab · S31 single mode · S20) — EP-BIL-03

| UI field | Screen | Source | DB column(s) | Type | Origin | Validation/notes |
|---|---|---|---|---|---|---|
| bill_type classification | — | US-BIL-010/011/013/014 §5 (cycle: US-BIL-005; rebill: US-BIL-015) · r10 #12 | `invoices.bill_type` enum cycle\|first\|final\|rebill\|backbill\|penalty (r10 #12) | enum | system-derived | `first` derived from move-in ∈ period — never user-set; `final` at move-out handoff |
| Prorated base/usage lines (first bill) | S30 detail | US-BIL-010 §5 · B4.3 + WE-6 | `invoice_lines` with `period_start` = move-in day (B2) | numeric(18,6) | system-derived (engine) | calendar-day factors; tier spans scaled with prorated period |
| Deposit line (first bill) | S30 detail | US-BIL-010 §5 · BR-BIL-012 | `invoice_lines` → deposit-liability designation GL (r10 #2); amount from `plan_deposit_rules` (r5 #8, rating-owned read) | numeric(18,6) USD | system-derived | non-taxable; NEVER revenue |
| Connection charge line | S30 detail | US-BIL-010 §5 · BR-BIL-012 | `invoice_lines.charge_id` → CONN charge code (B2 `charges`, own GL) | numeric(18,6) USD | reference-data | fee class, non-taxable (B4.2) |
| Move-in date | — | US-BIL-010 §5 · BR-CUS-056 | customers-owned read — `accounts.opened_at` (B2) | date | reference-data | drives proration start; same-day move = no gap, no double |
| Final-bill period end = move day | S30 | US-BIL-011 §5 · r10 #12 + BR-CUS-056 | `invoices.bill_type` (r10 #12) + `invoices.period_end` = move day (B2) | enum / date | system-derived | immediate at the move-out handoff (BR-CUS-031) |
| Deposit + interest application | S20 / S30 | US-BIL-011 §5 · BR-BIL-013 | applied-first credit on the final bill (deposit position: `accounts.deposit_on_file` B2, customers-owned; interest per BR-CUS-057) | numeric(18,6) USD | system-derived | always applies FIRST, before path choice |
| Settlement path choice | S20 step / S30 | US-BIL-011 §5 · BR-BIL-013 | final-settlement record (path enum, actor, when) — no B2/r10 anchor, see D-3 | enum(refund\|collect\|transfer\|payment_plan\|write_off) | user-input | exactly one per final bill; write-off auto when ≤ threshold |
| Transfer transaction | — | US-BIL-011 §5 · r10 #10 | balance-transfer rows (credit final / debit master) + master designation via landlord-agreement link (r10 #10) | numeric(18,6) | system-derived | balanced; audited; landlord-link prereq (OQ-069) |
| Write-off line | S30 | US-BIL-011 §5 · r10 #11 | write-off line → write-off GL designation + tenant threshold setting (r10 #11) | numeric(18,6) | system-derived | \|amount\| ≤ threshold (default $5, config 0–50); both directions |
| Refund handoff | — | US-BIL-011 §5 · r1.1 path 1 | payments `refunds` (B2; payments-owned execution) | numeric(18,6) | system-derived | billing records the handoff only |
| Account + period pick (one-time) | S30 One-time tab | US-BIL-012 §5 · prototype + BR-BIL-020 | `bill_runs` single-account scope (r10 #7) | uuid / dates | user-input | one account; period explicit |
| Kind select (interim/final/catch-up/deposit) | S30 One-time tab | US-BIL-012 §5 · prototype; typed via r10 #12 | `invoices.bill_type` derived (r10 #12) — final → US-BIL-011 rules, catch-up past-period → US-BIL-013 rules | enum | user-input | routed to the governing story's rules |
| Draft lines (single mode) | S31 single mode | US-BIL-012 §5 · BR-BIL-020 | `invoice_lines` from engine + charge codes only (B2) — same draft set as US-BIL-004 | numeric(18,6) | system-derived | free-typed amounts NEVER exist on any bill (prototype free inputs superseded) |
| Credit auto-apply preview | S31 | US-BIL-012 §5 · BR-PAY-010 | allocation preview (payments executes; B2 `allocations`) | numeric(18,6) | computed-display | order per tenant setting; total ≤ 0 = credit bill, carries forward |
| Past period (back-bill) | S30 One-time tab | US-BIL-013 §5 · BR-BIL-018 | run scope period, single mode (r10 #7) | dates | user-input | span ≤ tenant cap unless theft-coded |
| Period-labeled line groups | S30 detail | US-BIL-013 §5 · r1.5 | `invoice_lines.period_start/period_end` + `tariff_version_id` per group (B2) | rows | system-derived | each group priced on the version in force THEN — never today's rates |
| Back-bill cap setting | S66 | US-BIL-013 §5 · BR-BIL-018 + OQ-071 | tenant billing settings, default 12 months (r10 #6 family — key not enumerated, see D-7) | int months | reference-data | theft cases EXEMPT (by theft reason code) |
| Assessed reads | metering entry path | US-BIL-014 §5 · BR-BIL-019 + r10 #14 | `meter_reads` + assessed flag, reason-coded (B2 + r10 #14 — metering-owned write) | numeric + unit | user-input (metering) | committed before pricing (BR-MET-053 lifecycle) |
| Priced usage lines (penalty) | S30 detail | US-BIL-014 §5 · BR-BIL-019 | `invoice_lines` from engine over assessed reads (B2) | numeric(18,6) | system-derived | never typed |
| TAMPER / penalty charge line | S30 detail | US-BIL-014 §5 · BR-BIL-007/019 | `invoice_lines.charge_id` → TAMPER code (B2 `charges`, own GL) | numeric(18,6) USD | reference-data | fee, non-taxable (B4.2); amount from the code |
| Case reason + approval (back-bill/penalty) | wizard | US-BIL-013/014 §5 · BR-BIL-014 gate | reason-code lookup (r10 #13) + gate record via US-BIL-017 (`correction_cases.status/approver`, r10 #9) | uuid | user-input / reference-data | System Admin approval before any money-bearing write |
| Statement template class (penalty) | — | US-BIL-014 §5 · r10 #12 + r1.5 | statement template class pinned (`bill_templates` category r10 #4; pin r10 #3) | enum | system-derived | statement class per A19 |

*Section rows: 23*

---

**Total rows: 139** (31 + 28 + 7 + 10 + 12 + 13 + 15 + 23)

---

## Discrepancies for PM review

Targets cited in story §5 tables that could NOT be verified as an existing column/table in B2 DDL or addenda r5–r11. Nothing invented; rows above reference these entries instead of asserting the target exists.

| # | Story | Referenced target | Finding |
|---|---|---|---|
| D-1 | US-BIL-002 | `account_plan_assignments` (plan snapshot, Consumers tab read) | Not in B2 or any addendum. r5 #13 defines `unit_plan_assignments` only; the account-side table is marked PROPOSED-SCHEMA in the customers field map (03-customers/03-field-map.md). Needs a schema addendum or re-cite to the unit-side snapshot. |  ⚠ **`account_plan_assignments` is SUPERSEDED (PO 2026-08-11)** — no account-side plan table is built; the plan lives once on `units.rate_plan_id` and the account derives it. See BR-CUS-029.
| D-2 | US-BIL-005 (also US-BIL-001 TC context) | tenant `number_series` (BR-TEN-035) | `invoices.invoice_no` exists (B2 billing DDL) but the number-series mechanism/table is in no B2 DDL or addendum. Tenancy-owned per BR-TEN-035 — needs its schema anchor confirmed. |
| D-3 | US-BIL-011 | final-settlement record (path enum refund\|collect\|transfer\|payment_plan\|write_off, actor, when) | Not in r10. r10 #10 covers only the transfer transaction and #11 the write-off support; the settlement-choice record itself has no B2/r10 item. |
| D-4 | US-BIL-021 (consumed by US-BIL-022/005) | account-level template override (BR-BIL-025 "overridable per account") | No column in B2 `accounts`, r9, or r10 (r10 #3/#4 cover pin + templates only). Story marks it customers-owned; the customers field map does not carry it either. |
| D-5 | US-BIL-020 | `account_budget_status` status column (off_budget transition; epic capability matrix filters enrolled/off-budget/pending-settle-up) | r10 #5 enumerates level, variance balance, last_leveled_at, settle_up_month, level_override + reason — no status column. |
| D-6 | US-BIL-027 | void approval record (Admin/Executive, gated path) | No B2/r10 table. `correction_cases.approver` (r10 #9) is corrections-only and a void is explicitly NOT a correction; `audit_log` records the event but is not the approval artifact. |
| D-7 | US-BIL-006, US-BIL-013, US-BIL-023 | tenant setting keys / queue columns not enumerated in r10: pending-queue escalation days (US-BIL-006); back-bill cap months (US-BIL-013); dispatcher batch size, email-channel activation flag, dispatch-not-before, attempts/next-attempt (US-BIL-023) | The families exist — tenant billing settings (r10 #6, BR-BIL-021 "nothing hardcoded") and the outbound delivery queue (r10 #8) — and exact DDL is Eng-Lead-owned (r10 #15), but these specific keys/columns are not individually listed in any r10 item. Confirm they ride the existing families or add an addendum line. |
| D-8 | US-BIL-023, US-BIL-025 | cross-module reads with no B2 anchor: account delivery preference (paperless — customers map marks `accounts.paperless` PROPOSED-SCHEMA); per-user column-set preference (BR-SHL-027, shell-owned) | Consumed read-only by billing; the owning modules' schema anchors are not yet in B2. Tracked here so billing's dependency is visible when those modules land their addenda. |
