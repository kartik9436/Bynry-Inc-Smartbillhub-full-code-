# EP-TEN-09 — Settings → Custom fields (tenant-defined field registry)

**Module:** tenancy · **Wave:** W2 (release **R2**, B12 r7) · **Screens:** S8 (Settings → Reference data — new card + management view) · **Status:** draft

## Scope

**In:** a tenant System Admin defines their own fields — label, data type, options, required, and **placement** (which screens show it, and whether for input or for view) — and those fields then appear on the property and commercial entity screens with **no code change and no deploy**. This epic owns the *definitions*: the `custom_field` table, its S8 management UI, the cap, the lifecycle, and the registry endpoint every screen reads.

**Entities covered** (PO ruling 2026-08-10, "all property and commercial entities"):

| Group | Tables |
|---|---|
| Property | `premises` · `units` · `service_points` · `assets` |
| Commercial | `accounts` · `contacts` · `addresses` · `service_agreements` |

**Out, and each for a stated reason:**
- **The rendering component** — EP-SHL-07. Definitions here, pixels there.
- **The invoice snapshot** — US-BIL-028. A bill is immutable, so it stamps values rather than joining them. **WHERE THEY PRINT WAS RULED ON 2026-08-12 (PO, OQ-125 + OQ-118 → BR-TEN-082):** _"in remark or note section on bill - applicationd eicde the format for time being"_. **One section carries them all — the eight entities do not each get a designed place on the bill** — and the FORMAT is the application's call **for the time being**, a deliberate temporary grant, not a permanent rule. The four literals chosen under it (identifier `10432` not `10,432` · multiplier `1.5` · date `2026-03-04` ISO-8601, never `03/04/2026` · multi-select `Locked gate, Dog on site`) are each pinned by a test so that withdrawing the grant goes RED; ⚠ **a boolean prints `Yes`/`No` in ENGLISH on a bill that may be Spanish, and that one is flagged to go back to the PO.** The grant covers formatting and **never invention** — a number holding `"abc"` is still refused per bill.
- **Template variables** — US-NOT-016.
- **`tariffs` · `rate_tiers` · `charges` · `taxes`** — the calculation boundary. A tenant-defined field inside the rating tables invites the one thing BR-TEN-048 forbids.
- **`invoices` · `invoice_lines` · `payments` · `journal_*`** — append-only (DB-4). They receive a snapshot; they never host an editable custom field.
- **`meter_reads`** — monthly-partitioned, highest-volume table in the product, auto-detached to cold storage at 2 years (DB-7). A jsonb column there is an archival and performance cost with no product benefit.

**Why S8 and not a new screen** (PO ruling 2026-08-10, "follow same UI structure of Reference data"): a custom field is a configurable vocabulary, exactly like a lookup list. It becomes one more card in the S8 grid with the same card → table → Add-modal shape. No new screen ID is minted, and no A1 renumbering is proposed.

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S8 · Custom fields card | — | — | fixed card order (appended after Account statuses) | — | list name · sample labels · entry count | open list | — | — |
| S8 · Custom fields → management | Label, Key | Entity, Status | Entity A→Z, then display order (stable secondary by id per IS-2) | Label · Key · Entity · Type · Used on | Label · Key · Entity · Type · Required · Placement count · Status · Actions | Edit · Placement · Deactivate / Reactivate | — | — |

## Stories

---
```yaml
id: US-TEN-014
epic: EP-TEN-09
module: tenancy
screens: [S8]
wave: 2
status: draft
blocked_by: []
depends_on: [US-TEN-009, US-TEN-010]
journeys: []
rules: [BR-TEN-046, BR-TEN-047]
golden_tests: []
finance_calc: none
```
### US-TEN-014 — Custom fields card and management view

