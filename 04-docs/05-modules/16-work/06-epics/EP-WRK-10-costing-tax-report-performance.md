# EP-WRK-10 — Costing, tax, the report and performance: parts against a job, labour rates, the tax that is NOT built, the report generated on approval, and the Finance arrow that is refused

**Module:** work · **Wave:** phase **2** of `CR-070` · **Screens:** `Work-025` · `Work-027` · `Work-030` · `Work-031` (not drawn) · `Work-032` · `Work-008` · `Work-009` · **Status:** draft (`CR-070`, 2026-09-03; §15–§21 unread)

## Scope

**In:** `WM-22` parts against a job · `WM-45` labour rates · `WM-46` tax on a work order — **NOT BUILT, PO ruling** · `WM-47` the work-order report · `WM-41` the performance tab.

**Out:** posting anything to the ledger (`OQ-WRK-1491` — **CLOSED 2026-09-04 to option (a), captured and posted nowhere**) · stock levels (`OQ-WRK-1490` — **CLOSED 2026-09-04 to option (a), no stock**) · the tax flag and frequency (PO 2026-09-03). ⚠ **ALL THREE ARE NOW RULINGS RATHER THAN OPEN QUESTIONS, AND THAT CHANGES WHAT IS BUILT AT THE BOUNDARY** (`DEF-WRK-4030`): each absence raises the ruling's own sentence rather than a question id, because a stub invites a later lane to unblock it and a deliberate absence does not.

⚠ **THREE THINGS IN THIS EPIC ARE MONEY, AND NONE OF THEM IS A BILL.** A labour rate (`48.5000`), a part cost (`96.0000`) and a report total (`138.42`) are stored to four decimals and displayed to two (hard rule 2), computed by **one named function with a test on the worked figure** (`BR-WRK-051`), and **posted nowhere** (`BR-WRK-004`). No B4/B5 figure is touched. **And the one thing that WOULD have touched B4 — a third tax base — is ruled out:** PO 2026-09-03, verbatim, *"Dont add Tax on work order - for now"*. So `WO-4822`'s report totals **`$138.42`**, not the `$149.84` the wireframe draws with `$8.65` and `$2.77` of tax on it.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| `Work-025` Parts — Issue log | part, issued to | purpose | date desc | Date · Part | Date · Part · Qty · Issued to · Purpose · Recorded by | 👁 | — | ↓ (IS-9) |
| `Work-027` Performance — by job type | — | period | volume desc | every column | Job type · Volume · Avg duration · SLA met · First-time fix · Cost/job · Total cost | — | — | ↓ (IS-9) |
| `Work-030` Labour rates | role | — | effective from desc | — | Role · Per hour · Overtime/hour · Overtime starts after · Effective from | ✎ | — | — |

## Stories

---
id: US-WRK-050
epic: EP-WRK-10
module: work
screens: [Work-025, Work-008]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-010, US-WRK-032]
journeys: [J62]
rules: [BR-WRK-049]
golden_tests: []
finance_calc: proposed
---
### US-WRK-050 — Parts against a job: issue 1 × `MTR-W58` against `WO-4822`, read *used 1 of 1 planned* with who and when — and no on-hand count moves, because none lawfully exists (`WM-22`)

**1 · Details** — As **a technician**, I want **to record the parts I used against the parts the template planned**, so that **the Parts tab reads used-of-planned and the unused gasket is a real outcome worth keeping**.

