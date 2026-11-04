# EP-AST-03 — Asset lifecycle (repair · retire · reassign)
> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep.

**Module:** assets · **Wave:** W1 · **Screens:** S53 (Log repair/maintenance modal), S54 (Retire modal), S55 (Reassign modal) — IDs ratified, OQ-014 CLOSED; entry from S49 row actions and S50 header · **Status:** draft

## Scope
**In:** the three lifecycle modals: **Log repair / maintenance** (S53 — kind Repair/Inspection/Test, tech, detail, resulting status driving Needs repair → In repair → Active), **Retire** (S54 — reason, retire date, optional replaced-by; audit-locked retire-never-delete when referenced; terminal, recreate-with-linked-audit for mistakes per BR-AST-030), **Reassign** (S55 — move to unit or inventory, effective date, final-read capture; sub-meter move rules per BR-AST-037). Lifecycle per A5 v4 stages (Reference-data list w/ behavior classes, BR-AST-031): Inventory/Spare → Installed/Active → Needs repair → In repair → Active | Retired (terminal). **Single-vs-bulk action matrix per BR-AST-038:** bulk assign inventory→units via multi-select (BR-AST-036); unit→unit moves single or file-import only; repair transitions performable by the Billing Clerk.
**Out:** work orders, scheduling, parts, or any EAM depth beyond this repair/retire lifecycle (ADR-004 consequence — explicitly none) · the read validation applied to a captured final read (metering) · delete semantics (US-AST-003) · history-tab rendering (US-AST-006).
**Tables:** metering-owned B2 r4 `assets`, `asset_assignments`, `asset_maintenance`, `meter_reads` (final read) — writes via metering service functions only (B1).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| — | *(no list screens in this epic — three modals)* | | | | | | | |

## Stories

---
id: US-AST-007
epic: EP-AST-03
module: assets
screens: [S53, S49, S50]
wave: 1
status: draft
blocked_by: []
depends_on: [US-AST-001, US-AST-002]
journeys: []
rules: [BR-AST-018, BR-AST-020, BR-AST-038]
golden_tests: []
finance_calc: none
---
### US-AST-007 — Log repair / inspection / test with status transition

**1 · Details** — As a staff user, I want to log a repair, inspection, or test against an asset and set the resulting status in the same step, so that field work and the lifecycle state never drift apart. Repair transitions are performable by the Billing Clerk as well as the System Admin (BR-AST-038). Entry: row action **Log repair** (S49; "Log test" wording on backflow rows), header button or Maintenance-tab **+ Log repair** (S50). Fields per prototype: Type segment (Repair / Inspection / Test), Date, Assign tech, Detail, **Set status** (Needs repair / In repair / Active (fixed)). Exit: **Save ✓** → toast; maintenance row appears (US-AST-006); status pill updates everywhere; audit row written.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AST-018 | Maintenance entries are append-only with kind repair \| inspection \| test; a `test` entry updates `assets.last_test_date` (defined US-AST-006 — shared). | CONFIRMED — PO R4 Q20/B9 |
| BR-AST-020 | Lifecycle transitions are exactly A5 v4: `inventory →(assign)→ active` · `active →(flag)→ needs_repair →(start)→ in_repair →(fix)→ active` · `any →(retire)→ retired` (terminal). The S53 "Set status" choices are constrained to transitions legal **from the asset's current status** (plus no-change); illegal targets are rejected server-side regardless of UI. Stage labels come from the Reference-data lifecycle list; transition legality keys off each stage's behavior class (BR-AST-031). | CONFIRMED — A5 v4 addendum (2026-08-07 r4) |
| BR-AST-038 | The Billing Clerk may perform repair transitions (Active → Needs repair → In repair → Active); the full single-vs-bulk action matrix follows the PO Q13 table. | CONFIRMED — PO R4 Q13/Q14 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana logs Repair on M-4204 (needs_repair): "Register head replaced", tech Ray Delgado, set status **In repair** | Maintenance row created; status needs_repair → in_repair; toast; `audit_log` `asset.maintenance_logged` + `asset.status_changed` |
| TC-2 | Marcus Vega (Billing Clerk) completes: logs Repair on M-4204 (in_repair), set status **Active (fixed)** | Allowed — clerk repair transitions per BR-AST-038; status in_repair → active; asset leaves the Needs-repair filter; audit rows |
| TC-3 | Dana logs Inspection on M-4021 (active), set status **Needs repair** | Status active → needs_repair; row actions on S49 switch to the needs_repair set (BR-AST-006) |
| TC-4 | Dana logs **Test** on BF-3301 dated 2026-08-08, status unchanged | Maintenance row kind=test; `last_test_date` → 2026-08-08; "Test due" chip clears (BR-AST-007) |
| TC-5 *(negative)* | API call sets M-4021 (active) directly to **in_repair** | Rejected — active → in_repair is not a legal A5 v4 transition (must pass needs_repair) |
| TC-6 *(negative)* | Save with empty Detail and no kind selected | Inline validation errors; nothing written |
| TC-7 *(isolation)* | Erin (Lone Star Ridge) posts a maintenance entry against Brazos Bend's M-4204 id | Not-found under her tenant; no write, no status change |

