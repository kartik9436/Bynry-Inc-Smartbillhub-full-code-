# EP-REP-01 — Report center: library, viewer, downloads, run history (S44 · S46 · S45-runs)

**Module:** reports · **Wave:** W5 · **Screens:** S44, S46, S45 (Recent-runs half) · **Status:** draft (BR-REP-001..018 all CONFIRMED; IS-11 ratified)

## Scope
**In:** the **S44 report library** (cards by Financial/Operations/Compliance per A14 + the six audit-added reports, BR-REP-007) with routing to viewer/builder/scheduled · the **S46 report viewer** (parameter bar with LIVE vocabularies per BR-REP-006, KPI strip + report table, generic viewer for column-unknown reports, date-basis label on every money header per BR-REP-001) · **IS-11 downloads** (CSV always + PDF skeleton, filename convention, 50k guard, money-export audit — BR-REP-018/BR-SHL-016) · the **Recent-runs list** on S45 with the 3-day generated-file retention window (IS-11).
**Out:** the ledger-owned report stories — trial balance S56 (US-LED-008), account ledger S59 (US-LED-009), by-premises S60 (US-LED-010), dual-basis remittance S41 (US-LED-014), S42 export batches (US-LED-016) — S44 cards ROUTE to them, nothing re-implemented (BR-REP-003/005) · canned-report content (EP-REP-02) · builder (EP-REP-03) · schedules (EP-REP-04) · dashboards (EP-REP-05) · queue dispatch (US-NOT-002).
**Tables:** read-models only (module owns no financial tables); run/definition storage = `report_runs` family — B2 anchoring pending (pack report R-1, DDL 🔒).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S45 · Recent runs | report name | format (PDF/CSV), by (user/Scheduled), report | run_at desc | run_at, report, rows, format | Report · Run at · Range · By · Rows · Format · Download / +basis, filename, expires-on (IS-5) | Download ↓ (until retention expiry) | — | — (this list IS the download surface) |

*(S44 is a card grid, not an IS-2 list. S46 is a parameterized viewer — param bar + KPI strip + result table per A14; IS-4 URL-persisted state.)*

## Stories

---
id: US-REP-001
epic: EP-REP-01
module: reports
screens: [S44]
wave: 5
status: draft
blocked_by: []
depends_on: [US-SHL-001, US-LED-008, US-LED-009, US-LED-010, US-LED-014]
journeys: [J5]
rules: [BR-REP-002, BR-REP-007, BR-REP-006]
golden_tests: []
finance_calc: none
---
### US-REP-001 — S44 Report library: the full canned catalog + routing (nothing re-implemented)

**1 · Details** — As staff, I want the **Reports library** (S44): cards grouped **Financial / Operations / Compliance** per A14 §Report library + the prototype card set (AR aging summary · Days sales outstanding · Revenue by service & rate · Payments by method · Sales tax remittance · Trial balance · Account ledger · By-premises summary | Read completeness · High-usage exceptions · Disconnect & reconnect · Billing register · New & closed accounts · Meter inventory | PUC quarterly filing · User activity audit · Rate change history), **plus the six audit-added reports** (BR-REP-007: Back-bills & penalty · Bill corrections · Write-offs · Budget billing status · Delivery-queue health · Returned mail & bad addresses; ship wave RQ-9). Header actions: **Scheduled & history →** S45, **+ Build your own →** S47 (prototype). Finance cards **route to the ledger-owned surfaces** — Trial balance → S56 (US-LED-008), Account ledger → S59 (US-LED-009), By-premises → S60 (US-LED-010), Sales tax remittance → S41 (US-LED-014) — reports never duplicates them (BR-REP-003/005). Cards whose real columns are UNKNOWN per A14 ("generic viewer") open the S46 generic viewer (US-REP-002). Saved custom reports (US-REP-012) list for their tenant. Entry: sidebar Reports. Exit: viewer / builder / scheduled.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-REP-007 | Canned set += back-bills/penalty, corrections, write-offs, budget status, delivery-queue health, returned mail (read-models of their owning BRs); ship wave = RQ-9. | CONFIRMED — reports audit F-4/5/7..13, 2026-08-08 |
| BR-REP-002 | Every card opens a READ-MODEL — never a side-maintained number. | CONFIRMED — reports audit 2026-08-08 |
| BR-REP-003 / BR-REP-005 *(consumed)* | S41 remittance + S42 export are ledger-owned respecs — S44 routes, never re-implements. | CONFIRMED — audit F-1/F-6 |
| BR-REP-006 *(consumed)* | Downstream viewers enumerate live vocabularies (enforced in US-REP-002). | CONFIRMED — audit F-17..21 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Library render for Brazos Bend | All three groups + the six BR-REP-007 additions present; group placement per A14 (additions: corrections + back-bills/penalty = Compliance, write-offs + budget status = Financial, delivery-queue health + returned mail = Operations per their A14-item-5 audience tags) |
| TC-2 | Click Trial balance / Account ledger / By-premises / Sales tax remittance | Routes to S56 / S59 / S60 / S41 (ledger stories) — no second implementation, no divergent figures possible (BR-REP-002) |
| TC-3 | Click Billing register / AR aging / Revenue | Opens S46 with that report's built table (EP-REP-02) |
| TC-4 *(negative)* | Click a column-unknown card (e.g. Disconnect & reconnect, Meter inventory) | Generic viewer opens (Date/Reference/Detail/Category/Amount per A14) — NO invented per-report columns anywhere (column sets = candidate OQ, pack report R-2) |
| TC-5 | Header actions | "Scheduled & history" → S45; "+ Build your own" → S47 |
| TC-6 *(isolation)* | Lone Star Ridge library | Its saved custom reports only (RLS); Brazos Bend definitions never listed |