`Work-025`'s second tab, the **Issue log** (*− Issue parts · + Return entry*), plus the part detail (*Overview · Movements · Audit*), the Add part form and the two-step Issue parts flow — r10's `WRK-16`, `WRK-17`, `WRK-18`, **sub-screens of `Work-025`**. *"Issues deduct stock the moment they are recorded"* is the wireframe's sentence and **it is not built**: *"No stock decrement; stock levels are out of scope"* (`WM-22`), `OQ-WRK-1490`. *"The work-order reference is plain text — this register does not know what a work order is"* — kept, because it lets the register exist before the dispatcher; **and** the order's own `work_order_materials.used_qty` is what `Work-008`'s Parts tab reads, so the two are reconciled by the order number, not a key.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-049` | Used-of-planned; who and when; no on-hand count moves | CONFIRMED — `WM-22` |
| `BR-WRK-019` | Stock is `OQ-WRK-1490` | **CONFIRMED 2026-09-04 — no stock, ever** |
| `BR-WRK-051` | A part line on the report is quantity × unit cost | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Issue 1 × `MTR-W58` against `WO-4822` | Parts tab: *MTR-W58 · used 1 of 1 planned · issued by D. Ortiz · 15:40*; an issue-log row *−1 · D. Ortiz · Van 12 · (ref WO-4822)* |
| TC-2 | `GSKT-STD` planned 1, used 0 | *0 of 1 · not used* — a real outcome, kept |
| TC-3 · **negative** | A part used that the template did not plan | Accepted as an extra line, marked *unplanned* — a job is not refused for needing a gasket the template forgot |
| TC-4 · **negative** | `GET /work/parts/MTR-W58` after the issue | **No** `on_hand` key; the Movements tab lists the issue with no running balance |
| TC-5 · **negative · absence** | The banner *Reorder — 2 parts at or below reorder level* | Not rendered; `services.stock_position()` raises **the RULING SENTENCE and not a question id** — *"ruled 2026-09-04: Work keeps a parts register and an issue log and no stock at all"* — and nothing calls it. ⚠ **AMENDED 2026-09-05 (`DEF-WRK-4030`): this read `NotImplementedError("OQ-WRK-1490")` until the question CLOSED on 2026-09-04.** The closure is explicit that it becomes *"a DELIBERATE ABSENCE, NOT A STUB AWAITING A RULING"*, and the difference decides what the next lane does with it: a stub invites unblocking, a deliberate absence does not |
| TC-6 · **tenant isolation** | Lone Star Ridge's issue log | Its own rows |
| TC-7 | + Return entry | `+4 · R. Patel · return · Unused on job` — a row, never a deletion of the issue |

**4 · Test Data** — Issue log of `WS-25`: Aug 16 08:10 `MTR-W58` −2 D. Ortiz · Van 12 *Exchanges on Route 2 (ref WO-4821)* Alex Reed · Aug 15 16:40 `SEAL-01` −20 M. Chen · Van 8 *Van restock* · Aug 14 14:22 `GSKT-STD` +4 R. Patel · return *Unused on job*. `WO-4822`: `MTR-E1P` 1 of 1 · `SEAL-01` 1 of 1 · `GSKT-STD` 0 of 1.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| used | `Work-008` Parts | `WM-22` | `work_order_materials.used_qty`, `.issued_by`, `.issued_at` | numeric · uuid · ts | phone | unit from the row |
| issue log | `Work-025` | `WS-25` | `part_issues` (part_id · qty signed · issued_to (technician or crew) · purpose · order_ref text · recorded_by · at) `[our table — the card says "issues and returns"; §16 unread]` | rows | user-input / phone | `order_ref` plain text by design |
| on hand · reorder · location | `Work-025` | `WS-25` | **none** — `OQ-WRK-1490` | — | — | stub |

**6 · Acceptance** — **Given** a planned meter, **when** the technician records it used, **then** the Parts tab reads *1 of 1* with their name and time — **and** no count anywhere moves.

