# customers — Field Map
> Reconciled 2026-08-08 against PO rulings (BR-CUS-046..059) — propagation sweep.

One row per field. Origin: user-input | system-derived | reference-data | integration | computed-display. Rows cite A2 § or "prototype-extracted"; underivable = GAP (mint an OQ).

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Account # | S17/S21 | prototype (`A-#####`) | accounts.account_no (tenancy series, BR-TEN-035) | text | system-derived | unique per tenant | mapped |
| Customer name | S17/S21 | prototype | customers.display_name + contacts.full_name (is_primary) — customer entity per BR-CUS-054 | text | user-input | required | mapped / PROPOSED-SCHEMA (customers) |
| "All accounts for this customer" chip | S21 header | BR-CUS-054 (PO ruling; artwork pending design) | customer_accounts links | reference | computed-display | tenant-scoped | PROPOSED-SCHEMA |
| Premise / service address | S17/S21 | prototype | unit → premises join (⚠ metering read) | text | computed-display | — | mapped |
| Service tags | S17/S21 | prototype (svc-tag E/W/S) | service_agreements active → services catalog | reference | computed-display | active only | mapped |
| Balance | S17/S21/S22 | prototype ($ 2dp) | accounts.balance (cached; ledger = truth; = Σ opening buckets at import, BR-CUS-048) | numeric(18,6) USD | system-derived | 2dp display | mapped |
| Last bill date | S17 | prototype | latest issued invoice (⚠ billing read) | date | computed-display | "—" if none | mapped |
| Account status + aging pill | S17/S21 | prototype + A5 | accounts.status (BR-CUS-055 seeded lookup, tenant-extensible) + derived aging (BR-CUS-016) | lookup + derived | system-derived | vocabulary per BR-CUS-055 | mapped (OQ-058 closed; class seed OQ-064) |
| Status segment filter + AC-8 filters | S17 | prototype (All/Current/Past due/Closed) + BR-CUS-053 (status·category·plan·autopay·balance>0) | derived filter | enum | user-input | BR-CUS-016/053 | mapped |
| Search fields (acct#/name/address/meter#) | S17 | prototype + BR-CUS-053 | accounts + customers/contacts + address + asset # (⚠ reads) | text | user-input | IS-3; customer hit returns all linked accounts (BR-CUS-054) | mapped |
| Customer type | S18.1 | prototype (Ind/Bus/Gov) | accounts.account_type_id (r5 #12/#19) + customers.kind | uuid/enum | user-input | seeded set | mapped / PROPOSED-SCHEMA (kind) |
| DOB | S18.1/S21 | prototype | contacts.dob | date | user-input | masked display (BR-CUS-045) | mapped |
| ID type | S18.1 | prototype (DL/State/Passport/SSN-4/EIN) | contacts.gov_id_type | enum | user-input | — | PROPOSED-SCHEMA |
| ID number (last 4) | S18.1/S21 | prototype ("****4218") | contacts.gov_id_last4 (tokenized) | text | user-input | last-4 only | mapped |
| Phone / Email | S18.1/S21 | prototype | contacts.phone / contacts.email — edits propagate via the customer entity (BR-CUS-054) | text/citext | user-input | email format | mapped |
| Mailing address | S18.1/S21 | prototype ("Same as service") | addresses (kind mailing) | text | user-input | optional | mapped |
| Duplicate-check results | S18.1/S19.2 | prototype copy | query over customers + contacts; link via customer_accounts (BR-CUS-054) | — | computed-display | advisory (BR-CUS-019) | PROPOSED-SCHEMA (OQ-057 closed) |
| Premise + unit picker | S18.2/S19.1 | prototype | accounts.unit_id (⚠ cross-module FK) | uuid | user-input | vacant/reserved only (BR-CUS-020) | mapped |
| Service start / move-in date | S18.2/S19.3 | prototype | accounts.opened_at + service_agreements.started_on | date | user-input | BR-CUS-022; chained same-day ⇒ move-out day + 1 (BR-CUS-056) | mapped |
| Bill from (prorate / next cycle) | S19.3 | prototype | billing-start instruction on handoff | enum | user-input | B4.3 / GT-3 | mapped |
| Initial/final reads + source | S18.2/S19.3/S20.2 | prototype | meter_reads via metering service (⚠ B1) | numeric + enum | user-input/integration | BR-CUS-021, BR-MET-015/017; move-day reading owns the boundary (BR-CUS-056) | mapped |
| Plan (default + override) | S18.3/S19.4 | prototype ("(unit default)") | account_plan_assignments + unit_plan_assignments writeback (r5 #13) | uuid + int | user-input | BR-CUS-014 sc.2; published only | PROPOSED-SCHEMA (account side) |  ⚠ **`account_plan_assignments` is SUPERSEDED (PO 2026-08-11)** — no account-side plan table is built; the plan lives once on `units.rate_plan_id` and the account derives it. See BR-CUS-029.
| "What they'll be billed for" table | S18.3 | prototype | plan_services + plan_rate_schedules (⚠ rating read) | reference | computed-display | — | mapped |
| Paperless / SMS reminders | S18.4/S21 | prototype | accounts.paperless / accounts.sms_reminders | boolean | user-input | capture; execution scope per module owners | PROPOSED-SCHEMA |
| Autopay flag + method ref | S18.4/S21 | prototype | accounts.autopay + accounts.autopay_method_id (⚠ payments) | bool + uuid | user-input | CAPTURE-ONLY v1 (BR-CUS-059; execution W7, no re-enrollment) | mapped / PROPOSED-SCHEMA (method ref) |
| Budget billing | S18.4 | prototype | accounts.budget_billing (plan flag interaction BR-RAT-043) | boolean | user-input | BR-RAT-043; level-pay math = billing W3 | PROPOSED-SCHEMA |
| Statement language | S18.4 | prototype (English/Español) | accounts.statement_language | text | user-input | English-only v1 (IS-8) | PROPOSED-SCHEMA |
| Bill delivery day | S18.4 | prototype (Default/Day 8/Day 15) | DROPPED — cycles decide bill dates; "bill me on the 15th" = cycle assignment (BR-MET-009) | — | — | — | dropped (BR-CUS-060; OQ-059 closed) |
| Deposit rule (read-only) | S18.5/S19.4 | prototype + BR-RAT-020/023 | plan_deposit_rules[account_type] (r5 #8, ⚠ rating read) | numeric(18,6) | reference-data | fixed lookup | mapped |
| Deposit election (collect/first-bill/waive/carry) | S18.5/S19.4 | prototype | accounts.deposit_election | enum | user-input | exclusive (BR-CUS-023); `imported` value flagged (US-CUS-023) | PROPOSED-SCHEMA |
| Deposit waive reason | S18.5 | prototype | waive-reason lookup + accounts.deposit_waive_reason_id | uuid | user-input | required when waived | PROPOSED-SCHEMA |
| Deposit on file | S21/S20.3 | prototype ($150.00) | accounts.deposit_on_file | numeric(18,6) | system-derived | ≥ 0 | mapped |
| Deposit original receipt date | S21 / import | BR-CUS-050 | accounts.deposit_received_on — interest accrues from the true date | date | user-input/system-derived | required when deposit > 0 (import) | PROPOSED-SCHEMA |
| Deposit interest accrued | S21/S20.3 | prototype ($3.20) | accounts.deposit_interest_accrued — accrual per BR-CUS-057 (engine US-CUS-023 §7) | numeric(18,6) | system-derived | tenant rate, default 0% | PROPOSED-SCHEMA (col) / rule CONFIRMED (OQ-061 closed) |
| Deposit interest rate (tenant) | S66 Billing defaults | BR-CUS-057 | tenant billing settings deposit_interest_rate_annual DEFAULT 0 | numeric fraction | reference-data | ≥ 0; tenant-set | PROPOSED-SCHEMA |
| Credit tier (computed) | S18.5/S21 | prototype ("Passed · standard tier" / "A") | accounts.credit_tier — COMPUTED cache per BR-CUS-058; rule params credit_tier_rules (12-mo window; 0=A, 1–2=B, 3+=C; tenant-configurable) | text | system-derived (computed) | informational; no input path | mapped (col) / PROPOSED-SCHEMA (rule params) — OQ-062 closed |
| Tax-exempt + ref + expiry | S21 edit | B4.2 schema note | accounts.tax_exempt / .tax_exempt_ref / .tax_exempt_expires | bool/text/date | user-input | account-level (B4.2) | mapped |
| Solar/battery capacity units | S18/S21 | BR-CUS-012 + B2 r5 #5 | account_capacities (service, units ≥ 0, effective_from/to) | numeric(18,6) | user-input | ≥ 0; effective-dated | mapped |
| Portal access panel (last login / enabled) | S21 Overview | prototype | accounts.portal_enabled; login data deferred (portal out of v1 scope, roadmap) | boolean | system-derived | capture-only v1 | PROPOSED-SCHEMA / deferred |
| Move-out date + reason | S20.2 | prototype | accounts.closed_at + accounts.close_reason | date + enum | user-input | reason required ON THE SCREEN and optional at the door; outgoing pays the move day (BR-CUS-056) | **mapped / BUILT 2026-09-20** (PO ruling, option A; migration `customers/0058`). It read *PROPOSED-SCHEMA (reason)* until then. Five fixed codes, not a lookup table — `OQ-CUS-12512` is whether that becomes tenant-editable |
| Final-bill preview lines | S20.3 | prototype | computed from handoff — no invoice write (BR-CUS-031) | numeric USD | computed-display | B4.3 through the move day | mapped |
| Refund method | S20.3 | prototype (ACH/check/carry) | refund instruction → payments refunds (B2 r2) | enum | user-input | carry ⇒ same customer entity (BR-CUS-054) | mapped |
| Close-out checklist | S20.4 | prototype (5 checkboxes) | notification instructions + derived vacancy (BR-MET-036) | boolean | user-input | BR-CUS-030 | mapped |
| Record-payment modal fields | S22 | A2 §S22 (7 fields) | payments.* via service (amount/date/method/reference/memo + allocation instruction) | per A2 | user-input | amount > 0; BR-PAY-001/010; method records arrival only (BR-CUS-059) | mapped |
| Adjust modal fields | S22 | A2 §Adjust (6 fields) | billing adjustment row via service (sign/amount/reason/bill ref/GL/approval) | per A2 | user-input | BR-CUS-038 approval | mapped |
| Issue-credit modal fields | S22 | prototype (amount/reason/apply/memo/notify) | credit row via service; refund path via payments | numeric/enum/text | user-input | > 0; memo customer-visible | mapped |
| Statement type + period + delivery | S22 | prototype | ledger read-model params (B2 r2) + notification channels | enum/dates/bool | user-input | from ≤ to; BR-CUS-040 | mapped |
| Print-bill picker + copies | S22 | prototype | issued invoices read; print-job params | uuid/int | user-input | issued only | mapped |
| Disconnect tier / cut date / delivery | S22 | prototype (3 tiers) | notice instruction + notice_history append (⚠ notifications) | enum/date/bool | user-input | BR-CUS-039; certified for final | mapped |
| Reconnect fee display | S22 | prototype ($45.00 read-only) | charges catalog (⚠ rating; BR-BIL-007) | numeric USD | reference-data | display-only | mapped |
| Note title/body/pinned/customer-visible | S21/S22 | prototype | account_notes | text/bool | user-input | title or body; visible inert v1 | PROPOSED-SCHEMA |
| Document metadata | S21 | prototype (5 types) | account_documents (type lookup, uploader, size, storage ref) | text/int | user-input/system | audit-locked system docs | PROPOSED-SCHEMA |
| Change-plan picker + notes | S23.1 | prototype | rate_plans published + compatibility derivation | reference | user-input | BR-CUS-041 | mapped |
| Effective date (3 options) | S23.2 | prototype | assignment rows' assigned_from | date | user-input | ≥ unbilled period start | mapped |
| Proration preview + net impact | S23.2 | prototype | rating engine service (US-RAT-012) — display only | numeric USD | computed-display | B4.3 / GT-3 | mapped |
| ~~Deposit differential~~ | ~~S23.2~~ | ~~prototype ("–$50 refund")~~ ⚠ **REMOVED — PO 2026-08-12 (OQ-179): there is NO mid-plan deposit differential; the deposit settles only at closure** | ~~plan_deposit_rules diff (BR-CUS-042 — SUPERSEDED)~~ **nothing computed, quoted or billed** | — | — | **PO 2026-08-12 supersedes the OQ-011 closure** | **not built — neither −$18.50 nor −$68.50 is shown** |
| Plan-change notify + eligibility log | S23.3 | prototype | notification queue (A19 email) + audit link | boolean | user-input | BR-RAT-043 advisory | mapped |
| Payment-plan amount/term fields | S24.1 | prototype (6 fields + 3 toggles) | payment_plans via service (+ down_payment, autopay_enabled, suspend_late_fees, suspend_disconnect) | numeric/int/enum/date/bool | user-input | BR-CUS-043 | mapped / PROPOSED-SCHEMA (4 cols) |
| Installment schedule rows | S24.2 | prototype | payment_plan_installments (seq, due_date, amount) | numeric/date | user-input | Σ = total (BR-CUS-043) | mapped |
| Agreement elections + document | S24.3 | prototype + A19 §3 | S67 template render + DocuSign seam (B7) + account_documents copy | boolean/pdf | user-input/system | BR-CUS-044 | mapped |
| Payment-plan status | — | A5 · **BR-CUS-044 as amended** | payment_plans.status (~~+ PROPOSED defaulted~~ **no `defaulted` — SUPERSEDED PO 2026-08-11**; B2 O-8); **`closed` reached by paying every instalment OR by the utility WRITING THE ARREARS OFF (PO 2026-08-12, OQ-171)** | enum | system-derived | activation on sign; **closure on write-off is never automatic** | mapped |

## EP-CUS-07 — Account onboarding import (BR-CUS-046..052; wizard screen ID pending OQ-063)
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Import file / batch | import wizard | BR-CUS-046/051 | account_import_batches + account_import_rows (staging, S28/S52 pattern) | file/CSV | user-input | ≤10,000 rows; staged | PROPOSED-SCHEMA |
| customer_ref (column) | import wizard | BR-CUS-054 | customers.external_ref (UNIQUE per tenant) + customer_accounts links | text | user-input | distinct ref → one customer | PROPOSED-SCHEMA |
| Customer + contact columns | import wizard | BR-CUS-046 | customers + contacts + addresses | text/date | user-input | PII per BR-CUS-045 | PROPOSED-SCHEMA (customers) |
| Account # (optional) | import wizard | BR-CUS-046 | accounts.account_no (blank → tenancy series) | text | user-input/system-derived | duplicate = row error (no update path) | mapped |
| Premises/unit ref (REQUIRED) | import wizard | BR-CUS-046/047 | accounts.unit_id resolution | text → uuid | user-input | must exist first — never auto-create | mapped |
| Category / sub-type / status / plan (legacy codes) | import wizard | BR-CUS-046/052 | value-mapped → account_types/subtypes, BR-CUS-055 status lookup, rate_plans | text → uuid | user-input | mapped values only; unmapped = row error | mapped (via mapping step) |
| Source→target value map | import wizard | BR-CUS-052 | account_import_value_maps (batch-scoped, immutable post-commit — audit) | rows | system-derived | one row per (batch, column, value) | PROPOSED-SCHEMA |
| Status behavior class (seed) | Reference data | BR-CUS-055 | account-status lookup + behavior_class column (billable/billable-base-only/non-billable/terminal) | enum | reference-data | seed status→class assignment undetermined | GAP → OQ-064 |
| Import plan-override assignment source | — | BR-CUS-014 sc.2 | unit/account plan assignment `source` enum — needs an `import` value | enum | system-derived | flagged, not decided | PROPOSED-SCHEMA (enum value) |
| Opening bucket columns (Current/31–60/61–90/90+) | import wizard | BR-CUS-048 | account_opening_buckets (as_of, bucket, amount; append-only) + accounts.balance = Σ | numeric(18,6) USD | user-input | ≥ 0; negative (credit balance) undetermined | PROPOSED-SCHEMA / GAP → OQ-065 (negative) |
| Derived aging from buckets | S17/S21/aging report | BR-CUS-048 | bucket age + calendar days since as_of — computed | enum | computed-display | GT-16 forward-aging rule | mapped (derived) |
| Opening JE handoff | — (service contract) | BR-CUS-049 | handoff view/table → journal_entries + journal_lines via ledger posting service ONLY (source_type opening_balance; DR AR / CR opening-clearing) | rows | system-derived | balanced; immutable; idempotent per (batch, account) | PROPOSED-SCHEMA (handoff shape + source_type value + seeded clearing account) |
| deposit_amount / deposit_received_on (columns) | import wizard | BR-CUS-046/050 | accounts.deposit_on_file + accounts.deposit_received_on | numeric/date | user-input | date required when amount > 0 | mapped / PROPOSED-SCHEMA (date col) |
| Import result summary + error report | import wizard | BR-CUS-051 | computed over staging rows | text/jsonb | computed-display | "N created · N failed" always shown | mapped (derived) |

> **Addendum 2026-08-08 (OQ-064/065 closed):** the two GAP rows above are resolved — status behavior-class seed = Pending non-billable · Active/Marked-disconnect billable · Hold/Suspended base-only · Closed terminal (BR-CUS-055); opening CREDIT balances import as carried account credit, buckets stay debit-only (BR-CUS-061). Origin for both: reference-data / system-derived per B2.
