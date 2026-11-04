# EP-AST-04 — Asset bulk import
> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep.

**Module:** assets · **Wave:** W1 · **Screens:** S52 (Asset bulk import — ID ratified, OQ-014 CLOSED); entry from S49 header · **Status:** draft

## Scope
**In:** CSV bulk import of asset specifications (S52): drop-zone upload against the **published template per BR-AST-034** (asset # optional → auto-allocated, serial, type, service, UoM, multiplier, register digits, manufacturer, model, install date, status, unit ref optional, opening read optional), **cap 10,000 rows/file** (BR-AST-034), assignment strategy (map from CSV "unit" column / one premises / leave in inventory), **staged preview with per-row validation errors**, skip-errors-and-import-the-rest toggle, commit with the **result summary always shown: "N uploaded · N failed"** (BR-AST-034), and re-upload that matches asset # and updates **spec fields only** (BR-AST-034). Premises/units must exist before import — unmatched references error, never auto-create (BR-AST-034). Mirrors the read-import wizard pattern (S28, metering): upload → validate/stage → review counts → commit; partial-success counts per IS-7/A18.
**Out:** read imports (S28, metering) · single add (US-AST-002) · import of assignment/maintenance history (initial specs only) · integration-driven asset sync (Itron/Sensus MDM — B7 seam, integrations module).
**Tables:** metering-owned B2 r4 `assets` + `asset_assignments`; staging tables proposed. Writes via metering service functions (B1).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| — | *(no list screens — S52 is a modal wizard; its error-row review table is embedded, unpaginated in design)* | | | | | | | |

## Stories

---
id: US-AST-010
epic: EP-AST-04
module: assets
screens: [S52, S49]
wave: 1
status: draft
blocked_by: []
depends_on: [US-AST-001, US-AST-002]
journeys: []
rules: [BR-AST-008, BR-AST-009, BR-AST-023, BR-AST-034]
golden_tests: []
finance_calc: none
---
### US-AST-010 — Bulk import assets from CSV with staged preview and per-row errors

**1 · Details** — As a staff user onboarding or expanding a utility, I want to import hundreds of assets from a CSV, see exactly which rows are valid and why the rest are not before anything is written, and choose to import the valid ones, so that a 400-meter onboarding doesn't become 400 modals. Entry: **Bulk import** on any S49 tab. Per prototype + BR-AST-034: drop-zone upload of the **published template** (columns: asset # *(optional → auto from series)*, serial, type, service, UoM, multiplier, register digits, manufacturer, model, install date, status, unit ref *(optional)*, opening read *(optional)*), **≤10,000 rows per file**, **Assign all to** select (Map from CSV "unit" column / One premises (choose) / Leave in inventory), staged preview line ("Preview: **412 rows** · 408 valid · 4 need a unit match"), checkbox **Skip rows with errors and import the rest** (default on — partial imports allowed, PO R4-A5), commit button **Import 408 ✓** (count = valid rows). Exit: commit → **result summary ALWAYS shown: "N uploaded · N failed"** with a downloadable error report (BR-AST-034) → S49 list refreshed; Cancel discards the stage.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AST-008 | Asset-number uniqueness applies per row (defined US-AST-002 — shared); explicit duplicates in-file are row errors; an in-tenant match on asset # is the **re-upload update path** (spec fields only, BR-AST-034); a **blank asset # auto-allocates from the tenant series** with per-type prefix (BR-AST-026/034 — OQ-045 CLOSED). | CONFIRMED — BR-AST-026/033/034 (OQ-045 CLOSED) |
| BR-AST-009 | Type/service/UoM rules apply per row (defined US-AST-002 — shared). | CONFIRMED — PO R4-A8 |
| BR-AST-023 | Import is **staged**: the file parses into a staging area and NOTHING touches `assets` until explicit commit. Every row validates independently (unknown type, unknown/disabled service, in-file duplicate asset #, non-numeric or ≤0 multiplier, unmatched premises/unit reference); the preview shows total/valid/error counts and per-row error reasons. Commit with skip-errors ON (default — partial imports allowed, PO R4-A5) writes valid rows only; with skip-errors OFF, commit is all-or-nothing (any error blocks). **Premises/units must exist before import — unmatched references are row errors, never auto-created (BR-AST-034).** Assignment strategy: "Map from CSV unit column" resolves each row's unit reference (unmatched = row error); "One premises" assigns every row to the chosen premises' unit; "Leave in inventory" imports all unassigned as `inventory`. Assigned rows follow BR-AST-011 (assignment row + active). Measurement UoM defaults per row from the tenant's service UoM (EP-TEN-06) when the template column is blank and is **stamped explicitly on each staged row and shown in the preview** — never assumed silently (CLAUDE.md #3). Each commit records a batch (who/when/file/counts) and one `audit_log` row. **Re-upload matches on asset # and updates SPEC fields only — billing-affecting fields (multiplier, UoM/unit, net_metering, service) are never changed via upload (BR-AST-034 + BR-AST-012 forward-only).** | CONFIRMED — PO R4-A5 ("partial okay") + Q4–Q8 (BR-AST-034) |
| BR-AST-034 | Upload contract (PO Q4–Q8): published template (asset # optional → auto, serial, type, service, UoM, multiplier, digits, mfr, model, install date, status, unit ref optional, opening read optional); **premises/units must exist first** (unmatched refs error); re-upload matches asset # and updates SPEC fields only (billing-affecting never via upload); **result summary always shown: "N uploaded · N failed"** with error report; **cap 10,000 rows/file**. | CONFIRMED — PO R4 Q4–Q8 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana uploads `bbu-meters-2026.csv` (412 rows), Assign = Map from CSV unit column | Stage created; preview "412 rows · 408 valid · 4 need a unit match"; per-row reasons listed for the 4 (unit not found — premises/units must exist first, BR-AST-034); nothing yet in `assets` |
| TC-2 | Commit with skip-errors ON | 408 assets created (assigned ones active with assignment rows; unit-blank rows inventory); **result summary always shown: "408 uploaded · 4 failed"** with error report (BR-AST-034); batch + audit row recorded |
| TC-3 | The full file re-uploaded after fixing the 4 unit refs | The 4 fixed rows create; the 408 rows MATCH on asset # and **update spec fields only** (manufacturer/model, digits, install date…) — billing-affecting columns (multiplier, UoM, service) are ignored with a row notice (BR-AST-034); summary "412 uploaded (4 created · 408 spec-updated) · 0 failed" |
| TC-4 | Assign all to = Leave in inventory, file of 12 spare meters | 12 created unassigned, status inventory; all show under Unassigned filter |
| TC-5 *(negative)* | Skip-errors OFF with the 412-row file (4 errors) | Commit blocked ("4 rows must be fixed"); zero writes — all-or-nothing honored |
| TC-6 *(negative)* | File with duplicate asset # inside the file (two `M-6001` rows) and one row type "Turbine" | Both flagged as row errors (in-file duplicate; unknown type — turbine is not a meter-to-cash type, ADR-004); valid rows unaffected |
| TC-7 *(negative)* | Cancel after staging | Stage discarded; `assets` untouched; re-entering the modal starts clean |
| TC-8 *(isolation)* | Erin (Lone Star Ridge) imports a file whose unit column names Brazos Bend's "1408 Elm Street · Unit A" | Those rows error "unit not found" — unit resolution is tenant-scoped; committed rows exist only under Lone Star Ridge |
| TC-9 *(negative)* | `bbu-oversize.csv` with 12,000 rows dropped | Rejected at upload: exceeds the **10,000-row cap** (BR-AST-034); nothing staged |
| TC-10 | Spares file with the asset # column left blank | Numbers auto-allocated from the tenant series with per-type prefixes (BR-AST-026/034); allocations listed in the result report |

**4 · Test Data** — `bbu-meters-2026.csv`: 412 rows, template columns per BR-AST-034 — e.g. `M-6001, IT-77021, Meter, Electric, kWh, 1, 5, Itron, C2SX, 2026-07-15, active, 1408 Elm Street · Unit A, 42180`; 4 rows reference unknown unit "Elm St Bldg C". Spares file: 12 rows, unit + asset # blank. Error file: duplicate `M-6001` ×2 + one `Turbine` row. Oversize file: `bbu-oversize.csv`, 12,000 rows. Tenant service UoM defaults (EP-TEN-06): Electric kWh · Water kgal. Actors: Dana Whitfield; Erin Walsh.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| CSV file | S52 | published template (BR-AST-034; supersedes the prototype's short drop-zone column list) | staged rows → **PROPOSED-SCHEMA** `asset_import_batches` (id, tenant_id, filename, uploaded_by, row_count, valid_count, committed_at) + `asset_import_rows` (batch_id, row_no, raw jsonb, errors jsonb, asset_id NULL until commit) — mirrors the S28 read-import staging pattern | file/CSV UTF-8 | user-input | parseable; header row required; **≤10,000 rows (BR-AST-034)** |
| asset # (column, optional) | S52 | BR-AST-034 template | `assets.asset_no` | text | user-input / system-derived | BR-AST-008 per row; blank → auto-allocate from series with per-type prefix (BR-AST-026/034); in-tenant match → spec-only update path |
| serial (column) | S52 | BR-AST-034 template (Device ID/Serial — BR-AST-026) | **PROPOSED-SCHEMA** `assets.serial_no` | text | user-input | optional; duplicate serial warn-but-allow (BR-AST-033) |
| type (column) | S52 | prototype-extracted + BR-AST-034 | `assets.type` | lookup | user-input | BR-AST-009 set only |
| service (column) | S52 | prototype-extracted + BR-AST-034 | `assets.service_point_id` resolution | text → reference | user-input | enabled tenant service |
| UoM (column) | S52 | BR-AST-034 template | `assets.unit` | text (kWh/kgal/…) | user-input (blank → derived from tenant service UoM, stamped + shown) | explicit per row; never assumed (CLAUDE.md #3) |
| multiplier (column) | S52 | prototype-extracted + BR-AST-034 | `assets.multiplier` | numeric(18,6) | user-input | numeric > 0; never updated via re-upload (BR-AST-034) |
| register digits (column) | S52 | BR-AST-034 template | **PROPOSED-SCHEMA** `assets.register_digits` | integer 1–9 | user-input | blank → default 9 (BR-AST-015) |
| manufacturer / model (columns) | S52 | prototype-extracted + BR-AST-034 | `assets.manufacturer` / `.model` | text | user-input | optional |
| install date (column) | S52 | BR-AST-034 template | `assets.install_date` | date | user-input | required when assigning |
| status (column) | S52 | BR-AST-034 template | `assets.status` (lifecycle stage per BR-AST-031) | lookup | user-input | active stage entry; assigned rows follow BR-AST-011 |
| unit ref (column, optional) | S52 | prototype-extracted — the **premises-unit reference** (BR-AST-034) | `asset_assignments.unit_id` | text → uuid | user-input | must match an existing tenant unit when mapping — premises/units exist first, never auto-created (BR-AST-034) |
| opening read (column, optional) | S52 | BR-AST-034 template | first `meter_reads` row via metering service (source import) | numeric(18,6) + stamped UoM | user-input | ≥ 0; ≤ register max (BR-AST-015) |
| Assign all to | S52 | prototype-extracted (3 options) | drives `asset_assignments` creation | enum | user-input | — |
| Skip rows with errors | S52 | prototype-extracted (default on — PO R4-A5 partial imports) | commit strategy flag on batch | boolean | user-input | — |
| Preview counts / per-row errors | S52 | prototype-extracted ("412 · 408 valid · 4 need a unit match") | `asset_import_rows.errors` | jsonb | computed-display | — |
| Result summary ("N uploaded · N failed") | S52 | BR-AST-034 (always shown) | computed over batch counts + error report download | text/jsonb | computed-display | rendered after EVERY commit, success or partial |
| Template download | S52 | BR-AST-034 (published template — no longer a GAP) | static CSV template per the Q4 column set | — | computed-display | — |
| Audit | — | CLAUDE.md #7 | `audit_log` (`asset.bulk_imported`, counts + batch id) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given an uploaded file, When staged, Then valid/error counts and per-row reasons display and no `assets` row exists yet.
- Given skip-errors ON, When committed, Then exactly the valid rows import with correct status/assignment And the result summary "N uploaded · N failed" is ALWAYS shown with the error report (BR-AST-034); OFF blocks commit until clean.
- Given a re-upload matching existing asset #s, When committed, Then only spec fields update — billing-affecting fields never change via upload (BR-AST-034).
- Given a file over 10,000 rows, When dropped, Then it is rejected and nothing is staged (BR-AST-034).
- Given any error row, When listed, Then its reason names the offending column/value; Given a tenant's import, When units resolve, Then only that tenant's units match.

**7 · Finance Calculation** — N/A

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-045 | Asset numbering source (minted US-AST-002) — blank-asset-# handling in bulk import | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-AST-026) — blank # auto-allocates from the series with per-type prefix; template's asset # is optional (BR-AST-034 Q4) |
