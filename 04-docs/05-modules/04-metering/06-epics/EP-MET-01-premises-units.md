# EP-MET-01 — Premises & Units
> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep.

**Module:** metering (product name: **Meter Reads**) · **Wave:** W1 · **Screens:** S14, S15, S16 · **Status:** draft

## Scope
**In:** the Premises list tab (S14), the Units list tab (S15), and the guided Add Premises & Unit flows (S16): single premise, bulk premises from CSV, single unit, pattern-generated units, and bulk units from CSV — including the wizard's meter / sub-meter assignment and default-plan assignment steps (display + storage of the assignment; no rating math). Creates the physical hierarchy premises → units → service_points → assets that everything downstream (accounts, reads, billing) hangs on. **Detail views are CONFIRMED per BR-MET-045 (PO PU-16/17/18): Premises detail = Units / Assets / Accounts / Audit tabs; Unit detail = Overview / Assets / Account history / Plan history / Audit** — detail-view stories to be allocated in the next authoring pass. **Every premises/unit change writes an audit record (BR-MET-048)**; both detail views carry a read-only Audit tab.
**Out:** the Assets module UI surface (S49–S55 — 04-docs/05-modules/05-assets; this epic only *creates/links* asset rows via the unit wizard) · accounts and move-in/out (customers module, S17–S21) · plan/rate content and any pricing math (rating — the wizard stores the default-plan reference; plan-binding semantics per BR-CUS-014) · reads ingestion (EP-MET-03) · routes/cycles config (EP-MET-02) · table framework mechanics (EP-SHL-02 — consumed via the capability matrix below).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S14 Premises | address, premise_no, owner_manager | property type (from the Reference-data premises types list — BR-MET-034), status | premise_no asc | premise_no, address, type, units, status | 7 default (Premise ID · Address · Type · Units · Services available · Owner/manager · Status) / 9 available (+City, +External ref) | View units, Edit, Deactivate, Delete (only when unit count = 0 — BR-MET-037) | — (v1) | CSV (IS-9) |
| S15 Units | premise (no/address), unit label, meter_no | occupancy (All/Occupied/Vacant/Sub-metered — derived per BR-MET-036), premise, service | unit_no asc | unit_no, premise, label, type, status | 8 default (Unit ID · Premise · Unit · Type · Services · Meters · Occupant/Account · Status) / 10 available (+Floor, +Sq ft) | Edit, Deactivate, Delete (only when never referenced by account/asset/read — BR-MET-037) | — (v1) | CSV (IS-9) |

## Stories

---
id: US-MET-001
epic: EP-MET-01
module: metering
screens: [S14]
wave: 1
status: draft
blocked_by: []
depends_on: [US-TEN-007, US-SHL-006, US-SHL-007, US-SHL-008]
journeys: [J2]
rules: [BR-MET-001, BR-MET-003, BR-MET-034, BR-MET-037, BR-MET-048]
golden_tests: []
finance_calc: none
---
### US-MET-001 — Premises list tab

