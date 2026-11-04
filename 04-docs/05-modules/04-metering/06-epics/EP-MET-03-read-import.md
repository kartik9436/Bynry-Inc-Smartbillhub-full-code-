# EP-MET-03 — Read Import (CSV upload wizard)
> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep.

**Module:** metering (product name: **Meter Reads**) · **Wave:** W2 · **Screens:** S28 (consumes S25 entry, feeds S29) · S25/S27 completeness surfaces (US-MET-018) · headless archival job with archive search on S25 (US-MET-020) · **Status:** draft

## Scope
**In:** the 5-step Upload Reads wizard (S28): Source & context (batch tagging: reading month, cycle, route, service, read source) → Upload/enter (CSV against the **published standard template** — BR-MET-032; manual-entry grid) → Validation (rule outcomes over every staged row — **validate THEN accept**, BR-MET-032) → Review & fix (per-row dispositions: accept-with-reason, override, estimate*, reject, field visit) → Compliance & post (batch stamp: uploaded_by/at, file hash, session/IP; atomic commit executed as an **async job** per BR-MET-055; **file+tags idempotency block per the OQ-044 closure**). Includes staged-batch storage, per-row rejects with reasons, duplicate-vs-committed detection keyed **(meter, date, channel)** (BR-MET-052, B2 r8), and the consumption computation at commit. The **channel model (BR-MET-059, B2 r8)** applies throughout: one staged row per register per date, enum `total | tou_on | tou_mid | tou_off | export | demand`; channel-aware manual entry for TOU/demand meters is US-MET-017. Batches may arrive at **any cadence and append per cycle** (BR-MET-054). Also in: the **plan-driven cycle completeness bar + chase list** (BR-MET-049/057 — US-MET-018) and the **auto-archival job** (2-yr hot window → cold storage, 7-yr total — BR-MET-055, US-MET-020). *The estimate disposition invokes EP-MET-05's engine — surfaced here, specified there.
**Out:** the validation *thresholds and flag engine* semantics (EP-MET-04 — this epic runs those rules over staged rows and records outcomes; the completed VEE catalog BR-MET-052 lives there) · estimation math (EP-MET-05 — OQ-003 CLOSED, defaults confirmed tenant-configurable; per-channel per BR-MET-058) · the **AMI feed replay** source card (requires the Itron/Sensus head-end seam, B7 integrations — build seam only in W2; the card renders disabled until the integration wave) · Reads list, drawer and the Needs-attention landing (EP-MET-04) · billing pickup of committed reads and the billing-side consequence of the completeness gate (billing module) · the supersede/correction lifecycle flow incl. the BILLED lock (EP-MET-04 US-MET-016).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| — | *(S28 is a wizard, not a list screen; its step-4 flagged-rows table is wizard-internal — segment filter All/Errors/Warnings per prototype, not a framework list)* | | | | | | | |
| S25/S27 — Cycle chase list (US-MET-018) | unit label, meter_no, premise address | cycle (required context), route, service, missing channel | days-left-in-window asc, then unit label | unit, meter, route, missing channels, days left | 7 default (Unit · Premise · Meter · Route · Service · Missing channels · Days left) / 7 available | Estimate (EP-MET-05) · Schedule field visit · open unit | Export chase list | CSV (IS-9) |

## Stories

---
id: US-MET-007
epic: EP-MET-03
module: metering
screens: [S28]
wave: 2
status: draft
blocked_by: []
depends_on: [US-AST-002, US-MET-006, US-SHL-010]
journeys: []
rules: [BR-MET-012, BR-MET-013, BR-MET-014, BR-MET-032, BR-MET-059]
golden_tests: []
finance_calc: none
---
### US-MET-007 — Batch context, CSV upload & column mapping (steps 1–2, incl. manual entry)