**1 · Details** — As a System Admin, I want a Custom fields entry in Settings → Reference data listing every field my utility has defined, grouped by the entity it attaches to, so that I can see and manage our own vocabulary in the same place as the platform's. Entry: Settings → Reference data → Custom fields. The card shows a live count; the management view is the S8 table pattern (US-TEN-010) with Add, per-row Edit, Placement and Deactivate. "← Reference data" returns to the grid.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-046 | Custom fields are **tenant-defined data, not schema**: creating one writes a `custom_field` row and never runs DDL. No tenant can alter another tenant's field set, and no tenant's fields are visible to another — the table is tenant-scoped with RLS FORCE like every other tenant table (CLAUDE.md #1) | PROPOSED — derives from BR-TEN-036 (seeded + tenant-extensible vocabularies) extended from *rows* to *fields*, per PO ruling 2026-08-10 |
| BR-TEN-047 | The card and the management view live inside S8 and reuse the Reference-data framework (grid → table → FormModal), so custom fields inherit its audit-lock, deactivate and empty-state behaviour rather than defining new ones | CONFIRMED — PO ruling 2026-08-10 ("follow same UI structure of Reference data") |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Brazos Bend, no fields defined yet, opens Settings → Reference data | Custom fields card present, count 0; opening it shows the A18 empty state with a primary "Add custom field" action |
| TC-2 | Brazos Bend defines 3 account fields and 1 asset field, returns to the grid | Card count reads 4; management view groups them under Accounts (3) and Assets (1) |
| TC-3 | Search "feeder" in the management view | Matches on Label and Key; the Assets row for `feeder_number` returns |
| TC-4 | Filter Entity = Premises with no premises fields defined | Empty result state, not an error; the Add action stays available |
| TC-5 (neg) | Billing Clerk opens Settings → Reference data | Settings is System Admin-only per A4 — view denied with the A18/IS-7 permission state |
| TC-6 (isolation) | Lone Star Ridge opens Custom fields after Brazos Bend has defined 4 | Count 0 and the empty state. Brazos Bend's definitions are invisible, and no Lone Star Ridge screen gains a field |

**4 · Test Data** — Brazos Bend Utilities (`brazosbend`). Fields: `feeder_number` (Assets, text), `easement_ref` (Premises, text), `service_class` (Accounts, select — Residential / Commercial / Irrigation), `pole_tag` (Assets, text). Lone Star Ridge (`lonestarridge`) defines none.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Card entry count | S8 grid | prototype-extracted (Reference-data card shape) | COUNT over `custom_field` WHERE `is_active` | int | computed-display | — |
| Label | S8 management | GAP — new capability, PO 2026-08-10 | **PROPOSED-SCHEMA** `custom_field.label` | text | user-input | required, ≤60 chars, unique per (tenant, entity) |
| Key | S8 management | GAP | `custom_field.key` | text | user-input | required, `^[a-z][a-z0-9_]{1,39}$`, unique per (tenant, entity), **immutable after create** (BR-TEN-049) |
| Entity | S8 management | GAP | `custom_field.entity` | enum (8 values) | reference-data | must be one of the eight covered tables |
| Type | S8 management | GAP | `custom_field.data_type` | enum | reference-data | `text·number·date·boolean·select·multi_select` |
| Status | S8 management | GAP | `custom_field.is_active` | bool | system-derived | deactivate only, never delete (BR-TEN-050) |

**6 · Acceptance** — **Given** I am a System Admin for Brazos Bend with four custom fields defined, **when** I open Settings → Reference data, **then** a Custom fields card shows the count 4, and opening it lists the four grouped by entity with Edit, Placement and Deactivate on each row — **and** the same page for Lone Star Ridge shows none of them.

**7 · Finance Calculation** — N/A. Custom fields are display and capture only; BR-TEN-048 forbids them from every money path.

**8 · Open Questions** — None.

---
```yaml
id: US-TEN-015
epic: EP-TEN-09
module: tenancy
screens: [S8]
wave: 2
status: draft
blocked_by: []
depends_on: [US-TEN-014]
journeys: []
rules: [BR-TEN-048, BR-TEN-049, BR-TEN-051]
golden_tests: []
finance_calc: none
```
### US-TEN-015 — Define a custom field

