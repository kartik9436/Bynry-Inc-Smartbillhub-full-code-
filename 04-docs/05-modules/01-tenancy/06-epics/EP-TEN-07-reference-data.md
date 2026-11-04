# EP-TEN-07 — Settings → Reference data (lookup framework + core lists)

**Module:** tenancy · **Wave:** W0 · **Screens:** S8 (Settings → Reference data — A1 addendum 2026-08-07, renamed from "Lookup tables" in r6) · **Status:** draft

## Scope
**In:** the Reference-data card grid → per-list management view (table + Add modal, per-row Edit / Deactivate / Delete, 🔒 audit-lock when Used-by > 0), for the lists: **Units of measure · Charge codes · Reason codes · Tax jurisdictions · Payment methods · Meter types · Account statuses** (+ Asset types & Asset statuses per A2 r4 addendum) and the **Document & message templates** entry card — which is *navigation only* into Settings → Templates (notifications module, wave 6).
**Content ownership:** tenancy owns the framework (grid, table, modal, lock semantics) and the UoM list; list *content and validation* belong to their owning modules — charge codes & tax jurisdictions → rating, reason codes → billing, payment methods → payments, meter/asset types & statuses → assets. All writes route through owning-module service functions (B1).
**Out:** template designers S91–S106 (wave 6), Routes & Cycles (own tab, metering), the money semantics of any charge/tax value (B4), Plans & Rates charge-code wizard S12 (rating epic — same table, different entry).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S8 · Reference data (card grid) | — | — | fixed card order per A1 addendum list | — | per card: list name · sample values · entry count (no chooser) | open list | — | — |
| S8 · Reference data → list management | Code, Name | — (search only in prototype) | Code A→Z (proposed; stable secondary by id per IS-2) | Code · Name · Used by | Code · Name · list-specific detail col · Used by · Status · Actions (fixed) | Edit / Deactivate / Reactivate / Delete (🔒 blocked when Used by > 0) | — | — (not shown in design) |

## Stories

---
```yaml
id: US-TEN-009
epic: EP-TEN-07
module: tenancy
screens: [S8, S75, S76, S77, S78, S79, S80]
wave: 0
status: draft
blocked_by: []
depends_on: [US-TEN-002]
journeys: []
rules: [BR-TEN-029, BR-TEN-033]
golden_tests: []
finance_calc: none
```
### US-TEN-009 — Reference-data card grid and navigation

**1 · Details** — As a System Admin, I want one place listing every configurable vocabulary — each card showing the list name, sample values, and a live entry count — so that I can see and reach all reference data at a glance. Entry: Settings → Reference data. Card click → that list's management view (US-TEN-010); the **Document & message templates** card navigates to Settings → Templates instead. "← Reference data" returns to the grid.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-033 | The Document & message templates card is **navigation only** — template content, versioning, and designers belong to the notifications module (Settings → Templates, wave 6); tenancy stores nothing for it | CONFIRMED — A1 r8 addendum ("Numbering keeps number formats; its document-template list now points to Templates") + prototype card onClick → Templates tab |
| BR-TEN-029 | Card entry counts (like Used-by values) are computed live from the underlying tables at render time, never cached — one facet of the deactivation/liveness rule stated canonically in US-TEN-011; the grid intro copy states the lock rule ("Entries already used by bills are lock-protected…") | PROPOSED — prototype-extracted card copy + IS-1 |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Open Reference data for seeded Brazos Bend | Cards: Units of measure 6 · Charge codes 6 · Reason codes 5 · Tax jurisdictions 2 · Payment methods 6 · Meter types 5 · Account statuses 5 · Asset types 10 · Asset statuses 5 · Document & message templates → each with sample values line |
| TC-2 | Click Charge codes card, then "← Reference data" | Lands in the Charge codes management view; back-link returns to the grid with state intact |
| TC-3 | Click Document & message templates card | Navigates to Settings → Templates tab (no list management view opens); no tenancy write path exists |
| TC-4 | Add a UoM entry (US-TEN-010), return to grid | Units of measure card count reads 7 |
| TC-5 (neg) | Billing Clerk opens Settings → Reference data | Per A4, Settings is System Admin-only: view denied (permission-denied state per A18/IS-7) |
| TC-6 (isolation) | Lone Star Ridge grid after Brazos Bend adds entries | Lone Star Ridge counts unchanged — counts are per-tenant |