**1 · Details** — As a staff user, I want a Premises tab listing every physical property with its type, unit count, available services, owner/manager and status, so that I can find a property and drill into its units. Entry: sidebar → Premises (S14 is the default tab; header shows the roll-up "N premises · N units · N vacant · N pending activation" per prototype). Exit: row click → Units tab filtered to that premise (S15); **+ New premise** → S16; **Import CSV** → S16 bulk mode. List renders through the shared table framework per the capability-matrix row (EP-SHL-02); states per A18.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-001 | A premise is a tenant-scoped physical property (address, type, owner/manager) with an auto-generated premise number from the tenant numbering series; IS-1 deactivate-first. | PROPOSED — derived from prototype S14/S16 + B2 `premises` + IS-1 + EP-TEN-08 numbering; delete guard CONFIRMED via BR-MET-037 |
| BR-MET-003 | Service availability shown/settable on premises and units is limited to the tenant's enabled services (`tenant_services`); disabled services render disabled, never hidden data. | PROPOSED — derived from S16 service chips (Gas row disabled) + EP-TEN-06 |
| BR-MET-034 | Premises types are **Reference data**: seeded Apartment complex · Commercial building · Single-family · Mixed-use · Mobile-home park, tenant-extensible — never a hardcoded enum. | CONFIRMED — PO PU-1 |
| BR-MET-037 | Delete guards: premises hard-deletable only with zero units; unit only if never referenced (account/asset/read); otherwise deactivate. | CONFIRMED — PO PU-4 |
| BR-MET-048 | Every premises/unit change — create, edit, deactivate, plan assignment, asset tag/untag — writes an audit record (who/when/before→after). | CONFIRMED — PO PU-14 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana opens Premises with the §4 seed | 6 rows; header roll-up "6 premises · 143 units · 9 vacant · 1 pending activation"; default sort premise_no asc; services column renders E/W tags only (Brazos Bend has Electric+Water enabled) |
| TC-2 | Filter Type = Commercial (a Reference-data premises type entry — BR-MET-034) | Only P-00214 and P-00420 remain; filter chip + URL state per IS-4 |
| TC-3 | Search "Bluestem" | P-00101 only (address match, server-side per IS-3) |
| TC-4 | Click row P-00214 | Units tab (S15) opens scoped to P-00214 (18 units) |
| TC-5 *(negative)* | Dana chooses Delete on P-00101 (2 units) | Blocked with audit-lock message "has units — deactivate instead" (BR-MET-037, IS-1); no row removed |
| TC-6 *(negative)* | List endpoint returns 500 | A18 failed-with-retry card; Retry re-issues the identical query |
| TC-7 *(isolation)* | J. Okafor (Lone Star Ridge) opens Premises | Sees only Lone Star Ridge's 1 seeded premise; automated test asserts no Brazos Bend premise id in any page/sort/search permutation (RLS `app.tenant_id`) |