**7 · Finance Calculation** — A part line = `used_qty × parts.unit_cost` at 4 dp, displayed 2: `1 × 96.0000 = 96.00`; `1 × 0.2200 = 0.22`. Consumed by `US-WRK-053`'s one function. No GT. Posted nowhere (`BR-WRK-004`).

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-WRK-1490` | Can a parts stock table exist? | Stock levels, reorder, location, the deduct-on-issue behaviour | PO | **CLOSED 2026-09-04 — option (a), no stock.** PO: *"(a) — stock control is an inventory system, and the asset-maintenance precedent already parked it"* |

---
id: US-WRK-051
epic: EP-WRK-10
module: work
screens: [Work-030, Work-027, Work-032]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-020]
journeys: [J62]
rules: [BR-WRK-020]
golden_tests: []
finance_calc: proposed
---
### US-WRK-051 — Labour rates: per hour, overtime, dated, per ROLE and never per person — a closed job keeps the rate it closed at (`WM-45`)

**1 · Details** — As **a supervisor**, I want **to set Field technician `48.5000`/h and see `WO-4822`'s report price 52 minutes as `0.87 h × 48.50 = 42.20` — while the 184 exchanges closed before the change keep their old rate**, so that **what an hour in the field costs is a number and not a guess**.

`Work-030` — `/{tenant}/settings/configure/reference-data/work-labour-rates`. RATES BY ROLE, effective 01 Jan 2026: Field technician `48.5000` · `72.7500` · 8 h/day · Senior technician `61.0000` · `91.5000` · Network crew (per crew) `132.0000` · `198.0000` · Contractor · Apex Utility Svc `95.0000` · `95.0000` · — · and a superseded row Field technician `44.0000` · `66.0000` · 01 Jan 2025. *"The rate is per ROLE, not per person, and that is a decision rather than a simplification: a per-person rate is a salary, it belongs in payroll, and putting it on the crews screen would make `WS-23` a page a billing clerk must not open."* *"Contractors carry one rate: an agency invoices its own overtime… The dash is the honest value."* `hourly_rate`, `per_hour` and `overtime` return zero hits in the repository; GL `6020 Overtime` exists under `5500 Payroll & benefits` — *"the destination exists and the rate does not"*, and **nothing here posts to it** (`BR-WRK-004`).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-020` | Per role; hourly, overtime, threshold, effective-from; a closed job keeps its rate; contractor one rate | CONFIRMED — `WM-45` |
| `BR-WRK-004` | Posted nowhere | **CONFIRMED 2026-09-04 — `OQ-WRK-1491` closed to option (a)** |
| CLAUDE.md hard rule 2 | 4 stored, 2 displayed | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Set Field technician `48.5000`/h from 01 Jan 2026 | Stored `48.5000`; `Work-030` shows `48.5000` (a settings screen showing the stored precision, as drawn); the report shows `48.50` |
| TC-2 | Close `WO-4822` on 15 Mar 2026 (52 min, Field technician) | `labour_rate_snapshot = 48.5000`, `labour_role = field_technician` stamped on the order at close |
| TC-3 · **negative** | Change the rate to `50.0000` on 1 Apr | `WO-4822`'s report still prices at `48.5000`; the 184 earlier exchanges unchanged; a new row, the old one *superseded*, **never an UPDATE of the old row** |
| TC-4 · **negative** | A rate with 5 decimals | Refused |
| TC-5 | Contractor row | Overtime reads a dash; `overtime_rate` NULL; the threshold NULL |
| TC-6 · **negative** | `apps/work/**` posts to `6020` | The boundary gate fails on any ledger write; `OQ-WRK-1491` |
| TC-7 · **tenant isolation** | Lone Star Ridge's rates | Its own; Brazos Bend's absent |
| TC-8 | Overtime | 9 h worked on an 8 h/day threshold → 8 h at `48.5000` + 1 h at `72.7500`, computed by `US-WRK-053`'s one function |

