# EP-AST-05 — Net-meter reads (consumption + export read records)
> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep.

**Module:** assets · **Wave:** W2 · **Screens:** S50 (Reads tab), S28 (read upload — export-record touchpoint), S25/S29 (reads list/detail surfacing) · **Status:** draft

## Scope
**In:** capture and storage of BOTH directions — **consumption/import** (delivered to the customer) and **export** (fed back to the grid) — as **typed read records** (`meter_reads.read_type`, BR-AST-029 / B2 r7) on reads of `net_metering` assets, across every ingestion path (AMI/integration, S28 CSV upload, manual entry); read-type validation; and surfacing both record types wherever the read appears (S50 Reads tab, S25 list, S29 drawer). These stories are **capture/storage/display only and are NOT blocked** by the credit question.
**Out:** **the net-metering credit math itself — netting method, bank unit, true-up month, avoided-cost rate, payout threshold — is rating's EP-RAT-06, gated by OQ-001 (referenced, NOT re-asked, NOT duplicated)** · read validation thresholds (OQ-002 — closed; metering) · estimation of net reads (OQ-003 — closed; metering) · any $ display of export anywhere in this module.
**Tables:** metering-owned `meter_reads` + **B2 r7 `read_type` enum (`consumption` | `export`)** + `assets.net_metering`. Writes via metering service functions (B1); rating consumes via service read (B2 §2 interface set).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| — | *(no list screens owned here — S50 Reads tab declared in EP-AST-02; S25 is metering's screen and its matrix row belongs to the metering pack)* | | | | | | | |

## Stories

---
id: US-AST-011
epic: EP-AST-05
module: assets
screens: [S28, S50]
wave: 2
status: draft
blocked_by: []
depends_on: [US-AST-002, US-MET-007, US-MET-010]
journeys: []
rules: [BR-AST-010, BR-AST-029]
golden_tests: []
finance_calc: none
---
### US-AST-011 — Capture and store consumption + export read records on net-meter reads

**1 · Details** — As a utility billing solar customers, I want every cycle read of a net meter to record how much energy came in AND how much went out, so that rating has the inputs to compute net-metering credits when finance signs the math (OQ-001). Entry: reads arrive via the existing metering paths — AMI ingestion, the S28 read-upload wizard (gains an optional `read_type` column: `consumption` default, `export` honored only for net assets), and manual read entry (an export-read field appears for net assets). Storage: a net meter's cycle read is **TWO `meter_reads` records — one `read_type = consumption` and one `read_type = export`, same `read_at`** (BR-AST-029, B2 r7 — supersedes the earlier same-row two-column model, BR-AST-024). Exit: reads visible per US-AST-005/012; rating consumes downstream.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AST-010 | Only assets with `net_metering = true` carry export records (defined US-AST-002 — shared). | CONFIRMED — PO R4-A7 |
| BR-AST-029 | **Net-meter reads are TWO SEPARATE read records with a reading type** — `meter_reads.read_type` enum: `consumption` (default, all normal reads) \| `export`. A net meter's cycle read = one consumption record + one export record, same `read_at`; uniqueness `(asset, read_at, read_type)` (B2 r7). The register reading (`current_value`) belongs to the consumption record (42,180 → 42,864 = 684 delivered); an export register, if the AMI feed provides one, lives on the export record. Export records on non-net assets are rejected; a missing export record on a net cycle → 0-value export record + review flag. Records follow `meter_reads` append-only practice — corrections are new rows. Supersedes BR-AST-024 (two-columns-one-row model). | CONFIRMED — PO R4-A6 ("save them as two records with type of reading") + B2 Addendum r7 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | AMI ingests M-4021 read 2026-08-03: register 42,864, delivered 684 kWh, export 120 kWh | TWO `meter_reads` records, same read_at (BR-AST-029): `read_type=consumption` (current 42,864, consumption 684) + `read_type=export` (120), unit kWh, source ami, status ok |
| TC-2 | S28 CSV upload with `read_type` column rows for M-4021 (Sep cycle: 702 / 141) | Staged, validated, committed like any read; posts as one consumption record + one export record sharing read_at |
| TC-3 | Manual read entry on M-4021 | Reading and Export fields shown (net asset); save writes the two typed records, each with explicit unit kWh |
| TC-4 *(negative)* | S28 row supplies an export-typed read = 55 for M-4022 (`net_metering = false`) | Row error "export record not allowed — not a net-metering asset" (BR-AST-029); row excluded per the wizard's per-row error pattern |
| TC-5 *(negative)* | Export value = −12 or consumption non-numeric | Validation error; row rejected; nothing stored |
| TC-6 | AMI read for M-4021 arrives with the consumption record only | A 0-value export record is created and flagged for review (BR-AST-029); not silently treated as complete |
| TC-7 *(isolation)* | Lone Star Ridge uploads reads naming asset "M-4021" | Resolves to Lone Star Ridge's own M-4021 only; Brazos Bend's read history untouched |
| TC-8 *(negative)* | A second export record posted for M-4021 at the same read_at | Rejected by the `(asset, read_at, read_type)` uniqueness (B2 r7); correction path is a superseding row, never a duplicate record |

**4 · Test Data** — M-4021 (net, kWh, ×10) record pairs: Aug 3 register 42,864 / consumption 684 / export 120; Sep 3 CSV 702/141. M-4022 (water, non-net) for TC-4. Lone Star Ridge M-4021 (net, kWh). Actors: Dana Whitfield (uploads), system AMI feed; Erin Walsh.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Read type | S28 column / system default | B2 r7 (`read_type` enum) + BR-AST-029 | `meter_reads.read_type` enum `consumption` \| `export` NOT NULL DEFAULT 'consumption' | enum | integration/user-input/system-derived | export only for net assets; UNIQUE (asset, read_at, read_type) |
| Consumption (delivered) record | S28 / manual field | prototype-extracted (S50 Reads "Import") | `meter_reads` row with `read_type='consumption'` (`current_value`, `consumption`, `unit`) | numeric(18,6), asset unit | integration/user-input | ≥ 0 |
| Export record | S28 / manual field | prototype-extracted (S50 Reads "Export (net)") | second `meter_reads` row with `read_type='export'`, same `read_at` — quantity in `consumption`; export register in `current_value` when the AMI feed provides one (display-only, no computation) | numeric(18,6), asset unit | integration/user-input | ≥ 0; net assets only; rejected otherwise (BR-AST-029) |
| Register reading | existing | A3 r4 / B2 | `meter_reads.current_value` on the consumption record (BR-AST-029) | numeric(18,6) | integration/user-input | BR-AST-015 bound |
| Unit | existing | CLAUDE.md #3 / B2 | `meter_reads.unit` — explicit on EACH record | text | system-derived from asset | explicit, never assumed |
| Review flag (missing export) | — | derived (BR-AST-029) | `meter_reads.status` on the 0-value export record (existing read_status review path, metering-owned) | enum | system-derived | — |

**6 · Acceptance**
- Given a net-metering asset, When a cycle read arrives by any path, Then two typed records (consumption + export) share the read_at, each with an explicit unit (BR-AST-029).
- Given a non-net asset, When an export record is supplied, Then it is rejected/row-errored — never silently stored.
- Given a net cycle missing its export record, When stored, Then a 0-value export record exists and is flagged for review.

**7 · Finance Calculation** — N/A (records are quantities; credit math is EP-RAT-06, gated by OQ-001 — referenced, not duplicated).

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-001 *(existing — referenced, not duplicated)* | Net-metering credit math (netting, bank unit, true-up, avoided-cost rate, payout threshold) | EP-RAT-06 / GT-12 only — capture/storage here is NOT blocked | Product Owner + finance (per registry) | ROUTED — proposal in B4 addendum |

---
id: US-AST-012
epic: EP-AST-05
module: assets
screens: [S50, S25, S29]
wave: 2
status: draft
blocked_by: []
depends_on: [US-AST-005, US-AST-011, US-MET-012, US-MET-013]
journeys: []
rules: [BR-AST-016, BR-AST-029, BR-AST-025]
golden_tests: []
finance_calc: none
---
### US-AST-012 — Surface typed read records and hand them to rating (quantities only)

**1 · Details** — As a staff user, I want consumption/export shown wherever a net meter's reads appear — the asset's Reads tab (S50), the global Reads list (S25) and read drawer (S29) — and as a utility, I want rating to receive those typed read records through the module interface, so that billing can apply credits the moment finance signs the math without any rework here. Entry: existing read surfaces; the rating engine calls the metering read-interface (B2 §2 reviewed interface set), which returns **both `read_type` record kinds** (BR-AST-029). Exit: none (display + interface story). The credit **computation** never happens in this module (BR-AST-025).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AST-016 | Reads-tab display rules (defined US-AST-005 — shared); net reads render as two typed rows per BR-AST-029. | CONFIRMED — PO R4 Q20/B7 |
| BR-AST-029 | Two-record storage model (defined US-AST-011 — shared). | CONFIRMED — PO R4-A6 / B2 r7 |
| BR-AST-025 | Reads feed rating as **inputs only**: assets/metering expose the typed read records (`read_type`, `consumption`, `unit`) via the read service interface and never compute, store, or display a credit amount; export renders as quantity + unit everywhere, never money. Credit math lives in rating (EP-RAT-06), gated by OQ-001; nothing in this module blocks on it. | CONFIRMED — PO R4-B11 (module boundary per B1/B2 §2 + A8 net-metering addendum) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | S25 global Reads list rows for M-4021 | A net cycle lists as its two typed records: the consumption row (usage 684 kWh) and the export row ("↩ export · 120 kWh" type tag) — not channel columns (BR-AST-029); S29 drawer shows each record's type + a link to its paired record (same asset, same read_at) |
| TC-2 | S50 Reads tab for M-4021 | Two typed rows per cycle date per US-AST-005 (regression alongside the new surfaces) |
| TC-3 | Rating service requests M-4021 reads for the Aug cycle via the metering interface | Response includes both records: `read_type=consumption` (684 kWh) and `read_type=export` (120 kWh), unit kWh; contract test pins the field names incl. `read_type` |
| TC-4 *(negative)* | Search all module surfaces + API payloads for a computed credit $ on export | None exists — export is quantity-only everywhere (BR-AST-025); no currency field in the read interface |
| TC-5 *(isolation)* | Rating computation running for Lone Star Ridge requests reads | Interface returns only rows under `app.tenant_id` = Lone Star Ridge; Brazos Bend's M-4021 records never cross |

**4 · Test Data** — M-4021 Aug record pair (684 / 120 kWh) + Sep (702 / 141). Lone Star Ridge M-4021 Aug record pair (312 / 48 kWh). Rating consumer: stubbed EP-RAT-06 contract test (its math xfail'd behind OQ-001, per golden-test conventions).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Export row + read-type tag (S25) | S25 | derived — S25 is designed pre-r4; net record rows extend it per S50's pattern (GAP noted, no OQ: same data, same rendering rule) | `meter_reads.read_type = 'export'` rows (B2 r7 — supersedes the voided import_qty/export_qty PROPOSED-SCHEMA) | numeric + unit | computed-display | net reads only |
| Record types in S29 drawer | S29 | derived (drawer shows one read record + compliance) | `meter_reads.read_type` + `consumption` per record; paired record linked by (asset, read_at) | numeric + unit | computed-display | — |
| Read interface fields | — | B2 §2 (cross-module interface set) | metering read service response rows carry `read_type`, `consumption`, `unit` alongside existing fields — both record kinds returned | numeric(18,6) / enum | system-derived | contract-tested (TC-3) |
| No-credit invariant | — | BR-AST-025 / A8 addendum | — (absence of any credit field in this module) | — | — | TC-4 |

**6 · Acceptance**
- Given net reads exist, When any read surface renders them, Then both typed records show as quantities with explicit units and no money.
- Given rating requests reads, When both record types exist, Then they arrive through the service interface with pinned field names incl. `read_type`.
- Given tenant isolation, When rating runs per tenant, Then read records never cross tenants.

**7 · Finance Calculation** — N/A (explicitly out of scope — EP-RAT-06 / OQ-001).

**BUILT 2026-08-16 — the PAIR surface, and what it deliberately does not do.** The storage model, the validation refusing an export record on a flat meter and the flagged 0-value record for a net cycle without one had all shipped in W2, and **no screen showed the two channels AS A PAIR** — which `10-scripts/gates/surface_debt.txt` named as this module's last unreachable story. `selectors.net_meter_pair` serves both channels of one cycle, `GET /reads/{id}` carries it as `net_pair`, and `07-frontend/src/features/metering/NetMeterPair.tsx` draws them side by side in the S29 drawer — 684.000000 kWh delivered against 120.000000 kWh fed back, each with its own unit. **THE TWO FIGURES ARE NEVER NETTED AND A TEST ASSERTS THE STRING "564" APPEARS NOWHERE**: that subtraction IS the net-metering credit math, it is rating's EP-RAT-06, it is gated by OQ-001, and v1 bills solar and battery as capacity charges — the panel says so on its face rather than letting two numbers read like a bill in the making (BR-AST-025). A FLAT meter draws NOTHING (BR-AST-010) and a net cycle with no export reading says so in words, because "Export: 0" would be a measurement of a register nobody read. **TC-2's S50 asset Reads tab does NOT show the pair**, and the reason is one story further back: S50 HAS a Reads tab and it renders an `ArrivesWith` placeholder, because US-AST-005's `GET /assets/{id}/reads` is not served and an empty table there would claim *this asset has no reads*. There is no per-asset read LIST for the pair panel to sit in yet. REPORTED rather than counted, because the capability is reachable through S25/S29.

**8 · Open Questions** — None minted (OQ-001 referenced in US-AST-011 §8; nothing here blocks on it).
