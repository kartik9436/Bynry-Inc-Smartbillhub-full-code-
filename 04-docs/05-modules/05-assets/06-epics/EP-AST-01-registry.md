# EP-AST-01 — Asset registry
> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep.

**Module:** assets · **Wave:** W1 · **Screens:** S49 (Assets list, 3 tabs — ID ratified, OQ-014 CLOSED), S51 (Add asset modal) · **Status:** draft

## Scope
**In:** the Assets list (S49) with its three tabs **Meters · Sub-meters · Behind the meter** (r5 rename), search + status filter (All / Active / Needs repair / Retired / Unassigned), per-row actions varying by state, the single **Add asset** modal (S51) shared by all three tabs, and inline edit / delete-from-inventory of unreferenced assets. Meter-to-cash assets ONLY per ADR-004 (BR-AST-001): assignable to a Unit, able to affect a bill; transformer/generator admitted only as customer-premise BTM devices.
**Out:** asset detail S50 (EP-AST-02) · lifecycle modals S53–S55 (EP-AST-03) · bulk import S52 (EP-AST-04) · net-meter read records (EP-AST-05) · read ingestion/validation (metering module, S25–S29) · Asset types / lifecycle-stage reference-list management (tenancy EP-TEN-07; tenant-extensible per BR-TEN-036 — OQ-031 CLOSED) · any 09-infra/EAM asset class (ADR-004) · net-metering credit math (rating EP-RAT-06 / OQ-001).
**Tables:** owned by metering — B2 r4 `assets` (+ `asset_assignments`); this module is a docs + frontend surface (ADR-004). All writes via metering service functions (B1).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S49 · Meters tab | asset_no, serial, manufacturer/model, premises/unit address (BR-AST-041) | status · service · premises · assigned · test-due (BR-AST-041; IS-4, URL-persisted) | asset_no A→Z (CONFIRMED — BR-AST-041; stable secondary by id per IS-2) | asset_no · type · service · installed · status | 7 default per BR-AST-041 (☑ · Meter # · Type (+read method) · Service · Mult. · Assigned to · Installed · Status · Actions); IS-5 dynamic columns (BR-SHL-027 interim ⋮ spec — OQ-013 CLOSED) | per state, BR-AST-006 (View / Edit / Reassign / Log repair / Retire; inventory rows: Assign / Edit / Delete) | multi-select bulk assign inventory→units (BR-AST-036); unit→unit moves single or file-import only (BR-AST-038) | — (not shown in design) |
| S49 · Sub-meters tab | asset_no, parent asset_no, serial, address (BR-AST-041 set) | same filter set (BR-AST-041) | asset_no A→Z | asset_no · parent · service · installed · status | Sub-meter # · Parent / master · Service · Unit · Installed · Status · Actions | per state, BR-AST-006 | same as Meters tab (BR-AST-036/038) | — |
| S49 · Behind the meter tab | asset_no, serial, address (BR-AST-041 set) | same filter set (BR-AST-041) | asset_no A→Z | asset_no · type · installed · status | Device # · Type · Assigned to · Installed · Status · Actions | per state, BR-AST-006 (backflow rows show "Log test" wording per prototype) | same as Meters tab (BR-AST-036/038) | — |

## Stories

---
id: US-AST-001
epic: EP-AST-01
module: assets
screens: [S49]
wave: 1
status: draft
blocked_by: []
depends_on: [US-TEN-002, US-SHL-006, US-SHL-007, US-SHL-008]
journeys: []
rules: [BR-AST-001, BR-AST-004, BR-AST-005, BR-AST-006, BR-AST-007, BR-AST-031]
golden_tests: []
finance_calc: none
---
### US-AST-001 — Assets list with three tabs, search and status filter

**1 · Details** — As a staff user, I want one registry of every meter, sub-meter, and behind-the-meter device — searchable, filterable by lifecycle state, and split into three tabs — so that I can find any billable asset and see its assignment and health at a glance. Entry: sidebar **Assets** (after Plans & Rates, A1 r4 addendum). The three tabs (Meters / Sub-meters / Behind the meter, r5) share the page header actions **Bulk import** (→ S52) and **+ Add** (→ S51; label varies per tab). Search + filters per the capability matrix (BR-AST-041); table mechanics conform to B9 via EP-SHL-02 (declared, not restated). Exit: asset number click → S50 detail; row actions → EP-AST-03 modals; inventory-row Delete → US-AST-003.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AST-001 | An asset is in scope only if assignable to a Unit and able to affect a bill (no 09-infra/EAM). | CONFIRMED — ADR-004 (PO 2026-08-08) |
| BR-AST-004 | Tabs partition by type: **Meters** = `meter` + `net_meter`; **Sub-meters** = `sub_meter` (always with `parent_asset_id`); **Behind the meter** = `backflow`, `comms`, `pv`, `battery`, `ev_charger`, `transformer`, `generator` + seeded **Container/Cart** and **Modem/CPE** (BR-AST-042); types tenant-extensible per BR-TEN-036. Every asset appears on exactly one tab. | CONFIRMED — PO R4-B1 (+ Q19 seeds, BR-AST-042) |
| BR-AST-005 | Status filter semantics: Active/Needs repair/Retired match the stored lifecycle stage (Reference-data stages per BR-AST-031); **Unassigned** = no current `asset_assignments` row (covers Inventory/Spare stock and any unassigned state); **All** includes retired. Filters AND-combine with search per IS-4. | CONFIRMED — PO R4-B2 |
| BR-AST-006 | Row actions vary by state (IS-6): active → View/Edit/Reassign/Log repair/Retire · needs_repair/in_repair → View/Log repair/Reassign/Retire · inventory → Assign/Edit/Delete (delete gated by BR-AST-013) · retired → View only. Backflow rows label the repair action "Log test". Enforcement is server-side; UI gating is convenience (A4). | CONFIRMED — PO R4-B3 |
| BR-AST-007 | **"Test due" is a derived display state, not a stored status**: shown when `last_test_date + test_interval_months` has elapsed. Interval values are per-asset; seeded start defaults = backflow 12 mo, meter 96 mo, tenant has full control per type (BR-AST-027 — OQ-046 CLOSED). | PROPOSED (display state) — prototype BF-3301 pill + A5 v4; defaults CONFIRMED via BR-AST-027 |
| BR-AST-031 | Asset lifecycle stages live in **Reference data**: seeded defaults Inventory/Spare · Installed/Active · Needs repair · In repair · Retired; tenant may rename and add stages; every stage maps to a system behavior class (available \| in_service \| out_of_service \| terminal) so list filters and billing/rating logic stay sound regardless of tenant labels; seeded stages are is_system (deactivatable, never deletable — BR-TEN-036). Never a hardcoded enum. | CONFIRMED — PO R4 ("set in reference data — initial default, allow user to change") |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana opens Assets → Meters tab (Brazos Bend seed) | Rows M-4021, M-4022, M-4204, M-4310, M-5099 with type/service/multiplier/assignment/installed/status per fixture; M-5099 renders muted with Inventory pill and Assign/Edit/Delete actions |
| TC-2 | Switch to Sub-meters tab | SM-8801, SM-8802 (parent M-MASTER-12 · Vega Apts), SM-8803 (parent M-MASTER-08 · Riverside); no plain meters or BTM devices on this tab |
| TC-3 | Behind the meter tab | BF-3301 (Test due pill per BR-AST-007), PV-1180, COM-4420, EV-2210, BAT-0904 (inventory, muted); no meters/sub-meters listed |
| TC-4 | Filter = Unassigned on Meters tab | Only M-5099 (no current assignment); filter state appears in URL and survives reload (IS-4) |
| TC-5 | Search "1408 Elm" with filter = Active | M-4021 and M-4022 only (search AND filter); search "M-42" matches M-4204 etc.; search by serial "3894-A2210" finds M-4021 (BR-AST-041) |
| TC-6 *(negative)* | Filter = Retired on a tenant with no retired assets | Zero-results-after-filter state (A18) with clear-filter action — never the empty-list state |
| TC-7 *(isolation)* | Erin (Lone Star Ridge) opens Assets | Sees only Lone Star Ridge assets (M-4021 exists in BOTH tenants as distinct rows); Brazos Bend rows never returned; queries run with `app.tenant_id` = Lone Star Ridge |

**4 · Test Data** — Tenant A **Brazos Bend Utilities** (subdomain `brazosbend`, Katy TX, Electric + Water). Assets per prototype: M-4021 net meter · E · AMI · ×10 · 1408 Elm Street · Unit A · Active; M-4022 meter · W · AMI · ×1 · 1408 Elm · Unit A · Active; M-4204 meter · W · AMI · ×1 · 500 Main · 200 · Needs repair; M-4310 meter · E · AMR · ×10 · 77 Industrial Way · Active; M-5099 meter · E · AMI · ×1 · Inventory; SM-8801/8802 sub-meters E (parent M-MASTER-12, Vega Apts 102/104) Active; SM-8803 sub-meter W (parent M-MASTER-08, Riverside 224) Needs repair; BF-3301 backflow · 500 Main · 200 · Active, last_test_date 2025-06-02, test_interval 12 mo → Test due on 2026-08-08; PV-1180 PV · 901 Hillside; COM-4420 comms · 2200 Riverside; EV-2210 EV charger · 1200 Business Park · 12; BAT-0904 battery · Inventory. Actors: Dana Whitfield (System Admin), Marcus Vega (Billing Clerk). Tenant B **Lone Star Ridge Utilities** (`lonestarridge`), admin Erin Walsh; owns its own asset numbered M-4021.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Asset # (column) | S49 | prototype-extracted (Meter #/Sub-meter #/Device #) | `assets.asset_no` (B2 r4, generalized from `meters.meter_no`) — the user-facing number; the internal uuid PK is **never displayed** (BR-AST-026) | text | reference-data | UNIQUE (tenant_id, asset_no) |
| Type (+ read method) | S49 | A2 r4 addendum (Asset types lookup) | `assets.type`, `assets.read_method` | lookup · enum AMI\|AMR\|walk-by\|NA | reference-data | type set per BR-AST-004/009; tenant-extensible (BR-TEN-036) |
| Service | S49 | prototype-extracted (svc tags E/W) | `assets.service_point_id` → service (via metering) | reference | reference-data | required for measuring types |
| Mult. | S49 | prototype-extracted (×10/×1) | `assets.multiplier` | numeric(18,6) | reference-data | > 0 |
| Assigned to | S49 | prototype-extracted ("1408 Elm · Unit A" / "Inventory") | current `asset_assignments` row (to_date IS NULL) → unit/premises | computed-display | system-derived | one current row max (BR-AST-017) |
| Installed | S49 | prototype-extracted | `assets.install_date` | date | reference-data | — |
| Status | S49 | A5 v4 addendum + BR-AST-031 | `assets.status` → Reference-data lifecycle stage (seeded: Inventory/Spare, Installed/Active, Needs repair, In repair, Retired; tenant-renamable/extensible) with a system behavior class (available \| in_service \| out_of_service \| terminal) | lookup + behavior class | system-derived | transitions per BR-AST-020; stage list per BR-AST-031 — no hardcoded enum |
| Test due (pill) | S49 | prototype-extracted (BF-3301) | derived from **PROPOSED-SCHEMA** `assets.last_test_date` + `assets.test_interval_months` | computed | computed-display | display-only, BR-AST-007; seeded interval defaults per BR-AST-027 |
| Parent / master (Sub tab) | S49 | prototype-extracted | `assets.parent_asset_id` (B2 r4) | uuid self-FK | reference-data | required when type = sub_meter |

**6 · Acceptance**
- Given the Brazos Bend seed, When each tab is opened, Then every asset appears on exactly one tab with the columns declared in the capability matrix.
- Given filter Unassigned, When applied, Then exactly the assets with no current assignment are listed and the state persists in the URL.
- Given a backflow device whose test interval has elapsed, When listed, Then it shows "Test due" while its stored status remains unchanged.
- Given a tenant that renamed a lifecycle stage, When the list renders, Then the tenant label shows while filters/actions key off the stage's behavior class (BR-AST-031).
- Given a Lone Star Ridge session, When the list loads, Then no Brazos Bend asset is ever returned.

**7 · Finance Calculation** — N/A

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-046 | State-dependent test-interval mandate defaults | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-AST-027) — start defaults (backflow 12 mo, meter 96 mo) + full tenant control per type (PO R7) |

