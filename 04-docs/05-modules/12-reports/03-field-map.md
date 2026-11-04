# reports — Field Map

One row per field. Origin: user-input | system-derived | reference-data | integration | computed-display. Rows cite A2 § or "prototype-extracted"; underivable = GAP (mint an OQ).
> Consolidated from the US-REP-001..018 §5 tables (pack authoring 2026-08-09); verified against B2 (+addenda r8/r9/r10/r12/r13/r14) and NFR-26 rollup law. The module owns no financial tables; every money figure is a read-model (BR-REP-002). Run/definition/schedule metadata storage is NOT yet anchored in B2 — see R-1 below.

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Catalog cards (key, name, group) | S44 | A14 §Report library + prototype + BR-REP-007 | code-defined canned registry (no tenant table) | text | reference-data | ratified set only; six additions incl. | OK (US-REP-001) |
| Routing to ledger-owned reports | S44 | BR-REP-003/005 + A1/A9 | routes to S56/S59/S60/S41/S42 | — | computed-display | never re-implemented | OK (US-REP-001) |
| Viewer params (range, service, class, group-by) | S46 | A14 §Viewer + BR-REP-006 | query over read-models; `tenant_services`, class + status lookups | enum/dates | user-input | LIVE vocabularies only; From ≤ To; IS-4 URL state | OK (US-REP-002) |
| Date-basis label | S46/S7/S32 + files | BR-REP-001 | rendered label per report/widget definition + filename `{basis}` segment | text | computed-display | REQUIRED on every money header/file | OK (US-REP-002/003/016/018) |
| Generated-by line | S46 | prototype-extracted | run metadata, tenant TZ (IS-8) | text | system-derived | — | OK (US-REP-002) |
| CSV file contract | all reports | IS-11 (BR-REP-018) | streamed from read-model under RLS | file | computed-display | snake_case single header · 2dp money · ISO dates · no metadata rows · ≤50k (BR-SHL-016) | OK (US-REP-003) |
| PDF skeleton | finance/compliance reports | IS-11 | rendered over same rows | file | computed-display | letterhead/period/filters/basis/generated-by/X-of-Y/totals | OK (US-REP-003) |
| Export audit | — | CLAUDE.md #7 + BR-SHL-016 | `audit_log` (`report.exported`) | jsonb | system-derived | money exports always | OK (US-REP-003) |
| Run row (report, run_at, range, by, rows, format) | S45 | A14 §Scheduled + A6 §S46 `report_run` | **report_runs — B2 anchoring pending (R-1, DDL 🔒)** | row | system-derived | append-only history | GAP → R-1 |
| Generated-file ref + retention | S45 | IS-11 "3 days, tenant-config" | file store ref (mechanics 🔒) + tenant retention setting | file/int | system-derived / user-input | delete at expiry; row persists | OK w/ R-1 (US-REP-004) |
| AR aging buckets + days-late | S46 | A14 §Fully-built + BR-CUS-016/048 + BR-PAY-032 | open-invoice due-date math + `account_opening_buckets` (r9 #2) aged forward | numeric(18,6)/days | computed-display | derived, never stored; Σ = AR tie-out (BR-REP-008) | OK (US-REP-005) |
| DSO trend | S46/S7/S32 | prototype + BR-REP-011 | (AR ÷ billed-12-mo) × 365, rolling, posting | days | computed-display | single ruled formula | OK (US-REP-005/016/018) |
| Billing-register row + bill_type | S46 | A14 §Fully-built + item 6 | issued `invoices` (+`bill_type` r10 #12) + lines | row/enum | computed-display | issued only; 6-value vocabulary; usage w/ explicit unit (CLAUDE.md #3) | OK (US-REP-006) |
| Revenue by service & rate | S46 | A14 §Fully-built + item 9 | `invoice_lines` grouped service × tariff w/ drill-back | numeric(18,6) | computed-display | reconciles to S36 dimension view; rate schedule never a dimension | OK (US-REP-006) |
| Payments-by-method rows + purpose | S46 | A14 card + item 6 | `payments` cleared-in-period by method; `.purpose` (r12 #2); both dates (r12 #1) | $/enum | computed-display | clearing basis; BILL-only in collection framings (BR-REP-014); intents excluded (BR-PAY-015) | OK (US-REP-007) |
| Read-completeness rows + channel | S46 | A14 card + item 6 + BR-MET-049 | `meter_reads` channel set (r8) vs plan-required set via service fn | rows/% | computed-display | read-less services excluded; estimates labeled (US-MET-014) | OK (US-REP-008) |
| High-usage rows | S46 | A14 card + BR-MET-020/021 | flag-outcome read-model; thresholds from S64 settings | rows | computed-display | tenant thresholds, never constants | OK (US-REP-008) |
| New/closed counts + Active KPI | S46/S7 | A14 card + BR-REP-012 | `accounts.created_at` + status lookup (BR-CUS-055, r9 #7) | counts | computed-display | Active = Active+Marked disconnect+Vacation hold exactly | OK (US-REP-008/016) |
| Corrections-report rows | S46 | A14 item 5 + BR-BIL-014 | `correction_cases` + linked credit_notes/rebills (r10 #9) | rows/$ | computed-display | approved money only | OK (US-REP-009) |
| Back-bill/penalty rows | S46 | A14 item 5 + BR-BIL-018/019 | `invoices.bill_type` backbill\|penalty + tariff-version refs + reason/approver | rows/$ | computed-display | engine-priced only; no hand-typed amounts | OK (US-REP-009) |
| Write-off rows | S46 | A14 item 5 + BR-PAY-020 | `write_offs` (r12 #11) + GL + aging snapshot | rows/$ | computed-display | separate from collections (BR-REP-009) | OK (US-REP-009) |
| Budget-status rows | S46 | A14 item 5 + BR-BIL-017 | `account_budget_status` (r10 #5) + tenant budget settings | rows/$ | computed-display | parameters = tenant settings | OK (US-REP-009) |
| Delivery-queue-health rows | S46 | A14 item 5 + BR-BIL-016/BR-NOT-005 | `outbound_messages` statuses (r12 #16) | counts/rows | computed-display | read-only; re-queue links to owners | OK (US-REP-009) |
| Returned-mail rows | S46 | A14 item 5 + BR-PAY-018 | delivery-return events + `accounts.bad_address` (r12 #8) | rows | computed-display | balances unaffected | OK (US-REP-009) |
| Builder dataset | S47 | A14 §Builder | six-dataset registry (invoices/payments/accounts/meter_reads/adjustments+credit_notes/premises+units) | enum | user-input | CLOSED list; new entities = canned only (BR-REP-007) | OK (US-REP-010) |
| Builder columns | S47 | A14 §Builder + IS-5 + BR-PAY-021 | per-dataset column registry (payments: both dates; reads: channel + unit) | list | user-input | identity always on | OK (US-REP-010) |
| Builder filter/group/range/sort | S47 | A14 §Builder | predicates over the dataset read-model; past-due = derived (BR-CUS-016) | enum+values | user-input | named date field on Payments; typed inputs | OK (US-REP-011) |
| Saved definition | S47/S44 | A14 "Save & schedule" | **saved report definitions — B2 anchoring pending (R-1, DDL 🔒)** | row (params jsonb) | user-input | params only, never rows (BR-REP-002); creator + audit | GAP → R-1 |
| Schedule row (report, cadence, formats, recipients, next-run) | S45 | A14 §Scheduled + IS-11 | **report schedules — B2 anchoring pending (R-1, DDL 🔒)** | row | user-input / system-derived | CSV/PDF only; tenant-TZ next-run; IS-1/IS-6 lifecycle | GAP → R-1 |
| Scheduled-email queue row | — | BR-REP-007/017 + BR-NOT-005 | `outbound_messages` (r12 #16) w/ file ref, deferred → W6 | row | system-derived | never sent inline; dispatcher-only | OK (US-REP-015) |
| S7 KPI strip (AR/cash/MTD/unbilled/failed/active) | S7 | prototype + A14 §Dashboard + BR-REP-010/012 | dimension AR · cleared-today payments · MTD revenue postings · unbilled `meter_reads` · failed payments · status-class counts | mixed | computed-display | bases per BR-REP-001/010, all labeled | OK (US-REP-016) |
| S7 panels (billing status, exceptions, activity, aging, service mix, to-do) | S7 | prototype + A14 item 10 | `bill_runs` states · S31.3 cases · event read-model · US-REP-005 derivation · service dimension · route-outs | rows | computed-display | live sources; Σ aging = AR KPI | OK (US-REP-016) |
| Ops chips ×5 | S7/S32 | BR-REP-015 (RQ-7) | `outbound_messages` · BR-BIL-015 queue (r10 #7) · bad-address queue (r12 #8) · `correction_cases` (r10 #9) · tie-out views (r13 #6) | counts/state | computed-display | = owners' counts; drift undismissable (BR-LED-007) | OK (US-REP-017) |
| S32 label pair + purpose rule + dunning names | S32 | BR-REP-010/014/016 | labels on US-PAY-005 panels; `payments.purpose`; cadence config (r14 #5 / S70) | text/enum | computed-display / reference-data | posting/clearing pair; BILL-only; day numbers from config | OK (US-REP-018) |

## Discrepancies & prototype-only items (verified against B2 + NFR-26)

| # | Finding | Disposition |
|---|---|---|
| R-1 | **No B2 tables exist for report metadata**: run history (`report_runs` — named by A6 §S46), saved custom definitions, schedules, generated-file refs + retention. All are metadata-only (never money); IS-11/A14 fully determine their FIELDS but no schema addendum anchors them. | **GAP** — candidate OQ (pack report); Eng-Lead anchoring batch item (DDL 🔒 as always). Stories buildable — fields specced, storage pending anchor |
| R-2 | A14: reports beyond the fully-built set "use a generic viewer … real columns UNKNOWN per report" — Disconnect & reconnect, Meter inventory, PUC quarterly filing, User activity audit, Rate change history have no ratified column sets. Cards open the generic viewer (US-REP-002); nothing invented. User activity audit additionally overlaps the S61 audit-log viewer (OQ-029 design). | Candidate OQ (pack report) — per-report column ratification; S61 overlap flagged |
| R-3 | S47 "Save" — saved-definition visibility scope (private-to-creator vs all Reports-access staff) underivable from A14; v1 written as tenant-listed with creator recorded. | Candidate OQ (pack report), non-blocking |
| R-4 | A14 line 25 scheduled delivery "Email · PDF/**Excel**/CSV" — Excel DROPPED v1 by IS-11 ("CSV please"); email = W6 (BR-REP-017). Prototype S45 "Excel" rows re-specced to CSV. | Superseded — build per IS-11/A14 item 11 |
| R-5 | S46 "☆ Favorite" action — target surface for favorites (S44 ordering? a Favorites group?) underivable from the prototype (toast only). Action recorded; surfacing unspecced. | Candidate OQ (pack report), non-blocking |
| R-6 | Prototype schedule recipient "bookkeeper" implies an EXTERNAL email recipient; recipients are otherwise tenant staff. External-recipient policy = W6 email concern (BR-REP-017). | Candidate OQ (pack report) — decide before W6 dispatch |
| R-7 | Prototype DSO shows "target 15" — a target/threshold value with no ratified home (tenant setting?). DSO value itself fully ruled (BR-REP-011); the target line omitted from stories. | Candidate OQ (pack report), non-blocking |
| R-8 | "PUC quarterly filing · Auto-formatted Texas PUC template" — regulatory template content is jurisdiction-specific and human-owned; no agent story fills it. | Routed — human/finance-owned artifact (with R-2 columns) |
| R-9 | Prototype S7 KPI "MTD revenue … of $410k forecast" — a forecast figure with no ratified source anywhere in A/B docs. Widget renders without the forecast line v1. | Candidate OQ (pack report), non-blocking |
| R-10 | NFR-26 verified: dashboards/reports read rollups for CLOSED periods (rollups materialize at close, immutable); open-period figures compute live from dimensions. Stories cite NFR-26; rollup mechanics Eng-Lead 🔒. | OK — consumed, no gap |