**4 · Test Data** — M-4204 (needs_repair), M-4021 (active), BF-3301 (active, test due; last_test_date 2025-06-02, interval 12 mo). Techs: Ray Delgado. Dates around 2026-08-08. Actors: Dana Whitfield, Marcus Vega (Billing Clerk — repair transitions), Ray Delgado; Erin Walsh (isolation).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Type (Repair/Inspection/Test) | S53 | prototype-extracted | `asset_maintenance.kind` (B2 r4) | enum | user-input | required |
| Date | S53 | prototype-extracted (default today) | `asset_maintenance.date` | date | user-input | not future beyond today (proposed) |
| Assign tech | S53 | prototype-extracted (staff select + Unassigned) | **PROPOSED-SCHEMA** `asset_maintenance.tech_user_id` uuid NULL | uuid FK users | user-input | active tenant member |
| Detail | S53 | prototype-extracted (textarea) | `asset_maintenance.detail` | text | user-input | required; ≤1000 |
| Set status | S53 | prototype-extracted (3 options) | `assets.status` + `asset_maintenance.resulting_status` | lifecycle stage (BR-AST-031) | user-input | legal per BR-AST-020; clerk allowed for repair transitions (BR-AST-038) |
| Last test date update | — | derived (BR-AST-018) | **PROPOSED-SCHEMA** `assets.last_test_date` | date | system-derived | on kind = test only |
| Audit | — | CLAUDE.md #7 | `audit_log` (`asset.maintenance_logged`, `asset.status_changed`) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a needs_repair asset, When repair is logged with status In repair then Active, Then the asset walks needs_repair → in_repair → active with a maintenance row and audit row per step — by a System Admin OR a Billing Clerk (BR-AST-038).
- Given a test entry, When saved, Then the asset's last test date updates and any Test-due chip clears.
- Given an illegal transition, When attempted by any client, Then it is rejected server-side.

**7 · Finance Calculation** — N/A

**8 · Open Questions** — None.

---
id: US-AST-008
epic: EP-AST-03
module: assets
screens: [S54, S49, S50]
wave: 1
status: draft
blocked_by: []
depends_on: [US-AST-001, US-AST-002, US-AST-003]
journeys: []
rules: [BR-AST-002, BR-AST-013, BR-AST-020, BR-AST-021, BR-AST-030, BR-AST-032]
golden_tests: []
finance_calc: none
---
### US-AST-008 — Retire an asset (terminal; never hard-delete when referenced)