---
id: US-AST-002
epic: EP-AST-01
module: assets
screens: [S49, S51]
wave: 1
status: draft
blocked_by: []
depends_on: [US-AST-001, US-MET-003, US-TEN-008]
journeys: [J2]
rules: [BR-AST-003, BR-AST-008, BR-AST-009, BR-AST-010, BR-AST-011, BR-AST-026, BR-AST-033]
golden_tests: []
finance_calc: none
---
### US-AST-002 — Add a single asset (shared modal, all three tabs)

**1 · Details** — As a staff user, I want to add one asset — meter, sub-meter, or behind-the-meter device — from a single modal, optionally assigning it to a unit right away, so that new stock and field installs enter the registry immediately. Entry: **+ Add asset / + Add sub-meter / + Add behind-the-meter asset** on the respective S49 tab — one modal (S51), with Type preselected from the launching tab. Fields per prototype + the 3-identifier model (BR-AST-026): Asset # (auto-suggested from the tenant `number_series` with a per-type prefix M-/SM-/PV-/…, free-entry override allowed), Device ID / Serial #, Type (10 options), Service (Electric/Water/Gas/Sewer/—), Read method (AMI/AMR/Walk-by/N/A), Multiplier, Manufacturer / model, Install date, Assign to (Leave in inventory / unit picker), and the **Net metering — measure export (bidirectional)** checkbox. The internal system ID (uuid) is never displayed (BR-AST-026). Exit: **Add asset ✓** → toast + row appears on the correct tab; Cancel/✕/backdrop close without writes (IS-10).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AST-003 | Sub-meter = child asset via `parent_asset_id`; net meters carry `net_metering = true` and feed rating. | CONFIRMED — B2 r4 / A3 v4 (existing rule) |
| BR-AST-008 | Asset number: unique per tenant (`UNIQUE (tenant_id, asset_no)`) — numbering resolved by the **3-identifier model** (BR-AST-026, OQ-045 CLOSED): the user asset number auto-allocates from the tenancy `number_series` with per-type prefixes (M-/SM-/BF-/PV-/COM-/EV-/BAT-…), free-entry override allowed. Duplicate asset # = hard block; duplicate serial = warn-but-allow (BR-AST-033). | CONFIRMED — B2 UNIQUE + BR-AST-026/033 (OQ-045 CLOSED, PO R6) |
| BR-AST-009 | Type set per r5: meter, net meter, sub-meter, backflow, comms endpoint, PV/solar, battery, EV charger — plus transformer and generator **only as customer-premise BTM devices** (ADR-004); seeded Container/Cart + Modem/CPE per BR-AST-042. Service is required for measuring types (meter/net_meter/sub_meter); "—" is allowed only for non-measuring BTM types. Measuring types require an explicit UoM — never assumed (CLAUDE.md #3). | CONFIRMED — PO R4-A8 |
| BR-AST-010 | Net-metering flag: auto-checked and locked when Type = Net meter; optionally checkable for meter/sub-meter (converting it to a bidirectional revenue meter); unavailable for non-measuring BTM types — PV/battery/EV devices pair with a net meter, they do not themselves carry billing channels. | CONFIRMED — PO R4-A7 |
| BR-AST-011 | Assign-on-create: choosing a unit writes the first `asset_assignments` row (from_date = install date) and sets status `active`; "Leave in inventory" creates the asset unassigned with status `inventory`. Every create writes `audit_log`. | CONFIRMED — PO R4-B4 |
| BR-AST-026 | Three-identifier model: hidden internal system ID (uuid, **never displayed**) + Device ID/Serial # (physical identifier) + user asset number (auto from `number_series` with per-type prefixes, free-entry override allowed). | CONFIRMED — PO Q&A R6 (OQ-045) |
| BR-AST-033 | Duplicate guard: same serial → warn-but-allow; same asset # → hard block. | CONFIRMED — PO R4 Q2 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana adds M-5100 · Meter · Electric · AMI · ×1 · kWh · assign to 500 Main · 200, install 2026-08-08 | Asset # pre-filled "M-5100" from the meter series (override allowed — BR-AST-026); created `active`; assignment row from 2026-08-08; appears on Meters tab; toast + `audit_log` `asset.created` |
| TC-2 | Dana adds BAT-0905 · Battery storage · service "—" · leave in inventory | Created `inventory`, unassigned; appears muted on Behind the meter tab with Assign/Edit/Delete actions |
| TC-3 | Type = Net meter selected | Net-metering checkbox auto-checked and locked (BR-AST-010); saved asset has `net_metering = true` |
| TC-4 | Dana adds SM-8804 · Sub-meter · parent M-MASTER-12 · Apt 106 | Created with `parent_asset_id` = M-MASTER-12; appears on Sub-meters tab showing the parent |
| TC-5 *(negative)* | Asset # "M-4021" (already exists at Brazos Bend) submitted | Inline uniqueness error — hard block (BR-AST-033); no row written |
| TC-6 *(negative)* | Type = Meter with Service "—" (or no UoM) | Inline validation error per BR-AST-009; save blocked |
| TC-7 *(negative)* | Type = Sub-meter with no parent selected | Inline "parent meter required" error (BR-AST-003); save blocked |
| TC-8 *(isolation)* | Erin (Lone Star Ridge) adds asset # "M-4022" — a number Brazos Bend also uses | Succeeds — uniqueness is per tenant; row exists only under Lone Star Ridge's `tenant_id` |
| TC-9 | Dana adds a meter with serial 3894-A2210 (already on M-4021) | Warning "serial already exists on M-4021" — save still permitted (warn-but-allow, BR-AST-033); acknowledgement recorded in `audit_log` |

**4 · Test Data** — Fixtures from US-AST-001. New: M-5100 (Itron · OpenWay, kWh, serial IT-88412), BAT-0905 (Tesla · Powerwall 3), SM-8804 (parent M-MASTER-12, Vega Apts Apt 106, kWh). Duplicate-serial fixture: 3894-A2210 (M-4021's serial). Units available: 1408 Elm Street · Unit A, 500 Main · 200, 2200 Riverside · 224, 77 Industrial Way. Actors: Dana Whitfield; Erin Walsh (Lone Star Ridge).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Internal system ID | — | BR-AST-026 (3-identifier model) | `assets.id` uuid PK | uuid | system-derived | never displayed anywhere |
| Asset # | S51 | prototype-extracted (placeholder `M-5100`) + BR-AST-026 | `assets.asset_no` | text | system-derived (series) / user-input (override) | auto-allocated from the tenancy `number_series` asset series with per-type prefix (M-/SM-/PV-/…), free-entry override allowed (BR-AST-026); UNIQUE per tenant — duplicate hard-blocked (BR-AST-033) |
| Device ID / Serial # | S51 | BR-AST-026 (3-identifier model; spec capture shared with US-AST-004) | **PROPOSED-SCHEMA** `assets.serial_no` text | text | user-input | optional; duplicate serial warn-but-allow (BR-AST-033) |
| Type | S51 | prototype-extracted (10 options) + A2 r4 lookup | `assets.type` | lookup | user-input | BR-AST-009; preselected from launching tab |
| Service | S51 | prototype-extracted (E/W/G/Sewer/—) | `assets.service_point_id` (service point at assigned unit; NULL for "—") | reference | user-input | required for measuring types |
| Measurement unit (UoM) | GAP — not in prototype modal (derived: required by B2 `assets.unit` NOT NULL + CLAUDE.md #3) | derived | `assets.unit` | text (kWh/kgal/ccf/…) | user-input (defaulted from tenant service UoM, editable) | required for measuring types; explicit, never assumed |
| Read method | S51 | prototype-extracted + A2 r4 (Meter types AMI/AMR/walk-by reused) | `assets.read_method` (B2 r4) | enum | user-input | N/A allowed for BTM |
| Multiplier | S51 | prototype-extracted (default 1) | `assets.multiplier` | numeric(18,6) | user-input | > 0; measuring types only |
| Manufacturer / model | S51 | A2 r4 addendum (free text, not a lookup) | `assets.manufacturer` + `assets.model` (B2 r4; single input stored across both, split on "·"; whole string to manufacturer when no separator) | text | user-input | optional |
| Install date | S51 | prototype-extracted | `assets.install_date` | date | user-input | required when assigning |
| Assign to | S51 | prototype-extracted | `asset_assignments` (B2 r4) new row / none | uuid unit FK | user-input | unit must belong to tenant |
| Parent / master | GAP — column exists on Sub-meters tab but the Add modal lacks the picker (derived: required by BR-AST-003) | derived from prototype Sub tab + B2 r4 | `assets.parent_asset_id` | uuid self-FK | user-input | required iff type = sub_meter; parent must be a meter/net meter of same tenant |
| Net metering | S51 | prototype-extracted (checkbox) | `assets.net_metering` (B2 r4) | boolean | user-input | BR-AST-010 |

**6 · Acceptance**
- Given the modal launched from any tab, When a valid asset is saved, Then it appears on the tab its type belongs to, with status/assignment per BR-AST-011 and an audit row, And its asset # came from the series unless overridden (BR-AST-026).
- Given a duplicate asset number within the tenant, When submitted, Then the save is rejected inline (hard block) and nothing is written; Given a duplicate serial, When submitted, Then a warning shows and the save is allowed (BR-AST-033).
- Given type Net meter, When saved, Then `net_metering` is true and cannot have been unchecked.
- Given a sub-meter, When saved, Then it carries a valid same-tenant parent meter.

**7 · Finance Calculation** — N/A

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-045 | Asset numbering: series auto-allocation vs free entry | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-AST-026) — 3-identifier model: hidden system ID + serial + user number auto from series w/ per-type prefixes, override allowed (PO R6) |
| OQ-031 *(existing — referenced, not duplicated)* | Enum-backed reference lists (incl. asset types/stages): tenant-extensible vs platform-curated | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-TEN-036) — seeded defaults + tenant-extensible; enums→lookup tables (PO R6) |

---
id: US-AST-003
epic: EP-AST-01
module: assets
screens: [S49]
wave: 1
status: draft
blocked_by: []
depends_on: [US-AST-001, US-AST-002, US-AST-004]
journeys: []
rules: [BR-AST-002, BR-AST-012, BR-AST-013, BR-AST-032]
golden_tests: []
finance_calc: none
---
### US-AST-003 — Edit asset specs; delete only unreferenced inventory

**1 · Details** — As a staff user, I want to correct an asset's specification fields, and to hard-delete only a never-used inventory item, so that data-entry mistakes are fixable while billing history stays intact. Entry: row action **Edit** (S49) or from S50 Overview; row action **Delete** appears only on inventory rows per BR-AST-006. Edit reuses the S51 field set (plus the extended spec fields of US-AST-004). Roles: create/edit = System Admin + Billing Clerk; **Delete is System Admin only** (BR-AST-032). Exit: Save → toast + audit; Delete → confirm modal (IS-6) → row gone. Deactivate-first/audit-lock semantics follow IS-1.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AST-002 | Assets referenced by issued bills are audit-locked: retire, never hard-delete. | CONFIRMED — A5 v4 / CLAUDE.md #4 (existing rule) |
| BR-AST-012 | Every edit writes `audit_log` with before/after. Billing-affecting fields (multiplier, unit, net_metering, service) are edit-restricted once the asset has reads: the change applies **from now on only** — stored reads keep the consumption computed at their time, and issued invoices are never restated (corrections are new rows). | CONFIRMED — PO R4-A1 (forward-only fields) |
| BR-AST-013 | Hard delete is allowed only when status = `inventory` AND the asset has never been referenced — no read, no assignment history, no maintenance entry, no bill/invoice line, no `replaced_by` pointer. Anything else: delete is blocked with a pointer to Retire (S54). | CONFIRMED — PO R4-A2 (delete guard) |
| BR-AST-032 | Roles: create/edit = System Admin + Billing Clerk; retire + delete = System Admin only; Executive view-only. | CONFIRMED — PO R4 Q1 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana edits M-4310: manufacturer/model → "Honeywell · A3 Turbo" | Saved; toast; `audit_log` `asset.updated` with before/after |
| TC-2 | Dana edits M-4021 (has reads) multiplier ×10 → ×1 | Warning that historical reads/bills are untouched; change applies to future reads only; audited |
| TC-3 | Dana deletes M-5099 (inventory, never referenced) | Confirm modal → hard delete; row gone from all tabs; `audit_log` `asset.deleted` |
| TC-4 *(negative)* | Delete attempted on M-4021 (assigned, has reads) via direct API call | 409/blocked server-side with retire pointer — even though the UI hides Delete (BR-AST-006 enforcement is server-side) |
| TC-5 *(negative)* | Delete attempted on BAT-0904 after it once held an assignment history row | Blocked (referenced by assignment history) — retire instead |
| TC-6 *(negative)* | Marcus Vega (Billing Clerk) edits M-4310, then attempts Delete on M-5099 | Edit succeeds with audit (clerk may create/edit — BR-AST-032); Delete is System-Admin-only: disabled-with-reason in UI, direct API call rejected 403 (BR-AST-032, IS-6) |
| TC-7 *(isolation)* | Erin (Lone Star Ridge) calls edit/delete against Brazos Bend's M-5099 id | Not-found under Lone Star Ridge `app.tenant_id`; no cross-tenant write |

**4 · Test Data** — Fixtures from US-AST-001. M-5099 has zero reads/assignments/maintenance rows. A variant BAT-0904′ seeded with one closed assignment row for TC-5. Actors: Dana Whitfield (System Admin); Marcus Vega (Billing Clerk); Erin Walsh.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Editable spec fields | S49→edit | prototype-extracted (S51 set) + US-AST-004 extended set | `assets.*` per US-AST-002/004 rows | — | user-input | BR-AST-012 restrictions when reads exist; role gate BR-AST-032 |
| Delete action | S49 | prototype-extracted (inventory rows only) | row removal (hard delete) | — | user-input | BR-AST-013 gate, server-side; System Admin only (BR-AST-032) |
| Reference check | — | derived (IS-1 `used_by = 0` rule) | existence probes: `meter_reads`, `asset_assignments`, `asset_maintenance`, invoice lines (via billing service), `assets.replaced_by_asset_id` (**PROPOSED-SCHEMA**, see US-AST-008) | — | system-derived | any hit blocks delete |
| Edit audit | — | CLAUDE.md #7 / IS-6 | `audit_log` (`asset.updated` / `asset.deleted`) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given any edit, When saved, Then an audit row holds before/after and list/detail reflect the change.
- Given an asset with reads, When a billing-affecting field changes, Then no stored read or issued invoice changes.
- Given a never-referenced inventory asset, When deleted by a System Admin, Then it is gone; given any referenced asset or a non-admin actor, When delete is attempted by UI or API, Then it is blocked (retire pointer / 403 per BR-AST-032).

**7 · Finance Calculation** — N/A

**8 · Open Questions** — None (delete gate CONFIRMED per BR-AST-013 — PO R4-A2; roles per BR-AST-032).
