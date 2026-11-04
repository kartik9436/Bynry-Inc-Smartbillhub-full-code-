# EP-TEN-06 — Settings → Services & UoM

**Module:** tenancy · **Wave:** W0 · **Screens:** S8 (Settings → Services & UoM — A1 addendum 2026-08-07) · **Status:** draft

## Scope
**In:** the Services & UoM tab: one row per platform service type (Electric, Water, Gas, Sewer, Trash, Broadband) showing status On/Off, primary + alt UoM, rate-schedule count, account count, and row actions Enable/Disable · Edit UoM. Tenants control which services are ON and each service's units. **New service *types* are provider/backend-added — explicitly not user CRUD** (prototype copy + A1 addendum).
**Out:** the UoM reference list itself (managed in EP-TEN-07; this tab only *selects* from it), rate schedules (rating module), per-service tax config (rating), register-to-billed unit conversion math (OQ-004, rating).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S8 · Services & UoM | — (6 fixed rows) | — | fixed service order (E · W · S · G · T · B, per prototype) | — | Service · Status · Primary UoM · Alt UoM · Rate schedules · Accounts · Action (fixed set, no chooser) | Enable / Disable / Edit UoM (state-dependent per IS-6) | — | — |

## Stories

---
```yaml
id: US-TEN-007
epic: EP-TEN-06
module: tenancy
screens: [S8]
wave: 0
status: draft
blocked_by: []
depends_on: [US-TEN-001]
journeys: []
rules: [BR-TEN-016, BR-TEN-025, BR-TEN-026]
golden_tests: []
finance_calc: none
```
### US-TEN-007 — Enable / disable services per tenant

**1 · Details** — As a System Admin, I want to switch the six platform services on or off for my utility, so that pickers, Plans & Rates, and billing only offer what we actually bill. Entry: Settings → Services & UoM. Row action Enable (Off rows) / Disable (On rows) → confirm modal → toast → audit (IS-6). Off rows render dimmed with zero counts.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-025 | Service **types** are the closed platform `service_type` enum; new types ship as provider migrations; tenants can only toggle availability — no add/rename/delete | CONFIRMED — prototype copy ("New service types are added by your platform provider") + A1 addendum + B2 ENUM |
| BR-TEN-026 | Enable creates/reactivates the `tenant_services` row (soft state, history kept). Disable is **guarded**: blocked with an explanatory modal while active service agreements or rate schedules reference the service (counts shown); a service with zero usage disables freely. Disabled services vanish from all "new X" pickers but historical data keeps rendering | PROPOSED — derived from IS-1 deactivate-first + the 🔒 audit-lock principle applied at service level; prototype shows Disable on used rows but designs no error states (A10) |
| BR-TEN-016 | Enable/disable writes `audit_log` (`settings.service.enabled/disabled`) | PROPOSED — see EP-TEN-03 |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Enable Gas for Brazos Bend (currently Off, 0 accounts) | Confirm modal → row turns On (**ccf / therm** defaults from seed) → Gas appears in Plans & Rates service pickers → toast + audit row |
| TC-2 | Disable Gas again while it still has 0 rate schedules / 0 accounts | Allowed; row Off and dimmed; Gas gone from pickers; history (row) retained, not deleted |
| TC-3 (neg) | Attempt Disable on Electric (3 rate schedules, 612 accounts) | Blocked modal: "Electric has 3 rate schedules and 612 active accounts — end or reassign them first"; no state change; no audit "disabled" row |
| TC-4 (neg) | Billing Clerk opens the tab | Read-only: actions disabled-with-reason (IS-6; A4 — Settings is System Admin only); direct API call rejected server-side |
| TC-5 (isolation) | Brazos Bend disables Trash; Lone Star Ridge has Trash On | Lone Star Ridge unaffected; each tenant's tab reflects only its own `tenant_services` rows |

**4 · Test Data** — Brazos Bend (water + electric utility, Katy TX): Electric **On** (kWh / kW-demand, 3 schedules, 612 accounts) · Water **On** (kgal / ccf, 2 schedules, 568 accounts) · Sewer Off · Gas Off · Trash Off · Broadband Off. Actor: Dana Whitfield (System Admin); negative actor: Marcus Vega (Billing Clerk).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Service | S8 Services | prototype-extracted | tenant_services.service | service_type enum | reference-data | closed enum (BR-TEN-025) |
| Status On/Off | S8 Services | prototype-extracted | **PROPOSED-SCHEMA:** tenant_services.enabled boolean NOT NULL DEFAULT true + disabled_at timestamptz (B2 row today = presence only; soft toggle needed for history) | boolean | user-input | disable guard BR-TEN-026 |
| Rate schedules count | S8 Services | prototype-extracted | count of rating.tariffs by service (read via rating service fn) | int | computed-display | — |
| Accounts count | S8 Services | prototype-extracted | count of active service_agreements by service (read via customers service fn) | int | computed-display | — |
| Row action | S8 Services | prototype-extracted | — | — | user-input | state-dependent options (IS-6) |

**6 · Acceptance** — Given a System Admin on Services & UoM, When they enable an unused service, Then it becomes available across the app after confirm + toast + audit; When they try to disable a service with active rate schedules or accounts, Then the action is blocked with the counts named; and a disabled service disappears from new-record pickers while existing records still render it.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None (the disable guard is proposed, not open — finance impact is prevented, not decided, by blocking).

---
```yaml
id: US-TEN-008
epic: EP-TEN-06
module: tenancy
screens: [S8]
wave: 0
status: draft
blocked_by: []
depends_on: [US-TEN-002, US-TEN-007]
journeys: []
rules: [BR-TEN-016, BR-TEN-024, BR-TEN-027]
golden_tests: []
finance_calc: none
```
### US-TEN-008 — Edit UoM per service