**4 · Test Data** — Tenant: **Brazos Bend Utilities** (`brazosbend`, Katy TX, services Electric+Water — tenancy pack fixtures). Premises: P-00101 · 1408 Bluestem Ln · Residential · Duplex · 2 units · Whitfield Rentals LLC · Active; P-00102 · 2201 Cane Island Pkwy · Residential · Single · 1 · Chen, David · Active; P-00214 · 500 Mason Rd Plaza · Commercial · Multi-tenant · 18 · Mason Rd Holdings · Active; P-00318 · 2200 Riverbend Ct · Residential · Apartment · 120 · Riverbend Apts LP · Active; P-00350 · 3450 Pin Oak Dr · Residential · Single · 1 · Rodriguez, M. · Pending; P-00420 · 77 Gulf Fwy Industrial · Commercial · Warehouse · 1 · Northwind Mfg. · Active. (Type labels = Brazos Bend's tenant-extended Reference-data entries beside the 5 seeded types — BR-MET-034.) Isolation tenant: **Lone Star Ridge Water Co-op** (`lonestarridge`), premise P-00087 · 4102 Ranch Rd 12. Actors: Dana Whitfield (System Admin), Marcus Vega (Billing Clerk).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Premise ID | S14 | prototype-extracted (`P-10432`) | **PROPOSED-SCHEMA** `premises.premise_no` (tenant numbering series, unique per tenant) | text | system-derived | unique (tenant, premise_no) |
| Address | S14 | prototype-extracted | `premises.address_line` + `city`/`state`/`postal_code` | text | user-input | address_line required |
| Type | S14 | Reference data — premises types (BR-MET-034; supersedes the prototype's hardcoded 7-option enum) | **PROPOSED-SCHEMA** `premises.premises_type_id` → tenant premises-types lookup (seeded: Apartment complex, Commercial building, Single-family, Mixed-use, Mobile-home park; tenant-extensible per BR-TEN-036) | uuid ref | reference-data | active list entry |
| Units (count) | S14 | prototype-extracted | count of `units` where premises_id | integer | computed-display | — |
| Services available | S14 | prototype-extracted (E/W/S tags) | **PROPOSED-SCHEMA** `premises.services_available service_type[]` | enum[] | user-input | ⊆ tenant-enabled services (BR-MET-003) |
| Owner / manager | S14 | prototype-extracted | **PROPOSED-SCHEMA** `premises.owner_manager` | text | user-input | optional |
| Status | S14 | prototype-extracted (Active/Pending pills) | **PROPOSED-SCHEMA** `premises.status` (draft \| pending \| active \| inactive) | enum | system-derived | draft from Save-draft; deactivate → inactive (audited — BR-MET-048) |
| Header roll-up | S14 | prototype-extracted | counts over `premises`/`units` | integers | computed-display | — |

**6 · Acceptance**
- Given the §4 seed, When Dana opens Premises, Then all six Brazos Bend premises render with correct type/units/services/status and the roll-up counts match.
- Given a premise with units, When Delete is attempted, Then it is blocked per BR-MET-037 and Deactivate is offered instead; every deactivation writes an audit record (BR-MET-048).
- Given a Lone Star Ridge session, When Premises is opened, Then zero Brazos Bend rows appear in any permutation.

**7 · Finance Calculation** — N/A

**8 · Open Questions** — None.

---
id: US-MET-002
epic: EP-MET-01
module: metering
screens: [S15]
wave: 1
status: draft
blocked_by: []
depends_on: [US-MET-001, US-SHL-006, US-SHL-007, US-SHL-008]
journeys: [J2]
rules: [BR-MET-002, BR-MET-003, BR-MET-036, BR-MET-037]
golden_tests: []
finance_calc: none
---
### US-MET-002 — Units list tab

**1 · Details** — As a staff user, I want a Units tab listing every metered space with its premise, type, services, meters and occupant/account, so that I can see what is metered where and which units are vacant or sub-metered. Entry: Premises page → Units tab (S15), or premise row click (scoped). Exit: **+ New unit** → S16 unit wizard; row Edit. The tab restates the model rule in copy: "Accounts attach to units, not to premises" (prototype). List renders per the capability-matrix row; meters cell shows meter numbers with `(sub)`/`(master)` qualifiers. Occupancy is a derived display — active account ⇒ Occupied, none ⇒ Vacant (BR-MET-036). Unit detail (row click) carries Overview / Assets / Account history / **Plan history** / Audit tabs per BR-MET-045 (detail stories allocated separately).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-002 | A unit belongs to exactly one premise; its label is unique within (tenant, premise); accounts attach to units, never to premises. | CONFIRMED — B2 `units` DDL (FK + UNIQUE) + prototype S15 copy |
| BR-MET-003 | *(shared with US-MET-001)* services shown ⊆ tenant-enabled services. | PROPOSED — see US-MET-001 |
| BR-MET-036 | Unit occupancy is **DERIVED from the active account** on the unit — never manually set or stored as user input. | CONFIRMED — PO PU-3 |
| BR-MET-037 | Unit hard delete only if never referenced by an account, asset, or read; otherwise deactivate (premises: zero units). | CONFIRMED — PO PU-4 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana opens Units | Units render with premise, label, type, service tags, meters (e.g. `M-7001, W-7001`; `M-7204 (sub)`; `M-7200 (master)`), occupant/account, status pills (Active/Vacant/Pending/Disconnect) |
| TC-2 | Filter Occupancy = Vacant | Only vacant units (incl. U-00101-B) — occupancy derived from the absence of an active account (BR-MET-036); chip + URL per IS-4 |
| TC-3 | Filter = Sub-metered | Only units whose meters have a parent (U-00214-200, U-00318-101…103) |
| TC-4 | Search "M-7204" | U-00214-200 found via meter number (declared search field) |
| TC-5 *(negative)* | Delete U-00101-A (has account A-00412, assets M-7001/W-7001, and reads) | Blocked per BR-MET-037: "referenced by an account, assets and reads — deactivate instead"; row intact |
| TC-6 *(negative)* | Create a second unit labeled "Unit A" under P-00101 via Edit rename | Rejected by the (tenant, premise, label) uniqueness rule with inline error |
| TC-7 *(isolation)* | Lone Star Ridge session opens Units | Only Lone Star Ridge units; a unit labeled "Unit A" exists in both tenants without conflict (uniqueness is per tenant+premise) |

**4 · Test Data** — Units under §4/US-MET-001 premises: U-00101-A (Unit A, Residential, M-7001 E + W-7001 W, occupant Miller, Sarah · A-00412, Active); U-00101-B (Unit B, Vacant — no active account); U-00214-200 (Suite 200, Commercial, M-7204 (sub), Ridge Coffee Co. · A-00520, Active); U-00214-M (Master, Commercial · Master, M-7200 (master), Mason Rd Holdings · A-00518, Active); U-00318-101…103 (Apt 101–103, Residential · Sub-metered, M-7301…M-7303 (sub); 103 Vacant); U-00350 (—, Residential, Pending); U-00420 (Bldg 1, Commercial · Warehouse, M-7210, ×10 multiplier, Northwind Mfg. · A-00611, Active). Lone Star Ridge: U-00087-A "Unit A" under P-00087.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Unit ID | S15 | prototype-extracted (`U-10432-A`) | **PROPOSED-SCHEMA** `units.unit_no` (tenant numbering) | text | system-derived | unique per tenant |
| Premise | S15 | prototype-extracted | `units.premises_id` → `premises` | uuid | reference-data | must exist, same tenant |
| Unit label | S15 | prototype-extracted | `units.label` | text | user-input | unique (tenant, premises_id, label) |
| Unit type | S15/S16 | prototype-extracted (5 options) | **PROPOSED-SCHEMA** `units.unit_type` (residential \| residential_submetered \| commercial \| commercial_master \| common_area) | enum | user-input | from option set |
| Occupancy | S15 | BR-MET-036 (supersedes the prototype's manual Vacant/Occupied/Reserved select) | derived: active `accounts` row on the unit ⇒ Occupied, none ⇒ Vacant — **no stored occupancy column, never manually set** | derived enum | computed-display | BR-MET-036 |
| Services | S15 | prototype-extracted | `service_points.service` rows per unit | enum[] | system-derived | ⊆ tenant-enabled |
| Meters | S15 | prototype-extracted | `assets` (B2 r4, supersedes `meters`): `meter_no`, `parent_asset_id` for (sub)/(master) | text | reference-data | — |
| Occupant / Account | S15 | prototype-extracted | `accounts` via `accounts.unit_id` (⚠ cross-module read, customers) | text | computed-display | read via service function (B1) |
| Status | S15 | prototype-extracted (4 pills) | computed from `accounts.status` + derived occupancy (BR-MET-036) | enum | computed-display | display only — no stored unit status |

**6 · Acceptance**
- Given the §4 seed, When Dana opens Units, Then every unit shows its premise, meters with sub/master qualifiers, occupant and status, And filters for Occupied/Vacant/Sub-metered partition the rows correctly from derived occupancy (BR-MET-036).
- Given a referenced unit, When Delete is attempted, Then BR-MET-037 blocks it.
- Given two tenants each with "Unit A", Then neither list ever shows the other's row.

**7 · Finance Calculation** — N/A

**8 · Open Questions** — None.

---
id: US-MET-003
epic: EP-MET-01
module: metering
screens: [S16]
wave: 1
status: draft
blocked_by: []
depends_on: [US-MET-001, US-MET-002, US-MET-006, US-RAT-002, US-TEN-012, US-SHL-010]
journeys: []
rules: [BR-MET-001, BR-MET-002, BR-MET-003, BR-MET-006, BR-MET-007, BR-MET-036, BR-MET-048]
golden_tests: []
finance_calc: none
---
### US-MET-003 — Guided add: single premise & single unit with meter and plan assignment

**1 · Details** — As a staff user, I want guided wizards to add one premise (3 steps: How many? → Details → Review & save) and one unit (4 steps: Premise & mode → Define units → Meters & plan → Review & save), so that a new property is created with its meters and default plan in one pass. Entry: S14 **+ New premise** / S15 **+ New unit** (S16). Wizard mechanics (step rail, Save draft & exit, Cancel, Review) conform to EP-SHL-03; this story owns the metering content: premise details (ID auto, address, type from the Reference-data list (BR-MET-034), unit count, route, owner, services, "also create a unit automatically"), unit details (label, floor, type, sq ft — occupancy is derived from the active account and never entered, BR-MET-036), the **Meters — one row per service** grid (meter type, assignment mode Auto-generate / Assign existing / Leave blank, meter ID, multiplier), the **Sub-meter relationship** panel (master meter per service, allocation rule, loss tolerance), and the **Plan assignment** panel (default plan, effective from, vacant-standby toggle, plan lock, read-only plan summary). Exit: toast "1 premise created" / "1 unit created" → list; every create writes audit (BR-MET-048).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-001 | *(shared)* premise identity + numbering. | PROPOSED — see US-MET-001 |
| BR-MET-002 | *(shared)* unit belongs to one premise; label unique. | CONFIRMED — B2 |
| BR-MET-003 | *(shared)* services ⊆ tenant-enabled. | PROPOSED |
| BR-MET-006 | Meter assignment: at most one meter per enabled service per unit, created as an `assets` row (B2 r4) via mode Auto-generate (next number in tenant series) / Assign existing (from unassigned inventory) / Leave blank (fill later from Reads); multiplier defaults to 1 and is stored explicitly; a sub-meter references its master via `parent_asset_id`; the master's total is expected to reconcile against Σ sub-meters within the configured loss tolerance (checked by EP-MET-04's Mismatch flag). Inline asset creation/reference follows BR-AST-028 (bidirectional creation, one registry). | PROPOSED — derived from S16 step 3 + B2 r4 + A2 addendum; bidirectional creation CONFIRMED (BR-AST-028) |
| BR-MET-007 | The unit's default plan pre-selects when an account is created on the unit; "Lock plan on this unit" gates changes behind permission; stored as a cross-module FK unit → tariff (reviewed interface set, B2 §2). **Per BR-CUS-014 the unit plan is BINDING and two-way synced with the account (billing reads the account snapshot); direct unit-level plan edit is allowed as an error-correction override with warning + audit (BR-MET-042); after move-out the unit keeps its last plan as the next prefill (BR-MET-044).** | SUPERSEDED-REFINED by BR-CUS-014 (PO PU-9 scenarios 1–6) — supersedes the earlier "pre-fill reference only" framing |
| BR-MET-036 | *(shared)* occupancy derived from the active account — the wizard captures no occupancy input. | CONFIRMED — PO PU-3 |
| BR-MET-048 | Every wizard save (premise, unit, meter link, plan assignment) writes an audit record. | CONFIRMED — PO PU-14 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana adds premise "1901 Bluestem Ln" (Single-family type from the Reference-data list, 1 unit, Route 3, services E+W, auto-create-unit ON) and saves | One `premises` row (P-00421 auto), one auto-created unit, service tags E+W; toast; `audit_log` row `premises.created` (BR-MET-048) |
| TC-2 | Dana adds unit "Suite 220" under P-00214 with E meter mode Assign existing → M-7205 (inventory), multiplier 1; sub-metered under master M-7200; default plan "Small Commercial", effective Sep 1, 2026, plan locked | Unit + `service_points` (E) + asset link created; M-7205 leaves inventory (assets module status → active); `parent_asset_id` = M-7200; `units.default_tariff_id` set; unit shows Vacant (derived — no account yet, BR-MET-036); audit rows present |
| TC-3 | Meter mode Auto-generate for W | Next asset number in the Brazos Bend series (per-type prefix per BR-AST-026) is reserved and shown before save |
| TC-4 | Gas row in the meter grid | Renders disabled (Gas not enabled for Brazos Bend) — BR-MET-003 |
| TC-5 *(negative)* | Save unit labeled "Unit A" under P-00101 (already exists) | Inline uniqueness error at step 2; nothing written |
| TC-6 *(negative)* | Assign existing meter M-7001 (already active on U-00101-A) | Rejected: "already assigned to U-00101-A — reassign from Assets"; no double-assignment |
| TC-7 *(negative)* | Multiplier field set to 0 | Inline validation error (must be > 0); save blocked |
| TC-8 *(isolation)* | Lone Star Ridge admin runs the same wizard | Premise/unit/asset rows carry Lone Star Ridge tenant_id; their meter picker never lists Brazos Bend inventory |

**4 · Test Data** — Actor Dana Whitfield. New premise P-00421 · 1901 Bluestem Ln, Katy TX 77494 (type Single-family — seeded Reference-data entry, BR-MET-034). New unit Suite 220 under P-00214, Commercial, 1,150 sq ft (vacant — no account yet; occupancy derived per BR-MET-036). Meters: existing inventory M-7205 (E, AMI · Itron OpenWay), auto W candidate W-7205. Master meters M-7200 (E), W-7200 (W); allocation rule RUBS; loss tolerance 3% (sample value, tenant-editable). Plans (rating fixtures): Residential Standard $30.50/mo, Small Commercial $48.00/mo — displayed only, not priced here.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Premise ID (auto) | S16 | prototype-extracted ("Auto (P-11800)") | **PROPOSED-SCHEMA** `premises.premise_no` | text | system-derived | tenant series (EP-TEN-08) |
| External / GIS ref | S16 | prototype-extracted | **PROPOSED-SCHEMA** `premises.external_ref` | text | user-input | optional |
| Street address / City / State / ZIP | S16 | prototype-extracted | `premises.address_line`/`city`/`state`/`postal_code` | text | user-input | address required |
| Property type · Number of units · Route · Owner | S16 | prototype-extracted; type via Reference data (BR-MET-034) | `premises.premises_type_id`* (Reference-data lookup) · unit scaffold count · `service_points.route_id` default · `premises.owner_manager`* (*=**PROPOSED-SCHEMA**) | uuid/int/uuid/text | user-input / reference-data | route must exist; type = active list entry |
| Also create a unit automatically | S16 | prototype-extracted (default on) | creates one `units` row | boolean | user-input | single-unit premises only |
| Unit label / Floor / Type / Sq ft | S16 | prototype-extracted — occupancy input REMOVED (derived per BR-MET-036, never entered) | `units.label` · **PROPOSED-SCHEMA** `units.floor_label` / `units.unit_type` / `units.square_feet` | text/enum/int | user-input | label unique per premise |
| Meter type | S16 meter grid | prototype-extracted + A2 addendum (Meter types lookup) | `assets.read_method` (B2 r4) via Meter-types reference list | reference | reference-data | tenant lookup entry |
| Assignment mode | S16 meter grid | prototype-extracted (3 options) | write path only (no column) | enum | user-input | — |
| Meter ID / start # | S16 meter grid | prototype-extracted | `assets.meter_no` | text | user-input / system-derived | unique (tenant, meter_no) |
| Multiplier | S16 meter grid | prototype-extracted (default 1) | `assets.multiplier` (carried from `meters.multiplier`) | numeric(18,6) | user-input | > 0; explicit, never defaulted silently |
| Sub-metered toggle + master per service | S16 | prototype-extracted | `assets.parent_asset_id` | uuid | user-input | master must be same service + same premise |
| Allocation rule / Loss tolerance | S16 | prototype-extracted (RUBS/sqft/equal/absorb; "3%") | **PROPOSED-SCHEMA** `assets.allocation_rule` + `assets.loss_tolerance_pct` on the master asset | enum / numeric(18,6) % | user-input | tolerance ≥ 0; 3% is a sample, not a constant |
| Default plan / effective / lock / vacant-standby | S16 | prototype-extracted; binding semantics per BR-CUS-014 | **PROPOSED-SCHEMA** `units.default_tariff_id` (⚠ cross-module FK → rating `tariffs`) / `units.plan_effective_from` / `units.plan_locked` / `units.vacant_standby_auto` — assignment history rows append per BR-CUS-013 (`unit_plan_assignments`, B2 r5 #13) | uuid/date/bool/bool | user-input | tariff must be active, same tenant |
| Plan summary table | S16 | prototype-extracted | read-only render of rating data | — | computed-display | display only — no money math here |

**6 · Acceptance**
- Given a completed single-unit wizard, When Dana saves, Then premises/units/service_points/assets rows exist with the declared meters, sub-meter parentage, multiplier and default-plan reference, each with audit rows (BR-MET-048), And nothing was billed or priced.
- Given a duplicate label, an already-assigned meter, or a zero multiplier, When save is attempted, Then the wizard blocks with an inline error and writes nothing.
- Given the wizard forms, Then no occupancy input exists anywhere — occupancy derives from the active account (BR-MET-036).
- Given the isolation seed, Then no cross-tenant premise, meter, or plan is ever selectable.

**7 · Finance Calculation** — N/A (plan summary is a read-only display of rating-owned values; no rule from B4 is exercised).

**8 · Open Questions** — None.

---
id: US-MET-004
epic: EP-MET-01
module: metering
screens: [S16]
wave: 1
status: draft
blocked_by: []
depends_on: [US-MET-003]
journeys: []
rules: [BR-MET-002, BR-MET-004, BR-MET-005, BR-MET-006, BR-MET-007, BR-MET-031, BR-MET-038, BR-MET-039, BR-MET-048]
golden_tests: []
finance_calc: none
---
### US-MET-004 — Bulk create: premises CSV, unit pattern generator & units CSV

**1 · Details** — As a staff user onboarding a portfolio, I want to bulk-create premises from CSV and units by **BOTH paths — pattern generator AND CSV upload** (BR-MET-031): a pattern (floors × units-per-floor with `{seq}`/`{floor}` tokens, e.g. a 120-unit building in seconds) or a CSV (uneven layouts, existing meter IDs), so that setup scales to the product's 3,000-connection ceiling without data entry. Entry: S16 step 1 mode cards (Bulk from CSV / Pattern generator). Flow per prototype: drop CSV (≤10 MB, UTF-8, **≤10,000 rows — BR-MET-038**) → column mapping auto-detected by header, remappable → validation preview (Rows / Valid / Warnings / Errors + DUPE callout) → review ("Will create N…") → Create with skip-errors ON (staged, per-row errors — same import discipline as assets, BR-MET-038). Pattern mode: floors, units per floor, total (calc, ≤3,000/run), numbering pattern, unit-ID pattern, default type, live label preview. Units CSV can carry asset columns that **reference existing assets (asset #) or create new ones inline (serial + type)** per BR-MET-039/BR-AST-028 — units created and meters linked in one pass; step 3 (meters/sub-meters/plan) then applies batch-wide defaults exactly as in US-MET-003. Exit: **result summary always shown — "N created · N failed"** (BR-MET-038) with per-row error report; batch audit (BR-MET-048).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-002 | *(shared)* unit label unique per (tenant, premise) — enforced per CSV row too. | CONFIRMED — B2 |
| BR-MET-004 | Bulk import is staged and validates every row before anything is written: the preview shows row/valid/warning/error counts; rows sharing an address with an existing premise (or duplicating an existing unit label / meter no) are skipped unless the user opts to merge; errors block those rows; the create writes exactly the reviewed set with skip-errors ON (per-row errors, never a partial surprise), and the **result summary "N created · N failed" is always shown** with reasons. | PROPOSED (staging mechanics — S16 preview + DUPE callout); import standard CONFIRMED — PO PU-5/6 (BR-MET-038) |
| BR-MET-005 | Pattern generator: total = floors × units-per-floor, **capped at 3,000 per run**; the numbering/unit-ID patterns drive generated labels with a live preview using the **confirmed `{seq}` / `{floor}` token grammar** (BR-MET-031/038 — OQ-039 CLOSED). | CONFIRMED — PO R7/PU-5 (grammar); mechanics from S16 |
| BR-MET-031 | Bulk unit creation offers BOTH paths: pattern generator (`{seq}`/`{floor}` tokens) AND CSV upload of a unit list. | CONFIRMED — PO R7 (OQ-039) |
| BR-MET-038 | Bulk creation standard: pattern ≤3,000/run; CSV staged with per-row errors, skip-errors ON, "N created · N failed" summary, **10,000-row cap per file** (same discipline as assets, BR-AST-034). | CONFIRMED — PO PU-5/6 |
| BR-MET-039 | Unit CSV columns per PU-7; asset columns may REFERENCE existing assets (asset #) or CREATE new ones inline (serial + type) per BR-AST-028 — both land in the one assets registry, never duplicates. | CONFIRMED — PO PU-7/8 |
| BR-MET-006 / BR-MET-007 | *(shared)* meter assignment and default-plan assignment apply batch-wide in step 3 (plan binding per BR-CUS-014). | PROPOSED / SUPERSEDED-REFINED by BR-CUS-014 — see US-MET-003 |
| BR-MET-048 | Each bulk batch writes an audit record (file, counts, actor); per-unit plan assignments audit individually (BR-MET-041). | CONFIRMED — PO PU-14 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana uploads `brazosbend_premises_2026.csv` (184 rows, 3 address-dupes) | Preview: Rows 184 · Valid 181 · Warnings 3 · Errors 0; DUPE callout names the skip-or-merge choice; Create → exactly 181 premises; **summary "181 created · 3 failed/skipped" always shown with reasons (BR-MET-038)**; audit `premises.bulk_created` (file name, counts) |
| TC-2 | Pattern: P-00318, 6 floors × 20/floor, pattern `Apt {floor}{seq:01–20}` ({seq}/{floor} tokens — BR-MET-031) | Total (calc) = 120; preview shows Apt 101…Apt 620; Create → 120 units + auto meters M-7301→M-7420 (E) per step-3 choice, all sub-metered under M-7300 |
| TC-3 | Units CSV `riverbend_units.csv` (248 rows incl. asset columns) | 246 valid; units created **and** assets linked in one pass — rows with an asset # reference existing inventory, rows with serial+type create new assets inline (BR-MET-039/BR-AST-028); summary "246 created · 2 failed" with reasons |
| TC-4 *(negative)* | CSV with unknown premise_id `P-99999` in a row | That row errors ("premise must exist"); other rows import (skip-errors ON — BR-MET-038); error row exported/reviewable with reason |
| TC-5 *(negative)* | Pattern totals 6 × 600 = 3,600 | Blocked at step 2: exceeds the 3,000-per-run cap (BR-MET-038); nothing generated |
| TC-6 *(negative)* | 12 MB file dropped | Rejected client- and server-side (>10 MB); no upload |
| TC-7 *(negative)* | Re-upload the same premises CSV after TC-1 | All 181 now report as address-duplicates → skipped unless merge; no double-create |
| TC-8 *(isolation)* | Lone Star Ridge uploads a units CSV naming Brazos Bend premise P-00214 | Every such row errors "premise must exist" — cross-tenant premise ids never resolve |
| TC-9 *(negative)* | Units CSV with 12,000 rows | Rejected at upload: exceeds the **10,000-row cap** (BR-MET-038); nothing staged |

**4 · Test Data** — Files: `brazosbend_premises_2026.csv` (184 rows; columns address, city/state/zip, type, units, owner, services, route); `riverbend_units.csv` (248 rows; columns per PU-7 — premise_id, unit_label, type, services, asset ref (asset # OR serial+type), occupant); `riverbend_oversize.csv` (12,000 rows) for TC-9. Pattern run: P-00318 · 2200 Riverbend Ct, 6 × 20, tokens `{floor}`/`{seq}`, default type Residential · Sub-metered, masters M-7300 (E) / W-7300 (W), allocation RUBS, default plan Residential Standard. Caps: 10 MB · 10,000 rows/file (CSV) · 3,000 units/run (pattern).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| CSV file (premises/units) | S16 | prototype-extracted + BR-MET-038 | parsed → `premises` / `units` / `service_points` / `assets` rows | file ≤10 MB UTF-8 | user-input | size/encoding; **≤10,000 rows (BR-MET-038)**; template downloadable |
| Column mapping | S16 | prototype-extracted ("auto-detected", remap selects) | mapping applied at parse (no column) | — | user-input | required targets mapped (address; premise_id+unit_label) |
| Validation preview counts | S16 | prototype-extracted | computed over staged rows (no persistence in v1) | integers | computed-display | — |
| Skip/merge duplicates · Skip warnings · Auto-create unit per single-unit premise | S16 | prototype-extracted (checkboxes; skip-errors ON default per BR-MET-038) | import options (no column) | boolean | user-input | — |
| Floors · Units per floor · Total (calc) | S16 pattern | prototype-extracted | generator input (no column) | int | user-input / computed-display | total ≤ 3,000 (BR-MET-038) |
| Numbering pattern · Unit ID pattern | S16 pattern | **`{seq}` / `{floor}` token grammar CONFIRMED (BR-MET-031/038 — OQ-039 CLOSED)** | `units.label` / `units.unit_no` | text | user-input | tokens {seq}/{floor}; live preview |
| Asset columns (asset # OR serial+type) | S16 units CSV | PU-7 columns (BR-MET-039) | reference existing `assets` by asset_no OR create new inline (serial+type, BR-AST-028) + link to unit's service_point | text | user-input | referenced asset must exist unassigned; created assets follow BR-AST-011 |
| Result summary ("N created · N failed") | S16 | BR-MET-038 (always shown) | computed over batch + error report | text/jsonb | computed-display | rendered after EVERY create |
| Bulk audit entry | — | BR-MET-048 (PO PU-14) | `audit_log` (`premises.bulk_created` / `units.bulk_created`: file, counts, actor) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a 184-row premises CSV with 3 duplicates, When Dana imports with skip, Then exactly 181 premises exist, the summary "181 created · 3 failed/skipped" shows with reasons (BR-MET-038), and one audit row records the batch.
- Given a 6×20 pattern with `{floor}`/`{seq}` tokens, When created, Then 120 units with correctly sequenced labels, linked meters and default plan exist under the chosen premise (BR-MET-031).
- Given asset columns, When rows carry an asset #, Then existing assets link; When rows carry serial+type, Then assets are created inline — one registry, no duplicates (BR-MET-039/BR-AST-028).
- Given any error row (unknown premise, duplicate label/meter, row cap, size), Then that row (or run) is blocked with a stated reason and never partially applied.

**7 · Finance Calculation** — N/A

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-039 | Bulk-unit numbering: pattern token grammar + series interaction | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-MET-031) — BOTH paths (pattern `{seq}`/`{floor}` AND CSV) confirmed (PO R7); import standard per BR-MET-038 |