**4 · Test Data** — Brazos Bend seeded counts as TC-1. Lone Star Ridge: seeded with toggle OFF → all cards 0 with A18 empty state.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Card name + sample values | S8 grid | prototype-extracted | static per-list config | text | reference-data | — |
| Entry count | S8 grid | prototype-extracted (`.v` count) | COUNT over the list's table (charges / taxes+tax_jurisdictions / **PROPOSED-SCHEMA** uoms, reason_codes, asset_types… — see US-TEN-010) | int | computed-display | — |

**6 · Acceptance** — Given a System Admin on the Reference data tab, When the grid renders, Then every list card shows its live per-tenant count, clicking a card opens that list's management view (templates card excepted — it navigates to Templates), and non-admin roles cannot reach the tab.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
```yaml
id: US-TEN-010
epic: EP-TEN-07
module: tenancy
screens: [S8, S75, S76, S77, S78, S79, S80]
wave: 0
status: draft
blocked_by: []
depends_on: [US-TEN-002, US-TEN-009]
journeys: []
rules: [BR-TEN-016, BR-TEN-028, BR-TEN-030, BR-TEN-031, BR-TEN-032]
golden_tests: []
finance_calc: none
```
### US-TEN-010 — Per-list management: view, search, add, edit

**1 · Details** — As a System Admin, I want each lookup list managed in a consistent table (Code · Name · detail column · Used by · Status · Actions) with search and an Add-entry modal, so that every dropdown in the app is under my control without engineering help. Entry: card click (US-TEN-009). Add/Edit modal fields vary per list (e.g. charge codes: code, name, amount/percent/min, GL account; reason codes: code, name, default GL; UoM: code, name). Confirmation toast on save (A1 addendum).

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-030 | Codes are unique per list per tenant, case-insensitive; a code becomes **immutable once Used by > 0** (name and detail fields stay editable — renaming display text never rewrites history because documents stamp values at issue, BR-TEN-017) | PROPOSED — derived from B2 UNIQUE (tenant_id, code) patterns + immutability principle |
| BR-TEN-031 | Framework vs content ownership: tenancy renders the UX; create/update calls route to the owning module's service function (charge codes, tax jurisdictions → rating; reason codes → billing; payment methods → payments; meter/asset types & statuses → assets; UoM → tenancy). Validation rules (e.g. charge amount NUMERIC(18,6) ≥ 0) are owned and enforced by the owning module | PROPOSED — B1 boundary rule applied to the shared Settings surface |
| BR-TEN-028 | Lists backed by **closed B2 enums** (payment methods → `payment_method_t`, account statuses → `account_status`, meter types → `meter_source`, asset statuses → r4 status enum): whether tenants may ADD entries, or only rename/deactivate a curated platform set | OPEN — OQ-031; Add is buildable now only for the free-vocabulary lists (UoM, charge codes, reason codes) |
| BR-TEN-032 | Tax jurisdictions: B2 models `tax_jurisdictions` platform-global (no tenant_id, RLS-exempt) while S8 offers tenant Add/Edit | OPEN — OQ-032 (carries B2 §6 O-12 / A17 #12 into the registry) |
| BR-TEN-016 | Every add/edit writes `audit_log` with before/after | PROPOSED |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Add charge code `RECON` · "Reconnect fee" · $45.00 · GL 4910 | Modal validates via rating service fn; row appears Active, Used by 0; toast; audit row; card count +1 |
| TC-2 | Search "late" in Charge codes | Server-side, debounced 300 ms, min 2 chars (IS-3); matches LATE by code and "Late payment fee" by name |
| TC-3 | Edit reason code `LEAK` name → "Leak adjustment credit" while Used by = 12 | Name saves; code field read-only with lock explanation (BR-TEN-030); prior adjustments unchanged |
| TC-4 (neg) | Add UoM with code `kgal` (already exists, entered as `KGAL`) | Rejected: case-insensitive duplicate; inline error names the existing entry |
| TC-5 (neg) | Add charge code with amount `-30` or blank code | Owning-module validation rejects; modal shows field errors; nothing written |
| TC-6 (neg/blocked) | Attempt Add on Account statuses / Payment methods / Meter types | Behavior stubbed pending OQ-031 — build renders Add disabled-with-reason on these lists; no guessed implementation |
| TC-7 (isolation) | Brazos Bend adds `RECON`; Lone Star Ridge opens Charge codes | Lone Star Ridge does not see `RECON`; its own Add of `RECON` succeeds independently |

**4 · Test Data** — Brazos Bend charge codes after seed: LATE (1.5% · $5 min), CONN $45, DISC $45, NSF $30, DEPO-R, TAMPER; add `RECON` $45 → 7 entries. Reason codes: BILLERR, METERR, LEAK (Used by 12), GOODWILL, DISPUTE. UoM: kWh, kW, kgal, ccf, therm, month. Actors: Dana Whitfield (System Admin), Marcus Vega (Billing Clerk — denied).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Code / Name (all lists) | S8 list mgmt | prototype-extracted (table head) | charges.code/name · taxes.name · **PROPOSED-SCHEMA:** uoms.code/name, reason_codes.code/name, asset_types.code/name | text | user-input | BR-TEN-030 |
| Detail column (per list) | S8 list mgmt | prototype-extracted (`lookupCol3`) | e.g. charges.amount/percent/min_amount · reason_codes.default_gl_account_id · taxes.rate | varies; money NUMERIC(18,6) | user-input | owning module (BR-TEN-031) |
| Used by | S8 list mgmt | prototype-extracted | computed — see US-TEN-011 | int | computed-display | — |
| Status | S8 list mgmt | prototype-extracted (Active/Inactive pills) | **PROPOSED-SCHEMA:** `active boolean NOT NULL DEFAULT true` on each lookup table (charges/taxes rows today only have deleted_at — deactivation ≠ deletion) | boolean | user-input | — |
| Charge GL account | S8 Add modal | A2 §S22 GL list · B2 charges.gl_account_id | charges.gl_account_id → ledger_accounts | uuid FK | user-input | must exist, tenant-scoped |
| Payment methods / Account statuses / Meter types entries | S8 list mgmt | prototype-extracted cards | **GAP → OQ-031** — B2 closed enums vs tenant-editable lists | — | — | blocked |
| Tax jurisdiction entries | S8 list mgmt | prototype-extracted card · B2 tax_jurisdictions | **GAP → OQ-032** — platform-global vs tenant-scoped | — | — | blocked |

**6 · Acceptance** — Given a System Admin inside a free-vocabulary list, When they add or edit an entry, Then owning-module validation runs, the row appears with correct status and Used-by, search behaves per IS-3, duplicates are rejected case-insensitively, codes freeze once used, and enum-backed lists expose no Add until OQ-031/OQ-032 are answered.

**7 · Finance Calculation** — N/A (charge/tax *values* are data entry here; their math is B4/rating).

**8 · Open Questions**
| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-031 | Reference lists backed by closed B2 enums (payment methods `payment_method_t`, account statuses `account_status`, meter types `meter_source`, asset statuses): are they tenant-extensible (→ convert to tenant-scoped lookup tables) or platform-curated with per-tenant activation only? S8 shows Add/Edit on all cards; B2 says ENUM | Add/Edit on those four lists (US-TEN-010/011); B2 schema shape | Product Owner (chat session) | OPEN |
| OQ-032 | Tax jurisdictions: platform-global reference (B2, RLS-exempt, carries O-12/A17 #12) or tenant-entered list (S8 card with Add)? If global, does the tenant manage a scoped *linkage* (jurisdictions they remit to) instead? | Tax-jurisdictions list management; rating's taxes.jurisdiction_id linkage | Product Owner (chat session) | OPEN |

---
```yaml
id: US-TEN-011
epic: EP-TEN-07
module: tenancy
screens: [S8, S75, S76, S77, S78, S79, S80]
wave: 0
status: draft
blocked_by: []
depends_on: [US-TEN-010]
journeys: []
rules: [BR-TEN-016, BR-TEN-029, BR-TEN-034]
golden_tests: []
finance_calc: none
```
### US-TEN-011 — Deactivate, delete, and the 🔒 audit-lock

**1 · Details** — As a System Admin, I want to retire lookup entries safely — deactivate anything, delete only what nothing references — so that historical bills and records never point at vanished vocabulary. Entry: row actions in any list management view. Delete on a used row renders as `🔒 Delete` (disabled, tooltip "Locked — referenced by bills; deactivate instead"); Deactivate always available; unused rows offer a real Delete with confirm.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-034 | Audit-lock: `Used by > 0` → hard delete **blocked** (server-enforced, not just UI), deactivate allowed; `Used by = 0` → hard delete allowed after confirm modal. Financial records never lose their referenced rows | CONFIRMED — IS-1 delete-deactivate convention + A1 addendum 🔒 pattern + prototype tooltip copy |
| BR-TEN-029 | Deactivated entries: excluded from pickers for NEW records, keep rendering on existing records, reactivation allowed at any time. `Used by` is computed **live** from the owning module's references at render/action time (per-list definition: charge codes → invoice_lines.charge_id + plan links; reason codes → adjustments.reason_code; UoM → meters.unit + tenant_services; tax jurisdictions → taxes.jurisdiction_id; asset types → assets), never a cached counter | PROPOSED — derived from IS-1 + B1 (counts read via owning-module service fns) |
| BR-TEN-016 | Deactivate/reactivate/delete each write `audit_log` | PROPOSED |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Deactivate charge code `TAMPER` (Used by 0) | Status → Inactive; gone from S12/S22 pickers; July bills referencing nothing unaffected; toast + audit |
| TC-2 | Delete `DEPO-R` (Used by 0) after confirm | Row removed; card count −1; audit row records the deleted values |
| TC-3 | Deactivate `LATE` (Used by 1,240) | Allowed; no NEW late-fee lines can select it; the 1,240 historical invoice lines still render "LATE · Late payment fee" |
| TC-4 (neg) | Attempt Delete on `LATE` via UI and via direct API call | UI shows 🔒 disabled with tooltip; API returns 409 with the used-by count — server-enforced (BR-TEN-034) |
| TC-5 (neg) | Two admins race: one deletes `RECON` while another attaches it to a plan | Whichever commits second loses: delete fails with fresh Used-by, or attach fails on missing row — no orphan reference survives |
| TC-6 (isolation) | Brazos Bend deactivates `LATE`; Lone Star Ridge's `LATE` | Lone Star Ridge's entry stays Active — lock state and usage counts are per-tenant |

**4 · Test Data** — Brazos Bend usage: LATE Used by 1,240 (invoice lines) · CONN 18 · DISC 6 · NSF 11 · DEPO-R 0 · TAMPER 0 · RECON 1 (plan link). Reason code LEAK Used by 12 (adjustments). Actors: Dana Whitfield + second admin "Priya Natarajan" for TC-5.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Used by | S8 list mgmt | prototype-extracted | live COUNT via owning-module service fn (per-list definition in BR-TEN-029) | int | computed-display | recomputed at action time |
| Status Active/Inactive | S8 list mgmt | prototype-extracted | **PROPOSED-SCHEMA:** `active` flag per lookup table (see US-TEN-010) | boolean | user-input | — |
| Delete (hard) | S8 list mgmt | prototype-extracted 🔒 pattern | row DELETE (only when unused) | — | user-input | server 409 when Used by > 0 |
| Lock tooltip | S8 list mgmt | prototype-extracted ("Locked — referenced by bills; deactivate instead") | — | text | computed-display | — |

**6 · Acceptance** — Given lookup entries with and without references, When an admin deactivates, deletes, or attempts a locked delete, Then deactivation always succeeds and only hides the entry from new-record pickers, hard delete succeeds solely at Used-by 0 (verified server-side at commit time), locked deletes fail identically via UI and API, and every outcome is audit-logged.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None (enum-list and jurisdiction questions live on US-TEN-010).

---

## SCOPE ADDENDUM (2026-08-08) — post-authoring PO decisions appended

The prototype's 8 cards + asset lookups above are the authored baseline. The following PO-ruled additions EXTEND this epic's card grid; stories for them are allocated US-TEN-013..017 (authored with their build waves):

| New card / extension | Screen | Ruling | Wave |
|---|---|---|---|
| **Holiday calendar** (TOU Option B: holidays bill off-peak) | S63 | BR-TEN-039, BR-RAT-021 | W1 |
| **Read validation & estimation rules** (thresholds + estimation params, seeded defaults, tenant-editable) | S64 | BR-TEN-039, PO R6 config-over-constant | W2 (needed before W3 billing) |
| **Account types & sub-types** (4 fixed categories + tenant sub-type CRUD) | S65 | BR-TEN-039, D5 | W2 |
| **Billing defaults** (late-fee min/% · grace days/mode · allocation order — tenant fallbacks) | S66 | BR-TEN-039, PO R6 | W2 |
| **Contracts group** inside Document & message templates (4 types × category variants × effective-dated versions) | S67 | BR-NOT-001..004 | W6 |
| **Premises types** list (Apartment complex, Commercial building, Single-family, Mixed-use, Mobile-home park; extensible) | card grid | BR-MET-034 (PU-1) | W1 |
| **Asset lifecycle stages** list (5 seeded stages + tenant stages, mapped to behavior classes) | card grid | BR-AST-031 | W1 |
| Asset-types list gains **default test-interval** column + seeds **Container/Cart, Modem/CPE** device types | existing card | BR-AST-027/042 | W1 |
| Payment-methods seeds **include `wire`** — the prototype card lists it ("ACH, card, check, cash, lockbox, wire"); the B2 enum had only 5. Caught in PO screenshot review; list is seeded+extensible per BR-TEN-036 so this is a seed addition | existing card | BR-TEN-036 + prototype S8 | W0 |
| Services & UoM tab (EP-TEN-06) gains **billed_uom + conversion factor** per service (UoM gate) | EP-TEN-06 scope note | B2 r6.4, BR-RAT-038 | W1 |

> **Scope addendum — PO settings audit CONFIRMED 2026-08-08 (BR-TEN-041).** Three NEW cards: **S69 Budget billing rules** (BR-BIL-017 params + OQ-068 override bound) · **S70 Collections & notices rules** (BR-PAY-016/017 cadences, 2-miss void, NSF threshold BR-PAY-013, returned-mail suppression BR-PAY-018) · **S71 Finance controls** (bank match ±3d BR-PAY-019, write-off $5/0–50 OQ-070, correction-approval mode OQ-072, back-bill cap 12mo + theft exempt OQ-071, overcharge guardrail 200% BR-BIL-029). Eight UPGRADES to existing cards: payment-methods seeds += **money order** (wire already scoped above, BR-PAY-026) · reason-code seeds += correction / penalty-theft / assessed-read / write-off / reconcile-difference families (BR-BIL-014/019, BR-PAY-020) · tax-jurisdictions += per-authority **remittance basis** field (BR-LED-002) · templates card += **category assignment** (BR-BIL-025) · GL mapping += **export codes** + write-off/clearing designations (BR-LED-004/014, BR-BIL-010/013) · account-statuses card displays **behavior_class** (BR-CUS-055) · Numbering += PMT-/DEP-/RCT-/EXP- series (BR-PAY-025, BR-LED-004) · Settings→Notifications tab = delivery/dispatch home (batch size 500, channel activation, provider status — BR-NOT-005). S66 keeps its current scope (late fee, grace, allocation, deposit interest) — no junk drawer.

> **Scope addendum — CR-004 (2026-08-16): the six r10 SET-04 reference lists, S75–S80.**
> `areas` (S75) · `service_size_classes` (S76 — `meter_size_classes` until
> BR-TEN-170 renamed it 2026-08-27) · `occupancy_statuses` (S77) ·
> `device_types` (S78) · `certification_types` (S79) · `import_mappings` (S80).
> A1's S75–S80 addendum rules the ownership verbatim: *"**No new stories, and that
> is deliberate.** All six are ordinary lists on the ONE reference-data surface
> (S8), so they inherit **US-TEN-009** (card grid), **US-TEN-010**
> (view/search/add/edit) and **US-TEN-011** (delete/deactivate) unchanged"*. The
> three stories' `screens:` frontmatter now says so, which is the machine-readable
> half A1's prose could not carry — **DEF-776**: A1 gained the six rows on
> 2026-08-19 (commit `cf0423f3`) and no story claim or register line followed, so
> G25 read six inventory screens as owned by nobody and failed for six days.
> **The claim is true, not a silencer:** the six lists are built and served
> (`07-frontend/src/features/tenancy/referenceDataConfig.ts`,
> `apps.tenancy.models.{Area,MeterSizeClass,OccupancyStatus,DeviceType,CertificationType,ImportMapping}`)
> and CRUD-proven end to end by `07-frontend/e2e/CR-004-reference-crud.spec.ts`,
> whose own trace header already named these three stories against S75–S80.
> Content ownership per BR-TEN-031 stays with the owning modules (metering for
> S75–S79's content, ledger for S80); this epic owns the framework only.