**1 · Details** — As a System Admin, I want to set each service's primary and alternate unit of measure (e.g. Water: kgal primary, ccf alt), so that reads, rate schedules, and bills all speak one unit language per service. Entry: row action **Edit UoM** → modal with Primary UoM + Alt UoM selects (options from the tenant's UoM reference list, EP-TEN-07). Exit: Save (confirm + toast + audit) / Cancel.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-027 | UoM per service is **forward-only**: changing primary/alt UoM sets the default for NEW rate schedules, meters, and read imports; historical `meter_reads` and `invoice_lines` keep their explicitly stored `unit` and are never converted or restated. When existing rate schedules use the old unit, a warning names them; no automatic conversion is performed (register/billed conversion math is rating's OQ-004, ROUTED) | PROPOSED — derived from CLAUDE.md #3 (consumption always carries an explicit unit) + BR-TEN-020 no-restatement principle |
| BR-TEN-024 | Modal save is atomic + audited, with confirm per IS-6 | PROPOSED |
| BR-TEN-016 | Save writes `audit_log` (`settings.service_uom.updated`, before/after) | PROPOSED |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Edit Water UoM: primary kgal → ccf | Warning lists "2 rate schedules currently priced in kgal"; on confirm, new schedules/meters default to ccf; toast + audit row |
| TC-2 | After TC-1, open a July 2026 bill and the Reads list for July | July reads still show kgal (stored unit); July invoice lines unchanged; only new records pick up ccf |
| TC-3 | Edit Electric alt UoM to kW (demand) | Saved; demand-based rate creation in Plans & Rates offers kW |
| TC-4 (neg) | Deactivate `therm` in Reference data, then Edit UoM for Gas | `therm` absent from the Primary/Alt selects (deactivated entries excluded from new pickers, BR-TEN-029); existing assignments untouched |
| TC-5 (neg) | Submit with Primary UoM empty, or primary = alt | Inline validation: primary required, alt must differ; Save blocked. ⚠ **NARROWED 2026-09-02 BY `BR-TEN-1181` (`DEF-3232`) — THIS CASE BINDS `metered` AND `capacity` ONLY.** `BR-TEN-1180` (PO ruling 2026-09-02) created the first service that legitimately has NO unit: a `share` service is a percentage of another service's money and has no register, no count and no quantity of its own. Sewer was the case — a clerk who opened it and pressed Save met *primary required*, a refusal there was no way to satisfy. For a `share` service the primary unit is not required and a supplied unit is REFUSED (`settings.services.uom_not_for_share`); the S8 modal hides all four unit fields for it. This case is unchanged for every other service |
| TC-7 (neg, added 2026-09-02 · `BR-TEN-1181` · `DEF-3232`) | Open Sewer (billing basis `% of another service`) and press Save with nothing typed; then send a unit for it through the API | The save SUCCEEDS and the row keeps no unit — the four unit fields are not shown for a share service. The API call is refused by name, `settings.services.uom_not_for_share`. A metered or capacity service with no primary unit is still refused, `settings.services.primary_required` |
| TC-6 (isolation) | Brazos Bend sets Water = ccf; Lone Star Ridge keeps kgal | Each tenant's pickers and defaults reflect only their own `tenant_services` UoM values |

⚠ **TC-1's UNIT PAIR WAS *"therm / ccf"* UNTIL 2026-09-07 (`DEF-TEN-4505`).** `BR-TEN-1180` — the ruling closing `DEF-2409` and the PO-filed `DEF-3230` — swapped `SERVICE_DEFAULT_UOMS["gas"]` to `("ccf", "therm")` on **2026-09-02**, so the seeded gas register would agree with the billing workbook's signed *"Gas flat $1.15/ccf"*. **The TC's meaning is unchanged** — it names the PAIR and the pair is the same two ratified units — but the ORDER is which one is primary, and it stated the superseded choice for five days while `tests/test_us_ten_007_008_services_uom.py` asserted it and stayed RED. TC-4 below is unaffected: `therm` is still gas's unit, now as the alternate.

**4 · Test Data** — Brazos Bend UoM list (seeded): kWh, kW (demand), kgal, ccf, therm, month. Water currently kgal/ccf with 2 rate schedules ("Residential Water Tiered", "Commercial Water Flat") in kgal; Electric kWh / kW (demand). Actor: Dana Whitfield.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Primary UoM | S8 Edit-UoM modal | prototype-extracted (table cols) | **PROPOSED-SCHEMA:** tenant_services.primary_uom_id → uoms.id | uuid FK | user-input | required for a `metered` or `capacity` service, active UoM only; REFUSED for a `share` one, which has no unit (BR-TEN-1181, 2026-09-02) |
| Alt UoM | S8 Edit-UoM modal | prototype-extracted | **PROPOSED-SCHEMA:** tenant_services.alt_uom_id → uoms.id | uuid FK | user-input | optional; ≠ primary |
| Affected-schedules warning | S8 Edit-UoM modal | GAP — A10: no error/warning states designed | count via rating service fn | int | computed-display | — |
| Stored read/line units (context) | Reads / Bills | B2 meter_reads.unit, invoice_lines.unit | (unchanged by this story) | text | system-derived | never rewritten (BR-TEN-027) |

**6 · Acceptance** — Given a System Admin editing a service's UoM, When they save a change, Then new rate schedules, meters, and imports default to the new unit, every historical read and invoice line still displays its stored unit, a warning named any schedules still priced in the old unit, and the change is audit-logged.

**7 · Finance Calculation** — N/A (unit conversion factors and billed-unit math belong to rating — OQ-004, already ROUTED).

**8 · Open Questions** — None.