**4 · Test Data** — As §1. `WO-4822` on site 15:15–16:07, **52 min**.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| rate row | `Work-030` | `WM-45` | `labour_rates` (role ∈ {field_technician, senior_technician, network_crew, contractor:<crew_id>} · hourly `numeric(18,4)` · overtime_hourly NULL · overtime_after_hours NULL · effective_from · superseded_on NULL) | row | user-input | append-only; one current per role |
| snapshot | `Work-032` | `WM-45` | `work_orders.labour_rate_snapshot`, `.labour_role` | numeric(18,4) · text | system at close | never changes |
| GL 6020 | — | `WM-45` | **no write** | — | — | `OQ-WRK-1491` |

**6 · Acceptance** — **Given** a rate of `48.5000`, **when** a 52-minute job closes, **then** its report reads `0.87 h × 48.50 = 42.20` — **and when** the rate changes, **then** that report does not.

**7 · Finance Calculation** — Labour = `hours_2dp × rate_4dp`, stored 4 dp, displayed 2: `0.87 × 48.5000 = 42.1950 → 42.20`. Overtime above the daily threshold at `overtime_hourly`. **One function**, `US-WRK-053`. No GT; posted nowhere.

**8 · Open Questions** — None new; `OQ-WRK-1491` sits with `US-WRK-054`.

---
id: US-WRK-052
epic: EP-WRK-10
module: work
screens: [Work-031, Work-032]
wave: 2
status: blocked
blocked_by: []
depends_on: []
journeys: []
rules: [BR-WRK-052]
golden_tests: []
finance_calc: none
---
### US-WRK-052 — Tax on a work order: NOT BUILT — PO 2026-09-03, *"Dont add Tax on work order - for now"* (`WM-46`)

**1 · Details** — `WM-46` specified one base flag (`base_includes_field_work`, labour and parts) on the signed `taxes` table and a `per_work_order` value in `flat_frequency`, and drew `Work-031`, a filter of the S13 tax settings. **It is not built.** The Product Owner ruled on 2026-09-03, verbatim: *"Dont add Tax on work order - for now"*. B4 §Tax stands as frozen — *"tax base = usage + base charge only"*, summed from the rounded line amounts — and any change to it is a finance re-sign through `HUMAN-GUIDE.md` §6 with a review-ledger row, never a lane's edit. **`Work-031` is not drawn.** The report (`US-WRK-053`) carries **no tax line**; `WO-4822`'s worked figure is **`$138.42`**, not the wireframe's `$149.84`. What is NOT done, for the record and so nobody reconstructs it from the wireframe: 6.25% and 2.00% of `$138.42` would be `$8.65` and `$2.77`, total `$149.84`. This story exists so the card has a home and a status; it has no test beyond the assertion that nothing was built. `status: blocked` with no `OQ` — it is blocked by a ruling, not a question, and re-opening it is a change request through `13-change-process.md` step 2 (a ❄️ FROZEN figure means STOP).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-052` | Tax on a work order is not built; B4 §Tax stands | CONFIRMED (prohibition) — PO 2026-09-03 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 · **negative** | `rating/models.py` `taxes` and `flat_frequency` | **No** `base_includes_field_work`; `flat_frequency` still `per_bill \| per_service`; a grep for both strings across the repository returns zero — the test is the absence |

**4 · Test Data** — None.

**5 · Data Fields / Mapping** — None. The two columns the card named are **not added**.

**6 · Acceptance** — Nothing is built, and a reader of the report sees no tax line.

**7 · Finance Calculation** — Not done. Recorded only as what is NOT done: `138.42 × 0.0625 = 8.65`, `138.42 × 0.02 = 2.77`, `138.42 + 8.65 + 2.77 = 149.84`.

**8 · Open Questions** — None. A ruling, not a question.

---
id: US-WRK-053
epic: EP-WRK-10
module: work
screens: [Work-032, Work-009]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-051, US-WRK-050, US-WRK-036, US-WRK-048, US-WRK-003]
journeys: [J62]
rules: [BR-WRK-050, BR-WRK-051, BR-WRK-052]
golden_tests: []
finance_calc: proposed
---
### US-WRK-053 — The work-order report: generated ONCE on approval, frozen, versioned — and its arithmetic in one named function with a test on the worked figure (`WM-47`)