**1 · Details** — As a System Admin, I want to add a field by naming it, picking its entity and data type, and marking it required or not, so that my staff can capture something the platform does not ship. Entry: S8 → Custom fields → Add custom field (FormModal per US-SHL-009). The modal derives the key from the label on first entry and then locks it. Save returns to the management table with the new row present.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-048 | **A custom field can never influence money.** It may be captured, displayed, searched, sorted and exported; it may never be read by the rating engine, set or adjust an invoice-line amount, affect tax determination, produce or alter a ledger posting, or drive payment allocation or dunning. Enforced mechanically by the G6 forbidden-pattern gate, not by review: `custom_data` is a merge-blocking FAIL anywhere under `apps/rating/`, and under `apps/billing/`, `apps/ledger/` and `apps/payments/` outside the single allowlisted snapshot module named in US-BIL-028 | CONFIRMED — PO ruling 2026-08-10 ("we may not able to use it for calculation"). This is the load-bearing constraint that lets the feature exist without reopening finance-signed B4/B5 |
| BR-TEN-049 | `key` is **immutable once created**; only `label` is editable. A pinned template version and a stamped invoice snapshot both reference the key forever (US-BIL-028, US-NOT-016), so a rename would silently break historical documents | PROPOSED — derives from DB-4 (append-only financial rows) + DB-9 (pinned template_id + version) |
| BR-TEN-051 | **Cap: 10 active fields per entity per tenant.** The 11th attempt is refused with a 422 naming the cap and the count, not a silent truncation. Deactivated fields do not count against it | CONFIRMED — PO ruling 2026-08-10 ("10 are okay") |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Add label "Feeder Number", entity Assets, type text | Row created; key auto-derived as `feeder_number` and shown read-only |
| TC-2 | Add a select field "Service Class" with options Residential / Commercial / Irrigation | Row created with three options in the given order; order is preserved on reload |
| TC-3 | Edit the label of `feeder_number` to "Feeder ID" | Label updates; key still reads `feeder_number`; the field is not recreated |
| TC-4 (neg) | Attempt to change the key of an existing field via the API | 422 with `br_ref: BR-TEN-049`; the stored key is unchanged |
| TC-5 (neg) | Define an 11th active Accounts field | 422 `BIZ-CAP` with `br_ref: BR-TEN-051`, params `{entity: "accounts", active: 10, cap: 10}`; nothing is written |
| TC-6 (neg) | Add a second Accounts field with key `service_class` | 422 duplicate-key; unique per (tenant, entity) holds |
| TC-7 (neg) | Define a field on entity `invoices` | 422 — not in the eight covered entities (epic Scope); the immutable and rating tables are not addressable |
| TC-8 | Definition create, update and deactivate | Each writes an `audit_log` row (CLAUDE.md #7): `custom_field.created` / `.updated` / `.deactivated` with before/after |
| TC-9 (isolation) | Brazos Bend holds 10 active Accounts fields; Lone Star Ridge adds one | Accepted — the cap is per tenant per entity, and Lone Star Ridge's count is 1 |

**4 · Test Data** — As US-TEN-014, plus a 10-field Accounts set on Brazos Bend for the cap tests: `service_class`, `feeder_zone`, `tax_district`, `co_op_member_no`, `deposit_waiver_ref`, `site_contact_role`, `access_code`, `hazard_note`, `ada_flag`, `legacy_account_no` — then an 11th attempt (`route_note`) which must be refused.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Label | S8 Add modal | GAP | `custom_field.label` | text | user-input | required, ≤60 chars |
| Key (derived, locked) | S8 Add modal | GAP | `custom_field.key` | text | system-derived then immutable | slug of label; `^[a-z][a-z0-9_]{1,39}$`; unique per (tenant, entity) |
| Entity | S8 Add modal | GAP | `custom_field.entity` | enum | reference-data | one of the eight; not rating, not append-only, not `meter_reads` |
| Data type | S8 Add modal | GAP | `custom_field.data_type` | enum | reference-data | six values per BR-TEN-046 |
| Options | S8 Add modal | GAP | `custom_field.options` jsonb | text[] | user-input | required and ≥2 when type is `select`/`multi_select`; ignored otherwise |
| Required | S8 Add modal | GAP | `custom_field.is_required` | bool | user-input | a required field blocks save on its **input** placements only |
| Help text | S8 Add modal | GAP | `custom_field.help_text` | text | user-input | optional, ≤200 chars |
| Display order | S8 management | GAP | `custom_field.display_order` | int | user-input | within (entity), stable secondary by id per IS-2 |

**6 · Acceptance** — **Given** Brazos Bend has 10 active Accounts fields, **when** I add an 11th, **then** I get a 422 naming the cap and the current count, nothing is written, and the audit trail records no create — **and** when I instead add a 1st Premises field it succeeds, because the cap is per entity.

**7 · Finance Calculation** — N/A, and enforced: see BR-TEN-048.

**8 · Open Questions** — None.

---
```yaml
id: US-TEN-016
epic: EP-TEN-09
module: tenancy
screens: [S8]
wave: 2
status: draft
blocked_by: []
depends_on: [US-TEN-015]
journeys: []
rules: [BR-TEN-052]
golden_tests: []
finance_calc: none
```
### US-TEN-016 — Placement: choose where a field appears, and in which mode

**1 · Details** — As a System Admin, I want to choose which screens show each field and whether it is captured or only displayed there, so that a field my meter techs fill in appears on the asset form but read-only on the account page. Entry: S8 → Custom fields → row action "Placement". The editor lists the **eligible slots** for that field's entity — a fixed platform allow-list — and offers each as *Input*, *View* or *Not shown*. This is the no-code surface: after save the field appears on those screens with no deploy.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-052 | Placement is **bounded by the platform, chosen by the tenant.** The product ships a fixed allow-list of eligible screen slots per entity, expressed in A1 screen IDs; a tenant selects among them and can never place a field on a screen we have not cleared. Modes are `input`, `view`, `not_shown`; `input` implies `view` on that screen | PROPOSED — derives from A1 as the canonical screen vocabulary (CLAUDE.md "Screen IDs") + the PO's no-code requirement, 2026-08-10 |

**Eligible slots shipped in R2** (all IDs verified against A1; no new screen is minted):

> ⚠ **SUPERSEDED 2026-10-02 (`CR-161-BRC10`, BR-TEN-052 amended).** The table below is the R2 allow-list as it was written. The live list is `apps/tenancy/custom_fields.SLOTS` (served by `GET /settings/custom-fields/slots`): the PO's Part 2 screens, each marked rendered or not, and Settings offers only the rendered ones. Three rows below were never rendered by any screen and are corrected there: `addresses` on S16 (S16 is Add Premises — a service address lives on the premise, BR-MET-1161; mailing addresses are typed on New Account / Account detail), `units` viewed on S15 (the design shows units on the Premise page → Units tab), and `assets` Input on S50 (the design's input is Edit asset). BR-TEN-049 is CONFIRMED (PO 2026-10-02) and BR-TEN-046's entity list is amended in the same commit.

