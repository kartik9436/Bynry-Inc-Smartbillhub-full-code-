# EP-MET-04 — Read Validation & Flags
> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep.

**Module:** metering (product name: **Meter Reads**) · **Wave:** W2 · **Screens:** S25, S29 (flag categories also consumed read-only by S31.2 Run-Bills reads tabs) · **Status:** draft

## Scope
**In:** the validation-flag engine (High / Low / Zero / Missing / Days-threshold / Meter-factor / Mismatch + OK / Estimated states per A5, **completed by the Reads pre-session catalog BR-MET-052**: negative-usage hard error never auto-fixed · read on retired meter = error · read on vacant unit = warning · TOU sum-sanity Σwindows≈total ±1% · duplicate key (meter, date, channel)) with **tenant-configurable thresholds — config-driven, never hardcoded; sourced from the S64 Settings → Reference data card "Read validation & estimation rules" (`read_validation_settings`, B2 r5 #15) with PO-ratified seeded defaults (OQ-002 CLOSED)**; the **plan-driven completeness gate** (BR-MET-049) evaluated as a VEE validation before billing; the **read lifecycle & supersede/correction flow** incl. the BILLED lock and J6 routing (BR-MET-053/054 — US-MET-016); the Reads page landing on **Needs attention** (BR-MET-060 — US-MET-019) with the full list (S25) one tab away — flag pills, route/status/channel filters, per-flag fix actions, **server pagination with the 2-yr hot-window default** (BR-MET-055); and the Read detail drawer (S29) with content per **BR-MET-056** (full chain, math shown, flag reason WITH threshold values, channel, supersession history, dispute/audit, actions) and Override / Estimate / Dispute. The engine runs at import commit (invoked by EP-MET-03) and re-runs when a read is overridden/estimated.
**Out:** the S64 settings-card UI itself (tenancy EP-TEN-07, BR-TEN-039 — the engine reads the stored config regardless) · estimation math and true-up (EP-MET-05 — OQ-003 CLOSED, defaults confirmed; per-channel per BR-MET-058) · the Run-Bills exception handling built on these flags (billing module S31.2/S31.3 — consumes flag data read-only, incl. the completeness-gate outcome) · the upload wizard and the completeness bar/chase list surfaces (EP-MET-03 — US-MET-018 computes with this epic's gate semantics) · the archival job itself (EP-MET-03 US-MET-020 — this epic's list only honors the hot-window/archive-search posture) · dispute workflow beyond the v1 record+flag+hold flow (OQ-043 CLOSED) · the billing-side money correction of a billed read (J6 billing/ledger stories — US-MET-016 hands off to them).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S25 Reads | meter_no, premise address | route (All/Route n…), status (All/OK/Flagged/Pending/Estimated), cycle, service, source, channel (total/tou_on/tou_mid/tou_off/export/demand — B2 r8) | read_at desc | meter, cycle, route, previous, current, usage, status | 10 default (Meter · Cycle · Route · Service · Premise · Previous · Current · Usage · Source · Status) / 13 available (+Days since prior, +Batch, +Channel — B2 r8) | Open detail drawer (row click); per-flag fix action (Accept/Override/Estimate/Investigate/…) | — (v1; "Estimate all missing" lives in S28/S31.2 flows) | CSV (IS-9) |

> S25 **lands on the Needs-attention tab** (KPI chips Missing/Flagged/Disputed — BR-MET-060, US-MET-019); the table above is the "All reads" tab one click away.
> List queries are **server-paginated with a 2-yr hot-window default + explicit archive search** (BR-MET-055; archival job US-MET-020 in EP-MET-03).

## Stories

---
id: US-MET-011
epic: EP-MET-04
module: metering
screens: [S25]
wave: 2
status: draft
blocked_by: []
depends_on: [US-MET-002, US-MET-003]
journeys: [J2, J3]
rules: [BR-MET-020, BR-MET-021, BR-MET-022, BR-MET-025, BR-MET-049, BR-MET-052]
golden_tests: []
finance_calc: none
---
### US-MET-011 — Config-driven validation flag engine

**1 · Details** — As a utility, I want every committed read evaluated against **my** thresholds — high-usage ratio, low-usage ratio, zero-read handling, read-interval day bounds, meter-factor sanity, and master-vs-sub-meter mismatch tolerance — with the thresholds stored as tenant configuration (per service where applicable), so that a 3,000-meter water district and a small electric co-op can tune sensitivity without code changes. Entry: no dedicated engine screen — the engine runs at import commit (US-MET-010) and on override/estimate; its config is the **S64 card (Settings → Reference data → "Read validation & estimation rules", BR-TEN-039)** backed by `read_validation_settings` (B2 r5 #15) with PO-ratified seeded defaults (OQ-002 CLOSED). The catalog is **complete per the Reads pre-session (BR-MET-052)**: negative usage = hard error never auto-fixed (a full register wrap is rollover per the OQ-009 closure, not negative usage); read on a retired meter = error; read on a vacant unit = warning; TOU sum-sanity Σ(windows) ≈ total ±1%; duplicate key (meter, date, channel). Evaluation is per channel (B2 r8), and the **plan-driven completeness check (BR-MET-049)** runs as a VEE gate before billing. Every flag stores which rule fired, the threshold values used, and the computed comparison, so S25/S29/S31.2 can explain themselves ("High usage · 312% avg").

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-020 | All validation thresholds are tenant config in `read_validation_settings` (**B2 r5 #15 — approved table, no longer PROPOSED-SCHEMA**), per service where units differ; **no threshold value is ever hardcoded**. Seeded defaults are CONFIRMED (OQ-002 CLOSED, PO R6): high 200% + absolute floors 50 kWh / 1 kgal · low 25% · days 25–35 flag / 20–45 hard — PO-ratified values ship as SEEDED DEFAULTS, tenant-editable on S64. | CONFIRMED — OQ-002 CLOSED (PO R6) + B2 r5 #15; surfaced on S64 (BR-TEN-039) |
| BR-MET-021 | Flag vocabulary is fixed per A5: OK, High, Low, Zero, Missing, Estimated (1st/2nd consecutive), Days-threshold, Meter-factor, Mismatch. B2's `read_status` enum lacks `zero` and `mismatch` → PROPOSED-SCHEMA enum extension. Catalog completion (BR-MET-052) extends the outcome set with negative_usage, retired_meter, vacant_unit, tou_sum_sanity, incomplete_set — same PROPOSED-SCHEMA enum-extension mechanism. A read carries exactly one primary status plus the full rule-outcome detail. | PROPOSED (schema) — A5 states + prototype rule table + S16 copy; catalog additions CONFIRMED (BR-MET-052) |
| BR-MET-052 | Completed VEE catalog: negative usage = **hard error, never auto-fixed** (a full register wrap is classified rollover per the OQ-009 closure, not negative usage); read on retired meter = **error**; read on vacant unit = **warning**; TOU sum-sanity Σ(windows) ≈ total within **±1%** (the confirmed tolerance ships as the seeded config value per BR-MET-020's config-over-constant rule); duplicate rejection key = (meter, date, channel). | CONFIRMED — PO RD-5..8 (BR-MET-052) |
| BR-MET-049 | Plan-driven completeness is a VEE validation before billing: required record set per meter = the unit plan's channel set (flat → total; TOU → windows + total; demand → +demand); an incomplete set surfaces as a gate outcome the billing run consumes — flags and gate outcomes never block billing by themselves (S31.2 decides). | CONFIRMED — PO RD-2 (BR-MET-049) |
| BR-MET-022 | Evaluation runs at import commit and re-runs whenever a read is overridden or estimated; outcomes (rule, thresholds used, computed values) are stored on the read; flags never block billing by themselves — the billing run surfaces them as exceptions (S31.2) and decides there. | PROPOSED — derived from S28 step 3 (rules at import) + S31.2 (flags resurface at billing) |
| BR-MET-025 | Mismatch: for a master meter with sub-meters, if `|master consumption − Σ sub-meter consumption|` for the same period exceeds the loss tolerance configured on the master relationship (S16; default sample 3% — tenant-editable, not a constant), both the master read and the group are flagged `mismatch`. | PROPOSED — derived from S16 sub-meter panel copy ("master's total reconciles against the sum of sub-meters" + Loss tolerance field) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Brazos Bend config (S64 seeded defaults): high ratio 200% + absolute floors 50 kWh / 1 kgal; commit M-7204's read (26.24 kgal vs 8.40 kgal trailing avg = 312%, delta > 1 kgal) | Status `high`; outcome stores ratio 312%, threshold 200%, delta check passed |
| TC-2 | Low config 25%; M-7305 reads 22 kWh vs 420 kWh avg (5%) | Status `low` with stored comparison |
| TC-3 | Zero read on active, occupied unit (M-7110, 18,240 → 18,240) | Status `zero`; any read on a **vacant** unit (M-7115, unit 4B — occupancy derived per BR-MET-036) instead flags warning `vacant_unit` (BR-MET-052), fix option "Accept (vacant)" |
| TC-4 | Days config soft 25–35 / hard 20–45 (seeded defaults per B2 r5 #15); M-7610 at 52 days | Status `days_threshold` with days=52 vs bounds stored; 18-day read also flags (below soft bound) |
| TC-5 | M-7210 raw 2,754 with ×10 factor → 27,540 kWh vs history ~12,600 | Status `factor_flag`; outcome names the configured multiplier and the suspicion basis |
| TC-6 | Master M-7300 = 12,400 kWh; Σ subs M-7301…M-7420 = 11,900 kWh (4.0% gap > 3% tolerance) | Master read status `mismatch`; outcome stores master, sum, gap %, tolerance |
| TC-7 | Dana edits the S64 config: high ratio 200% → 250%; recommit a 240% read | No high flag — proof no value is hardcoded; config change writes an `audit_log` row with before/after |
| TC-8 *(negative)* | Config API receives high ratio = −10% or malformed per-service key | Rejected with validation error; config unchanged |
| TC-9 *(negative)* | Engine invoked for a tenant with no config row | Fails safe: flags requiring thresholds are skipped and the batch reports "validation config missing" — it does **not** fall back to hardcoded numbers (new tenants receive the B2 r5 #15 seeded row at provisioning) |
| TC-10 *(isolation)* | Lone Star Ridge sets low = 40%; Brazos Bend keeps 25% | Each tenant's reads evaluate only against its own config; automated test runs the same read fixture through both tenants and asserts different outcomes |
| TC-11 *(negative)* | M-7823: current 88,102 < prior 88,204, register nowhere near wrap | Hard error `negative_usage` (BR-MET-052); the engine offers **no auto-correction of any kind** — resolution only via human disposition (US-MET-008) or supersede (US-MET-016); a full register wrap instead classifies rollover (OQ-009 closure, GT-14) |
| TC-12 | Read row arrives for M-7702, retired Jun 15, 2026 (assets status `retired`) | Error `retired_meter` (BR-MET-052) with the retirement date in the outcome |
| TC-13 | M-7450 committed channel group Aug 3: windows 210 + 118 + 96 = 424 vs total 430 | Outcome `tou_sum_sanity` on the group: Σ 424, total 430, deviation 1.40%, tolerance 1.0% (tenant config seeded from the confirmed ±1%) — group flagged |
| TC-14 | Completeness gate: unit 12A (TOU plan) has tou_on/tou_mid/total committed but no tou_off at window close | Gate outcome `incomplete_set` naming meter M-7450 + missing channel tou_off (BR-MET-049); surfaced to the billing run as a VEE gate result; no read row invented |

**4 · Test Data** — Brazos Bend `read_validation_settings` (B2 r5 #15 seeded defaults — OQ-002 CLOSED, tenant-editable): high_pct 200, high_abs_kwh 50, high_abs_kgal 1, low_pct 25, zero flag on active non-vacant, days 25–35 flag / 20–45 hard, mismatch default tolerance 3%, tou_sum tolerance 1.0 (seeded from BR-MET-052's confirmed ±1%). Reads fixtures per EP-MET-03 §4 (incl. M-7823 negative, M-7702 retired, M-7115 vacant unit 4B, TOU group M-7450). Lone Star Ridge config: low_pct 40 (tenant-edited). Actors: Dana Whitfield (config), system (engine).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| High % / absolute floors | S64 (Settings → Reference data card, BR-TEN-039) | B4 addendum + B2 r5 #15 (OQ-002 CLOSED) | `read_validation_settings.high_pct` + `high_abs_kwh` / `high_abs_kgal` (B2 r5 #15) | pct / qty+unit | user-input (reference-data at eval) | > 0; per-service units explicit |
| Low % | S64 | same | `read_validation_settings.low_pct` (B2 r5 #15) | pct | user-input | 0 < x < 100 |
| Zero-read scope | S64 | prototype fix options ("Accept (vacant)") | **PROPOSED-SCHEMA** `read_validation_settings.zero_scope` (active_non_vacant \| all \| off) — S64-card extension beyond the r5 #15 column set | enum | user-input | — |
| Days bounds (soft/hard) | S64 | B2 r5 #15 (seeded 25–35 flag / 20–45 hard) | `read_validation_settings` day-bound columns (B2 r5 #15) | integer days | user-input | soft within hard; min < max |
| Mismatch tolerance | S16 (per master) + S64 default | prototype-extracted ("Loss tolerance 3%") | `assets.loss_tolerance_pct` (per master, EP-MET-01) + **PROPOSED-SCHEMA** `read_validation_settings.mismatch_default_pct` (S64-card extension) | numeric(18,6) % | user-input | ≥ 0 |
| TOU sum tolerance | S64 | BR-MET-052 (confirmed ±1%) + BR-MET-020 (config-over-constant) | **PROPOSED-SCHEMA** `read_validation_settings.tou_sum_tolerance_pct` (seeded 1.0) | numeric(18,6) % | user-input | > 0 |
| Channel | S25/S29/S31.2 | BR-MET-059 / B2 r8 | `meter_reads.channel` | enum | system-derived | evaluation per channel; sum-sanity across the meter's window group; completeness per plan set |
| Read status | S25/S29/S31.2 | A5 + B2 + BR-MET-052 | `meter_reads.status` + **PROPOSED-SCHEMA** enum extension (`read_status` + 'zero','mismatch','negative_usage','retired_meter','vacant_unit') | enum | system-derived | one primary status |
| Rule outcomes | S25 pill detail / S29 | prototype ("Rule outcomes: 10/10 passed") + BR-MET-052 catalog | **PROPOSED-SCHEMA** `meter_reads.rule_outcomes` jsonb (rule, thresholds used, computed values; incl. tou_sum_sanity + incomplete_set gate results) | jsonb | system-derived | self-describing (no re-derivation needed for display) |
| Days since prior | S25/S31.2 | prototype-extracted | `meter_reads.days_since_prior` (B2) | integer | system-derived | computed vs prior committed read (same channel) |

**6 · Acceptance**
- Given the S64 tenant config and the §4 fixtures, When the engine evaluates, Then each read carries the correct primary status and a stored, self-describing outcome including the thresholds used.
- Given the completed catalog (BR-MET-052) and the plan-driven gate (BR-MET-049), Then negative usage is never auto-fixed, retired/vacant reads flag as error/warning, TOU groups breaching ±1% flag, and incomplete plan-required sets produce a gate outcome billing consumes.
- Given a config change on S64, When re-evaluated, Then outcomes change accordingly and no code change was needed; Given missing config, Then the engine fails safe rather than using built-in numbers (seeded defaults arrive via provisioning, never via code constants).
- Given two tenants with different configs, Then identical readings can flag differently and never read each other's config or history.

**7 · Finance Calculation** — N/A (flags gate review, not money; the money consequences of accepting/overriding land in rating/billing under B4).

**8 · Open Questions** — None — threshold defaults CONFIRMED via the OQ-002 closure (tenant-configurable S64 settings, B4 values as seeded defaults — PO R6, B2 r5 #15); the pre-session catalog and gate are CONFIRMED (BR-MET-049/052).

---
id: US-MET-012
epic: EP-MET-04
module: metering
screens: [S25]
wave: 2
status: draft
blocked_by: []
depends_on: [US-MET-009, US-MET-010, US-MET-011, US-SHL-006, US-SHL-007, US-SHL-008]
journeys: [J2]
rules: [BR-MET-021, BR-MET-023, BR-MET-049, BR-MET-055, BR-MET-060]
golden_tests: []
finance_calc: none
---
### US-MET-012 — Reads list with flags & per-flag fix actions (S25)

**1 · Details** — As a billing clerk, I want the Reads tab to list every reading with meter, cycle, route, service, premise, previous/current, computed usage, source, and a status pill (OK / Hi-usage / Low / Zero / Pending / Est. / Days / Factor / Mismatch), filterable by route, status and channel, with a fix action appropriate to each flag, so that I can clear exceptions before the billing run instead of inside it. Entry: sidebar → Reads (S25) — the screen **lands on the Needs-attention tab (BR-MET-060, US-MET-019); this full list is one tab away**. Header roll-up "Cycle 08-A · N expected records · N collected · N pending meters · N disputes" and actions **Route sheet PDF** (out of scope here — W6 documents) and **↑ Upload reads** (→ S28). Exit: row click → S29 drawer; fix actions per row. Table renders per the capability-matrix row (EP-SHL-02) with a Channel column available (B2 r8); it is **server-paginated with a 2-year hot-window default and an explicit archive search** (BR-MET-055; archival job US-MET-020). Pending = plan-required record (meter × channel, BR-MET-049) with no committed read this cycle — derived, not stored.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-021 | *(shared)* flag vocabulary + pill rendering (incl. the BR-MET-052 catalog additions). | PROPOSED (schema) / catalog CONFIRMED |
| BR-MET-023 | Fix actions vary by flag per A2/A5 and are the only write paths from the list: High → Accept (bill as-is) / Override / Investigate · Low → Accept / Investigate · Zero → Accept (vacant) / Check meter / Skip this month · Missing/Pending → Estimate (EP-MET-05, per channel) / Schedule field visit / Skip cycle · Days → Prorate-to-cycle (offered to billing, per B4-addendum proposal) / Accept / Wait for next cycle · Factor → Confirm factor / Change multiplier (writes to the asset, audited) / Investigate · Mismatch → Investigate / Accept within reason · **Negative usage → Investigate / Override (supersede) / Reject only — never an auto-fix (BR-MET-052 hard error)**. Every fix = confirm modal → toast → `audit_log` (IS-6); "Cap at 2× average" from S31.3 is a **billing-run** action, not a metering write. | PROPOSED — A2 §S31.3 action enumerations + prototype S25/S28/S31.2 selects + IS-6; negative-usage clause CONFIRMED (BR-MET-052) |
| BR-MET-049 *(shared)* | Pending derives from the plan-driven required record set (meter × channel), never from bare meters. | CONFIRMED — PO RD-2 (BR-MET-049) |
| BR-MET-055 | The list is server-paginated; default query window = last 2 years (hot partitions); older reads only via the explicit archive search; no unbounded read endpoint exists. | CONFIRMED — PO RD-13 (BR-MET-055) |
| BR-MET-060 *(shared — landing story US-MET-019)* | The full list is one tab away from the Needs-attention landing. | CONFIRMED — PO RD-12 (BR-MET-060) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Marcus opens the All-reads tab with the §4 seed | Rows render with correct pills (M-7001 OK · M-7204 Hi-usage · M-7823 error path resolved · M-7110 Zero · M-7305 Low · M-7610 Days · M-7210 Factor · M-7300 Mismatch · M-7108 Est.); usage shows explicit units (684 kWh / 3.72 kgal); the +Channel available column shows `total` for flat meters and window values for M-7450 |
| TC-2 | Filter Status = Flagged | Only flagged rows; Route and Channel filters stack (AND, IS-4); URL restores state |
| TC-3 | Fix on M-7204 (High): Accept · bill as-is | Confirm modal → status stays `high` with disposition accepted + reason; toast; audit row; billing sees an accepted-high read |
| TC-4 | Fix on M-7210 (Factor): Change multiplier ×10 → ×1 | Writes `assets.multiplier` (audited, before/after); read's consumption recomputed via supersede (new row per BR-MET-053 — mechanics US-MET-016); flags re-evaluated |
| TC-5 | Fix on pending M-7612: Schedule field visit | Row marked field-visit (work-order intent recorded); no read row invented |
| TC-6 *(negative)* | Fix modal dismissed with Esc | No write, no toast, no audit row (IS-6) |
| TC-7 *(negative)* | Marcus attempts Override with empty reason | Blocked — reason required |
| TC-8 *(negative)* | Executive role attempts a fix action | Disabled-with-reason in UI; direct API 403 (server-enforced, A4) |
| TC-9 *(isolation)* | Lone Star Ridge opens Reads | Only their reads; a search for "M-7204" returns nothing; export honors RLS |
| TC-10 *(negative)* | Client requests page size 10,000 / an export of all history | Server caps the page size and scopes queries to the 2-yr hot window; older data only via the explicit archive-search path (BR-MET-055) — no unbounded endpoint exists |

**4 · Test Data** — Committed reads per EP-MET-03 §4 post (batch B-2608-04) plus estimated M-7108 (Est. pill) and TOU group M-7450 (channel rows). Expected-but-missing: per US-MET-018 §4 (28 records / 14 meters incl. M-7612, M-7613). Header: "Cycle 08-A · 762 expected records · 734 collected · 14 pending meters (28 missing records) · 1 dispute" (record counts per the BR-MET-049 channel model). Actors: Marcus Vega (fix actions), Dana Whitfield (multiplier change), Priya Natarajan (Executive — denied).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| List columns | S25 | prototype-extracted (10-column table) | `meter_reads` + joins (assets, service_points→routes/cycles, units→premises) | per B2 | computed-display | tenant-scoped joins only |
| Channel | S25 | B2 r8 (BR-MET-059) | `meter_reads.channel` | enum | computed-display | available column; filter values from the channel enum |
| Usage | S25 | prototype-extracted ("684 kWh", "3.72 kgal") | `meter_reads.consumption` + `unit` | numeric(18,6) + unit | computed-display | explicit unit always rendered (CLAUDE.md #3) |
| Status pill | S25 | prototype-extracted (OK/Hi-usage/Pending/Est.) | `meter_reads.status` (+ extension) | enum | computed-display | Pending is derived from the plan-required record set (BR-MET-049), not stored |
| Fix action + reason | S25 | A2 §S31.3 enumerations + BR-MET-052 (negative usage never auto-fixed) | disposition on the read (**PROPOSED-SCHEMA** `meter_reads.fix_disposition` + `fix_reason` + `fixed_by`) — value changes go through supersede (BR-MET-053) | enum/text/uuid | user-input | per-flag option set; reason on override/investigate |
| Multiplier change | S25 fix | prototype ("Change to ×1") | `assets.multiplier` | numeric(18,6) | user-input | > 0; audited before/after |
| Field-visit intent | S25 fix | prototype ("Schedule field visit") | **PROPOSED-SCHEMA** `read_import_rows.disposition`/read fix value `field_visit` (work orders themselves are a future integration — B7/S35 field-visit modal) | enum | user-input | recorded, not dispatched |
| Header roll-up | S25 | prototype-extracted + BR-MET-049 | computed over the plan-driven required record set vs `meter_reads` heads | integers | computed-display | — |
| Pagination / hot window | S25 | BR-MET-055 | server-side (page, capped size); default window read_at ≥ now() − 2 yr; archive via explicit opt-in (US-MET-020) | — | system-derived | no unbounded endpoint |

**6 · Acceptance**
- Given the seeded cycle, When Marcus opens the All-reads tab, Then every read shows the correct pill and unit-explicit usage (channel visible where selected), And filters/search/URL behave per B9.
- Given any fix action, When confirmed, Then exactly the declared write happens (disposition, supersede, or asset multiplier) with reason + audit; When dismissed, nothing happens; negative-usage rows never expose an auto-fix.
- Given scale, Then the list never issues unbounded queries: pagination is server-side and the default window is the 2-year hot set (BR-MET-055).
- Given role or tenant boundaries, Then fixes are server-enforced and no cross-tenant row is ever listed or exported.

**7 · Finance Calculation** — N/A

**8 · Open Questions** — None.

---
id: US-MET-013
epic: EP-MET-04
module: metering
screens: [S29]
wave: 2
status: draft
blocked_by: []
depends_on: [US-MET-009, US-MET-010, US-MET-011, US-MET-012]
journeys: [J2]
rules: [BR-MET-022, BR-MET-023, BR-MET-024, BR-MET-053, BR-MET-056]
golden_tests: []
finance_calc: none
---
### US-MET-013 — Read detail drawer (S29) with override & dispute

**1 · Details** — As a billing clerk, I want a right-hand drawer for any read showing Previous/Current (with dates), Usage **with the math shown** (register delta × multiplier — BR-MET-056), day count, Status **with the flag reason including the threshold values used**, the read's **channel**, tags (service · cycle · route · source), premise/unit/account linkage, the full compliance-metadata block (batch, source file, hash, uploaded by/at, session · IP, rule outcomes, approvals, version), the **supersession history (full chain)** and this meter's read history, with footer actions **Override read** (= supersede, BR-MET-053 — full correction flow US-MET-016), **Estimate**, and **Dispute**, so that any number on a bill can be traced to who loaded it and when. For a **BILLED (locked)** read, Override becomes "Correct billed read" and routes into the J6 correction path (BR-MET-053, US-MET-016). Entry: S25 row click (also linked from S31.2 and the Needs-attention drill-ins). Exit: ✕ / backdrop close; actions per below. Estimate delegates to EP-MET-05 (W3 build — OQ-003 CLOSED; per-channel per BR-MET-058).


**BUILT 2026-08-16 (DEF-046) — the shape the dispute actually took, recorded so the next agent does not re-decide it.** The marker columns, `needs_attention_counts`'s disputed tally and this drawer's Dispute button had all shipped and **no service and no route anywhere ever set a marker**, so the S25 chip could only ever read zero and the demo-fixture seeder refused to write the spec's one disputed read rather than fake the capability. What shipped is exactly the three acts OQ-043 signs and not one more: RECORD (`dispute_read` — marker + reason + actor, and **no value changes**, because a dispute is a claim ABOUT a reading and the correction doors stay `/supersede` and `/billed-correction`), HOLD (`selectors.dispute_holds_for_unit`, which `apps/billing/runs.prepare_run` BLOCKS on — and it takes no period argument, because the closure holds until the dispute is CLEARED rather than until the period passes), and CLEAR (`clear_read_dispute`, System Admin ALONE). **A BILLED READ IS DISPUTABLE ON PURPOSE** — BR-MET-053 calls the marker "orthogonal" and refusing here would refuse the ordinary case — and the BILLED lock is untouched, asserted by test. S25's Disputed chip now DRILLS IN, on a `disputed` filter the server declares (before it, BE-05 would have ignored an undeclared `f.` param and returned the whole list looking filtered). ✅ **WHAT A DISPUTE DOES TO A BILL ALREADY ISSUED IS RULED — BR-MET-133, PO 2026-08-26, CLOSING OQ-245.** This sentence said it was open. Verbatim: *"Bill stands, resolution through the billed-correction door, and the disputed amount doesn't age into late fees while open"*. Four clauses: the issued invoice is NOT voided and NOT held (hard rule 4); the marker still holds the NEXT run; resolution goes through `correct_billed_read`; and while the dispute is open the DISPUTED AMOUNT is excluded from ageing and late-fee assessment while the undisputed remainder ages normally. Built 2026-08-26: `billing.late_fee.ageable_portion` + `billing/dispute_ageing.py`, and the response code is now `issued_bill_stands_br_met_133` — every surface states the rule rather than the question. ⚠ Clause 4 needs a disputed AMOUNT and nothing records one, so an open dispute with no figure REFUSES rather than defaulting: **OQ-418**.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-022 | *(shared)* override/estimate re-runs the flag engine on the superseding read. | PROPOSED |
| BR-MET-023 | *(shared)* actions are audited confirm-modal writes (IS-6). | PROPOSED |
| BR-MET-024 | Override never edits: it appends a superseding read row (reason + new value required), the original stays immutable with its version chain (S29 "Version: v1 · immutable"; chain via `superseded_by_id`/`superseded_at`, B2 r8); the drawer's compliance block renders stored batch metadata verbatim — it is display-only. **Dispute** records a dispute marker + reason on the read (feeds the S25 "disputes" count); v1 dispute flow per the OQ-043 closure (PO R6): record + flag, and the account is **HELD from the bill run until a System Admin clears** the dispute. | CONFIRMED (override mechanics — supersede per BR-MET-053 + B2 r8); dispute flow CONFIRMED v1 record+flag+hold (OQ-043 CLOSED) |
| BR-MET-053 *(shared — full flow US-MET-016)* | Lifecycle staged → ok/flagged/estimated → committed → BILLED(locked); corrections = supersede, never edit; a billed-read fix routes into the J6 correction path. | CONFIRMED — PO RD-9/10 (BR-MET-053) |
| BR-MET-056 | Drawer content: full chain, math shown, flag reason WITH threshold values, channel, supersession history, dispute/audit, actions. | CONFIRMED — PO RD-14 (BR-MET-056) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open M-7001's Aug read | Drawer: Previous 42,180 (Jul 3) · Current 42,864 (Aug 3) · channel `total` · Usage line shows the math "(42,864 − 42,180) × 1 = 684 kWh · 31 days" (BR-MET-056) · "OK · passed all rules"; tags ELECTRIC / CYCLE 08-A / ROUTE 1 / WALK; premise/unit/account block; compliance block matches batch B-2608-04's stored stamp; history table lists the last 4 reads with usage and source |
| TC-2 | Override read → 42,876, reason "collector keying error" | Confirm modal → superseding row v2; v1's `superseded_by_id` → v2 + `superseded_at` (B2 r8); drawer now shows v2 with "Version: v2 · supersedes v1"; v1 still openable read-only; flags re-evaluated on v2; audit row with before/after |
| TC-3 | Dispute with reason "customer reports vacant since July" | Dispute marker + reason stored; S25 header dispute count and the Disputed KPI chip (US-MET-019) increment; audit row; no value change; the account is held from the bill run until a System Admin clears the dispute (OQ-043 closure) |
| TC-4 | Open an estimated read (M-7108) | Status shows "Est. · trailing-3 avg · 1st consecutive" (fields from EP-MET-05); Estimate button disabled on an already-estimated read |
| TC-5 *(negative)* | Override with value −5 or empty reason | Blocked with inline validation; no write |
| TC-6 *(negative)* | Direct API attempt to mutate the compliance metadata (uploaded_by/at) | Rejected — stamp fields are system-derived, immutable post-commit |
| TC-7 *(isolation)* | Deep-link a Brazos Bend read id from a Lone Star Ridge session | 404/denied under RLS; no field of the read (incl. compliance block) leaks |
| TC-8 | Open flagged M-7204's read | Status block: "Hi-usage · 312% of trailing avg — threshold 200% + 1 kgal floor (tenant config)" — the flag reason WITH the threshold values used (BR-MET-056); supersession-history section reads "v1 · head" |
| TC-9 *(negative)* | Override attempted on a BILLED read (M-7204's Jul read, priced on issued invoice BL-2607-018201) | Plain override refused — read is BILLED(locked); the drawer offers **"Correct billed read"** routing into the correction flow (US-MET-016, J6) so the read fix and money fix travel together (BR-MET-053) |

**4 · Test Data** — M-7001 read per TC-1 (batch B-2608-04, hash `a3f4c19e…8291`, uploaded by Marcus Vega, Aug 6 2026 09:14:22 CT, sess_9f27 · 98.200.114.7, rule outcomes 10/10 passed, approvals none, v1, channel `total`). History: Aug 3 42,864/684 · Jul 3 42,180/612 · Jun 4 41,568/618 · May 5 40,950/612 (walk/AMI mix). Billed fixture: M-7204's Jul read on invoice BL-2607-018201 (issued Jul 8, 2026) — lifecycle BILLED(locked). Flag-display fixture: M-7204 Aug read (high 312% vs 200% + 1 kgal floor). Actors: Marcus Vega; Dana Whitfield (override approver-of-record in audit; System Admin who clears disputes).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Previous / Current + dates | S29 | prototype-extracted | `meter_reads.prior_value` / `current_value` / `read_at` (+ prior read's date) | numeric(18,6) / timestamptz | computed-display | — |
| Usage + day count + math line | S29 | prototype-extracted ("684 kWh · 31 days") + BR-MET-056 ("math shown") | `meter_reads.consumption` + `unit` + `days_since_prior`; math rendered from stored prior/current/multiplier — no re-derivation | numeric(18,6)+unit / int | computed-display | unit explicit |
| Channel | S29 | BR-MET-056 + B2 r8 | `meter_reads.channel` | enum | computed-display | — |
| Flag reason + thresholds | S29 | BR-MET-056 ("flag reason WITH threshold values") | `meter_reads.rule_outcomes` (thresholds stored per BR-MET-022) | jsonb | computed-display | verbatim from the stored outcome |
| Tags | S29 | prototype-extracted | service (service_point), cycle, route, source (+detail) | enums | computed-display | — |
| Premise / Unit / Account | S29 | prototype-extracted | joins units→premises; `meter_reads.account_id` (⚠ cross-module → customers, B2) | text | computed-display | read-only service read |
| Compliance block | S29 | prototype-extracted (9 lines) | `read_import_batches.*` + `meter_reads.imported_by` / `rule_outcomes` / version chain | mixed | computed-display | immutable post-commit |
| Version line + supersession history | S29 | prototype-extracted ("v1 · immutable") + BR-MET-056 | derived by walking the `superseded_by_id` chain (**B2 r8 — CONFIRMED**, replaces the earlier PROPOSED-SCHEMA pair) | text | computed-display | full chain rendered |
| Override (value + reason) | S29 footer | prototype-extracted + BR-MET-053 | superseding `meter_reads` row + audit (full flow US-MET-016; BILLED reads → J6 routing) | numeric(18,6)/text | user-input | value ≥ 0; reason required; BILLED → correction flow only |
| Dispute (reason) | S29 footer | prototype-extracted + OQ-043 closure (v1: record + flag + hold-from-run until SysAdmin clears) | **PROPOSED-SCHEMA** `meter_reads.disputed_at` / `dispute_reason` / `disputed_by` (+ `dispute_cleared_by/at`); billing run reads the marker as an account hold | timestamptz/text/uuid | user-input | reason required; clear = System Admin only (OQ-043 CLOSED, PO R6) |
| Read history | S29 | prototype-extracted | this meter's committed reads (lineage heads), latest N | table | computed-display | tenant-scoped |

**6 · Acceptance**
- Given any committed read, When the drawer opens, Then every displayed value — including the math line, channel, flag reason with thresholds, full compliance block, supersession history and read history — comes from stored data with no re-derivation (BR-MET-056), And closes per IS-10 (Esc/✕/backdrop).
- Given an override on an unbilled committed read, Then a superseding, re-validated, audited row exists and the original remains readable as a prior version (`superseded_by_id`/`superseded_at`, B2 r8); Given a BILLED read, Then the only correction path is the J6-routed flow (US-MET-016).
- Given a dispute, Then the marker, reason and actor are stored and counted, And the account is held from the bill run until a System Admin clears it (OQ-043 closure) — nothing else changes.

**7 · Finance Calculation** — N/A

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-043 | Dispute workflow (triage/resolution/billing hold) | Nothing — closed | Product Owner (chat session) | CLOSED — v1: record + flag; account held from the run until a System Admin clears (PO R6) |
| OQ-245 | **A customer disputes a reading the bill already used — what happens to the bill that has gone out?** OQ-043's closure is entirely forward-looking: it says what the NEXT run does and nothing about the invoice the disputed read already priced, which is the ordinary case (a customer disputes BECAUSE they got the bill). Three sub-questions: (a) does the disputed amount stop accruing late fees and pause the dunning ladder? (b) does a dispute OPEN a J6 correction, or is that a separate staff decision after investigation? (c) is "cleared" one outcome or two — upheld (the reading was wrong → the correction path) versus rejected (the reading stands → the bill stands)? | Nothing: recording, the hold and the clear are all signed and BUILT. It blocks the CONSEQUENCE only, and each part is refused by absence and named on screen rather than chosen | Product Owner (chat session) | ✅ **CLOSED 2026-08-26 → BR-MET-133.** PO verbatim: *"Bill stands, resolution through the billed-correction door, and the disputed amount doesn't age into late fees while open"*. (a) the disputed amount stops accruing late fees; the DUNNING half is NOT ruled and stays with OQ-137's open ladder. (b) a dispute does NOT open a correction — clause 3 makes it a staff decision through the billed-correction door. (c) two outcomes: right → supersede + the money correction; wrong → clear the marker, the bill was always correct, and `clear_read_dispute` now records `outcome: "reading_stands"`. ⚠ The disputed AMOUNT is recorded nowhere, so (a) is built and REFUSES on a real bill — **OQ-418** |

---
id: US-MET-016
epic: EP-MET-04
module: metering
screens: [S25, S29]
wave: 3
status: draft
blocked_by: []
depends_on: [US-MET-009, US-MET-010, US-MET-013]
journeys: [J6]
rules: [BR-MET-053, BR-MET-054]
golden_tests: []
finance_calc: none
---
### US-MET-016 — Supersede & correction flow (BILLED reads route to J6)

**1 · Details** — As a billing clerk correcting a wrong read, I want every correction to be a **SUPERSEDE** — a new `meter_reads` row that becomes the lineage head, with the original kept fully visible in history via `superseded_by_id` (B2 r8) — and, when the read is already **BILLED (locked)**, I want the supersede to route into the **J6 billing-correction path** so the read fix and the money fix travel together, so that no committed value is ever edited and every bill stays traceable to the reads that priced it. Entry: S29 Override (US-MET-013) and S28 Replace-existing (US-MET-009) both resolve into this flow; also reachable from S25 row actions. Lifecycle per BR-MET-053: staged → ok/flagged/estimated → committed → BILLED(locked), with disputed→cleared as an orthogonal marker; delete exists only for staged/rejected rows (BR-MET-054). Exit / handoff (J6): for a BILLED read the supersede records the correction linkage the billing module consumes — J6 step 1's contract (original invoice UNTOUCHED; credit note references it, GT-6) starts from this row pair; metering never touches the invoice.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-053 | Read lifecycle: staged → ok/flagged/estimated → committed → BILLED(locked) · disputed→cleared; corrections = SUPERSEDE (new row, original kept visible), never edit; billed-read error = supersede + **automatic J6 correction path** — read fix and money fix travel together. B2 r8: `superseded_by_id uuid NULL` (self-ref) + `superseded_at`; committed rows never UPDATE except these two closure columns; BILLED lock enforced at the service layer + J6 linkage. | CONFIRMED — PO RD-9/10 (BR-MET-053) + B2 r8 |
| BR-MET-054 | CRUD: single manual entry + bulk upload (any cadence, batches append per cycle); **update = supersede only**; **delete = staged/rejected rows only**; roles per the OQ-042/043 closures. | CONFIRMED — PO RD-11 (BR-MET-054) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Supersede a committed (not yet billed) read: M-7001 · Aug 3 · `total` · 42,864 → corrected 42,876, reason "collector re-read — keying error" | New row v2 becomes the lineage head; v1 gets `superseded_by_id` = v2.id + `superseded_at` and stays fully visible in the S29 history; consumption recomputed on v2 = 696.000000 kWh; flag engine re-runs on v2 (BR-MET-022); audit `read.superseded` with before/after |
| TC-2 | v2 later superseded by v3 (42,870, reason "field verification Aug 9") | Drawer shows the full chain v1 → v2 → v3 (BR-MET-056); all consumers (S25, billing pickup, completeness) resolve the head v3 only |
| TC-3 | Billed read: M-7204's Jul read is priced on issued invoice BL-2607-018201 → lifecycle BILLED(locked); Dana runs "Correct billed read" with the new value + reason | Supersede succeeds **only through the correction flow**: superseding row created + a correction linkage referencing invoice BL-2607-018201 is recorded for the billing module (J6 step 1 contract — original invoice UNTOUCHED by metering; credit note/rebill is billing's story); audit row links read pair ↔ invoice |
| TC-4 *(negative)* | Plain supersede API call on the BILLED read without the correction flow | Rejected: "read is billed — corrections route through the billing correction path (J6)"; the service-layer BILLED lock (B2 r8) has no bypass |
| TC-5 *(negative)* | Direct `UPDATE` of value / `DELETE` on any committed read | Rejected — the only UPDATE ever accepted on a committed row sets `superseded_by_id`/`superseded_at` (B2 r8); no delete path exists for committed rows |
| TC-6 | Delete scope (BR-MET-054): delete a staged row in an un-posted batch; delete a rejected row; attempt delete on a committed row | First two succeed (batch record retains the audit trail); committed-row delete refused |
| TC-7 *(negative)* | Supersede submitted without a reason | Blocked — reason required; no write, no audit row (IS-6) |
| TC-8 | Channel-scoped supersede: correct M-7450 · Aug 3 · `tou_on` 13,210 → 13,201 | Only the tou_on lineage gains a new head; tou_mid/tou_off/total heads unchanged; TOU sum-sanity re-evaluates against the new head (BR-MET-052) |
| TC-9 *(isolation)* | Lone Star Ridge session attempts to supersede or read the Brazos Bend chain | Denied under RLS; chains, heads and correction linkages never cross `app.tenant_id` |

**4 · Test Data** — Chain fixture: M-7001 · Aug 3, 2026 · `total`: v1 42,864 → v2 42,876 (reason "collector re-read — keying error", Aug 6) → v3 42,870 (reason "field verification Aug 9"); consumptions 684.000000 / 696.000000 / 690.000000 kWh. Billed fixture: M-7204 Jul read, invoice BL-2607-018201 (issued Jul 8, 2026, status `issued`). TOU fixture: M-7450 tou_on 13,210 → 13,201 (delta 201.000000 kWh recomputed). Actors: Marcus Vega (unbilled supersedes), Dana Whitfield (billed-read correction; roles per the OQ-042/043 closures cited in BR-MET-054).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Supersede link | S29 | BR-MET-053 + B2 r8 | `meter_reads.superseded_by_id` (uuid NULL, self-ref) + `superseded_at` — **B2 r8 CONFIRMED** (no longer PROPOSED-SCHEMA) | uuid / timestamptz | system-derived | the only UPDATE permitted on a committed row |
| Correction value + reason | S29 / S28 | prototype Override/Replace + BR-MET-053 | superseding `meter_reads` row (new head) + audit | numeric(18,6) / text | user-input | value ≥ 0; reason required |
| Lifecycle state | — | BR-MET-053 | `meter_reads.status` + service-layer BILLED lock keyed on billing consumption of the read (B2 r8) | enum | system-derived | staged → ok/flagged/estimated → committed → BILLED(locked) |
| Correction linkage (J6 handoff) | — | BR-MET-053 ("read fix and money fix travel together") | **PROPOSED-SCHEMA** `read_corrections` (superseded_read_id, superseding_read_id, invoice_id — ⚠ cross-module ref → billing, reviewed interface; status) — the row J6 step 1 consumes | — | system-derived | created only when a BILLED read is superseded |
| Delete scope | S28 | BR-MET-054 | `read_import_rows` (staged/rejected) hard-deletable within the batch; `meter_reads` never | — | user-input | committed rows: no delete path |
| Supersede audit | — | CLAUDE.md #7 spirit + IS-6 | `audit_log` (`read.superseded` / `read.billed_correction_opened`, before/after, actor, invoice ref) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given any committed read, When corrected, Then a new head row exists, the original is closed with `superseded_by_id`/`superseded_at` and remains visible in history, flags re-run, and audit records before/after — values are never UPDATEd.
- Given a BILLED read, Then supersede succeeds only through the correction flow that records the J6 linkage; the invoice itself is untouched by metering (J6 step 1 contract).
- Given the CRUD rules (BR-MET-054), Then delete exists only for staged/rejected rows and update is supersede-only everywhere.
- Given a channel-model meter, Then supersede touches exactly one channel lineage.
- Given tenant boundaries, Then chains and correction linkages never cross.

**7 · Finance Calculation** — N/A — no money math (the money correction — credit note/rebill, reversing entries, reapply/refund — is J6's billing/payments/ledger stories; this story guarantees only the read-side supersede and the correction linkage).

**8 · Open Questions** — None.

---
id: US-MET-019
epic: EP-MET-04
module: metering
screens: [S25]
wave: 2
status: draft
blocked_by: []
depends_on: [US-MET-011, US-MET-012, US-MET-013]
journeys: []
rules: [BR-MET-056, BR-MET-060]
golden_tests: []
finance_calc: none
---
### US-MET-019 — Needs-attention landing (Missing/Flagged/Disputed KPI chips)

**1 · Details** — As a billing clerk opening Reads, I want the screen to land on a **Needs attention** view — KPI chips **Missing · Flagged · Disputed** with counts, each drilling into the matching filtered slice — with the full reads list one tab away (US-MET-012), so that my day starts at the exceptions, not at page 1 of thousands of OK rows. Entry: sidebar → Reads (S25) → Needs attention is the DEFAULT tab (BR-MET-060 — the landing rule holds on every open, not sticky-last). Chip semantics: **Missing** = plan-driven required records not collected in the open cycle window (BR-MET-049 computation shared with US-MET-018); **Flagged** = committed lineage heads whose primary status is a validation flag (BR-MET-021 vocabulary + BR-MET-052 catalog, excluding ok/estimated); **Disputed** = active dispute markers (BR-MET-024, OQ-043 closure). Drill-in rows open the S29 drawer whose content per BR-MET-056 shows the full chain, the math, the channel, and the flag reason WITH threshold values. Exit: chip → filtered slice; "All reads" tab → the US-MET-012 list.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-060 | Reads screen opens on **"Needs attention"** (Missing/Flagged/Disputed KPI chips + drill-in); full list one tab away. | CONFIRMED — PO RD-12 (BR-MET-060) |
| BR-MET-056 | Single-read drawer content (reached from every drill-in): full chain, math shown, flag reason WITH threshold values, channel, supersession history, dispute/audit, actions. | CONFIRMED — PO RD-14 (BR-MET-056) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Marcus opens Reads with the §4 seed | Lands on Needs attention: chips **Missing 28 · Flagged 6 · Disputed 1**; counts reconcile exactly with the slices behind them; the full list is not loaded eagerly |
| TC-2 | Click Flagged | Drill-in slice of the 6 flagged heads (M-7204 high · M-7305 low · M-7110 zero · M-7610 days · M-7210 factor · M-7300 mismatch); clicking M-7204 opens the S29 drawer: "Hi-usage · 312% of trailing avg — threshold 200% + 1 kgal floor", math line, channel, chain (BR-MET-056) |
| TC-3 | Click Missing | Chase-list slice of the 28 missing required records / 14 meters (US-MET-018 computation — BR-MET-049); Estimate / field-visit actions available per US-MET-012 |
| TC-4 | Click Disputed | The 1 disputed read (M-7333) with reason, actor and hold state; drawer shows dispute + audit trail (BR-MET-056) |
| TC-5 | Switch to "All reads", navigate away, reopen Reads | All-reads tab renders the full US-MET-012 list with B9 capabilities; the fresh open lands on Needs attention again (BR-MET-060 — landing, not sticky-last) |
| TC-6 *(negative)* | All-clear state (0 · 0 · 0) | Chips render zeros with "All clear — nothing needs attention" empty state; landing still Needs attention, no auto-redirect to the list |
| TC-7 *(negative)* | Chips endpoint returns 500 | A18 failed-with-retry card; Retry re-issues the identical query; no stale counts shown |
| TC-8 *(isolation)* | J. Okafor (Lone Star Ridge) opens Reads | Chips compute over Lone Star Ridge data only; automated test asserts Brazos Bend counts/ids never appear in chips or slices |

**4 · Test Data** — Brazos Bend, cycle 08-A, Aug 2026 seed: Missing 28 records / 14 meters (US-MET-018 §4); Flagged 6 heads (M-7204 high 312% vs 200%, M-7305 low 5% vs 25%, M-7110 zero, M-7610 days 52, M-7210 factor ×10, M-7300 mismatch 4.0% vs 3%); Disputed 1 (M-7333 · Aug 2 · "customer reports vacant since July" — clear pending with Dana Whitfield, System Admin, per OQ-043 closure). Actors: Marcus Vega; J. Okafor (Lone Star Ridge — isolation).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Default tab | S25 | BR-MET-060 | route/view state (no schema) | — | computed-display | landing = Needs attention on every open |
| Missing chip | S25 | BR-MET-060 + BR-MET-049 + **BR-MET-132** | derived: expected required records (US-MET-018 computation) − collected heads, for windows that are **OPEN or CLOSED-BUT-UNBILLED** (BR-MET-057 + BR-MET-132). ⚠ **AMENDED 2026-08-26 — this cell read "open window only (BR-MET-057)" and that literal reading was the defect (OQ-389).** CY-001's window closes Aug 20 and its run is Aug 25, so on Aug 22 the chip read **0** over sixty unread meters — zero on precisely the days a clerk chases stragglers. PO verbatim: *"Keep counting until the run consumes the period — those are the chase days"*. A period is dropped only once a bill run has consumed it. | integer | computed-display | window-scoped; records, not bare meters; served beside `missing_unresolved_meters` so a count over unresolvable meters cannot read as all-clear |
| Flagged chip | S25 | BR-MET-060 + BR-MET-021/052 | count of lineage heads with a flag primary status (`meter_reads.status` excluding ok/estimated) | integer | computed-display | heads only — chains count once |
| Disputed chip | S25 | BR-MET-060 + BR-MET-024 | count of reads with `disputed_at` set and not cleared | integer | computed-display | — |
| Drill-in slice | S25 | BR-MET-060 ("drill-in") | same list query as US-MET-012 with the chip's filter pre-applied | — | computed-display | B9 capabilities preserved; server-paginated (BR-MET-055) |
| Drawer content | S29 | BR-MET-056 | per US-MET-013 field map (chain, math, thresholds, channel) | — | computed-display | display-only |

**6 · Acceptance**
- Given committed data, When Reads opens, Then the Needs-attention tab renders first with chip counts that reconcile exactly against the slices behind them.
- Given any chip, When clicked, Then the filtered slice matches the count and every row's drawer explains itself per BR-MET-056 (flag reason with threshold values, math, channel, chain).
- Given zero exceptions or an endpoint failure, Then the empty/A18 states render and the landing rule still holds (BR-MET-060).
- Given tenant isolation, Then chips and slices never mix tenants.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.

---
> Reconciled 2026-08-08 — Reads pre-session (BR-MET-049..060, B2 r8).
