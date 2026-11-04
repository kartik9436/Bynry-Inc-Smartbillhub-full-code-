# metering — Field Map

One row per field. Origin: user-input | system-derived | reference-data | integration | computed-display. Rows cite A2 § or "prototype-extracted"; underivable = GAP (mint an OQ).

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Premise ID | S14/S16 | prototype-extracted (`P-10432`) | premises.premise_no | text | system-derived | unique per tenant (tenant series) | PROPOSED-SCHEMA (new column) |
| Premise address | S14/S16 | prototype-extracted | premises.address_line/city/state/postal_code | text | user-input | address_line required | mapped |
| Property type | S14/S16 | prototype-extracted (7 options) | premises.property_type | enum | user-input | from option set | PROPOSED-SCHEMA (new column) |
| Services available (premise) | S14/S16 | prototype-extracted (chips) | premises.services_available | service_type[] | user-input | ⊆ tenant-enabled (BR-MET-003) | PROPOSED-SCHEMA (new column) |
| Owner / property manager | S14/S16 | prototype-extracted | premises.owner_manager | text | user-input | optional | PROPOSED-SCHEMA (new column) |
| **Parcel ID** (was *External / GIS ref* until 2026-09-08) | S14/S16/PRM-02 | `BR-MET-1163`, PO ruling 2026-09-08 — *"you can make reference # = Parcel ID"* | premises.external_ref | text | user-input | optional; unique per tenant, case-insensitively | mapped (CR-089 wave A — SAME column, relabelled; it was NULL on all 673 properties, so nothing was overwritten and no migration was needed) |
| **On the map** (a property's point) | S14/S16/PRM-02 | `PUJ-10`, CR-089 wave A | premises.lat · premises.lng | NUMERIC(9,6) · NUMERIC(9,6) | user-input (was City/geocoder only) | both or neither; ±90 / ±180 | mapped — the columns shipped with CR-028 and **no screen read one until 2026-09-08**. Correctable on the edit form (`PUJ-19`); NOT a draggable pin (PO: *"we dont need this right now"*) |
| **Checked against GIS** | S16/PRM-02 | PO ruling 2026-09-08 — *"We will need GIS verfieid Flag or field … at the time of creating and in view also"* | premises.gis_unchecked **+ premises.gis_checked_by + premises.gis_checked_at** | boolean · uuid → identity.users · timestamptz | user-input | ⚠ **READ THE PAIR.** The flag is `NOT NULL DEFAULT false`, so `false` means *nobody has looked*; a property is **Checked** only where `gis_checked_at` is set | mapped (CR-089 wave A, `metering/0055`) |
| **A unit's own point** | PRM-03 | `BR-MET-1162`, PO ruling 2026-09-08 | units.lat · units.lng | NUMERIC(9,6) | user-input | both or neither; NULL = read the building's | mapped (CR-089 wave A). ⚠ **A UNIT STILL DECLARES NO ADDRESS COLUMN** — `BR-MET-1161`'s coordinate clause narrowed, its address half did not, and `G85` enforces that per FIELD |
| Premise status | S14 | prototype-extracted (Active/Pending pills) | premises.status (draft\|pending\|active\|inactive) | enum | system-derived | draft via Save-draft | PROPOSED-SCHEMA (new column) |
| Unit ID | S15/S16 | prototype-extracted (`U-10432-A`) | units.unit_no | text | system-derived | unique per tenant | PROPOSED-SCHEMA (new column) |
| Unit label | S15/S16 | prototype-extracted | units.label | text | user-input | unique (tenant, premises_id, label) | mapped |
| Unit type | S15/S16 | prototype-extracted (5 options) | units.unit_type | enum | user-input | from option set | PROPOSED-SCHEMA (new column) |
| Occupancy | S15/S16 | prototype-extracted (Vacant/Occupied/Reserved) | units.occupancy | enum | user-input | from option set | PROPOSED-SCHEMA (new column) |
| Floor / building · Sq ft | S16 | prototype-extracted | units.floor_label · units.square_feet | text · integer | user-input | optional | PROPOSED-SCHEMA (new columns) |
| Unit status pill | S15 | prototype-extracted (Active/Vacant/Pending/Disconnect) | derived: accounts.status + units.occupancy | enum | computed-display | display only | mapped (no column) |
| Default plan on unit | S16 | prototype-extracted (plan panel) | units.default_tariff_id (⚠ cross-module FK → rating tariffs) | uuid | user-input | active tariff, same tenant | PROPOSED-SCHEMA (new column) |
| Plan effective / lock / vacant-standby | S16 | prototype-extracted | units.plan_effective_from · units.plan_locked · units.vacant_standby_auto | date · bool · bool | user-input | — | PROPOSED-SCHEMA (new columns) |
| Meter ID | S15/S16/S25 | prototype-extracted (`M-4021`) | assets.meter_no (B2 r4, supersedes meters) | text | user-input / system-derived | unique (tenant, meter_no) | mapped |
| Meter type / read method | S16 | prototype-extracted + A2 addendum lookup | assets.read_method | reference | reference-data | tenant Meter-types entry | mapped (r4) |
| Multiplier (meter factor) | S16/S31.2 | prototype-extracted (×10 seen) | assets.multiplier | numeric(18,6) | user-input | > 0; explicit | mapped |
| Sub-meter parent | S16 | prototype-extracted (master selects) | assets.parent_asset_id | uuid | user-input | same service + premise | mapped (r4) |
| Allocation rule / Loss tolerance | S16 | prototype-extracted (RUBS…/"3%") | assets.allocation_rule · assets.loss_tolerance_pct (on master) | enum · numeric(18,6) % | user-input | tolerance ≥ 0; 3% sample | PROPOSED-SCHEMA (new columns) |
| Route name/code | S26/S8 | prototype-extracted | routes.code · routes.name | text | user-input | unique (tenant, code) | code mapped · name PROPOSED-SCHEMA |
| Route type / feeder | S26/S8 | prototype-extracted (Walk/Drive/AMI·F-01) | routes.route_type · routes.feeder_ref | enum · text | user-input | feeder AMI-only | PROPOSED-SCHEMA (new columns) |
| Route assigned-to | S26 | prototype-extracted | routes.assigned_to (⚠ cross-module FK → identity users) | uuid | reference-data | null = system auto-pull | PROPOSED-SCHEMA (new column) |
| Route sequence range | S8 | prototype-extracted ("1–300") | routes.sequence_start/sequence_end | integer | user-input | SUPERSEDED — routes = premises/unit selection + OPTIONAL walk order, no ranges (BR-MET-033; OQ-041 CLOSED); sequence columns dropped |
| Route → cycle assignment | S8/S26 | prototype-extracted | routes.cycle_id | uuid | user-input | one cycle per route (BR-MET-010) | PROPOSED-SCHEMA (new column) |
| Route status | S8 | prototype-extracted (Deactivate action) | routes.status (active\|inactive) | enum | user-input | deactivate-first (IS-1) | PROPOSED-SCHEMA (new column) |
| Cycle code | S27/S8 | prototype-extracted ('08-A') | cycles.code | text | user-input | unique (tenant, code) | mapped |
| Cycle read window | S27/S8 | prototype-extracted (Aug 1 – Aug 5) | cycles.window_start/window_end | date | user-input | start ≤ end | PROPOSED-SCHEMA (new columns) |
| Cycle bill date / due days | S27/S8 | prototype-extracted (Aug 8 · +20 days) | cycles.bill_date · cycles.due_days | date · integer | user-input | bill ≥ window end; due ≥ 0; 20 is a sample | PROPOSED-SCHEMA (new columns) |
| Cycle expected/collected/progress/status | S27 | prototype-extracted | derived from meter_reads vs route meters | int/%/enum | computed-display | never stored | mapped (no column) |
| Schedule seed | — | B2 read_schedules | read_schedules.cycle_id/frequency + last_generated_period | text/date | system-derived | generates next period | frequency mapped · bookkeeping PROPOSED-SCHEMA |
| Import batch (S28) | S28/S29 | prototype-extracted (B-2608-04 stamp) | read_import_batches (batch_no, source_kind, source_detail, period_month, cycle_id, route_id, service, file_name, file_hash, uploaded_by, uploaded_at, session_ref, ip, certified_by_uploader, counts, status) | table | system-derived | atomic post; append-only stamp | PROPOSED-SCHEMA (new table) |
| Staged import rows | S28 | derived (steps 2–4) | read_import_rows (batch_id, row_no, meter_no_raw, asset_id, read_at, value, raw_value, service, note, rule_outcomes, disposition, disposition_reason, disposed_by) | table | system-derived | errors block post (BR-MET-015) | PROPOSED-SCHEMA (new table) |
| Read source detail | S28 step 1 | prototype-extracted (6 options) | meter_reads.source (B2 enum) + read_import_batches.source_detail | enum + text | user-input | B2 enum coarser than UI | source mapped · detail PROPOSED-SCHEMA |
| Read prior/current/consumption/unit | S25/S29 | prototype-extracted | meter_reads.prior_value/current_value/consumption/unit | numeric(18,6) + unit | system-derived | B4 formula; unit explicit (CLAUDE.md #3) | mapped |
| Read status + flags | S25/S29/S31.2 | A5 + prototype pills | meter_reads.status + read_status enum extension ('zero','mismatch') | enum | system-derived | one primary status | enum values PROPOSED-SCHEMA |
| Rule outcomes | S28/S29 | prototype-extracted ("Rule outcomes: 10/10 passed") | meter_reads.rule_outcomes | jsonb | system-derived | self-describing (thresholds used) | PROPOSED-SCHEMA (new column) |
| Read ↔ batch linkage | S29 | prototype-extracted (compliance block) | meter_reads.import_batch_id | uuid | system-derived | set at commit | PROPOSED-SCHEMA (new column) |
| Read supersede chain | S29 ("v1 · immutable") | prototype-extracted | meter_reads.replaces_read_id · meter_reads.superseded_by | uuid | system-derived | append-only corrections (BR-MET-016/024) | PROPOSED-SCHEMA (new columns) |
| Fix disposition on read | S25/S31.2 | A2 §S31.3 selects | meter_reads.fix_disposition · fix_reason · fixed_by | enum/text/uuid | user-input | per-flag option set; audited | PROPOSED-SCHEMA (new columns) |
| Dispute marker | S25/S29 | prototype-extracted (button + counts; flow per BR-MET-056 drawer, RD-14) | meter_reads.disputed_at/dispute_reason/disputed_by | timestamptz/text/uuid | user-input | reason required; workflow OQ-043 | PROPOSED-SCHEMA (new columns) → GAP OQ-043 |
| Validation thresholds | S64 Read validation rules | OQ-002 CLOSED → BR-MET-020 (tenant-config, B4 seeded defaults) | read_validation_settings (high_ratio, high_min_delta per service, low_ratio, zero_scope, days_soft/hard bounds, mismatch_default_pct) | table | user-input | defaults OQ-002; never hardcoded | PROPOSED-SCHEMA (new table) |
| Estimation method / consecutive no | S31.2 | prototype-extracted ("3-cycle avg" · "1st/2nd estimate") | meter_reads.estimation_method · consecutive_estimate_no | text/enum · integer | system-derived | ≤ 2 consecutive (BR-MET-027, OQ-003) | PROPOSED-SCHEMA (new columns) |
| True-up linkage | S31.2/S29 | GT-9 + B4 addendum (OQ-003 CLOSED → BR-MET-026/029) | meter_reads.trues_up_read_ids | uuid[] | system-derived | links estimate rows corrected | PROPOSED-SCHEMA (new column) |
| Supervisor co-sign | S28 step 5 | prototype-extracted (checkbox) | import batch co-sign toggle | boolean | user-input | optional, default ON; supervisor = SysAdmin/Executive; blocks commit when enabled (OQ-042 CLOSED) | ok |
| Pattern tokens ({floor},{seq},{unit:01–20}) | S16 pattern | prototype-extracted | {seq}/{floor} token grammar + CSV alternative (BR-MET-031; OQ-039 CLOSED) → units.label/unit_no | text | user-input | ≤3,000/run (BR-MET-038) | ok |

---

## CR-023 · THE RECORDED IMPORT RUN (added 2026-08-21 — stages 1–3 BUILT, stages 4–5 UNBUILT)

Five new metering tables (design B15 §13). **Stages 1–3 write these and nothing
else** — B15 §16 TC-1 counts `premises`, `units` and `service_points` before and
after and they do not move.

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Import run | PRM-04 · WFL-01.\*.1–5 | B15 §5/§13 (`RUN-2812`) | import_runs (run_no, target, source_kind, file_name, file_hash, file_bytes, encoding_delimiter, mapping_id, mapping_spec, batch_label, write_mode, counts, status, run_by, session_ref, ip, started_at, finished_at, is_sample) | table | system-derived | `file_hash` SERVER-computed (TC-2); `counts` must reconcile (TC-3); unique (tenant, target, file_hash) **scoped to `loaded`** so re-upload is allowed and a second commit is not (TC-21) | **BUILT 2026-08-21** (metering 0014/0015) |
| Run number | WFL-01.\*.5 receipt | r10 SET-08 "Import run #" · CR-005 | import_runs.run_no | text | system-derived | EP-TEN-08 series `import_run`, default `RUN-{0000}`; **a missing series row is a warning and a NULL, never a faked number** | BUILT — first allocator of a series CR-005 added and nothing had ever used |
| Staged source row | WFL-01.\*.2–3 | B15 §5 | import_run_rows (row_no, source_key, raw, mapped, outcome, problem, fix_hint, created_record_id, is_sample) | table | system-derived | every row that entered the file comes out of the report; `raw` is never coerced | **BUILT** — `created_record_id` is unwritten until stage 4 |
| Row problem · fix | WFL-01.\*.3 rejects | prototype-extracted (*"Address falls outside the territory boundary"* → *"Confirm and load anyway"*) | import_run_rows.problem · .fix_hint | text | system-derived | customer-facing English, no ids (CR-016); a reject with no sentence is DEF-322's shape | BUILT |
| Import rule (tenant's own / an override) | WFL-01.\*.3 · endpoint 13 | BR-MET-090 · B15 §4.3A | import_rules (code, target, tier, sentence, severity, action, action_value, rule_kind, params, active) | table | user-input | unique (tenant, code); a **code is never reused**; **tier 1 codes are IGNORED here** — structural rules are not configurable | **TABLE BUILT · no write surface** (endpoint 13 `PATCH /import-rules/{code}` is unbuilt) |
| Rule severity · action | WFL-01.\*.3 `RULES THAT RAN` | BR-MET-090 (two columns, deliberately) | import_rules.severity (error\|warning\|pass\|off) · .action (reject_row\|skip_on_load\|default_to\|flag_only) | enum · enum | user-input | severity FIXED in tier 1, configurable in tiers 2–3; `action_value` only for `default_to` | BUILT |
| Rule results — **the run's own copy** | WFL-01.\*.3 · PRM-04 receipt | BR-MET-090 · BR-MET-091 | import_rule_results (rule_code, tier, sentence, severity, action, action_value, hits, available, unavailable_reason, is_sample) | table | system-derived | **STORED, NEVER RECOMPUTED** — re-deriving would rewrite history (TC-17); `unavailable_reason` is never NULL when `available` is false (TC-18) | BUILT |
| Rollback point | WFL-01.\*.5 receipt (`RB-2812`) | B15 §5 | rollback_points (point_no, run_id, expires_at, status) | table | system-derived | ⛔ **`expires_at` is NULLABLE and set by NOTHING** — r10's *"available for 30 days"* is screen copy, not a signed figure (B15 §8 Q7) | **TABLE BUILT · no writer** (stage 4 issues it — P5) |
| Mapping template | WFL-01.\*.1–2 | B15 §5 (`Migration v2`) | tenancy.import_mappings ← import_runs.mapping_id | uuid | user-input | ⚠ **the table has no column that can hold a column map — `DEF-512`**, so the run keeps its own in `import_runs.mapping_spec` and the template is a LABEL on the receipt | GAP — DEF-512 |

### The premises ETL field map — fourteen columns, and the three r10 gets wrong

`import_runs.target_columns("premises")` is **derived from `Premises._meta`**
(BR-MET-088), never listed by hand, so this table describes what the model has
rather than duplicating it. Three rows are worth stating because r10 disagrees:

| Column | What r10 does | What is built | Why |
|---|---|---|---|
| `external_ref` | `LEGACY_KEY` → `— ignore —` | **auto-detected to `external_ref`** | B15 §4.2A #12 — discarding the customer's key costs reconciliation, re-import matching, and any answer to *"what happened to property 88214"* |
| `inside_city_limits` | **no column at all** | mapped, **THREE-STATE**: a blank cell stores **NULL** and never `False` | BR-RAT-101 — `money_factor` refuses on NULL rather than assuming; either default is a silent pricing decision (TC-5, proved RED first) |
| *expected units* | `UNIT_CNT` → `Expected units` | **not offered, and it has no alias** | `premises` has no such column, and BR-MET-088 forbids offering a target with nothing behind it. The rule that would read it is declared `available: false`. ⛔ `OQ-330` |

### ⚠ A CORRECTION TO B15 §5's ER DIAGRAM, FOR THE LANES BUILDING P5–P8

The design draws `IMPORT_RULE_RESULT` and `ROLLBACK_POINT` hanging off the run
with **no `tenant_id` of their own**. As built, **all five tables carry one**,
because RLS is enforced per TABLE: a child with no tenant column has no policy
to enforce and is readable across tenants by anyone holding a uuid. That is
CLAUDE.md hard rule 1, and `read_import_rows` already carries `tenant_id` beside
its `batch_id` for the same reason. The diagram is a picture of relationships;
the policy is the guarantee.