**1 · Details** — As a staff user, I want to retire an asset with a reason, retire date, and optional replacement pointer, so that dead equipment leaves active lists while every read and bill it ever produced stays intact. **Retire is System Admin only (BR-AST-032).** Entry: row action **Retire** (S49) or header button (S50). Modal per prototype: an audit-lock notice card ("Retiring, not deleting — referenced by reads/bills, so it can't be deleted. Retiring keeps history and removes it from active lists."), Reason select (End of life / Failed / unrepairable / Replaced / Removed from service), Retire date, Replaced by (optional asset #). Exit: **Retire asset ✓** → toast; status → retired (terminal — a mistaken retirement is corrected by recreating the asset with a linked audit note, BR-AST-030); asset drops out of Active/default views but remains under filter Retired and in history.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AST-002 | Assets referenced by issued bills are audit-locked: retire, never hard-delete. | CONFIRMED — A5 v4 / CLAUDE.md #4 (existing rule) |
| BR-AST-013 | Delete gate (defined US-AST-003 — shared): referenced assets can only be retired. | CONFIRMED — PO R4-A2 |
| BR-AST-020 | `any → retired` is legal from every non-retired status; retired is terminal — no transition leaves it. | CONFIRMED — A5 v4 addendum |
| BR-AST-030 | **Retire is terminal — no un-retire.** A mistaken retirement is corrected by creating the asset anew with a **linked audit note** (the new asset's audit trail references the retired one); the retired row never reactivates. | CONFIRMED — PO R4-A3 |
| BR-AST-021 | Retire requires reason + retire date; optional `replaced_by` must reference a same-tenant, non-retired asset. Retiring an assigned asset closes its current assignment at the retire date (to_date set); a final read, if needed, is captured beforehand via Reassign/read entry (the S54 modal has no read capture). Retire writes `audit_log`; reads, invoices, and history rows are untouched. | CONFIRMED — PO R4-A3/A4 context |
| BR-AST-032 | Retire (and delete) = System Admin only; Executive view-only. | CONFIRMED — PO R4 Q1 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana retires M-4204: reason Failed / unrepairable, date 2026-08-08, replaced by M-5100 | Status → retired; current assignment closed with to_date 2026-08-08; `replaced_by_asset_id` → M-5100; audit row `asset.retired` with reason |
| TC-2 | After TC-1, default list views | M-4204 absent from All-active flows, present under filter Retired; detail still opens read-only (View only per BR-AST-006); its reads remain queryable |
| TC-3 | Retire BAT-0904 (inventory, unassigned) reason Removed from service | Allowed (any → retired); no assignment to close |
| TC-4 *(negative)* | Any lifecycle action (repair, reassign, edit-status) attempted on retired M-4204 | Rejected — retired is terminal (BR-AST-020/030) |
| TC-5 *(negative)* | Retire with Replaced-by = "M-9999" (nonexistent) or a retired asset | Inline/server validation error; no write |
| TC-6 *(negative)* | Hard-delete attempted on retired M-4204 which has reads referenced by issued bills | Blocked with audit-lock message (BR-AST-002/013) — retire is the end state, never deletion |
| TC-7 *(isolation)* | Erin (Lone Star Ridge) sets Replaced-by to Brazos Bend's M-5100 asset id | Rejected — replacement must be a same-tenant asset; no cross-tenant reference possible |
| TC-8 | Mistaken retirement: Dana recreates the accidentally-retired BAT-0904 as a new asset | Creation succeeds; its `audit_log` create entry carries a linked note referencing retired BAT-0904 (BR-AST-030); no un-retire path exists anywhere |
| TC-9 *(negative)* | Marcus Vega (Billing Clerk) attempts Retire on M-4310 | Blocked — retire is System Admin only (BR-AST-032): disabled-with-reason in UI, direct API call rejected 403 |

**4 · Test Data** — M-4204 (needs_repair, assigned 500 Main · 200, has reads consumed by issued Brazos Bend bills), M-5100 (active, from US-AST-002), BAT-0904 (inventory; also the mistaken-retire fixture for TC-8). Reasons per prototype list. Actors: Dana Whitfield (System Admin); Marcus Vega (Billing Clerk — denied); Erin Walsh.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Audit-lock notice | S54 | prototype-extracted (card copy) | rendered when reference probe hits (same probe as BR-AST-013) | — | computed-display | — |
| Reason | S54 | prototype-extracted (4 options) | **PROPOSED-SCHEMA** `assets.retire_reason` text/enum (B2 r4 adds `retire_date` only) | enum end_of_life\|failed\|replaced\|removed | user-input | required |
| Retire date | S54 | prototype-extracted (default today) | `assets.retire_date` (B2 r4) | date | user-input | required; ≥ install_date |
| Replaced by | S54 | prototype-extracted (optional, placeholder M-5100) | **PROPOSED-SCHEMA** `assets.replaced_by_asset_id` uuid self-FK | uuid | user-input | same tenant; not retired; optional |
| Status → retired | — | A5 v4 + BR-AST-030 | `assets.status` (terminal stage — behavior class `terminal`, BR-AST-031) | lifecycle stage | system-derived | terminal; no un-retire |
| Recreate-with-linked-audit | — | BR-AST-030 | new `assets` row + `audit_log` note referencing the retired asset id | jsonb | system-derived | the correction path for mistaken retirement |
| Assignment closure | — | derived (BR-AST-021) | `asset_assignments.to_date` = retire date | date | system-derived | only the current row |
| Audit | — | CLAUDE.md #7 | `audit_log` (`asset.retired`) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a referenced asset, When retired by a System Admin, Then it disappears from active views, keeps every historical row, and can never be hard-deleted or transitioned again (BR-AST-030/032).
- Given a mistaken retirement, When corrected, Then a NEW asset is created with a linked audit note — never an un-retire (BR-AST-030).
- Given a replacement pointer, When saved, Then it resolves to a same-tenant living asset.
- Given an assigned asset, When retired, Then its assignment closes on the retire date.

**7 · Finance Calculation** — N/A

**8 · Open Questions** — None — mistaken-retire recovery CONFIRMED as recreate-with-linked-audit (BR-AST-030, PO R4-A3); no un-retire flow exists.

---
id: US-AST-009
epic: EP-AST-03
module: assets
screens: [S55, S49, S50]
wave: 1
status: draft
blocked_by: []
depends_on: [US-AST-001, US-AST-002]
journeys: []
rules: [BR-AST-017, BR-AST-020, BR-AST-022, BR-AST-036, BR-AST-037, BR-AST-038]
golden_tests: []
finance_calc: none
---
### US-AST-009 — Reassign an asset (unit ↔ inventory) with final-read capture

**1 · Details** — As a staff user, I want to move an asset to a different unit or back to inventory with an effective date, capturing the outgoing final read, so that consumption is attributed to the right unit up to the day the asset moved. Entry: row action **Reassign** (S49; labeled **Assign** on inventory rows) or S50 header/Assignment panel. Modal per prototype: "Currently: 1408 Elm Street · Unit A" context line, **Move to** (Inventory (unassign) / unit picker), **Effective date**, and checkbox **Record the final read before moving** (default on). Sub-meters: moving a parent prompts "move children too?" (default yes); an **independent sub-meter move is ALLOWED with a warning** (BR-AST-037). Bulk: inventory→unit assignment supports multi-select on S49 (BR-AST-036); unit→unit moves are single or file-import only (BR-AST-038). Exit: **Reassign ✓** → toast; assignment history gains a closed row + (if to a unit) a new current row; status updates per BR-AST-022.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AST-017 | Assignment history append-only, non-overlapping (defined US-AST-006 — shared): reassign closes the current row at effective date and opens the new one the same date. | CONFIRMED — PO R4 Q20/B8 |
| BR-AST-020 | Assign from inventory = the A5 v4 `inventory →(assign/install)→ active` transition. | CONFIRMED — A5 v4 addendum |
| BR-AST-022 | Reassign to a unit keeps/sets status `active`; **move to Inventory (unassign) returns status to `inventory`** — unassign-to-spare adopted as the reverse of assign. With "Record the final read" on (default), a final read is captured at the effective date and linked to the closing assignment row; a needs_repair/in_repair asset may be unassigned (pulled for shop repair) but assigning **to a unit** requires status active or inventory. | CONFIRMED — PO R4-A4 (final-read-on-move); screen IDs ratified (OQ-014 CLOSED) |
| BR-AST-037 | Sub-meter movement: moving a parent prompts "move children too?" (default yes); **independent sub-meter moves are ALLOWED with a warning message** — wrong tagging must be correctable. | CONFIRMED — PO R4 Q12 ("allow but display the message") |
| BR-AST-036 | Bulk assign inventory→units via multi-select; unit→unit moves single or file-import only. | CONFIRMED — PO R4 Q11 |
| BR-AST-038 | Single-vs-bulk action matrix per the PO Q13 table (no bulk unit→unit UI; file import covers mass moves). | CONFIRMED — PO R4 Q13 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana reassigns M-4022 from 1408 Elm · Unit A to 2200 Riverside · 224, effective 2026-08-08, final read on: 1,421.0 | Old row closed (to 2026-08-08) with final read linked; new current row opened; status stays active; audit rows `asset.final_read_captured` + `asset.reassigned` |
| TC-2 | Dana assigns M-5099 (inventory) to 77 Industrial Way, effective 2026-08-08 | inventory → active (BR-AST-020); first assignment row opened; S49 row leaves Unassigned filter |
| TC-3 | Dana moves M-4310 to Inventory (unassign), final read captured 88,204 | Assignment closed; status → inventory; asset appears under Unassigned; read stored against the closed period |
| TC-4 | Final-read checkbox off (e.g. comms endpoint COM-4420, non-measuring) | Reassign completes without read capture; measuring assets warn before skipping (proposed inline notice) |
| TC-5 *(negative)* | Effective date before the current assignment's from_date | Validation error — would create an overlap (BR-AST-017); no write |
| TC-6 *(negative)* | Final read value 99,999,999 exceeds M-4022's register digits | Read validation rejects (BR-AST-015 via metering); reassign not committed — capture and move are one transaction |
| TC-7 *(isolation)* | Erin (Lone Star Ridge) reassigns her asset; unit picker probed via API for Brazos Bend unit ids | Picker/API expose only Lone Star Ridge units; cross-tenant unit id rejected not-found |
| TC-8 | Dana reassigns SM-8801 (child of M-MASTER-12) alone to Vega Apts 105 | ALLOWED with warning "this sub-meter is moving independently of its parent M-MASTER-12" (BR-AST-037); move + warning acknowledgement audited |
| TC-9 | Dana reassigns parent M-MASTER-12 to another unit | Prompt "Move its sub-meters (SM-8801, SM-8802) too?" — default YES (BR-AST-037); accepting moves the children with their own assignment rows; declining moves the parent alone with the warning |
| TC-10 | Dana multi-selects M-5099 + BAT-0904 (inventory) on S49 and bulk-assigns to units | Allowed — bulk assign inventory→units via multi-select (BR-AST-036); per-asset assignment rows + audit; no bulk unit→unit UI exists — mass unit→unit moves go through file import only (BR-AST-038) |

**4 · Test Data** — M-4022 (active, 1408 Elm · Unit A, register 1,412.6 prior, final 1,421.0 kgal-register), M-5099 (inventory), M-4310 (active, 77 Industrial Way, register_digits 6), COM-4420 (comms, non-measuring), SM-8801/SM-8802 (sub-meters, parent M-MASTER-12, Vega Apts 102/104), BAT-0904 (inventory). Units: 2200 Riverside · 224, 77 Industrial Way, Vega Apts 105. Effective dates around 2026-08-08. Actors: Dana Whitfield; Erin Walsh.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Currently (context) | S55 | prototype-extracted | current `asset_assignments` row | — | computed-display | — |
| Move to | S55 | prototype-extracted (Inventory + units) | `asset_assignments.unit_id` (new row; NULL-path = no new row, status inventory) | uuid FK | user-input | same-tenant unit |
| Effective date | S55 | prototype-extracted (default today) | `asset_assignments.to_date` (old) / `.from_date` (new) | date | user-input | ≥ current from_date; no overlap |
| Record final read | S55 | prototype-extracted (checkbox, default on) | `meter_reads` new row (source manual) + **PROPOSED-SCHEMA** `asset_assignments.final_read_id` uuid FK | — | user-input | measuring assets; one transaction with the move |
| Final read value | GAP — checkbox only in prototype; reading input not designed (derived: revealed inline when checked; minimal field proposed, no OQ — value must be entered somewhere) | derived | `meter_reads.current_value` (+ consumption computed by metering) | numeric(18,6) asset unit | user-input | BR-AST-015 register bound |
| Move-children prompt (parent move) | S55 | BR-AST-037 (PO R4 Q12) | children's `asset_assignments` rows when accepted (default yes) | boolean | user-input | prompt only when the asset has sub-meters |
| Independent sub-meter warning | S55 | BR-AST-037 (PO R4 Q12 "allow but display the message") | warning acknowledgement recorded in `audit_log` | — | computed-display | move always allowed |
| Bulk assign (multi-select) | S49 | BR-AST-036 | per-asset `asset_assignments` rows | — | user-input | inventory→unit only; unit→unit bulk = file import (BR-AST-038) |
| Status change | — | A5 v4 + BR-AST-022 | `assets.status` | lifecycle stage | system-derived | legal transitions only |
| Audit | — | CLAUDE.md #7 | `audit_log` (`asset.reassigned`, `asset.final_read_captured`) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given an assigned measuring asset, When reassigned with final-read on, Then read capture + old-row closure + new-row opening commit atomically and history shows contiguous non-overlapping intervals.
- Given an inventory asset, When assigned to a unit, Then it becomes active with its first assignment row; multi-select bulk assign works for inventory→unit only (BR-AST-036/038).
- Given a unit-to-inventory move, When completed, Then the asset is unassigned, status inventory, and visible under the Unassigned filter.
- Given a sub-meter moved independently, When confirmed past the warning, Then the move succeeds and the acknowledgement is audited (BR-AST-037); Given a parent move, Then the move-children prompt defaults to yes.

**7 · Finance Calculation** — N/A

**8 · Open Questions** — None — BR-AST-022 CONFIRMED (PO R4-A4); screen-ID ratification complete (OQ-014 CLOSED — S49–S62 canonical).
