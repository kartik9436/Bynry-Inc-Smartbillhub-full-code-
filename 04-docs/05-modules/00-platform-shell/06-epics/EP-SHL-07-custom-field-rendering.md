# EP-SHL-07 — Custom-field rendering (the shared input/view component)

**Module:** platform-shell · **Wave:** W2 (release **R2**, B12 r7) · **Screens:** every eligible slot in the US-TEN-016 allow-list (S14 · S15 · S16 · S18 · S21 · S23 · S49 · S50 · S51) · **Status:** draft

## Scope

**In:** the one component that turns a definition into pixels. Screens do not know what fields exist — they drop `<CustomFields entity="…" screen="S…" mode="input|view" />` into a cleared slot once, and every field a tenant defines afterwards appears there with no further code. Also in: validation and error mapping, and the CSV export columns.

**Out:** the definitions and placement (EP-TEN-09) · the invoice snapshot (US-BIL-028) · template variables (US-NOT-016).

**Why this is a shell component and not eight copies:** B8 LAW 0 says an abstraction earns its place on the third use. This one has eight entities and nine screens before a line is written, and the alternative is the same rendering logic pasted into four modules — which is also a cross-module consistency problem the moment one copy diverges.

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S49 · Assets list (custom columns) | custom text fields join the existing search set | — | unchanged | custom columns not sortable in R2 (server sort over jsonb is deferred) | custom View-placed fields are *available*, never default (IS-5 chooser) | unchanged | unchanged | included per US-SHL-016 |
| S14/S15 · Premises & Units | as above | — | unchanged | as above | as above | unchanged | unchanged | included |

## Stories

---
```yaml
id: US-SHL-015
epic: EP-SHL-07
module: platform-shell
screens: [S16, S18, S21, S23, S51, S50]
wave: 2
status: draft
blocked_by: []
depends_on: [US-TEN-015, US-TEN-016, US-SHL-009]
journeys: []
rules: [BR-SHL-036, BR-SHL-037]
golden_tests: []
finance_calc: none
```
### US-SHL-015 — Capture custom fields on input screens

**1 · Details** — As a staff user, I want my utility's own fields on the forms I already use, so that I record what we actually track without leaving the product. On any screen with an `input` placement, the component renders one control per active field in display order, below the platform's own fields and under a heading that names the tenant, not the platform.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-SHL-036 | One control per data type: `text` → text input · `number` → numeric input (**captured as a value, never computed with** — BR-TEN-048) · `date` → the platform date control with IS-8 tenant formatting · `boolean` → checkbox · `select` → single-select · `multi_select` → multi-select. Required fields block save on input placements only | PROPOSED — derives from IS-8 + US-SHL-009 FormModal contract |
| BR-SHL-037 | Validation failures return through the **existing error envelope**, with `field_errors[]` keyed `custom_data.<key>` so FormModal highlights the offending control exactly as it does a platform field. No second error path is invented for custom fields | CONFIRMED — B12 §3 error-envelope contract (G1) + 11b §3 |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | S51 Add asset with `feeder_number` (text) and `pole_tag` (text) placed as input | Both render in display order under a "Brazos Bend fields" heading; values save to `assets.custom_data` |
| TC-2 | `service_class` select on S18 | Renders the three defined options in the defined order; the saved account carries the chosen value |
| TC-3 | Required `feeder_number` left blank on S51 | Save blocked; envelope carries `field_errors: [{field: "custom_data.feeder_number", …}]`; FormModal highlights that control |
| TC-4 | A tenant with no fields defined opens S51 | No heading, no empty section, no layout shift — the component renders nothing at all |
| TC-5 (neg) | Submit `custom_data` containing a key with no active definition | Rejected 422; unknown keys are never persisted, so a stale client cannot write shadow data |
| TC-6 (neg) | Submit a `select` value that is not one of the defined options | 422 with the field key; nothing written |
| TC-7 | Edit an existing asset's custom value | The owning entity's normal `audit_log` row carries the change in before/after — no separate audit path, because the value lives in the entity's own row |
| TC-8 (isolation) | Lone Star Ridge opens S51 while Brazos Bend has two asset fields | No custom fields render, and a crafted POST carrying Brazos Bend's keys is rejected |

