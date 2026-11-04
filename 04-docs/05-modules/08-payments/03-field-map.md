# payments — Field Map

> Consolidated 2026-08-08 from the §5 "Data fields / Mapping" tables of the 25 authored payments stories (US-PAY-001..025, EP-PAY-01..07). Pure consolidation — every row cites its primary story; fields appearing in multiple stories are deduplicated to the primary story with cross-cites. Every DB target verified against B2 DDL or an addendum item (r2/r5/r9/r10/**r12**); unverifiable targets are NOT restated as real — they are listed in "Discrepancies for PM review" at the bottom (P-#; candidate-OQ items also appear in the pack report).

Origin vocabulary: user-input | system-derived | reference-data | integration | computed-display.

---

## 1 · Intake: single entry + purpose + bulk import (S22 · S35 · S33) — EP-PAY-01

| UI field | Screen | Source | DB column(s) | Type | Origin | Validation/notes |
|---|---|---|---|---|---|---|
| Account | S22/S35 | US-PAY-001 §5 · A2 §S22 | `payments.account_id` (B2) | uuid | user-input | active tenant account |
| Amount | S22/S35 | US-PAY-001 §5 · A2 §S22 | `payments.amount` (B2) | numeric(18,6) USD | user-input | > 0 |
| **Posting date** | S22/S35 | US-PAY-001 §5 · BR-PAY-021/022 (supersedes A2 single "Payment date") | `payments.posted_at` (r12 #1) | date/ts | user-input | defaults today (tenant TZ, IS-8); BILLING consumes this date (on-time = posted ≤ due) |
| **Clearing date** | S22/S35 | US-PAY-001 §5 · BR-PAY-021/022 | `payments.cleared_at` (r12 #1) | date/ts | user-input | blank = processing; NSF/bank-rec hang off this date; relation to legacy `received_at` = Eng-Lead (P-15) |
| Method | S22/S35 | US-PAY-001 §5 · A2 §S22 + BR-PAY-026 | `payments.method` → tenant lookup (r5 #20; seeds cash/check/card/ACH/wire/money order) | lookup | user-input | prototype "Lockbox" method superseded — lockbox = intake channel (BR-PAY-023) |
| Confirmation / check # | S22/S35 | US-PAY-001 §5 · A2 §S22 | `payments.confirmation` (B2) | text | user-input | optional |
| Memo | S22/S35 | US-PAY-001 §5 · A2 §S22 | no B2 column — see **P-14** | text | user-input | carried in audit payload until anchored |
| Apply-to instruction | S22/S35 | US-PAY-001 §5 (executed US-PAY-006) · A2 §S22 + BR-PAY-001 | allocation instruction → `allocations` rows (B2) | enum(+bill ref) | user-input | oldest (default) \| specific \| carry \| split |
| Payment number (PMT-) | S33 | US-PAY-001 §5 · r12 #13 | tenant PMT- number series (BR-TEN-035 mechanism; storage 🔒 r12 #17) | text | system-derived | minted at record |
| Payment status | S33 | US-PAY-001 §5 · A5 §Payment | `payments.status` (B2 enum processing\|cleared\|failed\|reversed\|posted) | enum | system-derived | cleared requires cleared_at |
| Submit idempotency | — | US-PAY-001 §5 · BR-PAY-028 | client token + unique key 🔒 Eng-Lead (r12 #17) | text | system-derived | double submit → one row |
| **Purpose** | S22/S35/S33 | US-PAY-002 §5 · BR-PAY-012 | `payments.purpose` enum bill\|deposit\|plan_down\|prepay (r12 #2) | enum | user-input | default bill |
| Deposit-purpose linkage | — | US-PAY-002 §5 · BR-PAY-012 | deposit position read (`accounts.deposit_on_file` + `.deposit_received_on`, B2 + r9 #5, customers-owned); satisfaction against the first-bill deposit line (BR-BIL-012) | uuid/numeric | system-derived | requires a deposit position |
| Plan-down linkage | — | US-PAY-002 §5 · BR-PAY-012 | payment → `payment_plans` reference (r12 family; exact column 🔒 #17 — see P-12) | uuid | system-derived | live-track plan required |
| Import file + SHA-256 + tags | S35 Lockbox | US-PAY-003 §5 · BR-PAY-023 | `payment_import_batches` (r12 #3) | file/text | user-input | file+tags idempotency (BR-PAY-028) — duplicate blocks who/when/link |
| Import row | S35 preview | US-PAY-003 §5 · BR-PAY-023 | `payment_import_rows` (r12 #3): refs, amount, dates, match state clean\|review\|error | per-column | integration | heuristic match ⇒ review, NEVER silent |
| Import commit → payments | S33 | US-PAY-003 §5 · BR-PAY-021/023 | `payments` rows: posted_at = commit, cleared_at = file bank date (r12 #1/#3) | rows | system-derived | errors skip w/ report; on-time interplay for mail arrivals = P-3 |
| Auto-post / send-receipts toggles | S35 Lockbox | US-PAY-003 §5 · prototype-extracted | batch commit scope flag; receipt queue rows on clearing (US-PAY-025) | boolean | user-input | review rows always excluded |
| Webhook dedupe (rails) | — | US-PAY-003 §5 · BR-PAY-003 | `payments.webhook_key` UNIQUE (tenant, key) (B2) | text | integration | schema-ready; dispatch W7 |
| S33 list row + columns | S33 | US-PAY-004 §5 · prototype + BR-PAY-027 | read-model over `payments` (+`allocations` for "Applied to"; purpose/batch/receipt refs) | rows | computed-display | IS-2/3/4/5; posted_at + cleared_at columns first-class |
| Column set preference | S33 | US-PAY-004 §5 · IS-5 | per-user preference (shell-owned, BR-SHL-013) | jsonb | user-input | identity column always visible |
| CSV export | S33/S34/S37 | US-PAY-004/013/020 §5 · IS-9 | computed file over filters + visible columns | file | computed-display | money 2dp, UTF-8 |
| S32 KPI panels (today/method mix/failed/collections) | S32 | US-PAY-005 §5 · prototype-extracted | computed over `payments` / S34 read-model / `write_offs` (r12 #11) | $/counts/% | computed-display | tie to lists exactly; DSO per BR-REP-011 (P-1 resolved) |
| Autopay-scheduled chip | S32 | US-PAY-005 §5 (rows US-PAY-024) · BR-PAY-015 | count over `autopay_capture_intents` (r12 #6) | int | computed-display | — |
| Returned-mail chip | S32 | US-PAY-005 §5 (flow US-PAY-016) · BR-PAY-018 | count over open bad-address queue (r12 #8) | int | computed-display | — |

*Section rows: 24*

---

## 2 · Allocation + credit + Reapply (S33 · S35) — EP-PAY-02

| UI field | Screen | Source | DB column(s) | Type | Origin | Validation/notes |
|---|---|---|---|---|---|---|
| Allocation row | S33 "Applied to" | US-PAY-006 §5 · BR-PAY-010 + B2 DDL | `allocations` (payment_id, invoice_id, amount) (B2) | numeric(18,6) | system-derived | Σ per payment ≤ amount; append-only |
| Within-invoice class order | — | US-PAY-006 §5 · BR-PAY-010 + **BR-PAY-038** | line-class walk over `invoice_lines` (taxable/charge class via service fn, B1) | ordered classes | system-derived | usage+base → taxes → **the tenant-defined class** → fees LAST — **the SHIPPED DEFAULT of a tenant setting since PO 2026-08-12 (OQ-189), never a constant**. **Instalment payments are the NAMED EXCEPTION: they reach the PLAN first (OQ-139)** |
| Tenant allocation-order setting | **Settings → Configure** (S66 family) | US-PAY-006 §5 · BR-PAY-010 + BR-BIL-021 · **PO 2026-08-12 (OQ-189)** | tenant billing settings allocation-order key (r10 #6 family) — **owed: `apps/payments/allocation.py` already takes `class_order` as an argument (`DEFAULT_CLASS_ORDER`); storage, screen and plumbing are what is missing** | enum[] (4 classes) | reference-data | seeded default = usage+base → taxes → tenant class → fees LAST; tenant-reorderable. Worked default: $120.00 on $128.88 → 100.58 / 8.30 / 11.12 / 0.00 |
| Carried credit position | S21/S33 | US-PAY-007 §5 · BR-PAY-010/012 (+BR-CUS-061 imports) | read-model: Σ unallocated credit `payments` (type credit, B2 `payment_type`) | numeric(18,6) | system-derived | auto-applies at next issue; refundable |
| Credit auto-application | — | US-PAY-007 §5 · BR-PAY-010 | `allocations` rows written at bill issue (engine call, B1); idempotent per issue 🔒 | numeric(18,6) | system-derived | ≤ credit balance; never lost |
| Reapply target + remainder behavior | S35 Reapply | US-PAY-008 §5 · prototype + BR-PAY-031 | reversing `allocations` rows + new rows; remainder → credit (US-PAY-007) or refund route (US-PAY-011) | enum/rows | user-input / system-derived | reason REQUIRED; originals never edited |
| Consequence line (reapply/reverse) | S35 | US-PAY-008/010 §5 · BR-PAY-030 | rendered from computed per-bill balance deltas | text | computed-display | always before confirm |
| Allocation/credit/reapply audit | — | US-PAY-006/007/008 §5 · CLAUDE.md #7 | `audit_log` `payment.allocated` / `credit.applied` / `payment.reapplied` (B2) | jsonb | system-derived | append-only |

*Section rows: 8*

---

## 3 · Exceptions: NSF · reverse · refund · write-off (S33 · S35 · S58) — EP-PAY-03

| UI field | Screen | Source | DB column(s) | Type | Origin | Validation/notes |
|---|---|---|---|---|---|---|
| Reversing payment row (NSF/reverse) | S33 | US-PAY-009/010 §5 · BR-PAY-002/013 | `payments` reversing rows referencing originals (B2 append-only) | numeric(18,6) | system-derived | never an edit/delete |
| Allocation reversal | — | US-PAY-009/010 §5 · BR-PAY-013 | `allocations` reversing rows | numeric(18,6) | system-derived | re-opens exact amounts; original due dates untouched |
| NSF fee line | S21/S30 | US-PAY-009 §5 · BR-PAY-013 + BR-BIL-007 | billing charge-line service → `invoice_lines.charge_id` = NSF code (B2 `charges`, own GL) | numeric(18,6) | reference-data | amount from the code, never typed ($30 = sample) |
| nsf_count + privilege flag | S21/S34 | US-PAY-009 §5 · BR-PAY-013 | `accounts.nsf_count` + cash-only/no-autopay flag (r12 #12) | int/boolean | system-derived | flag at tenant N (default 2, config) |
| Reversal reason + memo | S35 Reverse | US-PAY-010 §5 · prototype (4 options) | reason on the reversing event + audit (lookup anchoring = P-11) | enum/text | user-input | NSF reason routes to US-PAY-009 |
| Window evaluation | — | US-PAY-010 §5 · BR-PAY-011 | computed: method + days since posted; paid/cross-period detection | enum | system-derived | ACH 60d · card 120d · check unlimited (NSF) |
| Reversal approval record | — | US-PAY-010 §5 · BR-PAY-011 | approval (Admin/Executive, who/when — r12 family, DDL 🔒 #17) | uuid/ts | user-input | server-enforced role |
| Refund account/amount/method/reference/reason | S58 | US-PAY-011 §5 · prototype + B2 r2 | `refunds` (amount, method check\|ach, reference/check_no, reason — B2 + r2) | per-column | user-input | only from real credit; amount ≤ credit; card → W7 |
| Refund status | S58 | US-PAY-011 §5 · B2 r2 | `refunds.status` issued\|cleared\|void | enum | system-derived | void = reversing posting, never delete |
| Refund approval | — | US-PAY-011 §5 · BR-PAY-014 | `refunds.requested_by` / `.approved_by` + timestamps (r12 #5) | uuid/ts | user-input | Admin-only, server-enforced |
| Refund source (credit balance, not one payment) | S58 | US-PAY-011 §5 · **BR-PAY-014 as amended (PO 2026-08-12, OQ-167)** | `refunds.payment_id` names ONE payment and **cannot express a credit built from two overpayments** ($40.00 + $17.13 = $57.13) — a refund must be raisable against the CREDIT BALANCE | uuid/derived | system-derived | the clerk chooses **refund or credit**; neither is automatic |
| Other-account offset (offset first) | S58 | US-PAY-011 §5 · **BR-PAY-014 / BR-CUS-054 (PO 2026-08-12, OQ-135)** | `apps/customers/selectors.arrears_on_other_accounts` over `customer_accounts` (N:M) | numeric(18,6) | system-derived | refund **REFUSES** while an arrear stands ($57.13 vs $948.20); the offset is a **balance transfer**, never a subtraction from the `accounts.balance` cache (BR-CUS-015) |
| Write-off reason + note + GL | S35 Write-off | US-PAY-012 §5 · prototype + BR-PAY-020 | `write_offs` (reason, note, bad-debt GL ref — r12 #11) | enum/text/uuid | user-input / reference-data | note required; agency/deposit-flag checkboxes = **P-4/P-5** (no BR, out of v1) |
| Write-off approval + balance closure | Finance | US-PAY-012 §5 · BR-PAY-020 | `write_offs.approved_by` + ts (r12 #11); balance read-model → 0 on approval | uuid/ts | user-input / system-derived | Owner/Admin; money gated behind approval |
| Ledger handoffs (NSF pair+fee / reversing pair / DR credit-CR cash / DR bad debt-CR AR) | — | US-PAY-009/010/011/012 §5 · model §12 | posting service 🔒 → `journal_entries`/`journal_lines` (B2); payments writes NONE | rows | system-derived | balanced (CLAUDE.md #5) |
| Exception audits | — | EP-PAY-03 §5 · CLAUDE.md #7 | `audit_log` `payment.nsf/reversed`, `refund.*`, `write_off.*` (B2) | jsonb | system-derived | append-only |

*Section rows: 14*

---

## 4 · Outstandings + collections + returned mail (S34 · S35 · S32 · S30) — EP-PAY-04

| UI field | Screen | Source | DB column(s) | Type | Origin | Validation/notes |
|---|---|---|---|---|---|---|
| Outstandings row (rank/account/customer/balance) | S34 | US-PAY-013 §5 · A2 §S34 | read-model: `accounts` balance>0 (B2 partial index) + open `invoices` | rows | computed-display | balance desc default (BR-PAY-029) |
| Days late / age bucket | S34 | US-PAY-013 §5 · A2 §S34 (base UNKNOWN) | computed: today − oldest unpaid `invoices.due_date` → bucket 1–30\|31–60\|61–90\|90+ | int/enum | computed-display | due-anchor derivation = **P-2**; posted-by-due money excluded (BR-PAY-021) |
| Aging KPI strip | S34 | US-PAY-013 §5 · prototype | computed per bucket ($, accounts, %) | $/counts | computed-display | DSO per BR-REP-011 (P-1 resolved) |
| Last payment / Notice history / Autopay / Plan columns | S34 | US-PAY-013 §5 · A2 §S34 | max `payments.posted_at` · `notice_history` summary (r12 #7) · enrollment+intent reads (r12 #6, BR-PAY-015 — no retry action) · `payment_plans.status` | per-column | computed-display | A2 "Retry autopay" superseded |
| Collection tier / next-step date | S34 | US-PAY-013/014 §5 · BR-PAY-017 | collection state per account (r12 #7) | enum/dates | system-derived | advances per ladder step |
| Ladder settings | S66 | US-PAY-014 §5 · BR-PAY-017 | tenant collection settings (intervals per tier — r12 #7 family, keys = **P-13**) | ints | reference-data | seeded BR-PAY-017 defaults |
| Notice queue rows (all tiers, reminder, plan, NSF, receipts) | — | US-PAY-014/015/018/025 §5 · BR-NOT-005 | `outbound_messages` (r12 #16): account/payment ref, template, channel, status queued→sent→delivered/failed/bounced | rows | system-derived | queue-write ONLY; dispatcher sends; retry ×3 |
| Channel deferral markers (email W6 · SMS Twilio seam) | — | US-PAY-014/015/025 §5 · BR-PAY-017 + OQ-073 pattern | channel-config flags (US-BIL-023 pattern) | flag | reference-data | rows written, not dispatched before rails |
| Certified-final marker | — | US-PAY-014/015 §5 · A19 rule 3 (BR-CUS-039) | certified-mail marker on final-tier queue row | boolean | system-derived | required on final; SMS never alone |
| Medical-hold exclusion | S34/S35 | US-PAY-014/015 §5 · A15 | account medical-hold read (customers-owned) → skip + history | boolean | reference-data | excluded every step, skip recorded |
| notice_history append | S34/S21 | US-PAY-014/015 §5 · BR-PAY-017 + J4 | `notice_history` append-only (r12 #7) | rows | system-derived | every send AND skip |
| Reminder tone / notice tier / channels / cut date | S35 | US-PAY-015 §5 · prototype | tier template selection + queue rows; cut date in notice content + state | enum/date | user-input | tone→tier mapping = **P-9**; reconnect fee display from `charges` RECONN (BR-BIL-007, read-only) |
| Pay-now / text-to-pay link | S35 | US-PAY-015 §5 · BR-PAY-017 | token in email/SMS body — rails-deferred (W7) | flag | user-input | inert until rails |
| Mark-returned (single/bulk) | S30/S35 | US-PAY-016 §5 · BR-PAY-018 | delivery-return events (r12 #8) | rows | user-input | paper rows only; idempotent |
| bad_address flag + banner + chip + queue | S21/S32/S34 | US-PAY-016 §5 · BR-PAY-018 | `accounts.bad_address` (r12 #8) + queue read-model | boolean/rows | system-derived | balances unaffected |
| Paper suppression + config | — | US-PAY-016 §5 · BR-PAY-018 | held marker on paper `outbound_messages` rows; tenant setting suppress_paper_on_bad_address | flag/boolean | system-derived / reference-data | rows kept, released on verify |

*Section rows: 16*

---

## 5 · Payment plans (S24 · S21 · S34) — EP-PAY-05

| UI field | Screen | Source | DB column(s) | Type | Origin | Validation/notes |
|---|---|---|---|---|---|---|
| Plan totals (total, down) | S24 | US-PAY-017 §5 · BR-CUS-043 | `payment_plans.total_amount` (B2); down-payment column = **P-12** | numeric(18,6) | user-input | 0 < total ≤ balance |
| Installment rows | S24 step 2 | US-PAY-017 §5 · BR-CUS-043 | `payment_plan_installments` (seq, due_date, amount; UNIQUE (plan, seq)) (B2) | rows | system-derived (+edits) | (total−down)÷n half-up, remainder on FINAL; Σ = spread exactly (PE-13) |
| Per-plan elections (auto-charge, suspend-late-fees, suspend-disconnect) | S24 | US-PAY-017 §5 · BR-CUS-043 | plan election columns = **P-12** | boolean | user-input | late-fee suspension per-plan (CONFIRMED rule; column anchoring pending) |
| Plan status | S21/S34 | US-PAY-017/018 §5 · BR-CUS-044 + BR-PAY-016 | `payment_plans.status` proposed\|agreement_sent\|active\|closed ~~\|void~~ **— no `void`: SUPERSEDED PO 2026-08-11 (OQ-141)** (B2 O-8 resolved behaviorally; spelling 🔒 r12 #17) | enum | system-derived | active on customer e-signature ALONE; **`closed` is reached by paying every instalment OR by the utility WRITING THE ARREARS OFF (PO 2026-08-12, OQ-171) — never automatically** |
| Down payment | S22/S35 | US-PAY-017 §5 · BR-PAY-012 | `payments` purpose plan_down + plan link (r12 #2; link column P-12) | numeric(18,6) | user-input | PE-13: 50.00 |
| Installment payment link + on-time | S33 | US-PAY-017/018 §5 · BR-PAY-021 | payment ↔ installment linkage (P-12); on-time = posted_at ≤ installment due | uuid/dates | system-derived | clearing later never misses |
| Plan-notice settings | S66 | US-PAY-018 §5 · BR-PAY-016 | plan notice fields (r12 #9): reminder −3d, missed +1d, ~~void count 2~~ — seeded | ints | reference-data | tenant-config; **the void count triggers nothing (PO 2026-08-11) and the void notice has nothing left to announce** |
| missed_count | S21 | US-PAY-018 §5 · BR-PAY-016 | `payment_plans.missed_count` (r12 #9) | int | system-derived | ~~void at threshold~~ **a COUNTER WITH NO THRESHOLD (PO 2026-08-11)**; counts misses, never resets. **A PART-paid instalment counts as a miss (PO 2026-08-12, OQ-139)** |
| ~~Void transition~~ **Pause lift** + resume | S21/S34 | US-PAY-018/019 §5 · BR-PAY-016 + BR-PAY-017 · **PO 2026-08-12 (OQ-170)** | ~~status → void; full balance due~~ **no void and no acceleration**; the collections pause flag drops **the day after an unpaid instalment due date, no grace** → ladder resumes per tenant config over the arrears the plan spreads | boolean | system-derived | plan stays `active`; **after a BOUNCE the ladder resumes at RUNG 1 (OQ-133)** |
| Pause gate + disconnect block + late-fee election read | — | US-PAY-019 §5 · BR-CUS-043 | computed gate (active ∧ current) consumed by US-PAY-014 + billing late-fee flow (B1 reads) | boolean | system-derived | server-enforced |
| Agreement + signature event | S24 step 3 | US-PAY-017 §5 · BR-CUS-044 | e-sign envelope (DocuSign seam ⚠ B7); signed doc → account documents | event/pdf | integration | S67 template ① (BR-NOT-004) |

*Section rows: 11*

---

## 6 · Deposits & bank rec (S37 · S38 · S39 · S40) — EP-PAY-06

| UI field | Screen | Source | DB column(s) | Type | Origin | Validation/notes |
|---|---|---|---|---|---|---|
| Batch row (code, method, date, totals, status) | S37/S39 | US-PAY-020 §5 · B2 DDL + BR-PAY-025 | `deposit_batches` (code UNIQUE per tenant, method, deposited_on, recorded_total, bank_total, status) | row | system-derived | day × method by **posted_at** day — the drawer day (BR-PAY-025 / BR-REP-013, RQ-5; corrected 2026-08-11, DEF-065); DEP- series r12 #13, composed not allocated. **OQ-162 CLOSED 2026-08-12 (PO, *"Add the year + Date is important"*): the code must be YEAR-BEARING, and the banking DATE is a first-class field in its own right — a code is a label, never a data store** |
| Batch membership | S39/S33 | US-PAY-020 §5 · model §7 | `payments.deposit_batch_id` (B2) | uuid | system-derived | recorded_total = Σ members, never hand-edited |
| Batch status | S37 | US-PAY-020 §5 · B2 `batch_status` | in_transit\|unmatched\|matched\|reconciled | enum | system-derived | reconciled = locked (BR-PAY-004) |
| Statement file + period + bank account | S38 step 1 | US-PAY-021 §5 · prototype (CSV/OFX/QBO/QFX) | bank statement import record (r12 #10); bank-account registry = **P-10**; Plaid connect = **P-6** (out of v1) | file/dates | user-input | Owner/Finance only (BR-PAY-019); file idempotency (BR-PAY-028 family) |
| Bank line | S38/S39 | US-PAY-021 §5 · B2 DDL | `bank_lines` (posted_on, reference, amount, deposit_batch_id) | numeric(18,6)/text | integration | one per statement line |
| Auto-match rule + tolerance | — | US-PAY-021 §5 · BR-PAY-019 · **PO 2026-08-12 (OQ-161)** | match-rule config (r12 #10): amount equal + date ±3d default, finance setting — **applied MANY-TO-ONE as well as one-to-one: $2,840.00 + $14,280.00 tie to a single $17,120.00 bank credit** | rule | system-derived / reference-data | compares the BANK's posted date against the batch's drawer day; the ±N-day tolerance is what absorbs the gap. Read from S71 through `apps/payments/settings_seam.py`, never a constant |
| Match state + diff + KPIs | S38 step 2 | US-PAY-021 §5 · prototype | computed per row/statement | enum/$/counts | computed-display | exceptions → S40 only |
| Confirm & reconcile + reconciled-by | S38 step 3 / S39 | US-PAY-021 §5 · BR-PAY-004/019 | `deposit_batches.status` → reconciled + lock; trail event with actor/when | enum/uuid/ts | user-input / system-derived | matched batches only |
| Reconcile tiles (recorded / bank / difference) | S40/S39 | US-PAY-022 §5 · prototype | computed: recorded_total / bank_total / difference | numeric(18,6) | computed-display | difference = bank − recorded (PE-11 −5.00) |
| Resolution reason + GL | S40 | US-PAY-022 §5 · BR-PAY-019 | `bank_rec_resolutions` (reason_code, gl_account_id, SIGNED amount, note, journal_entry_id — r12 #10 family, append-only); posting via service 🔒 | enum/uuid | user-input | REQUIRED; Σ explanations = difference; "Force match anyway" superseded = **P-8**; a card day's fee line goes to **6800 Bank fees** (BR-PAY-040) |
| Bounced-item mark → NSF | S40/S39 | US-PAY-022 §5 · BR-PAY-013 | per-item cleared/bounced state → US-PAY-009 flow | enum | user-input | fee from the tenant NSF code |
| Reconciliation trail | S39 | US-PAY-023 §5 · prototype | append-only batch events (created/matched/flagged/resolved/reconciled/unreconciled — r12 #10 family, DDL 🔒 #17) | rows | system-derived | never truncated |
| Lock + Unreconcile | S39 | US-PAY-023 §5 · BR-PAY-004 · **PO 2026-08-12 (OQ-163, OQ-134)** | immutability on reconciled batches (trigger family B2 §3); Unreconcile = status reversal event, Owner/Finance, audited — **and it does NOT take the cash back out of the books: the PE-10 471.39 entries stand and a utility that needs them undone posts a manual journal entry** | — | system-derived / user-input | the ONLY reversal. **A member cheque that BOUNCES after the lock does not unlock or re-total the batch** ($2,840.00 stays $2,840.00) — the bounce is new rows plus the utility's bounce fee, recorded in payments |
| Deposit-slip export | S37 | US-PAY-020 §5 · prototype + IS-9 | computed file | file | computed-display | bookkeeper handoff |

*Section rows: 14*

---

## 7 · Autopay intents + receipts (S32 · S33 · S35) — EP-PAY-07

| UI field | Screen | Source | DB column(s) | Type | Origin | Validation/notes |
|---|---|---|---|---|---|---|
| Capture-intent row | S32/S33 | US-PAY-024 §5 · BR-PAY-015 | `autopay_capture_intents` (account, invoice, amount, scheduled_on, status awaiting-rails — r12 #6) | row | system-derived | one per enrolled-account bill at issue; scheduled_on = due date |
| Intent fulfilled display | S32/S33 | US-PAY-024 §5 · BR-PAY-015 (display) | computed over invoice settlement (`allocations`) — presentational = **P-7** | flag | computed-display | stored status set = r12 #6's |
| Enrollment + method read | S21/S33 | US-PAY-024 §5 · BR-CUS-059 | `payment_methods.is_autopay` + `accounts.autopay` (B2, customers-owned) | boolean/ref | reference-data | display only; NO charging path v1 |
| Receipt queue row | — | US-PAY-025 §5 · BR-PAY-024 + BR-NOT-005 | `outbound_messages` (r12 #16/#4): payment ref, template `receipt`, channel, status | rows | system-derived | triggered by CLEARING only (BR-PAY-021) |
| Receipt number (RCT-) | S33 | US-PAY-025 §5 · r12 #13 | tenant RCT- series ref | text | system-derived | unique per tenant |
| Receipt template + tokens | S35 | US-PAY-025 §5 · prototype + B2 `notification_templates` | template render ({first_name},{amount},{date},{balance},{confirmation}) | text/pdf | computed-display | notifications-owned content |
| Re-send elections (channels, attach-PDF) | S35 | US-PAY-025 §5 · prototype | new queue rows per election; opt-ins respected | boolean | user-input | audited; never a money event |

*Section rows: 7*

---

**Total rows: 94** (24 + 8 + 14 + 16 + 11 + 14 + 7)

---

## Discrepancies for PM review

Targets cited in story §5 tables that could NOT be verified as an existing column/table in B2 DDL or addenda (incl. r12), plus prototype elements with no ratified rule. Nothing invented; rows above reference these entries instead of asserting the target exists. Candidate-OQ items are also listed in the pack report for PO routing — none minted (session closed; genuine gaps routed via report).

| # | Story | Referenced target / element | Finding |
|---|---|---|---|
| P-1 | US-PAY-005, US-PAY-013 | **DSO KPI** (S32 Collections panel, S34 KPI strip) | **RESOLVED same day — BR-REP-011 (PO RQ-3):** DSO = (AR ÷ billed last 12 mo) × 365, rolling, posting basis. Tile renderable v1; stories' exclusion note superseded. |
| P-2 | US-PAY-013 | **Days-late base date** — A2 §S34 marks it "UNKNOWN exact base date" | Stories anchor on the oldest unpaid invoice's due_date (derivation from the due-anchored BR-PAY-017 ladder). Needs PO confirm. |
| P-3 | US-PAY-003 | **On-time evaluation for lockbox arrivals** where cleared_at (bank receipt) precedes posted_at (import commit) | BR-PAY-021 defines both dates and says billing consumes posted_at; a mail payment received by the bank on time but imported after the due date would read late. Ruling covers the counter case explicitly, not this inverse. Candidate OQ. |
| P-4 | US-PAY-012 | Write-off modal checkbox "**Send to collections agency instead**" | No BR covers agency handoff. Excluded from v1; candidate OQ. |
| P-5 | US-PAY-012 | Write-off modal checkbox "**Flag these accounts so future service requires a deposit**" | No BR covers the post-write-off deposit-required flag. Excluded from v1; candidate OQ. |
| P-6 | US-PAY-021 | S38 step-1 "**Or connect the bank**" (Plaid card, "Pull latest from Chase") | BR-PAY-019 ratifies statement IMPORT only. Direct feeds = integrations seam, no rule; excluded from v1. |
| P-7 | US-PAY-024 | Autopay intent "**fulfilled**" display state | r12 #6 stores status "awaiting-rails v1" only; the fulfilled state is computed presentation over invoice settlement. Confirm at rails (W7) whether it becomes a stored transition. |
| P-8 | US-PAY-022 | S40 "**Force match anyway**" button | Contradicts BR-PAY-019's reason+GL requirement; treated as superseded (no unexplained residual reconciles). Confirm the supersession. |
| P-9 | US-PAY-015 | Reminder modal "**Tone**" (Friendly/Firm/Final warning) | Mapped to tier templates by derivation from the BR-PAY-017 ladder; template-set mapping not itemized anywhere. Confirm. |
| P-10 | US-PAY-021 | **Tenant bank-account registry** (S38 "Bank account" select: "Chase Operating ••4021") | r12 #10 itemizes statement imports + match-rule config; a named bank-accounts reference table is not itemized. Confirm it rides r12 #10 / Eng-Lead DDL. |
| P-11 | US-PAY-010 | **Reversal reason lookup** (Bank chargeback / Data-entry error / Customer dispute / NSF) | Reason-code lookup families exist for billing (r10 #13, tenant-extensible); payments reversal reasons not itemized in r12. Confirm they ride the same lookup family. |
| P-12 | US-PAY-017, US-PAY-002 | **`payment_plans.down_payment`**, per-plan election columns (auto-charge / suspend-late-fees / suspend-disconnect), payment→plan/installment **linkage columns** | Rules CONFIRMED (BR-CUS-043, BR-PAY-012/016); r12 #9 itemizes notice fields + missed_count only. Columns need their r12/Eng-Lead anchor named (customers map carries down_payment/elections as PROPOSED-SCHEMA). |
| P-13 | US-PAY-014, US-PAY-018, US-PAY-016 | **Tenant setting keys** not individually enumerated: collection-ladder intervals per tier, nsf_privilege_n, plan-notice keys (beyond r12 #9's family), suppress_paper_on_bad_address | Families exist (r12 #7/#8/#9/#12 + config-over-constant principle); exact keys = Eng-Lead 🔒 (r12 #17). Confirm they ride the existing families. |
| P-14 | US-PAY-001 | **`payments.memo`** | A2 §S22 has the Memo field; B2 `payments` DDL has no memo column and r12 does not add one (US-CUS-012 §5 cites the same target). Needs a schema anchor; interim: audit payload. |
| P-15 | US-PAY-001 | **`payments.received_at` vs posted_at/cleared_at** | B2 keeps `received_at`; r12 #1 adds the two ruled dates. Whether received_at is superseded/dropped = Eng-Lead disposition at migration. |
| P-16 | US-PAY-021 | S38 step 3 offers the lock as an **optional checkbox** — *"Lock the reconciled batches (prevents back-dated edits)"*, default on | BR-PAY-004 makes the lock UNCONDITIONAL: a reconciled batch's totals and membership are immutable and Unreconcile is the only way back. The product locks on reconcile with no election, and the database enforces it (payments 0005); the checkbox is not built. Reported 2026-08-11 (bank-rec lane) — the prototype should drop it or the rule should gain an election, and the rule is the one that is CONFIRMED. |
| P-17 | US-PAY-021, US-PAY-022 | The prototype names **GL 6200 Merchant Fees**, **1010 Operating Cash** and **1020 Undeposited Funds** | None of the three is in the ❄️ finance-signed chart (B5 line 74: **1000 Cash · 1010 Undeposited funds · 6800 Bank fees**), and 1010 means the OPPOSITE of the prototype's label. The product resolves accounts BY DESIGNATION and never by number. **DEF-067**, reported 2026-08-11 (bank-rec lane); the epic's TC-3 copy of 6200 is corrected. The prototype's *"$227.50 card/bank fees"* also lumps an $80.00 CASH SHORTAGE in with processor fees, which is a different reason and a different account. |
| P-18 | US-PAY-021, US-PAY-022 | S38 step 2 shows a NON-EXACT bank line already PAIRED to a batch (*"Off by $100"*, *"Fees?"*) | The engine auto-matches on EXACT amount + date tolerance only (BR-PAY-019) and leaves a non-exact line unmatched until a human names the pairing — pairing on method or on a bank's prose is a guess (BR-PAY-023: never auto-guess silently). The screen may still SUGGEST a pairing; it may not have made one. Reported 2026-08-11. |
| P-19 | US-PAY-021 | The prototype's S38 step 3 shows a fee-posting election and NOTHING about cash | Since the PO's ruling of 2026-08-11 (BR-PAY-039) reconciling is the event that **realises the cash** — DR 1000 Cash / CR 1010 Undeposited funds — which no S38 screen mentions. The screen understates what the button does. Reported 2026-08-11 for the design session. |

> **Addendum 2026-08-08:** PP battery closed — P-2 days-late (BR-PAY-032), P-3 posting-date user-input (BR-PAY-033), P-7 fulfilled-computed (BR-PAY-034), P-8 force-match superseded + P-9 tone mapping (BR-PAY-035); P-10..14 anchored in B2 r14; P-15 = Eng-Lead per r14 #8. All 15 discrepancies now resolved or routed. **Addendum 2026-08-11 (bank-rec lane):** P-16..P-19 added from a law-6 diff of the built engine against the prototype's S37–S40 — the optional lock checkbox, three GL codes in no signed chart (DEF-067), a pre-made non-exact pairing, and a step-3 screen that never mentions the cash realisation it now performs (BR-PAY-039). **19 discrepancies.**
