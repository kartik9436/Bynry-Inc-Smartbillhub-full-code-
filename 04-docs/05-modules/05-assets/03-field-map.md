# assets — Field Map

One row per field. Origin: user-input | system-derived | reference-data | integration | computed-display. Rows cite A2 § or "prototype-extracted"; underivable = GAP (mint an OQ).

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Asset # | S49/S50/S51 | prototype-extracted | assets.asset_no (r4, from meters.meter_no) | text | user-input | UNIQUE per tenant; 3-identifier model — hidden system ID + serial + user number from series (BR-AST-026; OQ-045 CLOSED) | ok |
| Type | S49/S50/S51 | prototype-extracted + A2 r4 lookup | assets.type | enum (10) | user-input | BR-AST-009 | ok |
| Read method | S50/S51 | prototype-extracted + A2 r4 (meter types reused) | assets.read_method | enum AMI\|AMR\|walk-by\|NA | user-input | N/A for BTM | ok |
| Service | S49/S51 | prototype-extracted | assets.service_point_id → service | reference | user-input | required for measuring types | ok |
| Measurement unit (UoM) | S51/S52 preview | GAP — derived (B2 assets.unit NOT NULL + CLAUDE.md #3) | assets.unit | text kWh/kgal/… | user-input / system-derived (bulk) | explicit, never assumed | ok (derived, no OQ) |
| Multiplier | S49/S50/S51/S52 | prototype-extracted (×10/×1) | assets.multiplier | numeric(18,6) | user-input | > 0 | ok |
| **Connection size class** | S50/S51 (AST-01/02) · SET-06 step 3 Size column · r10 RAT-03 s2's per-size base matrix | **BR-AST-500 / DEF-514** — NOT prototype-extracted and NOT in A2: the fact was priced by rating (`RateTier.size_class`, `ChargeCodeAmount.size_class`) before any table could record it | `assets.size_class` | text, holding `service_size_classes.code` (BR-TEN-171 — `W-58`, `W-2`, `E-1P-100` …; the hosted TABLE is still `meter_size_classes`, DEF-970) | user-input | **NULL is lawful and means *"not recorded"*, never *"no size"*.** NOT an FK and NOT checked against the live list — `RateTier.size_class`'s own reason, that a size Settings RETIRES must not vanish from a row that already priced with it. The list is not service-scoped (BR-TEN-078), so a water code on an electric meter is a data error, not a schema one. Billing-affecting (BR-AST-501): changing it after reads exist raises the forward-only warning | ⚠ **column + API write path ONLY — DEF-1900: no control on AST-05/AST-01/02 and no SIZE column on the meters import**, so only an API call can set one today; the demo tenant is seeded with a ratified band so the read path is walkable |
| Manufacturer / model | S50/S51/S52 | A2 r4 addendum (free text) | assets.manufacturer + assets.model | text | user-input | optional; split on "·" | ok |
| Install date | S49/S50/S51 | prototype-extracted | assets.install_date | date | user-input | required when assigning | ok |
| Status | S49/S50 | A5 v4 addendum | assets.status | enum (5) | system-derived | BR-AST-020 transitions | ok |
| Net metering | S50/S51 | prototype-extracted (checkbox + detail line) | assets.net_metering (r4) | boolean | user-input | BR-AST-010 | ok |
| Parent / master | S49 Sub tab / S51 | prototype-extracted (column); picker GAP in modal | assets.parent_asset_id (r4) | uuid self-FK | user-input | required iff sub_meter | ok (GAP noted, derived) |
| Serial # | S50 Overview | task-directed (not in prototype) | assets.serial_no | text | user-input | optional ≤64 | PROPOSED-SCHEMA |
| Form / class | S50 Overview | task-directed | assets.form_class | text | user-input | optional | PROPOSED-SCHEMA |
| Register digits | S50 Overview | task-directed | assets.register_digits | smallint 1–9 | user-input | BR-AST-015 read bound | PROPOSED-SCHEMA |
| Firmware | S50 Overview | task-directed | assets.firmware_version | text | user-input | optional | PROPOSED-SCHEMA |
| Seal # | S50 Overview | task-directed | assets.seal_no | text | user-input | optional | PROPOSED-SCHEMA |
| Warranty end | S50 Overview | task-directed (depth capped by ADR-004) | assets.warranty_end | date | user-input | date only, no EAM depth | PROPOSED-SCHEMA |
| Last test date | S50 Overview | prototype-implied ("Test due") | assets.last_test_date | date | system-derived (test log) | updated by kind=test entries | PROPOSED-SCHEMA |
| Test interval | S50 Overview | prototype-implied | assets.test_interval_months | smallint months | user-input | ≥1; start defaults + tenant control per BR-AST-027 (OQ-046 CLOSED) | ok |
| Location note | S50 Overview | task-directed | assets.location_note | text ≤280 | user-input | optional | PROPOSED-SCHEMA |
| Retire reason | S54 | prototype-extracted (4 options) | assets.retire_reason | enum | user-input | required at retire | PROPOSED-SCHEMA |
| Retire date | S54 | prototype-extracted | assets.retire_date (r4) | date | user-input | ≥ install_date | ok |
| Replaced by | S54 | prototype-extracted (optional) | assets.replaced_by_asset_id | uuid self-FK | user-input | same tenant, not retired | PROPOSED-SCHEMA |
| Assignment from/to/unit | S50 Assignment history / S55 | prototype-extracted | asset_assignments.from_date/to_date/unit_id (r4) | date/date/uuid | system-derived | non-overlapping (BR-AST-017) | ok |
| Assignment actor | S50 Assignment history | prototype-extracted ("By") | asset_assignments.actor_user_id | uuid FK users | system-derived | System when NULL | PROPOSED-SCHEMA |
| Final read link | S55 | prototype-extracted (checkbox); reading input GAP (derived inline field) | asset_assignments.final_read_id → meter_reads | uuid FK | user-input → system-derived | atomic with move; BR-AST-015 | PROPOSED-SCHEMA |
| Maintenance kind/date/detail | S53 / S50 Maintenance | prototype-extracted | asset_maintenance.kind/date/detail (r4) | enum/date/text | user-input | kind+detail required | ok |
| Maintenance tech | S53 | prototype-extracted (staff select) | asset_maintenance.tech_user_id | uuid FK users NULL | user-input | active member | PROPOSED-SCHEMA |
| Maintenance resulting status / closed | S53 / S50 | prototype-extracted ("Set status"/"Closed") | asset_maintenance.resulting_status + .closed_at | enum + timestamptz | user-input / system-derived | legal per BR-AST-020 | resulting_status ok (r4) / closed_at PROPOSED-SCHEMA |
| Bulk import batch/rows | S52 | prototype-extracted (staged preview) | asset_import_batches + asset_import_rows (staging, mirrors S28 pattern) | tables | system-derived | per-row errors jsonb | PROPOSED-SCHEMA |
| Assign all to (bulk) | S52 | prototype-extracted (3 options) | drives asset_assignments creation | enum | user-input | — | ok |
| Skip rows with errors | S52 | prototype-extracted (default on) | batch commit-strategy flag | boolean | user-input | — | PROPOSED-SCHEMA (on batch) |
| Export register (feed) | — | GAP — AMI feeds may supply; display-only | meter_reads.export_register_value | NUMERIC(18,6) NULL | integration | optional | PROPOSED-SCHEMA |
| Test due (pill) | S49/S50 | prototype-extracted (BF-3301) | derived: last_test_date + test_interval_months | computed | computed-display | display-only (BR-AST-007) | ok (derived) |
| Read type | S50 Reads / import | B2 r8 (BR-MET-059 — supersedes r7 read_type) | metering.meter_reads.channel | enum total\|tou_on\|tou_mid\|tou_off\|export\|demand | system-derived | net assets add export-channel rows; UNIQUE (asset, read_at, chad_type) | SPECIFIED |