**4 · Test Data** — Brazos Bend asset `MTR-000117`: `{"feeder_number": "F-12", "pole_tag": "P-8842"}`. Account `ACC-1042`: `{"service_class": "Commercial"}`. Lone Star Ridge asset `LSR-0007`: `{}`.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Custom value (any type) | every input slot | GAP — PO 2026-08-10 | `<entity>.custom_data` jsonb, key = `custom_field.key` | per `data_type` | user-input | type-checked against the definition; unknown keys rejected; options enforced |
| Section heading | every input slot | GAP | none — client-side | text | computed-display | rendered only when ≥1 active input-placed field exists |

**6 · Acceptance** — **Given** Brazos Bend has defined `feeder_number` as required and placed it Input on S51, **when** a meter tech adds an asset without filling it, **then** save is blocked with the error on that control; **and when** they fill it, **then** the value is stored in `assets.custom_data` and appears in the asset's audit trail — with no deploy between the field being defined and being captured.

**7 · Finance Calculation** — N/A. A `number` custom field is captured and displayed; BR-TEN-048 and the G6 gate keep it out of every money path.

**8 · Open Questions** — None.

---
```yaml
id: US-SHL-016
epic: EP-SHL-07
module: platform-shell
screens: [S14, S15, S21, S49, S50]
wave: 2
status: draft
blocked_by: []
depends_on: [US-SHL-015]
journeys: []
rules: [BR-SHL-038, BR-SHL-039]
golden_tests: []
finance_calc: none
```
### US-SHL-016 — Display custom fields, and include them in exports

**1 · Details** — As a staff user, I want the fields we defined to show on detail pages and come out in CSV exports, so that our own data is as usable as the platform's. View placements render read-only in display order; list screens offer View-placed fields as **available** columns through the IS-5 chooser; exports include every active field for the exported entity.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-SHL-038 | Custom columns are **available, never default** (IS-5): a tenant's field set must not silently reshape a list every user already knows. Sorting on custom columns is out of R2 — sorting over jsonb needs an index decision per field and no story requires it yet; the column renders unsorted rather than pretending | PROPOSED — derives from IS-5 (dynamic columns) + BR-SHL-027 (server-side preferences) |
| BR-SHL-039 | CSV exports carry one column per active custom field, headed with the **label**, appended after the platform's columns and ordered by display order. Values follow IS-11 export conventions (ISO dates regardless of UI language), so a machine reading the file is not affected by who exported it | CONFIRMED — PO ruling 2026-08-10 ("Export yes") + IS-11 |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | S50 Asset detail for `MTR-000117` | "Feeder Number: F-12" and "Pole Tag: P-8842" render read-only in display order |
| TC-2 | S49 Assets list column chooser | `Feeder Number` and `Pole Tag` are offered; neither is on by default; enabling one persists per user (BR-SHL-027) |
| TC-3 | Export assets to CSV | Header ends `…,Feeder Number,Pole Tag`; row for `MTR-000117` ends `…,F-12,P-8842` |
| TC-4 | An asset with no value for a defined field | Cell is empty — never `null`, never `None`, never `undefined` |
| TC-5 | A `date` custom field on screen vs in CSV | Screen uses tenant IS-8 format; CSV uses ISO-8601 (IS-11) |
| TC-6 | Deactivated field | Gone from detail, chooser and export; stored values untouched (BR-TEN-050) |
| TC-7 (neg) | Export request while over the BR-SHL-016 row cap | Unchanged cap behaviour — 422 BIZ-CAP; custom columns do not alter the guard |
| TC-8 (isolation) | Lone Star Ridge exports assets | No custom columns in the header, and none of Brazos Bend's labels appear anywhere in the file |

**4 · Test Data** — As US-SHL-015. Export fixture: 120 Brazos Bend assets, 40 carrying `pole_tag`, 80 without.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Custom value (read) | S21 · S50 · S14 · S15 | GAP | `<entity>.custom_data ->> key` | per `data_type` | computed-display | missing → empty string, never a null literal |
| Custom column selection | S49 · S14 · S15 | GAP | `user_preferences` (existing, BR-SHL-024) | jsonb | user-input | unchanged ≤32 KB rule |
| CSV column | export | GAP | header = `custom_field.label` | text | computed-display | IS-11 formats |

**6 · Acceptance** — **Given** Brazos Bend has two active asset fields with values on some assets, **when** a staff user opens an asset, enables the columns on the list, and exports, **then** the values appear in all three places, blanks render as empty rather than as a null literal, and a Lone Star Ridge export of the same entity contains none of it.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
