# EP-REP-03 — Report builder v1 (S47)

**Module:** reports · **Wave:** W5 · **Screens:** S47 (→ S46 run) · **Status:** draft (BR-REP-001..018 CONFIRMED; dataset scope = A14 §Builder, closed list)

## Scope
**In:** the **v1 report builder** exactly per A14 §Builder: dataset picker over the SIX A14 datasets (**Bills / Payments / Accounts / Meter reads / Adjustments & credits / Premises & units**), column picker, filter + group-by + date range + sort, **Run → S46 generic render**, **Save & schedule**, IS-11 export.
**Out — explicitly scoped:** the NEW entities (write-offs, corrections, back-bills/penalty, budget status, delivery queue, returned mail) are **canned-report-only v1** (BR-REP-007 ships them canned; A14's builder dataset list is closed — no dataset invented over them) · scheduling mechanics (EP-REP-04) · viewer/download shell (EP-REP-01) · IS-5 column persistence framework (US-SHL-007, consumed).
**Tables:** read-models over the six datasets' owning tables; saved definitions = B2 anchoring pending (pack report R-1, DDL 🔒).

## Capability matrix (list screens only — B9 conformance)
*(S47 is a form/wizard surface, not an IS-2 list — no capability row. Its RUN output renders in S46 under the US-REP-002 viewer contract; export follows the visible column set per IS-9/IS-5.)*

## Stories

---
id: US-REP-010
epic: EP-REP-03
module: reports
screens: [S47]
wave: 5
status: draft
blocked_by: []
depends_on: [US-REP-002, US-SHL-006]
journeys: [J5]
rules: [BR-REP-006, BR-REP-007, BR-PAY-021]
golden_tests: []
finance_calc: none
---
### US-REP-010 — Dataset + column picker: six A14 datasets, closed list; new entities stay canned

**1 · Details** — As staff, I want the builder's **Dataset** select with exactly the A14 §Builder six: **Bills · Payments · Accounts · Meter reads · Adjustments & credits · Premises & units** — a CLOSED v1 list (the audit-added entities are served by their canned reports only, BR-REP-007; no builder dataset exists over them). **Columns** = the A14 chip palette (Account · Customer · Amount · Service · Cycle · Status · Date) mapped per dataset, with: the dataset's identity column always included (IS-5 rule), the **Payments dataset exposing BOTH `posted_at` and `cleared_at`** (BR-PAY-021 — staff always see both dates), **Meter reads exposing `channel` + unit** (A14 item 6; CLAUDE.md #3 — consumption never unitless), and Amount absent from non-money datasets (Premises & units). Status/Service/class values everywhere = live vocabularies (BR-REP-006). Entry: S44 "+ Build your own". Exit: US-REP-011 (filters/run).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| A14 §Builder | Dataset list = the six named datasets; column palette as extracted. | CONFIRMED — A14 (extraction) |
| BR-REP-007 *(scope)* | New entities ship as CANNED reports (RQ-9) — v1 builder never grows a dataset over them. | CONFIRMED — audit F-4/5/7..13 |
| BR-PAY-021 *(consumed)* | Payments rows carry posting + clearing dates as first-class columns. | CONFIRMED — PO explicit ruling, 2026-08-08 |
| BR-REP-006 | Column/filter value vocabularies are live, never hardcoded. | CONFIRMED — audit F-17..21 |
| IS-5 *(consumed)* | Identity column always visible; export follows the visible set. | CONFIRMED — B9 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dataset select | Exactly six options, A14 order; nothing else |
| TC-2 | Payments dataset columns | Both `posted_at` and `cleared_at` offered (BR-PAY-021); `purpose` available (BR-PAY-012 vocabulary via BR-REP-006) |
| TC-3 | Meter-reads dataset columns | `channel` + quantity WITH unit offered (A14 item 6, CLAUDE.md #3); no unitless consumption column exists |
| TC-4 *(negative)* | Attempt to build over write-offs / corrections / delivery queue (URL or API) | No such dataset — 4xx/validation; the canned report is the only surface (BR-REP-007 scope) |
| TC-5 *(negative)* | Deselect all columns | Identity column persists (IS-5) — a zero-column definition cannot be produced |
| TC-6 *(isolation)* | Lone Star Ridge builder | Vocabulary values (services, statuses, cycles) = its own only (RLS/BR-REP-006) |

**4 · Test Data** — Brazos Bend datasets: Bills (LE-1 month), Payments (PE-10 set), Accounts (status mix incl. Vacation hold), Meter reads (TOU channel rows M-7450), Adjustments & credits (ADJ-142 −15.00 goodwill, prototype), Premises & units (500 Main Plaza fixture). Actors: Sam Alvarez. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Dataset | S47 | A14 §Builder | one of: invoices / payments / accounts / meter_reads / adjustments+credit_notes / premises+units | enum | user-input | closed six-value list |
| Column set | S47 | A14 §Builder + IS-5 | per-dataset column registry | list | user-input | identity always on |
| Payments date columns | S47 | BR-PAY-021 | `payments.posted_at`, `.cleared_at` (r12 #1) | timestamps | computed-display | both offered |
| Channel/unit columns | S47 | A14 item 6 + CLAUDE.md #3 | `meter_reads.channel` + qty w/ UoM | enum/qty | computed-display | unit mandatory |

**6 · Acceptance**
- Given the picker, Then exactly the six A14 datasets exist and new entities have no builder path.
- Given columns, Then identity persists, payments carry both dates, and reads carry channel + unit.
- Given tenants, Then vocabularies never cross.

**7 · Finance Calculation** — N/A (definition surface).

**8 · Open Questions** — None.

---
id: US-REP-011
epic: EP-REP-03
module: reports
screens: [S47, S46]
wave: 5
status: draft
blocked_by: []
depends_on: [US-REP-010]
journeys: [J5]
rules: [BR-REP-001, BR-REP-006, BR-CUS-016]
golden_tests: []
finance_calc: none
---
### US-REP-011 — Filters, group-by, date range, sort → Run (basis-labeled generic render)

**1 · Details** — As staff, I want the builder's shaping controls per A14 §Builder: **Filter** (No filter / Amount > threshold / Status is past-due / Service is…), **Group by** (None / Service / Cycle / Account class / Month), **Date range** (This month / Last month / Custom), **Sort** (Amount high→low / Date newest / Account), then **Run report →** rendering in the S46 generic viewer (US-REP-002 shell). Semantics from ratified law only: "Status is past-due" = the DERIVED display state (BR-CUS-016 — open invoice past due, posting-basis money per BR-PAY-021); "Service is…" enumerates the tenant-enabled set (BR-REP-006); for the **Payments dataset the date range names the date field it filters** (posted vs cleared — both first-class per BR-PAY-021), defaulting per BR-REP-001's side rule (cash-side = clearing), and the run header **labels the applied basis** (BR-REP-001) — a money run rendering unlabeled is a defect. Money-dataset runs (Bills/Payments/Adjustments) always carry the basis label; totals footer per group. Entry: US-REP-010 definition. Exit: rendered run; US-REP-012 save/export.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| A14 §Builder | Filter/group/range/sort options as extracted. | CONFIRMED — A14 |
| BR-REP-001 | Money runs label their basis; billing-side = posting, cash-side = clearing. | CONFIRMED — PO ruling 2026-08-08 |
| BR-CUS-016 *(consumed)* | "Past-due" = derived from open-invoice due-date math (+ opening buckets), never a stored state. | PROPOSED (derivation) / vocabulary CONFIRMED — BR-CUS-055 |
| BR-PAY-021 *(consumed)* | Payments date filter operates on a NAMED date field; both dates first-class. | CONFIRMED — PO explicit ruling, 2026-08-08 |
| BR-REP-006 | "Service is…" and class values = live vocabularies. | CONFIRMED — audit F-17..21 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Bills · Amount > 500 · This month (LE-1 + specials fixture) | Returns WE-11 penalty 626.42 (and any bill > 500); WE-1 247.87 excluded; header labels **posting basis** |
| TC-2 | Accounts · Status is past-due | Membership = derived past-due state (open invoice past due / aged opening bucket, BR-CUS-016/048); a posted-by-due-date-but-uncleared payment keeps its account OUT (BR-PAY-021) |
| TC-3 | Payments date range | The range control names its field; default = cleared_at (cash-side per BR-REP-001), switchable to posted_at; header labels the chosen basis |
| TC-4 | Group by Month + sort | Groups with per-group totals footer; sort options apply; stable secondary sort by id (IS-2) |
| TC-5 *(basis label)* | Any money-dataset run | Basis label present on header + files — unlabeled = FAIL (BR-REP-001) |
| TC-6 *(negative)* | Amount threshold non-numeric / negative range | Inline validation per IS-7; no run |
| TC-7 *(isolation)* | Lone Star Ridge run | Its rows only (RLS) |

**4 · Test Data** — LE-1 bills + WE-11 penalty; PE-10 payments (posted Jul 31 / cleared Aug 2 divergence fixture from US-REP-007 TC-3); past-due fixture: WE-3 16.42 unpaid past due; A-12103 opening buckets. Actors: Sam Alvarez, Norma Reyes. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Filter | S47 | A14 §Builder | predicate over the dataset read-model | enum+value | user-input | typed per filter |
| Past-due predicate | S47 | BR-CUS-016/048 | derived display-state computation | bool | computed-display | never a stored flag |
| Group by / Sort | S47 | A14 §Builder | regroup/order of the same rows | enum | user-input | per-dataset options |
| Date range + field | S47 | A14 §Builder + BR-PAY-021 | window over the named date column | dates | user-input | field named; From ≤ To |
| Run render | S46 | A14 §Builder → generic viewer | generic table + totals (US-REP-002) | rows | computed-display | basis labeled on money |

**6 · Acceptance**
- Given the fixtures, Then filters/group/sort behave per A14 with ratified semantics (derived past-due, named payment date field).
- Given money runs, Then the basis label always renders.
- Given validation/tenants, Then bad inputs never run and rows never cross.

**7 · Finance Calculation** — N/A (row selection/ordering; no new money math — amounts render verbatim from their sources).

**8 · Open Questions** — None.

---
id: US-REP-012
epic: EP-REP-03
module: reports
screens: [S47, S44, S45]
wave: 5
status: draft
blocked_by: []
depends_on: [US-REP-011, US-REP-003]
journeys: [J5]
rules: [BR-REP-018, BR-REP-002]
golden_tests: []
finance_calc: none
---
### US-REP-012 — Save & schedule + export: named definitions, IS-4 sharing, IS-11 files

**1 · Details** — As staff, I want **Save & schedule** and export on a built report (A14 §Builder actions "Run / Save & schedule"): **Save** stores a named definition (dataset + columns + filters + group + range + sort; creator + timestamps recorded, audited) that lists on S44 for the tenant (US-REP-001) and re-runs from S44/S45; **share** = the IS-4 URL-persisted state (shareable/bookmarkable — any staff user opening the URL runs it under their OWN permissions and tenant); **Save & schedule** continues into the US-REP-013 scheduling flow with the definition attached; **export** of a run = IS-11 via US-REP-003, respecting the visible column set (IS-9/IS-5) — custom runs write report_run rows (US-REP-004) and obey the 50k guard + money-export audit (BR-SHL-016). A definition stores PARAMETERS only — never result rows (BR-REP-002: figures recompute from the read-model at every run). Entry: S47 actions. Exit: definition on S44; schedule in S45; file per contract.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| A14 §Builder | "Save & schedule" is the ratified action pair. | CONFIRMED — A14 |
| BR-REP-002 | Saved definitions hold parameters; results always recompute from read-models. | CONFIRMED — reports audit 2026-08-08 |
| BR-REP-018 / BR-SHL-016 *(consumed)* | Export per IS-11; streamed, 50k cap, money-export audit. | CONFIRMED — PO 2026-08-08 / PO R1 A2 |
| IS-4 / IS-5 / IS-9 *(consumed)* | URL state shareable; export follows visible columns. | CONFIRMED — B9 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Save "July high bills" (Bills · Amount > 500 · Jul) | Definition stored with creator Sam Alvarez + audit row; appears on S44 (US-REP-001 TC-6 pairing); re-run recomputes — an invoice corrected since save changes the output (BR-REP-002, WE-9) |
| TC-2 | Share via URL | A second staff user opens the URL → same definition runs under their session; params identical, data = their permissions/tenant (IS-4) |
| TC-3 | Export a custom run | IS-11 CSV with the VISIBLE columns only (IS-9/IS-5); filename `brazos-bend_custom_july-high-bills_2026-07_posting_20260805.csv`; report_run row written (US-REP-004) |
| TC-4 | Save & schedule | Hands the saved definition into the US-REP-013 create-schedule flow prefilled |
| TC-5 *(negative)* | Custom run > 50,000 rows exported | Rejected per BR-SHL-016 with narrow-or-schedule guidance |
| TC-6 *(isolation)* | Lone Star Ridge | Its definitions only on S44; a Brazos Bend definition URL under a Lone Star session yields that tenant's (empty) data, never cross-tenant rows (RLS) |

**4 · Test Data** — Definitions: "July high bills" (Bills, >500, Jul 2026), "Deposit-purpose payments" (Payments, purpose=deposit, cleared_at Aug). Creator: Sam Alvarez; second user: Priya Menon. Files per IS-11 convention. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Saved definition | S47 | A14 §Builder "Save & schedule" | saved report definitions — B2 anchoring pending (pack report R-1, DDL 🔒) | row (params jsonb) | user-input | name required; params only, never rows |
| Creator/audit | S47 | CLAUDE.md #7 | definition row + `audit_log` | uuid/jsonb | system-derived | append-only |
| Share URL | S47/S46 | IS-4 | URL-encoded state | text | computed-display | runs under opener's session |
| Export | S46 | IS-11 + IS-9/IS-5 | streamed file, visible columns | file | computed-display | 50k cap; audit |
| Schedule handoff | S47→S45 | A14 §Builder | schedule row referencing the definition (US-REP-013) | fk | user-input | definition must exist |

**6 · Acceptance**
- Given save, Then definitions persist parameters only, list per tenant, and re-runs recompute live.
- Given share/export, Then IS-4 URLs and IS-11 files behave exactly, visible-columns respected.
- Given guards/tenants, Then 50k and RLS hold.

**7 · Finance Calculation** — N/A (definition persistence; money renders per source stories).

**8 · Open Questions** — None. *(Saved-definition visibility scope beyond "lists for the tenant's Reports-access staff" — e.g. private-to-creator drafts — is underivable from A14; recorded as candidate OQ R-3 in the pack report, non-blocking.)*
