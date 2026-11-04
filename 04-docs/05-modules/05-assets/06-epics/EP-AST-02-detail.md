# EP-AST-02 — Asset detail
> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep.

**Module:** assets · **Wave:** W1 · **Screens:** S50 (Asset detail, 5 tabs — ID ratified, OQ-014 CLOSED) · **Status:** draft

## Scope
**In:** the asset detail page (S50): header (asset #, type kicker, status pill, assignment sub-line, actions Reassign / Log repair / Retire) and the five tabs **Overview** (specifications incl. the extended spec fields: register digits, multiplier, form/class, test dates — plus assignment panel) · **Reads** (per-asset read history incl. net-metering consumption + export read records, BR-AST-029) · **Assignment history** · **Maintenance & repairs** · **Audit**.
**Out:** the actions the header buttons open (S53–S55, EP-AST-03) · read ingestion/validation/estimation (metering S25–S29) · net-record **capture** rules (EP-AST-05) · net-metering credit math (rating EP-RAT-06 / OQ-001) · audit-log storage/semantics (audit module — this tab renders it).
**Tables:** read-only over metering-owned B2 r4 `assets`, `asset_assignments`, `asset_maintenance`, `meter_reads` (+ B2 r7 `read_type`), plus `audit_log` — all via service functions (B1).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| — | *(no list screens — S50's tab tables are embedded detail tables without search/filter/pagination in the design; if a table exceeds one page it paginates per IS-2, nothing more declared)* | | | | | | | |

## Stories

---
id: US-AST-004
epic: EP-AST-02
module: assets
screens: [S50]
wave: 1
status: draft
blocked_by: []
depends_on: [US-AST-001, US-AST-002]
journeys: []
rules: [BR-AST-007, BR-AST-014, BR-AST-015]
golden_tests: []
finance_calc: none
---
### US-AST-004 — Detail header + Overview tab (full specifications)

**1 · Details** — As a staff user, I want an asset's full specification and current assignment on one Overview tab under a header that names, states, and acts on the asset, so that field and billing questions ("what multiplier?", "how many dials?", "when was it last tested?") are answered without leaving the page. Entry: asset # click on S49. Header per prototype: back link "← Assets", kicker `Meter · M-4021 · AMI`, H1, sub-line (service · multiplier · installed · assigned to), status pill, actions **Reassign / Log repair / Retire**. Overview = Specifications panel + Assignment panel (premises, unit, account, net-metering line, "Reassign →"). The prototype's 8 spec rows are extended with the capture-only spec fields this story owns: serial #, form/class, register digits (default 9 — BR-AST-015), firmware, seal #, warranty end, last test date + test interval, location note. Exit: header actions → EP-AST-03 modals; tab bar → other tabs.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AST-007 | "Test due" derived display state (defined US-AST-001) also surfaces here: header pill row shows a "Test due" chip beside the status pill when elapsed; stored status unchanged. | PROPOSED — prototype BF pill + A5 v4; interval defaults CONFIRMED via BR-AST-027 (OQ-046 CLOSED: seeded start defaults backflow 12 mo / meter 96 mo, tenant-editable per type) |
| BR-AST-014 | Extended spec fields (serial #, form/class, register digits, firmware, seal #, warranty end, last test date, test interval, location note) are optional capture fields with **no behavior beyond display and validation** — warranty tracking is a single end-date, no claims/vendor/contract depth (ADR-004: no EAM). All are PROPOSED-SCHEMA columns on `assets` (B2 r4 lacks them). | CONFIRMED — PO R4-B5 |
| BR-AST-015 | `register_digits` bounds read entry: a reading for this asset cannot exceed `10^register_digits − 1`; it is also the rollover-detection input (rollover math itself is OQ-009 / rating — referenced, not decided here). Per-asset editable; **DEFAULTS to 9 when unspecified** (PO R4-B6 — the safer failure mode: an oversized span turns a missed rollover into a review exception, never a silent wrap). | CONFIRMED — PO R4-B6 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana opens M-4021 detail | Header: kicker `Meter · M-4021 · AMI`, sub "Electric · ×10 · installed Mar 2024 · assigned to 1408 Elm Street · Unit A", Active pill, 3 action buttons; Overview shows all 8 prototype spec rows + extended fields (serial 3894-A2210, form 2S, 5 digits, firmware 5.2.1, seal TX-88121, warranty Mar 12, 2029, last test Jun 2, 2026 · every 24 mo, location "left side wall, behind gate") |
| TC-2 | Assignment panel on M-4021 | Premises 1408 Elm Street · Unit A · Account A-10432 · Miller, Sarah · "Net metering: Enabled (measures export)" · Reassign → opens S55 |
| TC-3 | Open BF-3301 detail | Status pill Active + "Test due" chip (last test 2025-06-02 + 12 mo < today); spec panel shows test fields; no multiplier/register rows (non-measuring) |
| TC-4 | Open BAT-0904 (inventory) | Assignment panel reads "Inventory (unassigned)"; header shows Inventory pill; Retire/Log repair still offered, Reassign labeled Assign |
| TC-5 *(negative)* | Edit register digits to 0 or a non-integer via the edit form | Inline validation error (1–9 integer); save blocked; clearing the field reverts to the default 9 (BR-AST-015, PO R4-B6) |
| TC-6 *(negative)* | Direct URL to a non-existent asset id | A18 failed/not-found state — never a blank detail shell |
| TC-7 *(isolation)* | Erin (Lone Star Ridge) requests Brazos Bend's M-4021 detail URL | Not-found under her `app.tenant_id`; her own M-4021 (different id) renders her tenant's data only |

**4 · Test Data** — M-4021 extended specs as TC-1 (serial 3894-A2210, form 2S, register_digits 5, firmware 5.2.1, seal TX-88121, warranty_end 2029-03-12, last_test_date 2026-06-02, test_interval 24 mo, location_note "left side wall, behind gate"). BF-3301: last_test_date 2025-06-02, interval 12 mo. M-5099: register_digits unspecified → 9 (default, BR-AST-015). Reference date 2026-08-08. Actors: Dana Whitfield; Erin Walsh.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Asset # / Type / Read method / Service / Multiplier / Manufacturer·model / Install date / Status | S50 Overview | prototype-extracted (8 spec rows) | `assets.*` per US-AST-002 rows | — | computed-display | read-only here |
| Serial # | S50 Overview | task-directed field (not in prototype — GAP noted, no OQ: capture-only) + BR-AST-026 (Device ID/Serial identifier) | **PROPOSED-SCHEMA** `assets.serial_no` text | text | user-input | optional; ≤64; duplicate serial warn-but-allow (BR-AST-033) |
| Form / class | S50 Overview | task-directed field (electric form e.g. 2S; gas/water class) | **PROPOSED-SCHEMA** `assets.form_class` text | text | user-input | optional |
| Register digits | S50 Overview | task-directed field | **PROPOSED-SCHEMA** `assets.register_digits` smallint DEFAULT 9 | integer 1–9 | user-input | BR-AST-015; **default 9 when unspecified (PO R4-B6)** |
| Firmware | S50 Overview | task-directed field | **PROPOSED-SCHEMA** `assets.firmware_version` text | text | user-input | optional |
| Seal # | S50 Overview | task-directed field | **PROPOSED-SCHEMA** `assets.seal_no` text | text | user-input | optional |
| Warranty end | S50 Overview | task-directed field (depth capped by ADR-004) | **PROPOSED-SCHEMA** `assets.warranty_end` date | date | user-input | optional; date only |
| Last test date / Test interval | S50 Overview | prototype-implied (BF "Test due") + task-directed | **PROPOSED-SCHEMA** `assets.last_test_date` date · `assets.test_interval_months` smallint | date · months | system-derived (test log, BR-AST-018) · user-input | interval ≥ 1; seeded defaults per type (backflow 12 mo, meter 96 mo — BR-AST-027, OQ-046 CLOSED), tenant-editable |
| Location note | S50 Overview | task-directed field | **PROPOSED-SCHEMA** `assets.location_note` text | text | user-input | optional; ≤280 |
| Assignment panel | S50 Overview | prototype-extracted | current `asset_assignments` row → unit → premises → active account (via customers service) | — | computed-display | — |

**6 · Acceptance**
- Given any asset, When its detail opens, Then header identity/status/actions and the Overview panels render per prototype, with extended spec fields present (blank-tolerant) for measuring types, And register digits shows 9 unless a different value was captured (BR-AST-015).
- Given elapsed test interval, When the header renders, Then a "Test due" chip shows without any stored-status change.
- Given a cross-tenant asset id, When requested, Then the response is not-found.

**7 · Finance Calculation** — N/A

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-046 | Test-interval mandate defaults (minted US-AST-001) | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-AST-027) — start defaults (backflow 12 mo, meter 96 mo) + full tenant control (PO R7) |

---
id: US-AST-005
epic: EP-AST-02
module: assets
screens: [S50]
wave: 1
status: draft
blocked_by: []
depends_on: [US-AST-004, US-AST-011, US-MET-010]
journeys: []
rules: [BR-AST-003, BR-AST-016, BR-AST-029]
golden_tests: []
finance_calc: none
---
### US-AST-005 — Reads tab (per-asset history, incl. net-metering read records)

**1 · Details** — As a staff user, I want this asset's read history on its own tab — register reading, computed consumption with explicit unit, source, status, and for net meters the import/export split rendered as **two typed read rows** (`read_type` consumption | export, same read date — BR-AST-029) — so that I can verify what the billing run will consume without hunting through the global Reads screen. Entry: S50 tab **Reads**. Columns (r7 reconciliation of the prototype table): Date · Reading · Consumption · Type · Source · Status — a net meter's cycle read renders as **two rows** (consumption + export) distinguished by the Type tag, NOT as extra channel columns (BR-AST-029 supersedes the prototype's Import/Export columns); single-channel assets show Date · Reading · Consumption · Source · Status with no Type tag. Rows link to the read detail drawer (S29, metering). Exit: none (display tab). Read capture/validation belong to metering; record capture rules to EP-AST-05.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AST-003 | Net meters carry `net_metering = true` and feed rating (existing rule — governs which assets get export rows). | CONFIRMED — B2 r4 / A3 v4 |
| BR-AST-016 | The Reads tab lists reads of this asset only, newest first; every quantity renders with its explicit unit (CLAUDE.md #3); no money is ever shown on this tab (credit math is rating's, OQ-001). | CONFIRMED — PO R4 Q20/B7 |
| BR-AST-029 | Net-meter import/export are TWO typed read records (`read_type` consumption \| export, same read_at, unique per (asset, read_at, read_type) — B2 r7); the tab renders them as two typed rows, never single-row channel columns; single-channel assets never show a read-type tag or export row. | CONFIRMED — PO R4-A6 / B2 r7 (supersedes the BR-AST-024 columns model) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana opens M-4021 → Reads | Aug 3 renders TWO typed rows (BR-AST-029): consumption (reading 42,864 · 684 kWh) and export (120 kWh · Type "Export"); Jul 3 likewise (612 / 98); newest first |
| TC-2 | Open M-4022 (single-channel water) → Reads | Columns Date · Reading · Consumption (kgal) · Source · Status; **no** read-type tag and no export rows (BR-AST-029) |
| TC-3 | Row click on a read | Opens the S29 read detail drawer for that record (metering) |
| TC-4 | M-5099 (inventory, no reads) → Reads | A18 empty state ("No reads yet") — not an empty table header |
| TC-5 *(negative)* | A dollar amount is nowhere on the tab even for net meters with export rows | Only quantities + units render; no currency formatting anywhere (BR-AST-016) |
| TC-6 *(isolation)* | Erin (Lone Star Ridge) opens her M-4021 → Reads | Only Lone Star Ridge `meter_reads` rows; Brazos Bend's reads for its same-numbered asset never appear |

**4 · Test Data** — M-4021 record pairs per prototype values (Aug 3, 2026: consumption record current 42,864, prior 42,180, consumption 684 kWh + export record 120 kWh, AMI, OK; Jul 3, 2026: 42,180 / 612 + export 98). M-4022: Aug 3 reading 1,412.6 → consumption 8.4 kgal, AMI, OK. Lone Star Ridge M-4021: one read Aug 1, 2026, 10,204 kWh register.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Date | S50 Reads | prototype-extracted | `meter_reads.read_at` | timestamptz | integration/system-derived | — |
| Reading | S50 Reads | prototype-extracted | `meter_reads.current_value` | numeric(18,6) | integration/user-input | ≤ register max (BR-AST-015; digits default 9) |
| Consumption (single-channel) | S50 Reads | derived (global Reads screen shows usage) | `meter_reads.consumption` + `meter_reads.unit` | numeric(18,6) + unit | system-derived | unit explicit |
| Read type (net rows) | S50 Reads | B2 r7 + BR-AST-029 — supersedes the prototype's Import/Export columns (voided import_qty/export_qty PROPOSED-SCHEMA) | `meter_reads.read_type` (consumption \| export); export quantity on the export record's `consumption` | enum + numeric(18,6), asset unit | integration/user-input | export rows net assets only; UNIQUE (asset, read_at, read_type) |
| Source | S50 Reads | prototype-extracted (AMI) | `meter_reads.source` | enum meter_source | integration | — |
| Status | S50 Reads | A5 (read statuses) | `meter_reads.status` | enum read_status | system-derived | — |

**6 · Acceptance**
- Given a net-metering asset, When Reads opens, Then each cycle read shows a consumption row and an export row (typed), with units, newest first (BR-AST-029).
- Given a single-channel asset, When Reads opens, Then no read-type tag or export row renders.
- Given a tenant's session, When the tab loads, Then only that tenant's reads for that asset are returned.

**7 · Finance Calculation** — N/A

**8 · Open Questions** — None (record modeling CONFIRMED in BR-AST-029 — two typed records, B2 r7; no new OQ).

---
id: US-AST-006
epic: EP-AST-02
module: assets
screens: [S50]
wave: 1
status: draft
blocked_by: []
depends_on: [US-AST-004, US-AST-007, US-AST-009]
journeys: []
rules: [BR-AST-017, BR-AST-018, BR-AST-019]
golden_tests: []
finance_calc: none
---
### US-AST-006 — Assignment history, Maintenance & repairs, and Audit tabs

**1 · Details** — As a staff user, I want the asset's full movement history (which unit, when, by whom), its maintenance log, and its audit trail on three tabs, so that disputes ("that meter wasn't even at my property in June") and compliance checks are answerable from the record. Entry: S50 tabs 3–5. **Assignment history**: From · To · Premises · Unit · By (newest first; first row "current"). **Maintenance & repairs**: Date · Type · Detail · Status · Tech, with a **+ Log repair** button (opens S53, EP-AST-03). **Audit**: When · Actor · Action, rendered from `audit_log` for this asset. Exit: + Log repair → S53.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AST-017 | `asset_assignments` is append-only history: intervals never overlap per asset; exactly one current row (to_date NULL) when assigned, none when in inventory; rows record the acting user ("System" for provisioning/import). Corrections close a row and open a new one — no row edits. | CONFIRMED — PO R4 Q20/B8 (mechanism per A3 r4 + CLAUDE.md #4 correction pattern) |
| BR-AST-018 | `asset_maintenance` is an append-only log: kind ∈ repair \| inspection \| test, with date, detail, tech, resulting_status; a `test` entry updates `assets.last_test_date` (feeding BR-AST-007). Entries are never edited or deleted — corrections are new entries. | CONFIRMED — PO R4 Q20/B9 (mechanism per A3 r4 + prototype Maintenance tab) |
| BR-AST-019 | The Audit tab renders `audit_log` rows scoped to this asset; every lifecycle action, edit, assignment change, and maintenance entry must have written one (CLAUDE.md #7 discipline applied to asset actions). Read-only — the tab never writes. | CONFIRMED — PO R4-B10 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana opens M-4021 → Assignment history | Row 1: Mar 2024 → current · 1408 Elm Street · Unit A · Alex Reed; Row 2: — → Mar 2024 · Inventory (unassigned) · System; no overlapping intervals |
| TC-2 | M-4021 → Maintenance & repairs | Jun 2, 2026 · Inspection · "Annual accuracy check — passed" · Closed · tech; Jan 14, 2025 · Repair · "Comms module replaced" · Closed; + Log repair button opens S53 |
| TC-3 | M-4021 → Audit | Aug 3, 2026 06:12 · System · Read ingested · 42,864; Jun 2, 2026 10:20 · maintenance closed; Mar 12, 2024 09:00 · Installed & assigned to Unit A — chronological, newest first |
| TC-4 | A `test` maintenance entry is logged (via S53) dated 2026-08-08 | Maintenance tab gains the row AND Overview's Last test date becomes 2026-08-08 (BR-AST-018); "Test due" chip clears if interval satisfied |
| TC-5 *(negative)* | API attempt to UPDATE or DELETE an existing `asset_maintenance` or `asset_assignments` row | Rejected — append-only (corrections are new rows) |
| TC-6 *(isolation)* | Erin (Lone Star Ridge) opens her M-4021's three tabs | Only Lone Star Ridge history/maintenance/audit rows; Brazos Bend's audit trail never visible |

**4 · Test Data** — M-4021 history/maintenance/audit rows per prototype (TC-1..3). Techs: Ray Delgado (Brazos Bend field tech user); prototype's "Marcus J." mapped to fixture tech. Actors: Dana Whitfield; Erin Walsh.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| From / To | S50 Assignment history | prototype-extracted | `asset_assignments.from_date` / `to_date` (B2 r4) | date (to NULL = current) | system-derived | non-overlapping (BR-AST-017) |
| Premises · Unit | S50 Assignment history | prototype-extracted | `asset_assignments.unit_id` → unit/premises (NULL = inventory) | uuid FK | system-derived | unit of same tenant |
| By | S50 Assignment history | prototype-extracted | **PROPOSED-SCHEMA** `asset_assignments.actor_user_id` uuid (A3 r4 names "actor"; B2 r4 lists no column DDL) | uuid FK users | system-derived | "System" when NULL |
| Date / Type / Detail / Tech | S50 Maintenance | prototype-extracted | `asset_maintenance.date` / `.kind` / `.detail` / **PROPOSED-SCHEMA** `.tech_user_id` uuid (A3 r4 "tech" — typed as user FK) | date · enum repair\|inspection\|test · text · uuid | user-input | kind required |
| Status (maintenance row) | S50 Maintenance | prototype-extracted ("Closed") | `asset_maintenance.resulting_status` + **PROPOSED-SCHEMA** `.closed_at` timestamptz (open/closed display state) | enum + timestamptz | system-derived | — |
| When / Actor / Action | S50 Audit | prototype-extracted | `audit_log` (filtered to this asset's entity id) | jsonb rows | system-derived | read-only |

**6 · Acceptance**
- Given an asset with history, When each tab opens, Then rows render per prototype ordering with no gaps or overlaps in assignment intervals.
- Given a logged test entry, When saved, Then the Overview test date updates from the log — never by direct edit alone.
- Given any attempt to mutate history rows, When executed, Then it is rejected append-only.

**7 · Finance Calculation** — N/A

**8 · Open Questions** — None.