| Entity | Input slots | View slots |
|---|---|---|
| `accounts` | S18 New Account wizard · S21 Account detail (edit modal) | S21 Account detail |
| `contacts` | S21 (Contacts tab) | S21 |
| `addresses` | S21 (Addresses) · S16 | S21 |
| `service_agreements` | S18 · S23 Change Plan wizard | S21 |
| `premises` | S16 Add Premises & Unit | S14 Premises · S15 Units |
| `units` | S16 | S15 Units |
| `service_points` | S16 | S15 |
| `assets` | S51 Add asset · S50 Asset detail | S50 Asset detail · S49 Assets list |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Place `feeder_number` as Input on S51 and View on S50 | S51 Add-asset shows an editable field; S50 Asset detail shows the value read-only |
| TC-2 | Place `service_class` as Input on S18 only | S18 captures it; S21 does not display it until a View placement is added |
| TC-3 | Set a placement to Not shown | The field disappears from that screen; **the stored values are untouched** and reappear if it is placed again |
| TC-4 (neg) | Post a placement naming S31 (Run Bills wizard) for an accounts field | 422 — S31 is not an eligible slot; the money screens are not addressable (BR-TEN-052 + BR-TEN-048) |
| TC-5 (neg) | Post a placement naming S50 for an `accounts` field | 422 — slot/entity mismatch |
| TC-6 | A required field placed only as View | Save on that screen is not blocked — "required" binds input placements only (US-TEN-015 BR) |
| TC-7 | Placement change | Writes `custom_field.placement_changed` to `audit_log` with before/after |
| TC-8 (isolation) | Brazos Bend places a field on S50; Lone Star Ridge opens S50 | Lone Star Ridge's S50 renders no custom fields |

**4 · Test Data** — `feeder_number`: `{S51: input, S50: view, S49: view}`. `service_class`: `{S18: input, S21: view}`. `easement_ref`: `{S16: input, S14: view}`.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Placement map | S8 Placement editor | GAP | `custom_field.placement` jsonb — `{"S51": "input", "S50": "view"}` | jsonb | user-input | keys must be eligible slots for the field's entity; values in `input·view·not_shown` |
| Eligible slot catalogue | S8 Placement editor | GAP | platform constant, not tenant data | — | reference-data | the table above; changing it is a code change and a spec amendment |

**6 · Acceptance** — **Given** `feeder_number` is placed Input on S51 and View on S50, **when** a meter tech adds an asset, **then** the field is on the form; **and when** anyone opens that asset's detail, **then** the value shows read-only — with no deployment between defining the field and seeing it.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
```yaml
id: US-TEN-017
epic: EP-TEN-09
module: tenancy
screens: [S8]
wave: 2
status: draft
blocked_by: []           # was [OQ-075]; CLOSED 2026-08-10. Cleared 2026-08-15 (DEF-104)
depends_on: [US-TEN-015, US-TEN-016]
journeys: []
rules: [BR-TEN-050, BR-TEN-053]
golden_tests: []
finance_calc: none
```
### US-TEN-017 — Lifecycle (deactivate only) and the registry every screen reads