**1 · Details** — As **a supervisor accepting `WO-4822`**, I want **a report to appear on the order reading *7 of 7 tasks*, an out-of-range opening read of 1,204 kWh flagged rather than hidden, and a total of `$138.42`**, so that **pressing Accept a second time does not produce a second v1**.

`Work-032` — `/{tenant}/work/orders/WO-4822/report.pdf · generated 15 Mar 2026 16:41 · WO-4822-v1`. OUTCOME · TASKS · 7 OF 7 · READINGS AND PHOTOGRAPHS · COST · CUSTOMER. *"A PDF produced by `accept_field_result`, never by completion… Stored through `document_store` as kind `work_order_report`. A correction produces `-v2` beside `-v1`; neither is overwritten."* *"It is generated on approval and not on completion, because until a person accepts the field data nothing on the page is final."* ⚠ **THE WIREFRAME'S COST TABLE CARRIES TWO TAX LINES AND A TOTAL OF `149.84`; THE REPORT BUILT HERE CARRIES NEITHER AND TOTALS `138.42`** (`US-WRK-052`).

**The arithmetic (`BR-WRK-051`), in `apps/work/costing.work_order_cost_lines(order) → [CostLine]`:**
- hours worked = minutes on site ÷ 60, **rounded to 2 decimals** — 52 min → `0.87 h` (the blueprint's own figure fixes this: at four-decimal hours `0.8667 × 48.5 = 42.03`, seventeen cents away)
- labour = hours × the role rate snapshotted at close, stored 4 dp: `0.87 × 48.5000 = 42.1950`, shown `42.20`; overtime hours at the overtime rate on a second line when the daily threshold is passed
- a part line = `used_qty × unit_cost`: `1 × 96.0000 = 96.0000`, `1 × 0.2200 = 0.2200`
- **total = the sum of the ROUNDED displayed lines**, `42.20 + 96.00 + 0.22 = 138.42`, so a reader adding the column reaches it (the principle B4 already applies to a tax base)

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-050` | Generated once on approval; frozen; versioned; no second v1 | CONFIRMED — `WM-47` |
| `BR-WRK-051` | One named function; hours to 2 dp; lines 4 dp store / 2 display; total = sum of rounded lines | PROPOSED — with a test on the worked figure |
| `BR-WRK-052` | No tax line | CONFIRMED — PO 2026-09-03 |
| `BR-WRK-004` | Posted nowhere | **CONFIRMED 2026-09-04 — `OQ-WRK-1491` closed to option (a)** |
| hard rule 4's shape | The document is frozen; a correction is a new version | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 · **the worked figure** | `work_order_cost_lines(WO-4822)` | Lines: *Labour · Field technician · 0.87 h · 48.5000 · 42.20* · *Part · MTR-E1P · 1 · 96.0000 · 96.00* · *Part · SEAL-01 · 1 · 0.2200 · 0.22*; stored amounts `42.1950 · 96.0000 · 0.2200`; **total `138.42`** |
| TC-2 · **negative** | Hours kept at four decimals | The test asserts labour is **not** `42.03` — the rounding point is part of the rule |
| TC-3 · **negative** | grep the report renderer and `work_order_cost_lines` for `tax` | Zero — no tax line (`BR-WRK-052`) |
| TC-4 | Accept `WO-4822` at 16 Mar 09:12 | `WO-4822-v1.pdf` as `work_order_report`; *Completed 15 Mar 2026 16:07 by D. Ortiz · outcome Passed · approved 16 Mar 2026 09:12 by M. Torres · On site 15:15 – 16:07 · 52 min worked against a 45 min estimate*; the 1,204 kWh row reads *no · 0–999* and is **shown, not hidden** |
| TC-5 · **negative** | Press Accept a second time | Refused (the existing second-accept refusal); **no** `v2`; still one report |
| TC-6 · **negative** | A correction after acceptance (a supervisor edits the opening read's photo attachment) | `WO-4822-v2.pdf` beside v1; v1 byte-identical to before; the immutability trigger on `stored_documents` refuses any UPDATE of v1 |
| TC-7 · **negative** | Generate the report from `submit_field_result` | There is no such call site — a test asserts the renderer is reachable from `accept_field_result` only |
| TC-8 · **tenant isolation** | Lone Star Ridge fetches `WO-4822-v1.pdf` | `404` |
| TC-9 | Overtime | A 9 h job on an 8 h threshold: `8.00 × 48.5000 = 388.00` + `1.00 × 72.7500 = 72.75`, two lines, total `460.75` |

**4 · Test Data** — `WO-4822 · Meter exchange — residential · 221 Oak Ave · Unit 3 · account A-10688 · Miller, Sarah · Electric`. On site 15:15–16:07. Tasks 7 of 7; task 2 *48,221 kWh 📷*; task 5 *1,204 kWh out of range 0–999 · flagged 📷*; task 6 *seal 4417882*. Readings: 48,221 kWh yes `IMG-8841` · 1,204 kWh **no · 0–999** `IMG-8842` · `E1P-77412` — not required. Parts `MTR-E1P` 96.0000 · `SEAL-01` 0.2200. Signed *S. Miller · 15 Mar 2026 16:07 · SIG-4822*. Note *Customer present throughout. Old meter left for collection.*

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| report | `Work-032`, `Work-008` | `WM-47` | `stored_documents` kind `work_order_report`, `work_order_reports` (work_order_id · version · document_id · generated_at · generated_by) | rows | `accept_field_result` | unique (order, version); never updated |
| cost lines | `Work-032` | `WM-47` | `work_order_cost_lines` (kind ∈ {labour, overtime, part} · description · qty · unit · rate `numeric(18,4)` · amount `numeric(18,4)`) — persisted at acceptance so the report and the performance tab read the same figures | rows | `costing.work_order_cost_lines()` | display 2 |
| minutes on site | `Work-032` | `WS-32` | `arrive` assignment row → `completed_at` | minutes | derived | hours to 2 dp |
| total | `Work-032` | `WM-47` | sum of rounded lines | numeric(18,2) as displayed | computed | `138.42` |

**6 · Acceptance** — **Given** `WO-4822` is accepted, **when** the report is generated, **then** it prices 52 minutes as `0.87 h × 48.50 = 42.20`, totals `138.42` with no tax line, shows the flagged reading, and is frozen as v1 — **and** a second Accept produces nothing.

**7 · Finance Calculation** — As §1: `0.87 × 48.5000 = 42.1950 → 42.20`; `1 × 96.0000 = 96.00`; `1 × 0.2200 = 0.22`; **`42.20 + 96.00 + 0.22 = 138.42`**. What is NOT computed: `138.42 × 0.0625 = 8.65`, `138.42 × 0.02 = 2.77`, `149.84` (`US-WRK-052`). **No GT** — money on a non-invoice document; one named function, one test (TC-1, TC-2, TC-9). Posted nowhere.

**8 · Open Questions** — None new. `OQ-WRK-1491` decides whether these lines ever reach the books; the report is the same either way.

---
id: US-WRK-054
epic: EP-WRK-10
module: work
screens: [Work-027]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-053, US-WRK-024]
journeys: [J62]
rules: [BR-WRK-053, BR-WRK-004]
golden_tests: []
finance_calc: proposed
---
### US-WRK-054 — The performance tab: did the field keep its promises, and what it cost — with no link, button or note carrying the total into Finance (`WM-41`)

**1 · Details** — As **a manager**, I want **to read *SLA met 94.2%*, 740 jobs and `$56,337` of field cost across six job types**, so that **I can tell whether any of this was worth doing** — **and find no link anywhere on the page that carries that figure into Finance**.

`Work-027` — SLA MET `94.2%` ↑ 2.1pt · FIRST-TIME FIX `88%` · COST PER JOB `$74` · RECONNECT TIME `2h 40m` · BY JOB TYPE (six rows summing **740 · `$56,337`**). *"r10 says this total 'feeds the O&M / labour line in Finance → Cost & Margin.' Do not build that link. CR-028 D3 is the Product Owner removing exactly that sentence for asset maintenance. The contradiction is registered in §18 and is not settled here — the table is buildable, the arrow into Finance is not."* Everything above the consequence box is arithmetic over orders that already exist; cost per job reads the persisted cost lines (`US-WRK-053`).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-053` | Arithmetic over completed orders; no link into Finance | CONFIRMED — `WM-41` |
| `BR-WRK-004` | Cost captured, posted nowhere | **CONFIRMED 2026-09-04 — `OQ-WRK-1491` closed to option (a)** |
| B14 rule 34 | *Recorded*, never *In the books* | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | The fixture's 740 completed orders | Six rows; volumes 203 · 184 · 127 · 96 · 88 · 42 = **740**; total cost `$56,337` = the sum of the rows' totals |
| TC-2 | SLA met | share of completed orders with `completed_at ≤ due_at`; `94.2%` on the fixture |
| TC-3 · **negative** | grep the rendered page for *Finance*, *Cost & Margin*, *O&M*, `5300` | Zero |
| TC-4 · **negative · absence** | `costing.post_field_cost_to_ledger()` | Raises **the RULING SENTENCE and not a question id** — *"ruled 2026-09-04: a closed job's cost is captured and posted nowhere"*; nothing calls it; the boundary gate would fail a real write anyway. ⚠ **AMENDED 2026-09-05 (`DEF-WRK-4030`)** for `OQ-WRK-1491`'s closure, exactly as TC-5 of `US-WRK-050` above |
| TC-5 | First-time fix | share of orders with no follow-up (`follows_order_id` NULL pointing at them); `88%` |
| TC-6 · **tenant isolation** | Lone Star Ridge's tab | Its own figures; zeros drawn as zeros |
| TC-7 · **copy** | Every tile qualifier | ≤ 6 words; the word under the cost figure is *Recorded* |

**4 · Test Data** — By job type (r10's own, verbatim): Read verification 203 · 16m · 98% · 96% · $31 · $6,293 · Meter exchange 184 · 42m · 95% · 91% · $186 · $34,224 · Move-in activation 127 · 24m · 97% · 94% · $44 · $5,588 · Disconnect — non-payment 96 · 21m · 92% · 89% · $38 · $3,648 · Reconnect after payment 88 · 14m · 89% · 97% · $29 · $2,552 · Leak investigation 42 · 51m · 88% · 74% · $96 · $4,032 · **Total 740 · $56,337**.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| tiles and table | `Work-027` | `WM-41` | `GET /work/performance?period=` — aggregates over `work_orders` + `work_order_cost_lines` | numbers | computed | cost displayed 2 dp; percentages 1 dp as drawn |
| the arrow | — | `WM-41` | **none** | — | — | `OQ-WRK-1491` |

**6 · Acceptance** — **Given** 740 completed orders, **when** a manager opens Performance, **then** the six rows sum to 740 and `$56,337` — **and** nothing on the page offers to move that figure anywhere.

**7 · Finance Calculation** — Cost per job = the order's persisted cost-line total; total cost = the sum over completed orders in the period; both displayed 2 dp. **Posted nowhere.** No GT.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-WRK-1491` | Does a closed job's cost reach the books? | Any posting; the Finance arrow. The table ships | PO | **CLOSED 2026-09-04 — option (a), captured and posted nowhere.** PO: *"(a) captured, posted nowhere"*. Payroll already posts the hour; posting field labour beside it would count the same hour twice |