**1 · Details** — As a billing clerk with a route sheet or collector export, I want to tag a whole batch (reading month, cycle, route, utility service, read source) and then upload a CSV whose columns are auto-mapped by header — or type a few reads into a grid — so that every read lands with full context without per-row retyping. Entry: S25 **↑ Upload reads** → S28 step 1. Step 1: source cards CSV upload / Manual entry / AMI feed replay (disabled, B7 seam) + tag fields; copy per prototype: "Tag the whole batch. Every read inherits these unless overridden per row." Step 2 (CSV): drop zone ≤10 MB UTF-8, `reads_template.csv` download — the **PUBLISHED standard template (BR-MET-032)**: import is a rules-based process, validation rules run BEFORE acceptance and data enters only after passing them; **no fuzzy per-vendor mapping memory** — mapping auto-detects against the template headers and is re-detected on every upload. The template carries one row per register per date with an optional `channel` column (**BR-MET-059, B2 r8**: enum `total | tou_on | tou_mid | tou_off | export | demand`); a file without the column stages every row as `total` (the flat-meter single channel). Mapping table (CSV column → target, sample value shown). Step 2 (manual): Tab/Enter grid (Meter #, Date, Channel, Reading, Notes) inheriting step-1 tags — the plan-aware TOU/demand entry form is US-MET-017. Exit: Continue → Validate (US-MET-008). Nothing is committed in these steps — an uploaded file creates a **staged batch** only (BR-MET-012).

**BUILT 2026-08-15 (DEF-115) — the shape the screen actually took, recorded so the next agent does not re-decide it.** S28 is a **ROUTE**, `/{tenant}/reads/upload`, not a modal over S25: a half-filled five-step import must survive a refresh and be linkable into a ticket, and a browser Back must leave the wizard rather than unwinding it a step at a time — the same reasoning that made S16 and S68 routes. Entry is S25's header primary action (which until this date was a DISABLED control carrying its own reason) and S25's empty-state CTA. **Two controls this story names are deliberately not drawn, each with its reason on screen (BR-SHL-025 / BR-SHL-020):** the **AMI feed replay** card IS drawn and IS disabled, because `_validate_batch_tags` refuses `source_kind: ami_replay` outright until the B7 head-end seam exists; and the **Utility service** batch tag is omitted entirely, because the tag is optional server-side (absent = every service) and no role-safe endpoint lists a tenant's enabled service codes, so a Billing Clerk would meet an empty control — S25 omits the same filter for the same reason. The detected column mapping is shown READ-ONLY: BR-MET-032 forbids a remembered mapping and no endpoint exists to remap through, so a remap control would offer something nothing can store.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-012 | Import is staged: upload/entry creates a staged batch (`read_import_batches` + `read_import_rows`, PROPOSED-SCHEMA); no `meter_reads` row exists until the step-5 commit; an abandoned or discarded batch never appears in Reads (the batch record is retained for audit). | PROPOSED — derived from S28's staged flow + S25 showing only posted reads |
| BR-MET-013 | Column mapping auto-detects by header name against the published template and is remappable per column; meter id, read date and read value must be mapped before Continue; channel, service and notes are optional (channel falls back to `total` per BR-MET-059; service falls back to the batch tag); the template is downloadable. **Mapping is re-detected on every upload — no per-tenant/per-vendor mapping persistence (BR-MET-032, OQ-040 CLOSED).** | PROPOSED (mechanics) — prototype step-2 mapping table; no-persistence CONFIRMED via BR-MET-032 (PO R7) |
| BR-MET-032 | Read import is a **standard, rules-based process**: published CSV template + validation rules run BEFORE acceptance — data enters only after passing the rules. No fuzzy per-vendor mapping memory. | CONFIRMED — PO R7 (OQ-040) |
| BR-MET-014 | Batch tags (reading month, cycle, route, service, read source) inherit to every row unless a mapped column overrides that row (prototype: service column "Service (override)"); the effective tag set is recorded on both batch and rows. | PROPOSED — prototype step-1 copy + step-2 mapping |
| BR-MET-059 *(shared — channel entry UX in US-MET-017)* | Channel model: every register read is one record — meter, date, `channel` (total \| tou_on \| tou_mid \| tou_off \| export \| demand — extensible), value, status; flat meter = single `total` channel; new register kinds = new channel values, never schema changes. The template's `channel` column is optional; absent → `total`. | CONFIRMED — PO RD-1 Option B (BR-MET-059) + B2 r8 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Marcus tags: Aug 2026 · cycle 08-A · All routes in this cycle · Electric · Walk-by, drops `brazosbend_reads_08A.csv` (620 rows) | Staged batch created (status `staged`), 620 `read_import_rows`; mapping auto-detects meter_id → Meter #, read_date → Read date, reading → Read value, channel → Channel against the published template; the file's channel column carries `total` on every row (flat meters — BR-MET-059); sample values shown |
| TC-2 | CSV has service column with row-level `W` values under an Electric batch tag | Those rows carry service W (row override beats batch tag); recorded on the row |
| TC-3 | Manual entry: 3 reads typed for Route 3 walk-by | 3 staged rows inherit the step-1 tags and stage as channel `total` (grid default — BR-MET-059); grid supports Tab/Enter |
| TC-4 | Marcus abandons the wizard at step 2 | No `meter_reads` rows; S25 unchanged; staged batch marked `discarded` on explicit Cancel |
| TC-5 *(negative)* | CSV missing a mappable read-value column | Continue blocked: "map a Read value column"; nothing staged as valid |
| TC-6 *(negative)* | 12 MB file / non-UTF-8 file | Rejected with the size/encoding reason; no staged batch |
| TC-7 *(negative)* | Row with unparseable date "13/45/2026" | Row staged with a parse error attached (surfaces as an error in US-MET-008); not silently coerced — validate then accept (BR-MET-032) |
| TC-8 *(isolation)* | J. Okafor stages a Lone Star Ridge batch at the same time | Each tenant's staged batches, rows and meter lookups resolve only within `app.tenant_id`; batch lists never mix |
| TC-9 *(negative)* | Marcus manually remaps a column, posts, then uploads the next file | Mapping is re-detected fresh against the published template — the prior manual remap is NOT auto-applied (no mapping memory, BR-MET-032) |
| TC-10 | CSV without a channel column | Accepted: every row stages as channel `total` (BR-MET-059 flat-meter default); TOU/demand meters needing per-window rows surface later as missing required records (BR-MET-049 — US-MET-018), never guessed here |
| TC-11 *(built 2026-08-15)* | Marcus opens Reads and presses **↑ Upload reads** | S28 renders at `/{tenant}/reads/upload` with the five-step rail. The control is a live navigation, NOT a disabled control with a reason — that state was DEF-115, and with it `meter_reads` held 0 rows on a fully seeded stack |
| TC-12 *(built 2026-08-15)* | Marcus selects the **AMI feed replay** card | It cannot be selected: the card is drawn and disabled and states that the meter head-end connection is not built and arrives with the integrations wave. Nothing is staged and no request is made |
| TC-13 *(built 2026-08-15)* | Marcus stages a file and then chooses a different one before continuing | The staged batch is dropped from the screen's state, so step 3 cannot show the PREVIOUS file's counts. Continuing on a stale preview is how somebody posts the wrong 600 rows |

**4 · Test Data** — Tenant Brazos Bend Utilities. File `brazosbend_reads_08A.csv`: 620 rows, published-template columns `meter_id, read_date, reading, channel, service, flags` (samples: `M-7001, 2026-08-03, 42864, total, E, Access ok`). Tags: Aug 2026 · 08-A (Aug 1–5 window) · All routes · Electric · Walk-by · hand-held collector. Manual rows: M-7108 / Aug 3, 2026 / total / 89,204; M-7109 / Aug 3, 2026 / total / 132,120; M-7110 / Aug 3, 2026 / total / 21,880. Actor: Marcus Vega (Billing Clerk). Isolation: `lsr_reads_08A.csv` (40 rows) by J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Source card | S28 step 1 | prototype-extracted (CSV/Manual/AMI) | **PROPOSED-SCHEMA** `read_import_batches.source_kind` (csv \| manual \| ami_replay) | enum | user-input | ami_replay disabled until B7 seam |
| Reading month | S28 step 1 | prototype-extracted | **PROPOSED-SCHEMA** `read_import_batches.period_month` | date (month) | user-input | required |
| Cycle / Route | S28 step 1 | prototype-extracted | **PROPOSED-SCHEMA** `read_import_batches.cycle_id` / `route_id` (null = all routes in cycle) | uuid | user-input | must exist, same tenant |
| Utility service | S28 step 1 | prototype-extracted (segment) | **PROPOSED-SCHEMA** `read_import_batches.service` | service_type \| null (=All) | user-input | tenant-enabled only |
| Read source (audit trail) | S28 step 1 | prototype-extracted (6 options) | `meter_reads.source` (B2 enum ami \| manual \| import) + **PROPOSED-SCHEMA** `read_import_batches.source_detail` (walk_by \| drive_by \| self_read \| field_visit \| ami_itron \| ami_sensus) | enum + text | user-input | B2 enum too coarse for the 6 UI options — detail column carries the full value |
| CSV file | S28 step 2 | prototype-extracted (≤10 MB UTF-8) + published template (BR-MET-032) | **PROPOSED-SCHEMA** `read_import_batches.file_name` / `file_hash` (SHA-256) | file/text | user-input | size, encoding |
| Column mapping | S28 step 2 | prototype-extracted + BR-MET-032 (OQ-040 CLOSED) | applied at parse; **re-detected each upload against the published template — never persisted** (no mapping memory, BR-MET-032) | — | user-input | meter/date/value required; channel optional (absent → `total`, BR-MET-059) |
| Channel (per row) | S28 step 2 | BR-MET-059 (PO RD-1) + B2 r8 | `read_import_rows.channel` → `meter_reads.channel` (B2 r8 enum total \| tou_on \| tou_mid \| tou_off \| export \| demand) | enum | user-input | valid enum value; defaults `total` |
| Staged rows | S28 | derived (no UI table name) | **PROPOSED-SCHEMA** `read_import_rows` (batch_id, row_no, meter_no_raw, asset_id resolved, read_at, channel — B2 r8 enum, value, service, note, parse/rule outcomes jsonb, disposition, disposition_reason) | — | system-derived | append-only within batch |
| Manual grid (Meter # / Date / Channel / Reading / Notes) | S28 step 2 | prototype-extracted + BR-MET-059 | same `read_import_rows` (plan-aware TOU/demand form = US-MET-017) | text/date/enum/numeric(18,6)/text | user-input | meter resolves; value ≥ 0; channel defaults `total` |

**6 · Acceptance**
- Given a tagged batch and a well-formed CSV, When Marcus reaches step 3, Then every row is staged with its effective tags (row overrides beating batch tags) and no read is visible anywhere else in the app — validation always runs before acceptance (BR-MET-032).
- Given a file with or without a channel column, Then every staged row carries an explicit channel (`total` default per BR-MET-059) — never a null or guessed channel.
- Given a missing required mapping or a bad file, When Continue is pressed, Then the step blocks with a specific reason.
- Given a subsequent upload, Then mapping re-detects against the published template with no memory of prior remaps (BR-MET-032).
- Given concurrent staging in two tenants, Then batches, rows and meter resolution never cross tenants.

**7 · Finance Calculation** — N/A

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-040 | CSV column-mapping persistence (save remap vs re-detect) | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-MET-032) — standard rules-based template import, validate-then-accept; no mapping memory (PO R7) |

---
id: US-MET-008
epic: EP-MET-03
module: metering
screens: [S28]
wave: 2
status: draft
blocked_by: []
depends_on: [US-MET-007, US-MET-011]
journeys: []
rules: [BR-MET-012, BR-MET-015, BR-MET-019, BR-MET-049, BR-MET-052]
golden_tests: []
finance_calc: none
---
### US-MET-008 — Validation run & staged review with per-row dispositions (steps 3–4)

**1 · Details** — As a billing clerk, I want every staged row validated against the rule set with a summary (rows / passed / warnings / errors / missing records) and a rule-outcomes table, then a Review & fix step where each flagged row gets a disposition — accept-with-reason, override the value, estimate (missing), reject, or schedule a field visit — with bulk "Accept all warnings" / "Estimate all missing", so that only clean or consciously-accepted reads go forward. Entry: step 2 Continue. The rules executed are EP-MET-04's engine (config-driven thresholds from the S64 tenant settings — BR-MET-020); this story owns *running them on staged rows and capturing dispositions*. Row severity per the **completed VEE catalog (BR-MET-052)**: Errors — negative usage (**hard error, never auto-fixed**), duplicate (key = meter+date+channel), unknown meter, read on a **retired** meter; Warnings — zero, high, low, days-out-of-window, out-of-cycle-window, multiplier mismatch, digit-count mismatch, read on a **vacant** unit; plus the **TOU sum-sanity** check (Σ windows ≈ total ±1%) over each meter's channel group and the **plan-driven completeness** computation (BR-MET-049) for the missing-record list. Exit: Continue → Compliance & post (US-MET-010).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-012 | *(shared)* all of this happens on the staged batch. | PROPOSED |
| BR-MET-015 | Severity model: **errors must be resolved** (reject, override to a valid value, or investigate-out of the batch) before the batch can post; **warnings may be accepted** only via an explicit disposition that records who/why (reason text or reason option); every row's disposition + reason is stored on the staged row and carried onto the posted read. Negative/rollover classification per the CONFIRMED rollover rule (OQ-009 CLOSED, PO R7 — GT-14): a full register wrap auto-computes rollover consumption (flagged for review); any other negative usage is a **hard error that is never auto-fixed** (BR-MET-052) — resolution is always a human disposition (investigate/override/reject). | PROPOSED (severity mechanics) — prototype step-3 pills + step-4 selects; rollover rule CONFIRMED (OQ-009 CLOSED); negative-usage hard error CONFIRMED (BR-MET-052) |
| BR-MET-052 *(shared — engine catalog in US-MET-011)* | Completed VEE catalog applied to staged rows: negative usage = hard error, never auto-fixed; read on a retired meter = error; read on a vacant unit = warning; TOU sum-sanity Σ(windows) ≈ total within ±1%; row-level duplicate rejection key = (meter, date, channel). | CONFIRMED — PO RD-5..8 (BR-MET-052) |
| BR-MET-049 | Completeness is plan-driven: the missing-record set = the unit-plan-required channel records (flat → `total`; TOU plan → per-window records + `total`; demand plan → +`demand`) not present as staged/committed rows for the cycle window; tracked per batch here and enforced as a VEE gate before billing. | CONFIRMED — PO RD-2 (BR-MET-049) |
| BR-MET-019 | At commit each accepted row computes `consumption = (current_value − prior_value) × multiplier` in NUMERIC(18,6) with an explicit unit, unrounded (rounding only at invoice-line finalization); prior = latest committed read for the meter **and channel** (B2 r8); water registers store raw gallons — billed-unit handling per the OQ-004 closure: unit must match or a conversion factor is defined (`tenant_services.billed_uom` + `conversion_factor`, B2 r6.4); mismatch without a factor blocks rating with a user message; kgal default. | CONFIRMED — B4 Consumption (+B4.4 multiplier-before-tiers); water unit per OQ-004 CLOSED (PO R6) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Run validation on the §4 batch | KPIs: Rows 620 · Passed 596 · Warnings 20 · Errors 4 · Missing records 28 (14 meters); rule-outcomes table lists hits per rule with severity pills |
| TC-2 | High-usage warning row M-7204 (438,240 vs prior 412,000; 312% of average) | Listed with rule "High usage"; disposition options Accept · flag hi-usage / Override value / Reject |
| TC-3 | Marcus bulk-clicks "Accept all warnings" then sets row-level reason "verified against route sheet" | All 20 warnings → accepted; each row stores disposition + reason + actor |
| TC-4 | Missing-record list (plan-driven, BR-MET-049) | Rendered as expected meter×channel records minus batch/committed rows: 28 records over 14 meters — 8 flat meters missing `total`, 4 TOU meters (M-7451..M-7454) missing their full window sets (tou_on/tou_mid/tou_off + total), 2 demand meters (M-7461, M-7462) missing `total` + `demand`; dispositions Estimate (per channel — EP-MET-05) / Skip cycle / Schedule field visit |
| TC-5 *(negative)* | Attempt Continue with error row M-7823 (current 88,102 < prior 88,204 — no register wrap → negative usage, a HARD error per BR-MET-052) unresolved | Blocked: "errors need a resolution"; no auto-fix exists or is offered (BR-MET-052 — never auto-fixed); the row's options are Investigate (meter replacement?) / Override value / Reject |
| TC-6 *(negative)* | Override M-7823's value to 88,102 with no reason text | Save of the override blocked — reason required |
| TC-7 | Reject row 530 (duplicate) with reason "already posted in 08-A" | Row disposition `rejected` + reason; excluded from the post composition; retained in the batch record |
| TC-8 *(negative)* | Unknown meter `M-9999` in a row | Error "not in inventory"; resolutions: fix meter id (remap/override) or Reject — never auto-create a meter |
| TC-9 *(isolation)* | Same meter number `M-7001` exists in both tenants | Brazos Bend validation resolves only Brazos Bend's M-7001; prior values never read from the other tenant (RLS) |
| TC-10 *(negative)* | Row for meter M-7702, retired Jun 15, 2026 (assets status `retired`) | Error "read on retired meter" (BR-MET-052); resolutions fix meter id or Reject — never posts against a retired asset |
| TC-11 | TOU group M-7450 staged: usage deltas tou_on 210 + tou_mid 118 + tou_off 96 = 424 vs total 430 | Deviation \|430 − 424\| ÷ 430 = 1.40% > 1% → group flagged `tou_sum_sanity` (BR-MET-052) with Σ, total, deviation stored; disposition required on the group before post |
| TC-12 | Row for M-7115 on unit 4B (vacant — no active account, occupancy derived per BR-MET-036) | Warning `vacant_unit` (BR-MET-052); postable only via explicit accept-with-reason (BR-MET-015) |

**4 · Test Data** — Batch from US-MET-007 §4. Flagged fixtures: M-7204 (W, prior 412,000 → 438,240 raw gal = 26.24 kgal, high 312%); M-7823 (E, 88,204 → 88,102, negative usage — hard error, no wrap); M-7110 (W, 18,240 → 18,240, zero); M-7305 (E, 4,120 → 4,142 = 22 kWh, low 18%); M-7610 (E, 52 days since prior, days warning); M-7210 (E, ×10 factor, raw 2,754 → computed 27,540 kWh, factor warning); row 530 duplicate of M-7001 Aug 3 `total`; M-7702 (retired Jun 15, 2026); M-7115 (unit 4B vacant); TOU M-7450 (E, kWh — deltas tou_on 210 / tou_mid 118 / tou_off 96 / total 430 → sum-sanity 1.40%). Missing (Route 3, plan-driven): 28 records over 14 meters = 8 flat (incl. M-7612, M-7613) + 4 TOU (M-7451..M-7454) + 2 demand (M-7461, M-7462). Consumption check: M-7001 (42,180 → 42,864, ×1, `total`) = 684.000000 kWh.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Validation KPIs | S28 step 3 | prototype-extracted | computed over `read_import_rows` | integers | computed-display | — |
| Rule outcomes per row | S28 step 3/4 | prototype-extracted (rule table) + BR-MET-052 catalog | **PROPOSED-SCHEMA** `read_import_rows.rule_outcomes` jsonb (rule, severity, detail) | jsonb | system-derived | rules & thresholds from EP-MET-04's S64 tenant config |
| Severity | S28 step 3 | prototype-extracted (Warning/Error pills) + BR-MET-052 | derived within `rule_outcomes` | enum | system-derived | per BR-MET-015; negative usage/retired = error, vacant = warning (BR-MET-052) |
| Channel (per row) | S28 | BR-MET-059 / B2 r8 | `read_import_rows.channel` | enum | user-input | duplicate key (meter, date, channel) — BR-MET-052 |
| TOU sum-sanity outcome | S28 step 3/4 | BR-MET-052 | within `rule_outcomes` (rule = tou_sum_sanity: Σ windows, total, deviation %, tolerance ±1%) | jsonb | system-derived | evaluated per meter channel group when full window set + total present |
| Disposition + reason | S28 step 4 | prototype-extracted (action selects) | **PROPOSED-SCHEMA** `read_import_rows.disposition` (accept \| accept_with_flag \| override \| estimate \| reject \| field_visit \| skip) + `disposition_reason` + `disposed_by` | enum/text/uuid | user-input | errors: no plain accept; reason required for accept-warning/override/reject |
| Override value | S28 step 4 | prototype-extracted ("Override value") | `read_import_rows.value` (new) + original preserved in `raw_value` (**PROPOSED-SCHEMA**) | numeric(18,6) | user-input | ≥ 0; reason required |
| Prior value | S28 step 4 | prototype-extracted ("Prior") | `meter_reads.prior_value` ← latest committed read for the same meter **and channel** (B2 r8) | numeric(18,6) | system-derived | same meter+channel, same tenant |
| Usage (preview) | S28 step 4 | prototype-extracted | `(current − prior) × multiplier` preview; committed to `meter_reads.consumption` | numeric(18,6) + explicit `unit` | computed-display → system-derived | B4 formula; unrounded |
| Missing-record set | S28 step 3/4 | prototype-extracted + BR-MET-049 | expected meter×channel records (plan-driven required set) minus staged/committed rows | — | computed-display | flat → total; TOU → windows + total; demand → +demand |

**6 · Acceptance**
- Given the staged batch, When validation runs, Then every row carries machine-readable rule outcomes and the KPI counts reconcile with the row set.
- Given unresolved errors, When Continue is pressed, Then the step blocks naming the count; Given each error resolved (override-with-reason / reject / investigate), Then it unblocks.
- Given the completed catalog (BR-MET-052), Then negative-usage rows are never auto-fixed, retired-meter rows error, vacant-unit rows warn, and TOU channel groups breaching the ±1% sum-sanity are flagged for a disposition.
- Given the plan-driven required sets (BR-MET-049), Then the missing list counts records (meter × channel), never bare meters.
- Given accepted warnings, Then each stores disposition, reason and actor, And rejected rows are excluded from the composition but retained with reasons.

**7 · Finance Calculation** — N/A (consumption is quantity arithmetic per B4's confirmed formula, no currency; pricing of consumption is rating's GT-1/GT-2/GT-5 territory).

**8 · Open Questions** — None minted (rollover per pre-existing OQ-009 — CLOSED, GT-14 rule confirmed; thresholds per pre-existing OQ-002 — CLOSED, S64 tenant settings — referenced, not duplicated).

---
id: US-MET-009
epic: EP-MET-03
module: metering
screens: [S28]
wave: 2
status: draft
blocked_by: []
depends_on: [US-MET-008]
journeys: []
rules: [BR-MET-016, BR-MET-017, BR-MET-052, BR-MET-053]
golden_tests: []
finance_calc: none
---
### US-MET-009 — Duplicate-vs-committed detection & replace-as-correction

**1 · Details** — As a billing clerk, I want any staged row that matches a read already **committed** for the same meter, read date **and channel** (BR-MET-052; B2 r8 UNIQUE (asset, read_at, channel)) — or the same meter+channel within the same cycle — flagged as a duplicate error with the existing read shown, and a Replace-existing path that supersedes the old read with a new row instead of editing it, so that double uploads never double-post and corrections keep history. Entry: runs inside step 3/4 validation (US-MET-008); prototype row 530: "Error · duplicate (exists 08-A)" with options Reject / Replace existing. Exit: disposition recorded; replacement takes effect only at commit (US-MET-010). The full supersede/correction lifecycle (incl. the BILLED lock and J6 routing) is US-MET-016 — this story is the import-side entry into it.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-016 | Duplicate-vs-committed: a staged row whose meter matches a committed `meter_reads` row at the same read date **and channel** — or that would create a second read for the meter+channel in the same cycle window with an unchanged value — is an **error**; resolutions are Reject (default) or **Replace existing**, which appends a superseding read row linked from the original via `superseded_by_id`/`superseded_at` (B2 r8 — CONFIRMED columns) — committed reads are never UPDATEd or DELETEd; downstream consumers (billing pickup, S25) read the read *lineage head* only. Duplicates *inside* one staged batch (same meter+date+channel twice in the file) are also errors, resolved by keeping exactly one row. | CONFIRMED (key + supersede) — BR-MET-052/BR-MET-053 (PO RD-5..10) + B2 r8; UI mechanics per prototype step-3/4 |
| BR-MET-052 *(dup clause, shared)* | Row-level duplicate rejection key = (meter, date, channel). | CONFIRMED — PO RD-5..8 (BR-MET-052) |
| BR-MET-053 *(shared — full flow US-MET-016)* | Corrections = SUPERSEDE (new row, original kept visible), never edit; B2 r8 `superseded_by_id uuid NULL` + `superseded_at` are the only UPDATE ever permitted on a committed row. | CONFIRMED — PO RD-9/10 (BR-MET-053) + B2 r8 |
| BR-MET-017 | *(shared with US-MET-010)* every read row links to its import batch; the compliance stamp identifies who introduced a replacement. | PROPOSED |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Batch contains M-7001 · Aug 3 · `total` · 42,864 — identical to a committed read (same meter+date+channel) | Error "duplicate (exists 08-A)"; drawer/expand shows the committed read (value, channel, batch, uploaded by); options Reject / Replace existing |
| TC-2 | Marcus rejects it | Row disposition `rejected` + reason; commit posts nothing for M-7001; committed read untouched |
| TC-3 | Batch contains M-7001 · Aug 3 · `total` · **42,876** (corrected value); Marcus chooses Replace existing with reason "collector re-read — keying error" | At commit: new `meter_reads` row v2 (42,876) appended; original v1 intact with `superseded_by_id` → v2 + `superseded_at` (B2 r8); S25/billing resolve M-7001's Aug `total` read to v2; audit row `read.superseded` with before/after |
| TC-4 | File itself lists M-7420 twice (same date + channel `total`, different values) | Intra-batch duplicate error (key meter+date+channel); must keep exactly one row (choose/merge) before posting |
| TC-5 *(negative)* | Attempt to post with the TC-1 duplicate unresolved | Blocked by BR-MET-015 (errors need resolution) |
| TC-6 *(negative)* | Direct API `UPDATE`/`DELETE` on the committed read | Rejected — append-only enforcement; the only permitted UPDATE on a committed row sets `superseded_by_id`/`superseded_at` (B2 r8); only the supersede path exists |
| TC-7 *(isolation)* | Lone Star Ridge commits a read for *their* M-7001 · Aug 3 · `total` | No duplicate flag in the Brazos Bend batch — duplicate detection is tenant-scoped |
| TC-8 | Batch contains M-7450 · Aug 3 · `tou_on` while a committed read exists for M-7450 · Aug 3 · `total` | **No duplicate** — the key is (meter, date, channel) (BR-MET-052); both records coexist per the channel model (B2 r8) |

**4 · Test Data** — Committed: M-7001 · Aug 3, 2026 · `total` · 42,864 · batch B-2608-01 (posted by Dana, Aug 3). New file rows per TCs. Reasons: "already posted in 08-A", "collector re-read — keying error". Lineage: v1 42,864 → v2 42,876 (v1.`superseded_by_id` = v2.id, `superseded_at` Aug 6, 2026); consumption recomputed on v2 = (42,876 − 42,180) × 1 = 696.000000 kWh. Channel fixture: M-7450 committed `total` Aug 3 + incoming `tou_on` Aug 3 (no conflict).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Duplicate rule hit | S28 step 3/4 | prototype-extracted ("meter+date exists") + BR-MET-052 (key incl. channel) | `read_import_rows.rule_outcomes` (rule = duplicate, ref = committed read id) | jsonb | system-derived | tenant-scoped match on (meter, date, channel) |
| Existing-read reference | S28 step 4 | prototype-extracted ("exists 08-A") | committed `meter_reads` (tenant_id, read_at, id) | — | computed-display | read-only |
| Replace existing | S28 step 4 | prototype-extracted (option) + BR-MET-053 | new `meter_reads` row (lineage head) + `meter_reads.superseded_by_id` / `superseded_at` set on the old row (**B2 r8 — CONFIRMED**; the only UPDATE allowed on a committed row); reverse link derives by querying `superseded_by_id` — no extra column | uuid / timestamptz | user-input → system-derived | reason required; original otherwise immutable |
| Supersede audit | — | derived (CLAUDE.md #7 spirit) | `audit_log` (`read.superseded`, before/after values, actor) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a staged row matching a committed read on (meter, date, channel), When validation runs, Then it errors with the committed read displayed, And posting is impossible until it is rejected or replaced.
- Given Replace existing with a reason, When the batch commits, Then a superseding row exists, the original is unchanged apart from its `superseded_by_id`/`superseded_at` closure (B2 r8) and chained, consumption is recomputed on the head, and an audit row records the correction.
- Given the same meter+date on a **different channel**, Then no duplicate fires (BR-MET-052 key).
- Given the same meter number in another tenant, Then it never triggers or receives a duplicate match.

**7 · Finance Calculation** — N/A

**8 · Open Questions** — None.

---
id: US-MET-010
epic: EP-MET-03
module: metering
screens: [S28, S29]
wave: 2
status: draft
blocked_by: []
depends_on: [US-MET-008, US-MET-009, US-TEN-012]
journeys: [J2]
rules: [BR-MET-015, BR-MET-017, BR-MET-018, BR-MET-019, BR-MET-053, BR-MET-055]
golden_tests: []
finance_calc: none
---
### US-MET-010 — Compliance stamp & atomic commit (step 5)

**1 · Details** — As a billing clerk (with finance looking over my shoulder), I want step 5 to show the full compliance stamp — batch ID, source + file name, SHA-256 file hash, uploaded by, uploaded at, session + IP — plus the batch composition (accepted / warnings-accepted / estimated / rejected / field-visit counts and total to post), a certification checkbox, and a **Post batch** that commits atomically, so that every posted read is traceable end-to-end (visible later in the S29 drawer's Compliance metadata block). Entry: step 4 Continue. Commit: all dispositioned rows post in one transaction — accepted/overridden/estimated rows become `meter_reads` (one row per meter × date × channel, B2 r8), rejected/field-visit rows are recorded on the batch only; per prototype "Posting is atomic — either every row is accepted or the batch is rejected." Posting executes as an **async job** (BR-MET-055 — async imports) with progress surfaced in the wizard — still atomic: the job either commits every dispositioned row or nothing. Committed rows enter lifecycle state `committed` (BR-MET-053: staged → ok/flagged/estimated → committed → BILLED(locked); the BILLED lock is applied when a bill run consumes the read, enforced at the service layer per B2 r8 — correction path beyond that is US-MET-016). An identical re-submission (same file hash + tag set) is **blocked** per the OQ-044 closure (option b). Exit: toast → S25 with the new reads visible; batch status `posted`.

**BUILT 2026-08-15 (DEF-115) — three promises this step does NOT make, because the server does not keep them.** *(a)* **The commit is SYNCHRONOUS on this deployment.** BR-MET-055 asks for a background job with progress; `services.commit_read_batch` runs it inside the request and says why in its own docstring (no BE-07 job store is registered), and it answers `async: false`. The screen renders a working state on a blocking call and states that in words — a progress bar over a blocking call would be a picture of something that is not happening. ⚠ **(a) SUPERSEDED 2026-09-30 (`DEF-MET-8106`, `2.411.2`)** — the job store had been registered since 2026-08-10, and 480 readings then took ~60 s in the request and died at the web worker's timeout after they were saved. A batch of more than 200 staged rows now posts as a background job: the post answers 202, stage 4 draws the job's *Posting N of M*, and the receipt is collected from `GET /read-batches/{id}/post-receipt`. At or below 200 the post is synchronous exactly as described above. TC-9 below is now covered by `tests/test_def_met_8106_read_post_job.py`. *(b)* **No supervisor co-sign control.** OQ-042 closed as a tenant toggle, default ON; no endpoint serves or stores that setting and nothing writes `read_batch_dict`'s `cosigned_by`, so the checkbox would change nothing. Named in an arrives-with block instead. *(c)* **No Finance receipt email.** The prototype's default-on checkbox needs a cross-module call into notifications that no endpoint on this path makes; the batch record IS the receipt and it is permanent. **What the step DOES insist on: "N created · N failed", always, both figures with equal weight** — `posted_reads` and `counts.rows − posted_reads`, computed from the server's own reconciling counts — plus the per-bucket breakdown. A partial success that reads as a success is the defect BR-MET-038's sibling rule exists to prevent. **And there is no usage figure anywhere on a staged row:** consumption is computed HERE, at commit, from the meter (`unit=asset.unit`), so a staged row carries neither a quantity nor a unit and printing one would break CLAUDE.md rule 3. The committed reading shows its usage WITH its unit on S25, one click later.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-015 | *(shared)* commit is only reachable with zero unresolved errors. | PROPOSED |
| BR-MET-017 | Compliance stamp: every batch permanently records batch number (tenant numbering), source kind + detail, file name + SHA-256 hash, uploaded_by (user), uploaded_at (UTC, rendered in tenant TZ), session id + IP, and the certification acknowledgement; every posted read links to its batch (`meter_reads.import_batch_id`, PROPOSED-SCHEMA); posted reads are append-only ("v1 · immutable" per S29) — corrections only via the supersede path (BR-MET-053/US-MET-016) or estimation true-up (EP-MET-05). | PROPOSED — prototype step 5 + S29 compliance block + B2 `meter_reads.imported_by` |
| BR-MET-018 | Re-submitting an identical batch must not double-post — **idempotency = file hash + tag set (option b, OQ-044 CLOSED, PO R8)**: on match, the commit is **BLOCKED** with a message naming who posted the original, when, and a link to that batch. Exact key mechanics remain human-owned (Eng Lead 🔒, per CLAUDE.md "do not touch idempotency keys") — agents scaffold the check, never redefine the key. | CONFIRMED (policy — OQ-044 CLOSED, option b); key mechanics Eng-Lead-owned 🔒 |
| BR-MET-019 | *(shared)* consumption computed at commit per B4, per channel (prior = latest committed read of the same meter+channel). | CONFIRMED (formula) |
| BR-MET-053 *(shared — full flow US-MET-016)* | Commit moves rows into lifecycle state `committed` (staged → ok/flagged/estimated → committed → BILLED(locked)); corrections beyond commit are supersede-only. | CONFIRMED — PO RD-9/10 (BR-MET-053) |
| BR-MET-055 *(async clause)* | Imports execute asynchronously (no synchronous unbounded request); posting runs as a background job with progress, preserving the atomic all-or-nothing semantics. | CONFIRMED — PO RD-13 (BR-MET-055) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Marcus posts the §4 batch (596 accepted + 20 warnings-accepted + 11 estimated; 3 rejected; 3 field visits) | One transaction: 627 `meter_reads` rows (each with import_batch_id, source, **explicit channel — B2 r8**, lifecycle state `committed`, status, disposition reason where present); batch B-2608-04 → `posted`; composition table matches exactly; toast; audit `read_batch.posted` |
| TC-2 | Open a posted read in S29 | Compliance metadata shows batch id, source + file, hash `a3f4…8291`, "Uploaded by Marcus Vega", timestamp in America/Chicago, session + IP, rule outcomes, "v1 · immutable" |
| TC-3 | Commit fails midway (simulated DB error at row 400) | Transaction rolls back — zero reads posted, batch stays `staged`, error surfaced with retry (A18); no partial batch ever visible |
| TC-4 *(negative)* | Post without the certification checkbox | Blocked — certification required before Post batch enables |
| TC-5 *(negative)* | Marcus re-uploads the same file with the same tags after TC-1 | File hash + tag set match → commit **BLOCKED** with "already posted by Marcus Vega on Aug 6, 2026" + link to batch B-2608-04 (OQ-044 closure, option b); no double-post path exists |
| TC-6 *(negative)* | Tampered replay: same file name, one changed row | Hash differs → treated as a new batch; per-row duplicate detection (BR-MET-016, key meter+date+channel) still catches overlapping rows |
| TC-7 | Supervisor co-sign ("batch > 500 rows or any errors") | Tenant toggle, default ON (OQ-042 closure); when enabled, posting blocks until a System Admin or Executive co-signs; the co-sign is recorded on the batch |
| TC-8 *(isolation)* | Posted Brazos Bend batch queried from Lone Star Ridge session | Batch, rows and reads invisible; isolation suite asserts zero cross-tenant ids |
| TC-9 | 620-row batch posts via the async job path (BR-MET-055) | Post batch enqueues the job; wizard shows progress then completion; TC-3's semantics hold identically mid-job (atomic — no partially visible batch at any point) |
| TC-10 *(built 2026-08-15)* | Marcus posts a one-row batch on a deployment with no background worker | The commit runs inside the request and the result panel reads **Readings created 1 · Rows that did not become readings 0**, with the per-bucket breakdown beside it and a line stating the posting ran here and now rather than in the background. The reading is then on S25 **with its unit** |
| TC-11 *(built 2026-08-15)* | Marcus looks for the supervisor co-sign and the Finance-receipt checkboxes the prototype draws | Neither is drawn. Each is replaced by a stated reason: the co-sign setting has no storage and no endpoint records a co-signature; the receipt needs a notifications call no endpoint on this path makes |

**4 · Test Data** — Batch B-2608-04 · `brazosbend_reads_08A.csv` · SHA-256 `a3f4c19e…8291` · uploaded by Marcus Vega (`marcus@brazosbendutilities.com`) · Aug 6, 2026 09:14:22 CT · session `sess_9f27` · IP 98.200.114.7. Composition per TC-1. Batch numbering per tenant series (EP-TEN-08 style): `B-2608-04`. Co-signer: Dana Whitfield (System Admin).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Batch ID | S28 step 5 / S29 | prototype-extracted (`B-2608-04`) | **PROPOSED-SCHEMA** `read_import_batches.batch_no` | text | system-derived | tenant series |
| File hash | S28 step 5 / S29 | prototype-extracted (SHA-256) | **PROPOSED-SCHEMA** `read_import_batches.file_hash` | text (sha256 hex) | system-derived | computed server-side; part of the file+tags idempotency check (OQ-044 closure — key mechanics Eng-Lead 🔒) |
| Uploaded by / at | S28 step 5 / S29 | prototype-extracted | `meter_reads.imported_by` (B2) + **PROPOSED-SCHEMA** `read_import_batches.uploaded_by` / `uploaded_at` | uuid / timestamptz UTC | system-derived | actor from session, never client input |
| Session · IP | S28 step 5 / S29 | prototype-extracted | **PROPOSED-SCHEMA** `read_import_batches.session_ref` / `ip` | text / inet | system-derived | — |
| Certification | S28 step 5 | prototype-extracted (checkbox) | **PROPOSED-SCHEMA** `read_import_batches.certified_by_uploader` | boolean | user-input | required to post |
| Supervisor co-sign | S28 step 5 | prototype-extracted + OQ-042 closure (optional tenant toggle, default ON; supervisor = SysAdmin/Executive; blocks when enabled) | **PROPOSED-SCHEMA** `read_import_batches.cosigned_by` uuid NULL + tenant setting | boolean/uuid | user-input | required before post when the tenant toggle is ON; co-signer role SysAdmin/Executive |
| Email batch receipt to Finance | S28 step 5 | prototype-extracted (default on) | dispatch via notifications module (⚠ cross-module service call) | boolean | user-input | send only on successful post |
| Composition counts | S28 step 5 | prototype-extracted | computed over row dispositions; denormalized **PROPOSED-SCHEMA** `read_import_batches.counts` jsonb | jsonb | computed-display → system-derived | must reconcile with rows |
| Async job execution | S28 step 5 | BR-MET-055 (async imports) | background job (queue) wrapping the commit transaction | — | system-derived | atomic; progress surfaced; no partial visibility |
| Posted reads | — | derived + B2 r8 | `meter_reads` (read_at, **channel — B2 r8**, prior_value, current_value, consumption, unit, source, status, days_since_prior, imported_by) + **PROPOSED-SCHEMA** `meter_reads.import_batch_id`; lifecycle `committed` per BR-MET-053 (BILLED lock later at service layer, B2 r8) | per B2 | system-derived | atomic transaction; append-only; UNIQUE (asset, read_at, channel) |

**6 · Acceptance**
- Given a fully dispositioned batch, When Post batch runs, Then all-and-only the accept/override/estimate rows exist as reads in one transaction, each carrying the batch linkage and an explicit channel, And the batch record holds the complete compliance stamp verifiable later from S29.
- Given the commit, Then every posted row is in lifecycle state `committed` (BR-MET-053); the BILLED lock and the correction path beyond commit are US-MET-016's contract.
- Given a mid-commit failure — including mid-async-job — Then nothing posted and the batch remains staged.
- Given an identical re-upload (same file hash + tag set), Then the commit is blocked with who/when/link to the original batch (OQ-044 closure, option b) — no double-post path exists.
- Given the co-sign toggle ON and a qualifying batch, Then posting blocks until a System Admin or Executive co-signs (OQ-042 closure).

**7 · Finance Calculation** — N/A

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-042 | Supervisor co-sign for read batches | Nothing — closed | Product Owner (chat session) | CLOSED — optional tenant toggle, default ON; supervisor = SysAdmin/Executive; blocks posting when enabled (PO R6) |
| OQ-044 | Read-import idempotency key definition + collision behavior | Nothing — closed (key mechanics with Eng Lead 🔒) | Product Owner (chat session) | CLOSED — option (b): file+tags idempotency; commit blocked with who/when/link message; exact key mechanics Eng-Lead-owned (PO R8) |

---
id: US-MET-017
epic: EP-MET-03
module: metering
screens: [S28]
wave: 2
status: draft
blocked_by: []
depends_on: [US-MET-007, US-MET-008, US-RAT-006, US-RAT-007]
journeys: [J2]
rules: [BR-MET-049, BR-MET-052, BR-MET-059]
golden_tests: []
finance_calc: none
---
### US-MET-017 — Channel-based manual entry for TOU/demand meters

**1 · Details** — As a billing clerk reading TOU and demand meters, I want the S28 single-entry form and the bulk upload to accept **one row per channel** (BR-MET-059: meter · date · channel · value), with the entry form pre-building the unit's **plan-driven required-channel set** (BR-MET-049: TOU plan → tou_on/tou_mid/tou_off + total; demand plan → +demand) and the **TOU sum-sanity check** (BR-MET-052: Σ windows ≈ total ±1%) running on save, so that multi-register meters land complete and internally consistent instead of as loose single numbers. Entry: S28 step 2 — the manual grid (US-MET-007) gains a plan-aware form: picking a meter whose unit plan is TOU/demand renders exactly the required channel rows; the CSV path uses the template's `channel` column (US-MET-007/TC-1). Demand rows capture the manual demand-register value at cycle read with the register reset noted (BR-MET-051 — cited as confirmed context). Flat meters are unchanged: a single `total` row (BR-MET-059). Sum-sanity evaluates on the entered usage deltas and only when the full window set + total are present (it cannot be computed otherwise); a failing group is flagged and requires a disposition in steps 3–4 (BR-MET-015 path, US-MET-008). Exit: staged rows per channel → validation → commit. Handoff (J2 step 5): commit leaves one committed `meter_reads` row per (meter, date, channel) — the channel model generalizes J2's read_type note per BR-MET-059.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-059 | Channel model (RD-1 Option B): every register read is one record — meter, date, `channel` (total \| tou_on \| tou_mid \| tou_off \| export \| demand — extensible), value, status; flat meter = single `total` channel; new register kinds = new channel values, never schema changes. B2 r8: UNIQUE (asset, read_at, channel). | CONFIRMED — PO RD-1 Option B (BR-MET-059) + B2 r8 |
| BR-MET-049 | Plan-driven read set: the unit's plan determines the required channel set per meter (TOU plan → per-window records + `total`; demand plan → +`demand` record — the demand value entered manually at cycle read with reset noted, per BR-MET-051); the entry form renders exactly this set; completeness is enforced as a VEE gate before billing. | CONFIRMED — PO RD-2 (BR-MET-049); demand entry PO RD-4 (BR-MET-051) |
| BR-MET-052 | TOU sum-sanity: Σ(tou_on + tou_mid + tou_off) ≈ total within ±1%, checked over the entered channel group; row-level duplicate rejection key = (meter, date, channel). | CONFIRMED — PO RD-5..8 (BR-MET-052) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Unit 12A (TOU plan "Residential TOU"), meter M-7450, Aug 3, 2026: entry form opens | Form renders exactly 4 required rows — tou_on, tou_mid, tou_off, total (BR-MET-049); Marcus enters registers 13,210 / 8,946 / 22,406 / 44,562 (deltas 210 / 118 / 96 / 424); Σ windows 424 = total 424 → sum-sanity passes (0.0%); 4 staged rows, one per channel |
| TC-2 | Unit 2C (demand plan "Small Commercial Demand"), meter M-7460 | Form adds a `demand` row: value 42.600000 kW (explicit unit) + "register reset noted" checkbox (BR-MET-051); staged rows = total + demand |
| TC-3 | Bulk CSV rows `M-7450,2026-08-03,13210,tou_on` / `…,8946,tou_mid` / `…,22406,tou_off` / `…,44562,total` | Each row stages as its own `read_import_rows` row keyed by channel; sum-sanity evaluated over the group in step 3 exactly as for form entry |
| TC-4 *(negative)* | TOU group with total register 44,568 (delta 430) vs Σ windows 424 | Deviation \|430 − 424\| ÷ 430 = 1.40% > 1% → group flagged `tou_sum_sanity` on save (BR-MET-052); a disposition is required in steps 3–4 before the batch can post (BR-MET-015) |
| TC-5 *(negative)* | Second row M-7450 · Aug 3 · tou_on entered when one is already committed | Duplicate error keyed (meter, date, channel) — BR-MET-052; the same date on a *different* channel is never a duplicate |
| TC-6 | Partial entry: only tou_on entered for M-7451, other rows left blank | 1 row stages; nothing invented for the blank channels; sum-sanity not evaluated (full set absent); the unit surfaces in the chase list missing tou_mid/tou_off/total (BR-MET-049 — US-MET-018) and the completeness gate holds billing |
| TC-7 *(negative)* | CSV row with channel `tou_evening` | Parse error "unknown channel" (enum per B2 r8); never coerced to a valid value (BR-MET-032 validate-then-accept) |
| TC-8 *(isolation)* | J. Okafor enters TOU reads for Lone Star Ridge meter LSR-201 | Plan lookup, required-channel derivation and duplicate checks resolve only within Lone Star Ridge's `app.tenant_id`; no Brazos Bend plan or read is touched |

**4 · Test Data** — Brazos Bend unit 12A (premise Cane Island Apts), plan "Residential TOU" (windows On/Mid/Off per US-RAT-006 config); meter M-7450 (E, ×1, kWh) registers: tou_on prior 13,000 → 13,210; tou_mid 8,828 → 8,946; tou_off 22,310 → 22,406; total 44,138 → 44,562. Bad-sum variant: total register 44,568 (delta 430 vs Σ 424 → 1.40%). Demand: unit 2C, plan "Small Commercial Demand", meter M-7460, demand value 42.600000 kW read Aug 3, 2026, reset noted ✓. Partial-entry meter M-7451 (TOU). Actor: Marcus Vega. Isolation: Lone Star Ridge unit L-3, meter LSR-201 (TOU), J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Channel (per row) | S28 step 2 | BR-MET-059 (PO RD-1) + B2 r8 | `read_import_rows.channel` → `meter_reads.channel` (enum total \| tou_on \| tou_mid \| tou_off \| export \| demand) | enum | user-input | valid enum; UNIQUE (asset, read_at, channel) at commit |
| Required-channel set | S28 entry form | BR-MET-049 | derived: unit → `unit_plan_assignments` → rate_plan → tariff model (TOU windows / demand config — ⚠ cross-module read of rating config, reviewed interface) | — | computed-display | TOU → windows + total; demand → +demand; flat → total |
| Register value per channel | S28 | prototype grid + BR-MET-059 | `read_import_rows.value` | numeric(18,6) + explicit unit | user-input | ≥ 0 |
| Sum-sanity result | S28 save / step 3 | BR-MET-052 | `read_import_rows.rule_outcomes` (rule = tou_sum_sanity: Σ windows, total, deviation %, tolerance ±1%) | jsonb | system-derived | evaluated only when full window set + total present |
| Demand reset note | S28 | BR-MET-051 (PO RD-4) | **PROPOSED-SCHEMA** `read_import_rows.demand_reset_noted` boolean (carried to the posted demand read) | boolean | user-input | demand channel only |

**6 · Acceptance**
- Given a TOU-plan unit, When the entry form opens, Then exactly the plan-driven channel set renders, And a complete save stages one row per channel with sum-sanity evaluated and stored.
- Given a channel group failing the ±1% sum-sanity, Then the group is flagged and cannot post without an explicit disposition.
- Given a duplicate (meter, date, channel), Then the row errors; the same date on a different channel never does.
- Given a partial entry, Then only the entered channels stage, nothing is invented, and the completeness gate (BR-MET-049) reports the gap.
- Given two tenants, Then plan derivation, duplicates and staging never cross `app.tenant_id`.

**7 · Finance Calculation** — N/A — no money math (register/consumption quantities only; pricing of TOU windows and demand is rating's territory per B4).

**8 · Open Questions** — None.

---
id: US-MET-018
epic: EP-MET-03
module: metering
screens: [S25, S27]
wave: 2
status: draft
blocked_by: []
depends_on: [US-MET-005, US-MET-006, US-MET-010, US-MET-017]
journeys: [J2]
rules: [BR-MET-049, BR-MET-057]
golden_tests: []
finance_calc: none
---
### US-MET-018 — Cycle completeness bar + chase list

**1 · Details** — As a billing clerk during a read window, I want every cycle to show its read-window expectations and a **completeness bar** — expected required records (plan-driven, per meter × channel) vs collected — plus a **chase list** of units still missing required channels, with export and chase actions (Estimate → EP-MET-05, Schedule field visit), so that I chase the right meters before the bill date instead of discovering the gaps inside the billing run. Entry: S25 header roll-up ("Cycle 08-A · N expected · N collected · N pending") expands into the completeness bar + chase list; S27 cycle rows link the same view per cycle. Expectations derive from the **cycle read-window** (BR-MET-057) over the cycle's route membership (BR-MET-033/BR-MET-010 — context) crossed with the **required channel set per unit plan** (BR-MET-049: flat → total; TOU → windows + total; demand → +demand); a unit with no plan contributes no required records (the plan determines the set — BR-MET-049). Collected counts committed lineage heads only (BR-MET-016/053 — a superseded read and its replacement count once). This is the same computation the VEE completeness gate uses before billing (BR-MET-049). Exit: chase actions record the existing dispositions (no new write paths); Export downloads the chase list CSV (IS-9).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-057 | The cycle read-window drives expectations; each cycle carries a per-cycle completeness bar + chase list. Expectations count only within the window — before window open there is nothing to chase. | CONFIRMED — PO RD-15 (BR-MET-057) |
| BR-MET-049 | Expected set = Σ over the cycle's route-member units of the plan-driven required channel records; completeness % = collected required records ÷ expected required records; the same set is enforced as a VEE gate before billing (metering computes, billing decides the consequence). | CONFIRMED — PO RD-2 (BR-MET-049) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Cycle 08-A (window Aug 1–5), §4 seed, viewed Aug 4 | Expected 762 required records · collected 734 → completeness bar 96.3% (734 ÷ 762); pending = 14 meters / 28 missing records; figures reconcile exactly with the S25 header roll-up (US-MET-012) |
| TC-2 | Open the chase list | 14 rows: Unit · Premise · Meter · Route · Service · Missing channels · Days left (1 — window ends Aug 5); e.g. "Unit 3F · Cane Island Apts · M-7451 · Route 3 · E · tou_on, tou_mid, tou_off, total · 1 day" |
| TC-3 | Chase actions on a row | Estimate routes to EP-MET-05's per-channel disposition; Schedule field visit records the field-visit disposition — no read row is invented (existing write paths only, BR-MET-023/IS-6) |
| TC-4 | Export | Chase-list CSV (IS-9) with exactly the listed rows and columns |
| TC-5 | Unit 9C has a metered service but no plan and no active account | Contributes 0 expected records and never appears in the chase list (BR-MET-049 — no plan, no required set); a stray read on it flags `vacant_unit` (BR-MET-052 — US-MET-011) |
| TC-6 *(negative)* | View cycle 08-B (window Aug 12–16) on Aug 4 | No pending pressure before window open (BR-MET-057): chase list empty with "window opens Aug 12"; nothing counted as missing |
| TC-7 *(negative)* | M-7001's Aug `total` read was superseded (v1 → v2, US-MET-009) | Collected counts the lineage exactly once (head only) — completeness never double-counts a superseded chain |
| TC-8 *(isolation)* | Lone Star Ridge opens its own cycle 08-A (code collision) | Expectations, counts and chase rows computed only from Lone Star Ridge units/plans/reads; automated test asserts no Brazos Bend id appears |

**4 · Test Data** — Brazos Bend cycle 08-A per EP-MET-02 §4 (routes 1–3, window Aug 1–5, 2026, bill Aug 8). Required-record mix: 754 flat meters × 1 (`total`) + 1 TOU meter × 4 + 2 demand meters × 2 = **762 expected records**; collected 734. Missing 28 records / 14 meters: 8 flat (incl. M-7612, M-7613) missing `total` + 4 TOU (M-7451..M-7454) missing window sets (4 each = 16) + 2 demand (M-7461, M-7462) missing `total` + `demand` (2 each = 4). Unplanned unit 9C (no plan, no account). Reference date Aug 4, 2026 (America/Chicago). Actor: Marcus Vega. Isolation: Lone Star Ridge cycle 08-A, J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Expected required records | S25/S27 | BR-MET-049 + BR-MET-057 | derived: cycle → routes → unit membership → plan-required channel set (no stored counter — BR-MET-011) | integer | computed-display | window-scoped (BR-MET-057) |
| Collected records | S25/S27 | BR-MET-049 | committed `meter_reads` lineage heads in the window, keyed (asset, read_at, channel) (B2 r8) | integer | computed-display | heads only — chains count once |
| Completeness % | S25/S27 | BR-MET-057 ("completeness bar") | collected ÷ expected, rendered as bar | % | computed-display | 0–100 |
| Chase list row | S25/S27 | BR-MET-057 ("chase list") | set difference expected − collected, grouped by unit/meter with missing channel names | — | computed-display | tenant-scoped joins only |
| Days left | S25/S27 | BR-MET-057 | `cycles.window_end` − today | integer days | computed-display | ≥ 0 within window |
| Chase actions | S25/S27 | BR-MET-023 (existing dispositions) | Estimate (EP-MET-05) / field-visit disposition — existing write paths, confirm modal + audit (IS-6) | enum | user-input | no new write path introduced |
| Export | S25/S27 | IS-9 | CSV download of the chase list | file | computed-display | honors RLS |

**6 · Acceptance**
- Given the §4 seed inside the window, When the cycle view opens, Then expected/collected/completeness and the chase list reconcile exactly (762 / 734 / 96.3% / 28 records over 14 meters) and match the S25 header roll-up.
- Given a unit without a plan, Then it produces no expectation and no chase row (BR-MET-049).
- Given a window not yet open, Then nothing is counted missing (BR-MET-057); Given superseded chains, Then collected counts heads once.
- Given chase actions, Then only the existing audited dispositions fire; Given Export, Then the CSV matches the list.
- Given two tenants with colliding cycle codes, Then all figures stay tenant-scoped.

**7 · Finance Calculation** — N/A — no money math (completeness is count arithmetic; the billing consequence of the gate belongs to the billing run per BR-MET-049).

**8 · Open Questions** — None.

---
id: US-MET-020
epic: EP-MET-03
module: metering
screens: [S25]
wave: 3
status: draft
blocked_by: []
depends_on: [US-MET-010, US-MET-012]
journeys: []
rules: [BR-MET-055]
golden_tests: []
finance_calc: none
---
### US-MET-020 — Auto-archival job (2-yr hot window → cold storage, 7-yr retention)

**1 · Details** — As a utility subject to multi-year retention obligations, I want a **scheduled monthly job** that detaches `meter_reads` monthly partitions older than the 2-year hot window and moves them to cold storage — automatic, **never manual**, fully audited — with archived reads reachable from the UI only via an explicit **"Search archive"** opt-in, and cold data purged only past the 7-year total-retention bound, so that hot-path queries stay fast at scale while nothing is lost early (BR-MET-055; B2 r8 auto-archival job; resolves B2 §5's open retention note for `meter_reads`). **Epic placement:** EP-MET-03, because this epic owns the read data's storage lifecycle — the import pipeline writes the monthly partitions this job later detaches, and the batch/compliance trail it must preserve is defined here (US-MET-010); EP-MET-05 (estimation/true-up) involves no storage semantics, so it would be a worse fit. Entry: none — scheduled job (monthly, per B2 r8); the UI touchpoint is the S25 "Search archive" opt-in (US-MET-012's list stays hot-window by default). Exit: partitions detached + archived, job run recorded, audit written.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-055 | Scale posture: server pagination, hot-window default (2 yr) + explicit archive search, monthly partitions, async imports, no unbounded read endpoints; **archival to cold storage runs as an AUTOMATIC scheduled job (2 yr hot → archive, 7 yr total retention) — never manual.** | CONFIRMED — PO RD-13 + addition (BR-MET-055); B2 r8 auto-archival job |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Monthly run fires 2026-09-01 02:00 UTC | Partition `meter_reads_2024_08` (every row with read_at in Aug 2024 — fully older than 2 yr) detached and shipped to cold storage; `meter_reads_2024_09` and younger untouched; job-run record: partition name, row count 18,412, destination, checksum, status `success` |
| TC-2 | Audit trail after TC-1 | Audit entries written (action `meter_reads.partition_archived`: partition id, row count, run id, timestamps) — the job is fully audited per BR-MET-055 |
| TC-3 | Archive search: Marcus toggles "Search archive" ON in S25 and queries M-7001 for Jul 2024 | Archived rows return read-only under his tenant scope; with the toggle OFF (default) the same query returns only hot-window rows (BR-MET-055 — explicit opt-in) |
| TC-4 *(negative)* | Any attempt to trigger or skip archival manually (UI or API) | No such action exists; a direct call to the job's internal entry point outside the scheduler is rejected — archival is scheduler-only, never manual (BR-MET-055) |
| TC-5 *(negative)* | Duplicate schedule fire re-runs the 2026-09-01 job | Nothing new detached; a no-op run is recorded — never a double archive, never an error |
| TC-6 | Retention bound: run of 2031-09-01 | Cold-storage partition `meter_reads_2024_08` (data now older than 7 yr) purged, with the purge recorded in the run record and audit; nothing younger than 7 yr is ever purged |
| TC-7 *(isolation)* | Archive search from a Lone Star Ridge session | Returns only Lone Star Ridge rows — partitions are physically shared across tenants, but every archive read executes under `app.tenant_id` RLS scope exactly like hot reads; automated test asserts zero cross-tenant rows |

**4 · Test Data** — Partitions: `meter_reads_2024_08` (18,412 rows, oldest hot candidate), `meter_reads_2024_09` … `meter_reads_2026_08` (hot). Schedule: monthly, 1st, 02:00 UTC. Cold-storage destination fixture: `s3://smartbillhub-archive/prod/meter_reads/2024_08/` + SHA-256 manifest checksum `77b1e4d0…a9c3`. Reference tenants: Brazos Bend (M-7001 Jul 2024 reads archived), Lone Star Ridge. Purge fixture: run date 2031-09-01 vs Aug 2024 data (7 yr elapsed).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Hot-window bound | — | BR-MET-055 (2 yr) | job configuration: 24 months | interval | reference-data | fixed by BR-MET-055 |
| Partition detach | — | B2 §5 partitioning + r8 | `meter_reads` monthly partitions → DETACH PARTITION + transfer to cold storage | DDL/storage op | system-derived | only partitions *fully* older than the hot window |
| Retention purge | — | BR-MET-055 (7 yr total) | cold-storage partition removal past 7 yr | storage op | system-derived | never younger than 7 yr; audited |
| Job run record | — | BR-MET-055 ("audited") | **PROPOSED-SCHEMA** `archive_job_runs` (run_at, partition, row_count, destination, checksum, status, purged list) | — | system-derived | append-only; rerun-safe (no-op recorded) |
| Audit entries | — | BR-MET-055 + CLAUDE.md #7 spirit | `audit_log` (`meter_reads.partition_archived` / `meter_reads.partition_purged`) | jsonb | system-derived | append-only |
| "Search archive" opt-in | S25 | BR-MET-055 (explicit archive search) | query-scope flag routing the read to the archive reader (no schema) | boolean | user-input | default OFF; RLS enforced identically on archive reads |

**6 · Acceptance**
- Given the monthly schedule, When the job runs, Then every partition fully older than 2 years is detached to cold storage with a checksummed, audited run record, And no younger partition is touched.
- Given the S25 default view, Then only hot-window reads are queried; Given the explicit archive opt-in, Then archived reads return read-only under the caller's tenant scope.
- Given a duplicate run or any manual invocation attempt, Then nothing double-archives and no manual path exists (BR-MET-055 — never manual).
- Given the 7-year bound, Then cold partitions older than 7 years are purged with an audited record, and nothing younger ever is.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.

---
> Reconciled 2026-08-08 — Reads pre-session (BR-MET-049..060, B2 r8).