**1 · Details** — As a System Admin, I want to retire a field without destroying what staff have already recorded, so that last year's data survives this year's process change. Deactivate hides the field everywhere; the values stay in the row. There is no delete. Every screen that renders custom fields reads one cached registry endpoint rather than querying definitions per field.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-050 | **Deactivate only — no delete, no API for it.** Deactivating hides the field from every placement and excludes it from new snapshots; stored values are retained and reappear verbatim on reactivation. Dropping a tenant-defined field would destroy data nobody can reconstruct, and the platform has no way to know what it was worth | CONFIRMED — PO ruling 2026-08-10 ("Deactivate only") |
| BR-TEN-053 | The registry (definitions + placement for a tenant) is read on nearly every screen and written rarely, so it is **cached, keyed by tenant**: `cf:v{version}:{tenant_id}:{entity}`, with the tenant's `version` bumped on any definition write so a new key supersedes the old one — no delete fan-out to get wrong. **Redis has no RLS**: a key missing its `tenant_id` is a silent cross-tenant leak with none of the database's guardrails in the way, so tenant identity is part of every key and an isolation test proves it. A cache outage degrades to a Postgres read and never fails the request | PROPOSED — derives from CLAUDE.md #1 + PO ruling 2026-08-10 ("Ensure you use Redis also") |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Deactivate `pole_tag` which holds values on 40 assets | Field vanishes from S50/S51; all 40 stored values remain in `assets.custom_data` |
| TC-2 | Reactivate it | Field returns on its placements with every value intact |
| TC-3 (neg) | `DELETE` the definition via the API | 405 / no route — no delete endpoint exists (BR-TEN-050) |
| TC-4 | Deactivate frees cap headroom | An entity at 10 active with one deactivated accepts a new field (US-TEN-015 BR-TEN-051) |
| TC-5 | Registry read after a definition write | Reflects the change on the next request — version bumped, new cache key |
| TC-6 | Redis unavailable | Registry still resolves from Postgres; screens render; a warning is logged and no request fails |
| TC-7 (isolation) | Warm the cache as Brazos Bend, then read as Lone Star Ridge | Lone Star Ridge gets its own (empty) registry. Asserted directly against the cache, because Redis will hand over any key it is asked for |
| TC-8 | Deactivate a field referenced by a published bill template | **RULED — implement it, do NOT stub it (amended 2026-08-15, DEF-104).** OQ-075 CLOSED 2026-08-10: **warn, do not block — and the field may carry a DEFAULT VALUE.** Deactivation proceeds and lists every affected published template BY NAME; new documents render the field's default rather than an empty variable; historical documents are untouched because values are snapshotted at issue (US-BIL-028). The default is a STRING like every other snapshot value and BR-TEN-048/DB-17 still applies — it can never enter a money path. The old wording here asked for `NotImplementedError("OQ-075")`, which any agent following it would now fail G8 on the spot |

**4 · Test Data** — Brazos Bend `pole_tag` with values on 40 of 120 assets. Lone Star Ridge: no definitions. Cache: a live Redis for TC-5..7; TC-6 runs with the client pointed at a closed port.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Status | S8 management | GAP | `custom_field.is_active` | bool | user-input | deactivate/reactivate only |
| Registry version | — | GAP | `tenant_settings.custom_field_version` | int | system-derived | monotonic; bumped in the same transaction as any definition write |
| Registry response | every placed screen | GAP | read model over `custom_field` | jsonb | computed-display | cache key must contain `tenant_id` (BR-TEN-053) |

**6 · Acceptance** — **Given** `pole_tag` holds values on 40 assets, **when** I deactivate it, **then** it disappears from every screen and all 40 values remain stored; **and when** I reactivate it, **then** every value returns unchanged. **And** no delete path exists at any layer.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**
| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-075 | Deactivating a field that a **published** bill or notice template references: warn (listing affected templates) or block? Historical documents are safe either way because values are snapshotted (US-BIL-028); new documents would render the variable empty | TC-8 of this story; the deactivate branch in the template-reference check | Product Owner | **CLOSED** — PO 2026-08-10: **warn, do not block — and the field may carry a DEFAULT VALUE.** Mirrored here 2026-08-15 (DEF-104): this cell still read `**OPEN**` five days after the ruling |
| OQ-125 / OQ-118 | Where does a custom field PRINT on a bill, and how does a non-string value become the string a bill prints? | The invoice snapshot's format rules (US-BIL-028) and the bill layout | Product Owner | **CLOSED 2026-08-12 — the REMARK / NOTE section, one section for all of them, and the application chooses the format _"for time being"_ → BR-TEN-082. The four chosen literals are HUMAN-REVIEW-PENDING; OQ-118's flat-key-space question for MULTI-ROW entities stays OPEN** |
