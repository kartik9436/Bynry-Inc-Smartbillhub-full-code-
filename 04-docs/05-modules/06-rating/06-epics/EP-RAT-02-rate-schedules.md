# EP-RAT-02 — Rate Schedules

> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep.

**Module:** rating (product name: Plans & Rates) · **Wave:** W1 · **Screens:** S9 (Rate schedules tab), S11 · **Status:** draft

## Scope
**In:** the Rate schedules tab of S9 (**r10's nine-column table** — corrected 2026-08-21, DEF-441; it said *"rate cards with structure preview + used-by/applied-to counts"* and the drawing is a table) and the New Rate wizard (S11, four steps per prototype: Basics → Pricing formula → Effective & approval → Review & activate — **the step-3 board-approval workflow is removed per BR-RAT-031 as-modified (PO R5-1): approval happens outside the system; the step captures effective dates + regulator reference**). Structure capture for every `tariff_model` in B2 r5 #16: **flat** · **tiered** (pure tiers, BR-RAT-026) · **time_of_use** Option B (up to 3 windows, 2 seasons, weekday/weekend/holiday day-types, tenant holiday calendar — BR-RAT-021) · **demand** (v1 scope per BR-RAT-014; measurement rules remain PROPOSED) · **seasonal** (first-class model, D3, `rate_seasons`) · **capacity** (tenant-defined unit label + rate, BR-RAT-018/019/022, `capacity_rates`). Also owns the sewer **% of water** structure (BR-RAT-015 — rule confirmed; schema home flagged as a gap). A schedule prices exactly one service with one model (A8); its name is internal.
**Out:** plan bundling (EP-RAT-01) · effective-dating mechanics beyond the wizard's capture, and single/bulk *changes* to live schedules (EP-RAT-04) · executing any pricing math (EP-RAT-05/06) · net-metering kWh credits (v1.1, roadmap / OQ-001 closure) · the prototype's dead "ERCOT rate templates / AWWA library / Upload CSV" buttons (no behavior in prototype — not v1 build) · demand *measurement/ratchet* rules (PROPOSED in B4 addendum; capture-only here) · any in-system rate-approval workflow (**removed — BR-RAT-031 as-modified; boards approve outside the system**).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S9 Rate schedules tab | schedule name | service, structure (flat/tiered/TOU/demand/seasonal/capacity), status | name asc | **all nine columns** | **r10's NINE-COLUMN TABLE** (r10 line 764): Schedule · Svc · Structure · Sizes · Seasons · Plans · Accounts · Effective · Status. **IS-5 column chooser APPLIES** — r10's own toolbar draws the chooser glyph. | Edit (new version via EP-RAT-04), View history, Archive (IS-1 — blocked while any plan references it) | — (v1) | **CSV (IS-9)** — `rate-schedules`, money-bearing, server writes the BR-SHL-016 audit row |

> ⚠ **THIS ROW WAS WRONG UNTIL 2026-08-21 AND IT IS WHY DEF-441 EXISTS.** It read
> *"Card grid per prototype (not an IS-2 table) … IS-5 column chooser N/A — card
> fields fixed"* and *"— (card grid; tabular export ships with EP-RAT-04's history
> view)"*. **The prototype it cites draws a table.** `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html`
> line 764 is `<table class="table lt">` with the nine headers above, and the line
> before it draws the column-chooser glyph tooltipped *"Choose columns · ↑↓ to
> reorder"*. The PO found it by comparing screens: *"rate schedule is in table
> format in Proto - you ahve done card format"* (2026-08-21).
>
> Five of the nine columns had **no field behind them** as a result — the card
> grid gave nothing a place to be missing from. `Sizes`, `Seasons` and `Effective`
> were unserved; `Plans` and `Accounts` were served but rendered as a prose
> footer sentence. All five are on `selectors.schedule_card` as of 2026-08-21.
>
> The structure preview the old row describes did not disappear — it moved to the
> schedule DETAIL (RAT-02), which is where a person goes to read prices. The row
> carries the summary r10 draws: `Tiered · 3 blocks`, `TOU · 2 periods`.

## Stories

---
id: US-RAT-004
epic: EP-RAT-02
module: rating
screens: [S9]
wave: 1
status: draft
blocked_by: []
depends_on: [US-TEN-007, US-SHL-006, US-SHL-007]
journeys: []
rules: [BR-RAT-019, BR-RAT-024, BR-RAT-025, BR-RAT-031]
golden_tests: []
finance_calc: none
---
### US-RAT-004 — Rate schedules list tab (cards with structure preview)

**1 · Details** — As an Owner/Admin, I want a Rate schedules tab showing each pricing formula as a card — name, service tag, status pill, a structure preview (tier table / TOU period table / demand components / capacity unit+rate), and usage counts ("Used by N plans · Applied to N accounts") — so that I can see every formula in force and spot pending changes. Entry: S9 → Rate schedules tab. Exit: **+ New rate schedule** → S11; card Edit → EP-RAT-04 change flow. Explainer per prototype: "Rate schedules define pricing formulas — flat, tiered, time-of-use, or demand. Plans bundle these into customer offerings." A **"Change scheduled — effective <date>"** note renders on cards with a future-effective version (per prototype Res Water card; the prototype's "Change pending approval" wording is superseded — **the in-system approval hold is removed, BR-RAT-031 as-modified**).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-025 | D1: rate structure is not service-tied — any model may price any service; D2: plans attach one schedule per service. | CONFIRMED — PO Q&A R3 |
| BR-RAT-019 | `tariff_model` = flat \| tiered \| time_of_use \| demand \| seasonal \| capacity (r5 #16). | CONFIRMED — B2 r5 #16 (PO-approved) |
| BR-RAT-024 | Service tags limited to tenant-enabled services. | CONFIRMED — PO Q&A R3 |
| BR-RAT-031 | A rate schedule prices exactly one service with one model; name is internal (customers see the plan name); draft schedules are excluded from plan-builder pickers until activated; activation requires a complete structure + effective_from — **the board-approval workflow is removed (approval happens outside the system; `tariff_versions.approved_by` = optional metadata only, never a gate)**. | CONFIRMED-AS-MODIFIED — PO R5-1 (A8 §Plan-vs-Rate + S11 step-1 copy) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana opens the tab with the §4 seed | 7 cards; Res Electric · Tiered card shows the 3-tier table (0–500 @ $0.11 …) and "Used by 2 plans · Applied to 1,098 accounts" |
| TC-2 | Filter Structure = Capacity | Only Solar Capacity and Battery Capacity cards remain; chips/URL per IS-4 |
| TC-3 | Res Water card with a future-effective Sep 1 version (EP-RAT-04) | Card footer shows "Change scheduled — effective Sep 1"; **no approval-pending state exists** (BR-RAT-031 as-modified — the version is live-on-date once published by a System Admin) |
| TC-4 *(negative)* | Archive attempted on Res Electric · Tiered (used by 2 plans) | Audit-locked: "referenced by 2 plans — detach first" (IS-1); card unchanged |
| TC-5 *(negative)* | Cards endpoint returns 500 | A18 failed-with-retry card; Retry re-issues the identical query |
| TC-6 *(isolation)* | Lone Star Ridge admin opens the tab | Only "Co-op Water Flat"; usage counts computed solely from Lone Star Ridge plans/accounts |

**4 · Test Data** — Brazos Bend schedules (all effective Aug 1, 2026, v1 unless noted): **Res Electric · Tiered** (E, kWh: 0–500 @ 0.11, 500–1,000 @ 0.14, 1,000+ @ 0.19; used by 2 plans / 1,098 accts) · **Res Water · Inclining** (W, kgal: 0–4 @ 3.20, 4–10 @ 4.80, 10+ @ 7.20; scheduled Sep 1 change) · **Comm Electric · TOU** (E; §US-RAT-006 config) · **Industrial Electric · Demand** (E; energy $0.08/kWh, demand $14.50/kW) · **Comm Water · Flat** (W, $2.90/kgal) · **Sewer · % of water** (S, **90% of the water VOLUME priced at $5.0000/kgal** — `CR-081`, PO re-sign 2026-09-08; it read *"40% of water usage-charge $"* until that date. A percent schedule now states a RATE as well as a factor, and one with no rate is an incomplete structure that will not activate — `BR-RAT-031`/`BR-RAT-1015`) · **Solar Capacity** (Solar, "panel" @ $10.00) + **Battery Capacity** (Battery, "kW block" @ $12.00). Lone Star Ridge: "Co-op Water Flat" (W, $3.10/kgal). Actor: Dana Whitfield.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Schedule name | S9 | prototype-extracted | `tariffs.name` | text | user-input | unique (tenant, name, service) |
| Service tag | S9 | prototype-extracted | `tariffs.service` → `services` catalog (r5 #1) | reference | reference-data | tenant-enabled |
| Structure label | S9 | prototype-extracted ("Tiered", "Time-of-use"…) | `tariff_versions.model` (r5 #16 enum) | enum | reference-data | — |
| Structure preview | S9 | prototype-extracted (tier/period/component tables) | `rate_tiers` / `time_of_use_windows` (+`rate_seasons`) / `capacity_rates` of the current `tariff_versions` row | rows | computed-display | current version only |
| Status pill | S9 | prototype-extracted (Active pill) | derived: current `tariff_versions` in force → Active; none → Draft; future-effective version → "Change scheduled" note (**no approval-pending state — BR-RAT-031 as-modified**) | enum | computed-display | — |
| Used by / applied to | S9 | prototype-extracted | counts over `plan_rate_schedules` and `unit_plan_assignments` (⚠ cross-module read via service function, B1) | integers | computed-display | — |

**6 · Acceptance**
- Given the §4 seed, When Dana opens the tab, Then every schedule card shows its structure preview verbatim from the current version rows and correct usage counts.
- Given a referenced schedule, When Archive is attempted, Then the audit-lock blocks it with the reference count.
- Given a Lone Star Ridge session, Then only its own schedules and counts render.

**7 · Finance Calculation** — N/A (display of stored rates; no computation).

**8 · Open Questions** — None.

---
id: US-RAT-005
epic: EP-RAT-02
module: rating
screens: [S11]
wave: 1
status: draft
blocked_by: []
depends_on: [US-RAT-004, US-TEN-008, US-SHL-010]
journeys: [J2]
rules: [BR-RAT-013, BR-RAT-026, BR-RAT-031, BR-RAT-032, BR-RAT-038]
golden_tests: [GT-2]
finance_calc: confirmed
---
### US-RAT-005 — New Rate wizard: basics, flat & tiered (pure tiers) structures

**1 · Details** — As an Owner/Admin, I want the New Rate wizard's step 1 (schedule name, service, customer class, unit of measure) and step 2 structures **Flat** (one price per unit) and **Tiered** (inclining block rows From/To/Rate, add/remove tier, last To blank = ∞), plus step 3 (effective from/to, regulator reference — **the prototype's "Board approval required" checkbox is removed: approval happens outside the system, BR-RAT-031 as-modified**) and step 4 (review & activate / save as draft), so that the two most common formulas are built in about 3 minutes. Entry: S9 Rates tab **+ New rate schedule** or S10 step-3 "Create a new rate schedule" link. Exit: **Create rate schedule ✓** → the System Admin publishes directly — active `tariffs` + `tariff_versions` (+ `rate_tiers`); draft → resumable. Wizard mechanics per EP-SHL-03.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-026 | **Pure tiers only (Style 1)**: base charge lives on the plan; every unit of usage bills through the tiers; no allowance/"included units" field exists in v1 (supersedes BR-RAT-013). | CONFIRMED — PO Q&A R5 Q5 |
| BR-RAT-032 | Tier validation: rows ordered by seq; tier n+1's From equals tier n's To (contiguous, no gaps/overlaps); From < To; only the last tier may have To = ∞ (NULL); rates ≥ 0; NUMERIC(18,6). Flat = a single stored tier row (0 → ∞) so the engine has one execution path. | CONFIRMED — PO R5-5 (S11 tier grid + B2 `rate_tiers` DDL) |
| BR-RAT-031 | *(shared)* one service, one model, internal name; Save-draft resumable; **activation requires a complete structure + effective_from and is published directly by a System Admin — the board-approval workflow is REMOVED (approval happens outside the system); `tariff_versions.approved_by` stays as optional metadata only, never a gate**. | CONFIRMED-AS-MODIFIED — PO R5-1 |
| BR-RAT-038 | UoM gate: the schedule's unit of measure must match the service's billed unit, or a per-service conversion factor must be defined; on mismatch with no factor the system shows a clear message and blocks rating for that read — no silent conversion. Default billed water unit kgal. | CONFIRMED — PO Q&A R6 (OQ-004 closure, B4 R6 §) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana builds "Res Water · Inclining" (W, kgal, Residential): tiers 0–4 @ 3.20, 4–10 @ 4.80, 10–∞ @ 7.20; effective Sep 1, 2026; activates directly | `tariffs` + `tariff_versions` (model tiered, effective_from Sep 1) + 3 contiguous `rate_tiers`; **no approval step or hold state** (BR-RAT-031); card appears on S9; audit `tariff.activated` |
| TC-2 | Flat schedule "Comm Water · Flat" @ 2.90/kgal | Stored as one `rate_tiers` row (0 → NULL @ 2.90), model flat; review shows "Flat · $2.90 / kgal" |
| TC-3 | Dana records regulator ref "TX PUC docket 51234", saves draft at step 3, reopens later | Draft resumes at step 3 with structure intact (Save-draft resumable, BR-RAT-031); activation attempted without effective_from → blocked inline; setting Sep 1 + activate → published directly by the System Admin, `approved_by` left NULL (optional metadata — **no Awaiting-approval state exists**) |
| TC-4 *(negative)* | Tiers entered 0–4, 5–10 (gap 4–5) | Inline error "tiers must be contiguous"; Continue blocked; nothing written |
| TC-5 *(negative)* | Middle tier's To left blank | Inline error "only the last tier can be open-ended" |
| TC-6 *(negative)* | Rate entered as −0.50 | Inline validation error (rate ≥ 0) |
| TC-7 *(negative)* | Water schedule built in **ccf** while Brazos Bend bills water in kgal with no ccf factor defined | Activation warns and rating is blocked for reads priced by it until a factor exists — message per BR-RAT-038, never a silent conversion |
| TC-8 *(isolation)* | Lone Star Ridge builds "Co-op Water Flat" | Rows carry Lone Star Ridge tenant_id; Brazos Bend's S9 never shows the card; name reuse across tenants allowed |

**4 · Test Data** — Per TC-1/TC-2 above. UoM config: Brazos Bend water billed unit kgal (register gallons, factor ÷1000 defined); electric kWh. Mismatch fixture: ccf schedule with no factor. Regulator ref "TX PUC docket 51234". Actors: Dana Whitfield; J. Okafor (Lone Star Ridge).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Schedule name | S11 step 1 | prototype-extracted | `tariffs.name` | text | user-input | unique (tenant, name, service) |
| Service | S11 step 1 | prototype-extracted (segmented control) | `tariffs.service` | reference | user-input | tenant-enabled (BR-RAT-024) |
| Customer class | S11 step 1 | prototype-extracted (4 options) | **PROPOSED-SCHEMA** `tariffs.account_type_id` → `account_types` (r5 names no column; informational targeting) | uuid | reference-data | optional |
| Unit of measure | S11 step 1 | prototype-extracted (kWh/kW/kgal/ccf/therm) | **PROPOSED-SCHEMA** `tariff_versions.uom` (B2 stores unit only on meters/lines; schedule UoM has no column) | text | user-input | BR-RAT-038 gate at rating time |
| Structure picker | S11 step 2 | prototype-extracted (4 cards; +seasonal/capacity per r5 #16) | `tariff_versions.model` | enum | user-input | one model per version |
| Flat rate per unit | S11 step 2 | prototype-extracted | `rate_tiers` single row (from 0, to NULL, unit_price) | numeric(18,6) | user-input | ≥ 0 |
| Tier rows From/To/Rate | S11 step 2 | prototype-extracted | `rate_tiers.seq/from_qty/to_qty/unit_price` | numeric(18,6) | user-input | BR-RAT-032 contiguity |
| Effective from/to | S11 step 3 | prototype-extracted | `tariff_versions.effective_from/effective_to` | date | user-input | no overlap (B2 EXCLUDE); effective_from required for activation (BR-RAT-031) |
| Regulator reference | S11 step 3 | prototype-extracted ("TX PUC docket 51234") | **PROPOSED-SCHEMA** `tariff_versions.regulator_ref` | text | user-input | optional; audit-logged |
| Notify-30d / public-page toggles *(board-approval checkbox removed — BR-RAT-031 as-modified)* | S11 step 3 | prototype-extracted | **PROPOSED-SCHEMA** `tariff_versions.notify_customers`, `publish_public` (capture-only; public rate page has no A1 screen); `tariff_versions.approved_by` = optional out-of-system approval metadata, never a gate | bool/uuid | user-input | capture-only v1 |
| Review summary | S11 step 4 | prototype-extracted *(Awaiting-approval pill removed — BR-RAT-031 as-modified)* | render of the above | — | computed-display | — |

**6 · Acceptance**
- Given a completed tiered wizard, When activated, Then tariff + version + contiguous tiers exist, the S9 card previews them exactly, and audit rows are written — no pricing has run.
- Given a gap, an open middle tier, a negative rate, or a UoM mismatch without factor, Then the wizard blocks (or rating is blocked) with the stated message and writes nothing silently.
- Given a draft without effective_from or with an incomplete structure, Then activation is blocked inline; a complete draft activates directly on a System Admin's publish — **no in-system approval hold exists** (BR-RAT-031 as-modified).

**7 · Finance Calculation** — The formula this structure drives (executed only in EP-RAT-05): `usage_charge = Σ over tiers of min(remaining_usage, tier_span) × unit_price` on post-multiplier consumption (BR-RAT-001), tiers reset each bill and thresholds scale with prorated periods (BR-RAT-002) — all CONFIRMED (B4 §Tiered). Worked example (GT-2 fixture): tiers 0–2 @ 3.00, 2–5 @ 4.50, 5+ @ 6.00; usage 3.72 kgal → 2 × 3.00 + 1.72 × 4.50 = 6.00 + 7.74 = **$13.74** usage charge (+ plan base $12.00 = $25.74 before tax). Ref: **GT-2**.

**8 · Open Questions** — None.

---
id: US-RAT-006
epic: EP-RAT-02
module: rating
screens: [S11]
wave: 1
status: draft
blocked_by: []
depends_on: [US-RAT-005]
journeys: [J2]
rules: [BR-RAT-021, BR-RAT-024, BR-RAT-031, BR-RAT-033]
golden_tests: []
finance_calc: confirmed
---
### US-RAT-006 — New Rate wizard: TOU Option B (windows × seasons × day-types + holiday calendar)

**1 · Details** — As an Owner/Admin, I want the Time-of-use structure per PO-confirmed **Option B**: up to 3 windows (on/mid/off-peak) with start–end hours, 2 seasons with date ranges, per-season window prices, weekday/weekend/holiday day-types, and a tenant holiday calendar (holidays bill off-peak), so that commercial TOU pricing is configurable without interval-data complexity — reads arrive pre-split per window (assets/metering supply the split; optional interval-CSV import aggregates to windows). Entry: S11 step 2, Time-of-use card. Exit: TOU version with windows/seasons rows. The holiday calendar is managed from the same step (add/remove dates; shared per tenant across schedules).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-021 | TOU v1 = Option B: ≤3 windows · 2 seasons (date ranges + per-season prices) · weekday/weekend/holiday day-types with tenant holiday calendar, holidays bill off-peak · reads pre-split per window · optional interval-CSV aggregated to windows. | CONFIRMED — PO Q&A R3 Q6 |
| BR-RAT-033 | TOU config validation: within each (season × day-type), windows must cover 00:00–24:00 with no overlap (a window may wrap midnight, e.g. 20:00–14:00); each season needs ≥1 window; the two seasons' date ranges must cover the full year without overlap; every holiday date resolves through the tenant calendar to the off-peak (lowest-price) window of its season. | CONFIRMED — PO R5-6 (BR-RAT-021 + prototype TOU table) |
| BR-RAT-031 | *(shared)* wizard flow + activation (complete structure + effective_from; System Admin publishes directly — **no in-system approval, as-modified**). | CONFIRMED-AS-MODIFIED — PO R5-1 |
| BR-RAT-024 | *(shared)* service ⊆ tenant-enabled. | CONFIRMED |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana builds "Comm Electric · TOU" (E, kWh): Summer Jun 1–Sep 30 with On-peak 14:00–20:00 @ 0.22 / Off-peak 20:00–14:00 @ 0.09 (weekday); weekend+holiday → off-peak; Winter Oct 1–May 31 All-day @ 0.13; activates | 2 `rate_seasons` rows + `time_of_use_windows` rows carrying season_id + day_type + prices; S9 card previews the period table exactly as the prototype's |
| TC-2 | Holiday calendar: adds Jul 4, Sep 7, Nov 26, Dec 25 2026 | 4 `holiday_calendars` rows (unique per tenant+date); step copy states "holidays bill off-peak" (BR-RAT-021) |
| TC-3 | Mid window added (3rd): Mid-peak 11:00–14:00 @ 0.15 summer weekday | Accepted (≤3 windows); coverage check passes (off-peak reshapes to 20:00–11:00) |
| TC-4 *(negative)* | 4th window added | Blocked: "Option B supports up to 3 windows" (BR-RAT-021) |
| TC-5 *(negative)* | Summer weekday windows leave 13:00–14:00 unpriced | Inline error "every hour must belong to exactly one window"; activation blocked |
| TC-6 *(negative)* | Seasons entered Jun 1–Sep 30 and Sep 15–May 31 (overlap) | Inline error "season date ranges must not overlap and must cover the year" |
| TC-7 *(negative)* | Duplicate holiday date Dec 25 added twice | Rejected by (tenant, holiday_date) uniqueness with inline error |
| TC-8 *(isolation)* | Lone Star Ridge holiday calendar has Mar 2 (TX Independence) only | Brazos Bend TOU resolution never consults it; each tenant's calendar is RLS-scoped |
| TC-9 | **Dana says which meter register each window reads** — On-peak → `tou_on`, Mid-peak → `tou_mid`, Off-peak → `tou_off`, chosen per window on the Time-of-use card (PO ruling 2026-08-16, verbatim: _"make the rate wizard say which register is which"_; BR-RAT-067, OQ-236 CLOSED) | Each `time_of_use_windows` row stores its `channel`; the S9 card and the resumed draft read it back; the bill run prices the register the utility NAMED, not the one its price rank implies. **Worked:** registers reading 120 / 200 / 380 kWh at $0.22 / $0.14 / $0.09 bill **$88.60** as stated; the same meter with the registers named the other way round bills **$122.40**, a 38% difference the schedule now decides explicitly |
| TC-10 *(negative)* | A window is left with no register; and (b) two windows in one season both name `tou_on` | (a) Inline error on that window — Continue blocked, nothing written; a schedule already stored without one REFUSES AT PRICING by name ("window 'On-peak' does not say which meter register it is measured on") and is never billed at $0.00. (b) Inline error naming both windows: one register holds ONE number for the period, so two windows on it would drop one window's money silently (BR-RAT-067 clause 2) |

**4 · Test Data** — Comm Electric · TOU per TC-1 (effective Aug 1, 2026; used by Small Commercial, 96 accounts). Brazos Bend holidays 2026: Jul 4, Sep 7, Nov 26, Dec 25. Lone Star Ridge: Mar 2. Actor: Dana Whitfield. TC-9/TC-10 registers: `tou_on | tou_mid | tou_off` (metering's own vocabulary, B2 r8 / BR-MET-059) against the seeded electric reads of 120 / 200 / 380 kWh.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Season label + date range | S11 step 2 | prototype-extracted ("Summer"/"Winter") + r5 #2 | `rate_seasons` (tariff_version_id, label, start/end month+day) | text + month/day | user-input | BR-RAT-033 coverage |
| Window label | S11 step 2 | prototype-extracted (On-peak/Off-peak/All day) | `time_of_use_windows.label` | text | user-input | ≤3 windows per season×day-type |
| Window hours | S11 step 2 | prototype-extracted ("14:00–20:00") | `time_of_use_windows.start_time/end_time` | time | user-input | may wrap midnight; coverage per BR-RAT-033 |
| Window price (per season) | S11 step 2 | prototype-extracted ("0.22") | `time_of_use_windows.unit_price` + `season_id` (r5 #17) | numeric(18,6) | user-input | ≥ 0 |
| Day-type | S11 step 2 | B2 r5 #17 (weekday\|weekend\|holiday DEFAULT weekday) | `time_of_use_windows.day_type` | enum | user-input | holiday rows resolve off-peak |
| Holiday dates | S11 step 2 panel | B2 r5 #3 + BR-RAT-021 | `holiday_calendars` (tenant, holiday_date UNIQUE, label) | date + text | user-input | unique per tenant+date |
| Interval-CSV import (optional) | S11/S28 seam | BR-RAT-021 (aggregated to windows) | input path only — aggregated quantities land as pre-split window quantities on reads (metering-owned) | file | integration | out of rating's write scope |

**6 · Acceptance**
- Given a completed Option B config, When activated, Then seasons/windows/day-type rows reproduce the prototype's period table and every (season × day-type × hour) resolves to exactly one price.
- Given a coverage gap, >3 windows, overlapping seasons, or a duplicate holiday, Then activation is blocked with the specific inline error.
- Given a holiday billing day, Then usage prices at the season's off-peak rate via the tenant's own calendar only.

**7 · Finance Calculation** — TOU pricing (executed in EP-RAT-05): `usage_charge = Σ over windows of window_qty × window_unit_price`, where window quantities arrive pre-split (BR-RAT-021, CONFIRMED); per-line half-up 2dp rounding at finalization (BR-RAT-003). Worked example (§4 config, a summer weekday bill): on-peak 180 kWh × 0.22 = 39.60; off-peak 560 kWh × 0.09 = 50.40 → TOU usage lines **$39.60 + $50.40 = $90.00** (+ plan base; tax per GT-10 rules). GT ref: — (no TOU golden test exists; fixture above is story-level).

**8 · Open Questions** — None.

---
id: US-RAT-007
epic: EP-RAT-02
module: rating
screens: [S11]
wave: 1
status: draft
blocked_by: []
depends_on: [US-RAT-005]
journeys: [J2]
rules: [BR-RAT-014, BR-RAT-015, BR-RAT-018, BR-RAT-019, BR-RAT-022, BR-RAT-031, BR-RAT-034]
golden_tests: [GT-15]
finance_calc: confirmed
---
### US-RAT-007 — New Rate wizard: demand, seasonal, capacity & %-of-water structures

**1 · Details** — As an Owner/Admin, I want the remaining structures: **Demand** (energy $/kWh + demand $/kW + peak-window note + optional power-factor penalty capture), **Seasonal** (first-class model: per-season flat/tier price sets via `rate_seasons`), **Capacity** (tenant-defined unit label + rate per unit for solar/battery, e.g. "panel" @ $10), and **Sewer % of water** (percent of the water usage-charge dollars), so that every v1 tariff model is configurable. Entry: S11 step 2 structure cards (demand per prototype; seasonal/capacity/%-of-water cards added per r5 #16 + BR-RAT-015 — prototype shows only 4 cards; A8 lists %-of-water as a supported structure). Exit: activated version with the model's rows.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-014 | Demand billing is v1 scope; measurement = max-demand register read, ratchet OFF by default — measurement/ratchet rules remain **PROPOSED** (B4 addendum OQ-006 family); the wizard captures config, the engine treats demand quantity as an input. | CONFIRMED (scope) / measurement PROPOSED — PO Q&A R1 Q7 + B4 addendum |
| BR-RAT-018 / BR-RAT-019 / BR-RAT-022 | Capacity model: fixed rate × account capacity qty; unit label + rate are tenant-defined per service; prorated calendar-days on mid-cycle start per B4.3; taxable like base (BR-RAT-029). NOT net-metering kWh credits (v1.1). | CONFIRMED — PO Q&A R1 Q10 + R3 (OQ-051) |
| BR-RAT-015 | Sewer = % of water **usage-charge dollars** (excl. base, excl. tax); cap/winter-averaging deferred v1.1. | CONFIRMED — PO Q&A R1 Q8 |
| BR-RAT-034 | Seasonal model validation: `rate_seasons` date ranges must cover the full year without overlap; each season carries its own price set (flat rate or tier rows scoped to the season); season boundaries split the bill period pro-rata by calendar days (B4.3). | CONFIRMED — PO R5-7 (r5 #2 D3 first-class seasonal + B4.3) |
| BR-RAT-031 | *(shared)* wizard flow + activation (complete structure + effective_from; System Admin publishes directly — **no in-system approval, as-modified**). | CONFIRMED-AS-MODIFIED — PO R5-1 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana builds "Industrial Electric · Demand": energy 0.08/kWh, demand 14.50/kW, peak window "15-min monthly", PF-penalty toggle off; activates | Version model=demand with both components stored; S9 card matches the prototype's component table; PF penalty row absent |
| TC-2 | "Solar Capacity" (Solar service): unit_label "panel", rate 10.00; "Battery Capacity" (Battery): "kW block", 12.00 | `capacity_rates` rows (tariff_version_id, unit_label, rate_per_unit, currency) — labels are free tenant text (BR-RAT-022) |
| TC-3 | "Sewer · % of water" at 40% | Version model captures percent 40 and basis = water usage-charge dollars; review restates the BR-RAT-015 basis in copy |
| TC-4 | Seasonal water schedule: Summer (May 1–Oct 31) flat 4.10/kgal, Winter (Nov 1–Apr 30) flat 3.40/kgal | rate_seasons + per-season price rows; coverage check passes |
| TC-5 *(negative)* | Capacity rate entered as −10 | Inline error (rate ≥ 0); nothing written |
| TC-6 *(negative)* | Sewer percent entered as 140% | Inline warning-with-confirm at >100% and hard error at ≤0 — value must be 0 < p (confirm required above 100); default validation from BR-RAT-015's "% of dollars" semantics |
| TC-7 *(negative)* | Seasonal config with only Summer (Nov–Apr unpriced) | Activation blocked: "seasons must cover the year" (BR-RAT-034) |
| TC-8 *(negative)* | PF-penalty toggle on | Captured but flagged "demand measurement rules pending ratification (B4 addendum)" — engine will not compute PF penalties until the demand rules ratify; no silent math |
| TC-9 *(isolation)* | Lone Star Ridge defines capacity unit_label "meter equivalent" @ 6.00 | Fully independent of Brazos Bend's "panel"; labels never leak across tenants |

**4 · Test Data** — Per TCs above; Industrial Electric · Demand used by Industrial (18 accounts, meter M-7210 ×10). Solar Capacity / Battery Capacity used by Solar Residential (12 accounts). Sewer · % of water 40% used by Industrial. Actor: Dana Whitfield.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Energy $/kWh · Demand $/kW · Peak window | S11 step 2 | prototype-extracted (0.08 / 14.50 / "15-min monthly") | **PROPOSED-SCHEMA** — no home in B2/r5 for demand components (e.g. `demand_rates`: tariff_version_id, energy_price, demand_price, peak_window) — r5 gap | numeric(18,6)/text | user-input | ≥ 0 |
| PF-penalty toggle (+$/kW below 0.9 pf) | S11 step 2 | prototype-extracted | **PROPOSED-SCHEMA** capture-only field on demand config; engine excluded until demand rules ratify (BR-RAT-014) | bool/numeric | user-input | capture-only v1 |
| Capacity unit label + rate | S11 step 2 | B2 r5 #4 + BR-RAT-022 | `capacity_rates.unit_label` (tenant-defined) + `capacity_rates.rate_per_unit` + `currency` | text + numeric(18,6) | user-input | rate ≥ 0; label required |
| Sewer percent + basis service | S11 step 2 | A8 ("Sewer · % of water") + BR-RAT-015 | **PROPOSED-SCHEMA** — `tariff_model` r5 #16 has no percent-of-service value; needs e.g. model `percent_of_service` + `tariff_versions.percent`, `basis_service` — r5 gap | numeric(18,6) % | user-input | 0 < p; confirm >100 |
| Season price sets | S11 step 2 | r5 #2 (D3) | `rate_seasons` + season-scoped `rate_tiers` rows (**PROPOSED-SCHEMA** `rate_tiers.season_id` — r5 adds season_id to TOU windows only) | rows | user-input | BR-RAT-034 coverage |

**6 · Acceptance**
- Given each structure completed, When activated, Then its rows are stored per §5, the S9 card previews them, and nothing prices until EP-RAT-05/06 runs.
- Given invalid values (negative rates, uncovered seasons, out-of-range percent), Then activation is blocked with inline errors.
- Given PF-penalty capture, Then it is stored with an explicit pending-ratification flag and excluded from engine math.

**7 · Finance Calculation** — Formulas these structures drive (executed in EP-RAT-05/06):
- Demand (CONFIRMED scope; measurement PROPOSED): `energy_qty × energy_price + demand_kW × demand_price` — e.g. 12,400 kWh × 0.08 + 38 kW × 14.50 = 992.00 + 551.00 = **$1,543.00**.
- Capacity (CONFIRMED — BR-RAT-018/022, GT-15): `account_capacities.units × capacity_rates.rate_per_unit` — GT-15 fixture: solar 4 × 10.00 = **$40.00**; battery 2 × 12.00 = **$24.00**; taxable like base (BR-RAT-029); calendar-day prorated (B4.3).
- Sewer (CONFIRMED — BR-RAT-015): `percent × water usage-charge dollars (excl. base, excl. tax)` — 40% × 13.74 = **$5.496 → $5.50** at line finalization (BR-RAT-003 half-up 2dp).
Ref: **GT-15** (capacity); GT-2 feeds the sewer example's water charge.

**8 · Open Questions** — None (demand measurement/PF ratification is tracked in B4's addendum as PROPOSED — referenced, not re-minted).