**4 · Test Data** — Brazos Bend MUD (billing workbook §1 fixture tenant, 8 services enabled) with 2 saved custom reports ("July high bills", "Deposit-purpose payments"); Lone Star Ridge with 0. Actors: Alex Reed (Owner), Sam Alvarez (Staff). Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Card (key, name, group, description) | S44 | A14 §Report library + prototype-extracted + BR-REP-007 | canned-report registry (code-defined catalog; no tenant table) | text | reference-data | catalog = ratified set only |
| Saved-custom entries | S44 | prototype "Build your own" + S47 Save | saved report definitions — B2 anchoring pending (pack report R-1, DDL 🔒) | rows | user-input | tenant-scoped (RLS) |
| Routing targets | S44 | A1/A9 + BR-REP-003/005 | route map to S45/S46/S47/S56/S59/S60/S41 | — | computed-display | ledger surfaces never duplicated |

**6 · Acceptance**
- Given the library, Then the full A14 catalog + the six BR-REP-007 additions render in their groups and every card routes to its single owning surface.
- Given column-unknown reports, Then only the generic viewer opens — no invented columns.
- Given tenants, Then saved definitions never cross.

**7 · Finance Calculation** — N/A (catalog/routing only).

**8 · Open Questions** — None.

---
id: US-REP-002
epic: EP-REP-01
module: reports
screens: [S46]
wave: 5
status: draft
blocked_by: []
depends_on: [US-REP-001, US-SHL-006]
journeys: [J5]
rules: [BR-REP-001, BR-REP-002, BR-REP-006]
golden_tests: []
finance_calc: none
---
### US-REP-002 — S46 Report viewer: live-vocabulary parameter bar, run, basis-labeled render

**1 · Details** — As staff, I want the **report viewer** (S46): header per prototype (report name · tenant · "generated {date time} by {user}") + actions ☆ Favorite / Schedule (→ US-REP-013) / ↓ Export (→ US-REP-003) / Print; **parameter bar** per A14 §Viewer — Date range (This month / Last month / This quarter / Year to date / Custom), **Service** (= the tenant-enabled service set, BR-REP-006 — never the prototype's hardcoded Electric/Water/Sewer trio), **Account class** (All + Residential / Commercial / Industrial / **Government**, BR-REP-006), Group by (Age bucket / Service / Cycle / Account class), **Run report** — filters AND-combined, shown as chips, URL-persisted (IS-4). Render = per-report KPI strip + table (EP-REP-02) or the **generic viewer** (Date · Reference · Detail · Category · Amount, A14) where real columns are UNKNOWN. **Every money KPI/report header carries its date-basis label** (BR-REP-001: billing-side = POSTING, cash-side = CLEARING) — a money report rendering without its basis label is a defect. All figures are read-models (BR-REP-002). Entry: S44 card. Exit: back to library; export/schedule.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-REP-001 | Every money KPI/report header labels its date basis — no unlabeled money number anywhere. | CONFIRMED — PO ruling 2026-08-08 (extends BR-PAY-021) |
| BR-REP-006 | Filters enumerate LIVE vocabularies (tenant services, 4 consumer classes incl. Government, 5 statuses + behavior classes, bill_type, payment purpose, read channel) — never hardcoded. | CONFIRMED — audit F-17..21 |
| BR-REP-002 | Viewer output = read-model over dimensions/module read-models. | CONFIRMED — reports audit 2026-08-08 |
| BR-CUS-055 *(consumed)* | Account-status vocabulary where status filters render = the seeded, tenant-extensible lookup. | CONFIRMED — PO OQ-058 (b) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Param bar for Brazos Bend (8 services enabled) | Service dropdown = exactly the 8 enabled services + "All services"; a tenant with 2 services lists 2 (BR-REP-006) |
| TC-2 | Account class options | All / Residential / Commercial / Industrial / **Government** (BR-REP-006 — Government present) |
| TC-3 | Run + chips + URL | Filters apply AND-combined; chips with clear-all; URL state shareable/bookmarkable (IS-4) |
| TC-4 *(basis label)* | AR aging (money, billing-side) and Payments by method (money, cash-side) rendered | Headers read "posting basis" and "clearing basis" respectively; **any money report rendering with no basis label = FAIL** (BR-REP-001) |
| TC-5 | Generic viewer | Column-unknown report renders Date/Reference/Detail/Category/Amount + Rows/Total/Period/Generated KPIs (prototype) — no invented columns |
| TC-6 *(negative)* | Custom range From > To; service param not in the tenant's enabled set (hand-edited URL) | Validation rejects the range; foreign vocabulary value → zero-results-after-filter state per IS-7/A18, never a silent full-set render |
| TC-7 *(isolation)* | Same report, Lone Star Ridge | Its rows/vocabularies only (RLS); Brazos Bend services never listed |

**4 · Test Data** — Brazos Bend MUD: services Electric, Water, Gas, Sewer, Trash, Broadband, Solar, Battery (workbook §1); classes incl. a Government account (Travis Co. Parks, A-11900). Ranges: This month (Aug 2026), Custom Jul 1–31. Actors: Alex Reed, Norma Reyes. Isolation: J. Okafor (2-service tenant: Water, Sewer).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Date range | S46 | A14 §Viewer | query window (fiscal presets per BR-TEN-022) | enum/dates | user-input | From ≤ To |
| Service filter | S46 | A14 §Viewer + BR-REP-006 | `tenant_services` enabled set | enum | user-input | live set only |
| Account class filter | S46 | A14 §Viewer + BR-REP-006 | consumer-category vocabulary (4 classes incl. Government) | enum | user-input | live set only |
| Group by | S46 | A14 §Viewer | regroup of the same read-model rows | enum | user-input | per-report options |
| Basis label | S46 | BR-REP-001 | rendered header label per report definition | text | computed-display | REQUIRED on every money header |
| Generated-by line | S46 | prototype-extracted | run metadata (tenant TZ per IS-8) | text | system-derived | — |
| KPI strip + table | S46 | A14 §Fully-built tables / generic | per-report read-model (EP-REP-02) | rows | computed-display | ties to KPIs exactly |

**6 · Acceptance**
- Given any tenant, Then every filter lists that tenant's live vocabulary and nothing hardcoded.
- Given any money report, Then its header names its basis — an unlabeled money render fails the suite.
- Given params/URL/tenants, Then IS-4 state, validation and RLS hold.

**7 · Finance Calculation** — N/A (parameter/render shell; figures owned by the per-report stories).

**8 · Open Questions** — None.

---
id: US-REP-003
epic: EP-REP-01
module: reports
screens: [S46]
wave: 5
status: draft
blocked_by: []
depends_on: [US-REP-002, US-SHL-008]
journeys: [J5]
rules: [BR-REP-018, BR-REP-001]
golden_tests: []
finance_calc: none
---
### US-REP-003 — IS-11 downloads: CSV always + PDF skeleton, filename contract, 50k guard, audit

**1 · Details** — As staff, I want **↓ Export / Print** on every report to follow **IS-11 exactly** (BR-REP-018): **CSV always** — UTF-8, comma, ONE header row, stable documented snake_case columns, money plain 2dp (no symbols/separators), ISO dates, tenant-TZ timestamps with offset, NO metadata rows in the data, context in the filename **`{tenant}_{report}_{period}_{basis}_{generated}.csv`**; **PDF where layout matters** — skeleton: tenant letterhead · title · period · every active filter echoed · **date-basis label (BR-REP-001)** · generated-at (tenant TZ) + by whom · page X/Y · totals footer · IS-8 regional formats; **NO XLSX in v1**. Guards: server-side streamed under RLS, >50,000 rows rejected, money-table exports write `audit_log` (BR-SHL-016/IS-9); Print = the PDF render. Scheduled runs produce identical files (US-REP-014). Entry: S46 actions (+ every canned-report surface). Exit: file matching the contract byte-for-byte rules.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-REP-018 | Every report download follows IS-11: CSV always + PDF where layout matters; no XLSX v1; standard PDF skeleton; strict CSV contract; context in filename. | CONFIRMED — PO 2026-08-08 (IS-11) |
| BR-REP-001 *(consumed)* | The basis label appears in the PDF skeleton and the filename `{basis}` segment. | CONFIRMED — PO ruling 2026-08-08 |
| BR-SHL-016 *(consumed)* | CSV export: streamed under RLS; >50,000 rows rejected; money exports audit. | CONFIRMED — PO R1 A2 |
| IS-8 / IS-9 *(consumed)* | Regional formats in PDF; export respects filters + visible columns. | CONFIRMED — B9 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | AR aging CSV, Jul 2026 | One snake_case header row (`account_no,customer,class,current,d31_60,d61_90,d90_plus,total` — documented set); money `247.87` style; filename `brazos-bend_ar_aging_2026-07_posting_20260805.csv`; zero metadata rows |
| TC-2 | AR aging PDF | Letterhead · title · period · filter chips echoed ("Service: All · Class: All") · **"Posting basis"** · "Generated Aug 5, 2026 10:14 CT by Norma Reyes" · page X/Y · totals footer |
| TC-3 *(basis label)* | PDF/CSV generated for any money report | PDF skeleton carries the basis label and the CSV filename carries the `{basis}` segment — a generated money file missing either = FAIL (BR-REP-001/IS-11) |
| TC-4 *(negative)* | 50,001-row result exported | Rejected with guidance (narrow filters / schedule it); no partial file (BR-SHL-016) |
| TC-5 *(negative)* | Any surface offering XLSX | None exists — the A14 "Excel" mention is corrected (IS-11); format pickers offer CSV/PDF only |
| TC-6 | Audit | Money-report export writes `audit_log` (`report.exported`: who, report, params, row count) |
| TC-7 *(isolation)* | Export under Lone Star Ridge session | Streamed under its RLS context; a Brazos Bend row can never appear in the stream |

**4 · Test Data** — Files: `brazos-bend_ar_aging_2026-07_posting_20260805.csv` · `brazos-bend_payments_by_method_2026-07_clearing_20260805.pdf`. 50k-guard fixture: synthetic 50,001-row billing-register result. Actors: Norma Reyes (Finance), Alex Reed. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| CSV file | S46 | IS-11 | streamed from the report read-model (RLS) | file | computed-display | contract columns; 2dp money; ISO dates; ≤50k |
| PDF file | S46 | IS-11 | rendered skeleton over the same rows | file | computed-display | letterhead/filters/basis/generated-by/totals/X-of-Y |
| Filename | S46 | IS-11 | `{tenant}_{report}_{period}_{basis}_{generated}` | text | system-derived | basis segment required |
| Print | S46 | prototype-extracted + IS-11 | the PDF render | file | computed-display | same skeleton |
| Audit row | — | CLAUDE.md #7 + BR-SHL-016 | `audit_log` (`report.exported`) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given any report, Then CSV export always exists, PDF exists where specced, XLSX exists nowhere.
- Given a generated file, Then the CSV contract and PDF skeleton hold exactly, basis included.
- Given guards, Then 50k/RLS/audit behave per BR-SHL-016; given tenants, streams never cross.

**7 · Finance Calculation** — N/A (file contract; figures owned upstream — file money renders at 2dp per IS-11 from NUMERIC(18,6) sources, rounding rule = B4 finalization/display).

**8 · Open Questions** — None.

---
id: US-REP-004
epic: EP-REP-01
module: reports
screens: [S45]
wave: 5
status: draft
blocked_by: []
depends_on: [US-REP-003, US-SHL-006]
journeys: [J5]
rules: [BR-REP-018, BR-REP-017]
golden_tests: []
finance_calc: none
---
### US-REP-004 — Recent runs (S45): run history + the 3-day generated-file retention window

**1 · Details** — As staff, I want the **Recent runs** list (S45 lower half, A14 §Scheduled): columns **Report · Run at · Range · By · Rows · Format · Download ↓** (prototype adds By = a user name or "Scheduled"). Every manual run/export (US-REP-002/003), builder run (US-REP-012) and scheduled run (US-REP-014) records a run row (A6 §S46: export/schedule actions create `report_run`). **Generated files are retained 3 days by default, tenant-configurable** (IS-11/BR-REP-018 — "the download list is a courtesy window"; delivery is the email, W6 per BR-REP-017): within retention Download streams the exact generated file; after retention the file is deleted, the run row remains as history and Download is disabled with a re-run affordance. Entry: Reports → Scheduled & history. Exit: downloaded file identical to the original generation (IS-11).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-REP-018 | Scheduled/generated files retained 3 days default, tenant-config (IS-11). | CONFIRMED — PO 2026-08-08 |
| BR-REP-017 | v1 delivery = download; email delivery ships W6 — the run list is the v1 hand-over surface. | CONFIRMED — PO RQ-9, 2026-08-08 |
| BR-REP-002 *(consumed)* | Run rows are metadata; report figures stay read-models — a stored file never becomes a source of truth for later renders. | CONFIRMED — reports audit 2026-08-08 |
| IS-2/IS-3/IS-4 *(consumed)* | List behavior per capability row. | CONFIRMED — B9 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Run history render | Prototype rows reproduce: "AR aging summary · Aug 4 06:00 · As of Aug 3 · Scheduled · 184 · PDF · Download" · "Billing register · Aug 1 09:14 · Cycle 08-A · Alex Reed · 1,124 · CSV" — By distinguishes user vs Scheduled |
| TC-2 | Download within retention | Streams the exact generated file (filename per IS-11 incl. basis segment); no regeneration |
| TC-3 | Retention expiry (file generated Aug 1, opened Aug 5; tenant default 3 days) | File deleted; row remains; Download disabled with re-run affordance — history never disappears |
| TC-4 | Tenant-config retention | Tenant set to 7 days keeps files 7 days (setting, audited); default remains 3 |
| TC-5 *(negative)* | Direct URL fetch of an expired/foreign file id | 4xx — never a stale or regenerated-in-place file; foreign id 404s (RLS) |
| TC-6 *(isolation)* | Lone Star Ridge run list | Its runs only; Brazos Bend files unreachable (RLS) |

**4 · Test Data** — Runs per prototype (AR aging 184 rows PDF · Billing register 1,124 rows CSV · Revenue by service 28 rows · Payments by method 412 rows PDF). Retention: default 3 days; variant tenant setting 7. Files from US-REP-003 fixtures. Actors: Alex Reed. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Run row (report, run_at, range, by, rows, format) | S45 | A14 §Scheduled + A6 §S46 `report_run` | `report_runs` — B2 anchoring pending (pack report R-1, DDL 🔒) | row | system-derived | append-only history |
| Generated file ref | S45 | IS-11 | file store ref on the run row (storage mechanics 🔒) | file | system-derived | deleted at retention expiry |
| Retention setting | S8 | IS-11 "3 days, tenant-configurable" | tenant settings key (retention days) | int/days | user-input | default 3; audited |
| Download action | S45 | prototype-extracted | streamed original file (RLS) | file | computed-display | disabled after expiry |

**6 · Acceptance**
- Given runs, Then history records every generation with By = user/Scheduled and downloads stream originals within retention.
- Given expiry, Then files delete on the tenant's window, rows persist, and no stale file is ever served.
- Given tenants, Then runs and files never cross.

**7 · Finance Calculation** — N/A (run metadata; file contents fixed at generation per IS-11).

**8 · Open Questions** — None.
