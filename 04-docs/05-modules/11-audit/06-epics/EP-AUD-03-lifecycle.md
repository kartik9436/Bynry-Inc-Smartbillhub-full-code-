# EP-AUD-03 — Trail lifecycle: retention job, archive query path, and the user-activity-audit feed

**Module:** audit · **Wave:** W5 (nothing ages past the hot window before then; feed ships with the reports wave) · **Screens:** S61 (archive toggle) · S44 (Compliance card routing — feed owned here, reports dedups R-2) · **Status:** draft

## Scope
**In:** the **retention job** — monthly partition pre-create + AUTOMATIC detach-to-cold of partitions fully older than 2 years + supervised purge only past the 7-year total (NFR-28; OQ-017 closure; the reads pattern BR-MET-055/US-MET-020 applied verbatim — NFR-28: "matches reads pattern"); the **cold-storage query path** — explicit "Search archive" opt-in on S61, hot-window default untouched, RLS identical on archive reads; the **User-activity-audit report feed** — the A14 Compliance card served as an IS-11 CSV/PDF feed over the S61 dataset (S61's ratified columns), **owned by this story; reports pack dedups its R-2 flag for this card** (bespoke columns beyond the S61 set stay unratified — R-2 candidate).
**Out:** meter-read archival (US-MET-020 — the pattern's origin, untouched) · report-center surfaces S44/S46 themselves (US-REP-001/002 — the card routes, reports renders) · closed-tenant / closed-account end-of-retention disposition (**OPEN**: data-retention.md closed-tenant row + **SC-7 pending — NOT decided here**) · security-event catalog expansion (**SC-3 pending**) · exact partition/cold-store/scheduler DDL + mechanics (Eng-Lead 🔒).

## Capability matrix (list screens only — B9 conformance)
No new list screens (S61's matrix row is in EP-AUD-02; the archive toggle is a query-scope flag on that same screen; the feed renders in the S46 viewer per US-REP-002's conformance).

## Stories

---
id: US-AUD-007
epic: EP-AUD-03
module: audit
screens: [S61]
wave: 5
status: draft
blocked_by: []
depends_on: [US-AUD-001]
journeys: [J5]
rules: [BR-AUD-012, BR-AUD-002, BR-AUD-015]
golden_tests: []
finance_calc: none
---
### US-AUD-007 — Auto-archival job: 2-yr hot → cold storage, 7-yr total, audited, never manual

**1 · Details** — As a platform subject to a 7-year audit-retention obligation (OQ-017 closure: 7-yr total, 2 yrs hot then archived — PO R6), I want a **scheduled monthly job** that detaches `audit_log` monthly partitions fully older than the 2-year hot window to cold storage and purges cold partitions only past the 7-year bound — **automatic, never manual, fully audited** (NFR-28; B2 r8's archival-job wording; BR-MET-055's "never manual" applied per NFR-28 "matches reads pattern"; US-MET-020 is the sibling implementation) — with a checksummed run record per detachment and the job's own actions written as audit rows (`audit_log.partition_archived` / `.partition_purged` — the trail records its own lifecycle). End-of-retention deletion is this supervised archival job, **never an operational path** (data-retention.md). **Not decided here:** closed-tenant offboarding SLA (data-retention OPEN row) and closed-account PII retention (SC-7) — if either closes with a different bound, this job takes new config; today it enforces exactly the 7/2 law. Partition pre-create (3 ahead) rides the same scheduler (US-AUD-001). Entry: monthly schedule. Exit: partitions detached/purged, run + audit records written; S61 default view unaffected (US-AUD-008 reads the archive).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AUD-012 | Monthly partitions; partitions fully older than 2 yrs detach to cold storage via an AUTOMATIC scheduled job (never manual), audited; 7-yr total; purge only past 7 yrs, recorded. | CONFIRMED — NFR-28 + OQ-017 closure (PO R6) + data-retention.md addendum + BR-MET-055 pattern (PO RD-13; B2 r8 "scheduled, audited") |
| BR-AUD-002 *(shared)* | Archival moves partitions; it never UPDATEs/DELETEs rows in the operational path. | CONFIRMED — B2 §audit + data-retention.md ("supervised archival job, never an operational path") |
| BR-AUD-015 *(shared)* | Closed-tenant / SC-7 dispositions are OPEN — the job takes config when they close; nothing pre-decided. | OPEN — data-retention.md + SC battery (PO) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Monthly run 2028-09-01 02:00 UTC | `audit_log_2026_08` (fully older than 2 yrs) detached → cold storage; younger partitions untouched; run record: partition, row count 2,318,407, destination, SHA-256 manifest, status success |
| TC-2 | Trail after TC-1 | `audit_log.partition_archived` rows written (partition id, row count, run id) — the job audits itself per BR-AUD-012 |
| TC-3 | Run 2033-09-01 | Cold partition `audit_log_2026_08` (now past 7 yrs) purged; purge recorded in run record + `audit_log.partition_purged` row; nothing younger than 7 yrs ever purged |
| TC-4 *(negative — never manual)* | UI/API attempt to trigger, skip, or early-run archival | No such action exists; direct calls to the job entry point outside the scheduler rejected (BR-MET-055 pattern — "never manual") |
| TC-5 *(negative)* | Duplicate schedule fire re-runs 2028-09-01 | No-op run recorded; nothing double-detached, no error (US-MET-020 TC-5 pattern) |
| TC-6 *(immutability)* | Operational DELETE attempted against a hot or cold partition's rows | Rejected — deletion exists ONLY as the supervised 7-yr purge inside this job; no operational delete path (BR-AUD-002) |
| TC-7 *(isolation)* | Partitions are physically shared across tenants; archive of 2026_08 contains both tenants' rows | Detachment is a platform storage op; every subsequent READ (US-AUD-008) still executes under `app.tenant_id` — the isolation suite asserts zero cross-tenant rows from archive reads |

**4 · Test Data** — Partitions: `audit_log_2026_08` (2,318,407 rows — B6-scale month) … `audit_log_2028_08` (hot). Schedule: monthly, 1st, 02:00 UTC. Destination: `s3://smartbillhub-archive/prod/audit_log/2026_08/` + SHA-256 manifest `4be7…d902`. Purge fixture: run 2033-09-01 vs Aug 2026 data. Tenants in-partition: Brazos Bend + Lone Star Ridge.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Hot-window bound | — | NFR-28 (2 yr) | job config: 24 months | interval | reference-data | fixed by NFR-28 |
| Partition detach | — | B2 §5 + NFR-28 | DETACH PARTITION → cold storage transfer | DDL/storage op | system-derived | only fully-older-than-2-yr; Eng-Lead 🔒 |
| Retention purge | — | NFR-28 (7 yr) + data-retention.md | cold partition removal past 7 yrs, supervised | storage op | system-derived | never younger; recorded |
| Job run record | — | BR-AUD-012 ("audited") | **PROPOSED-SCHEMA** `archive_job_runs` family (US-MET-020 §5 pattern; one mechanism, two tables) | row | system-derived | append-only; rerun-safe |
| Self-audit rows | S61 | BR-AUD-012 + CLAUDE.md #7 spirit | `audit_log` `audit_log.partition_archived` / `.partition_purged` | jsonb | system-derived | append-only |
| Open-disposition config seam | — | data-retention.md OPEN + SC-7 | config consumed when the PO closes them | — | reference-data | nothing pre-decided |

**6 · Acceptance**
- Given the monthly schedule, Then partitions fully older than 2 years detach to checksummed cold storage with run + audit records, and nothing younger is touched.
- Given the 7-year bound, Then only the supervised job purges, recorded — no operational delete exists.
- Given manual or duplicate invocation, Then no path / no-op respectively.
- Given archive reads later, Then tenant isolation holds identically.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None (closed-tenant + SC-7 dispositions tracked as OPEN at their owners; cited, not decided).

---
id: US-AUD-008
epic: EP-AUD-03
module: audit
screens: [S61]
wave: 5
status: draft
blocked_by: []
depends_on: [US-AUD-004, US-AUD-007]
journeys: [J5]
rules: [BR-AUD-013, BR-AUD-007, BR-AUD-002]
golden_tests: []
finance_calc: none
---
### US-AUD-008 — Archive search: explicit opt-in reads over cold storage (hot default untouched)

**1 · Details** — As a System Admin answering a 2019-vintage dispute or an auditor's sample, I want an explicit **"Search archive"** opt-in on S61 — default OFF, hot-window (2-yr) queries untouched — that routes the SAME filter bar (US-AUD-004) at the cold store, returning archived rows **read-only under my tenant scope exactly like hot reads**, so that 7 years of trail stay reachable without a single hot-path query ever paying for them (BR-AUD-013 = NFR-28 "matches reads pattern" applying BR-MET-055's hot-window + explicit-archive-search posture; US-MET-020 TC-3 is the sibling). Archive queries are server-paginated like everything else (NFR-3); results are visually labeled "Archive"; export follows the same BR-SHL-016 guards (US-AUD-006). Entity Audit tabs stay hot-window (their "full log" link → S61 is where archive depth lives). Reader mechanics against cold storage = Eng-Lead 🔒. Entry: S61 toggle ON + filters. Exit: labeled archive results / export.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AUD-013 | Hot-window default (2 yr) + EXPLICIT archive search only; server pagination; no unbounded endpoint. | CONFIRMED — NFR-28 ("matches reads pattern") applying BR-MET-055 (PO RD-13) + NFR-3 |
| BR-AUD-007 *(shared)* | Archive reads execute under `app.tenant_id` identically to hot reads — no cross-tenant view, support included. | CONFIRMED — B2 §3 + OQ-029 closure + US-MET-020 TC-7 pattern |
| BR-AUD-002 *(shared)* | Archived rows are as immutable as hot rows — read-only path, no restore-and-edit. | CONFIRMED — B2 §audit + A1 S61 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Toggle OFF (default): filter entity A-10432, range 2026–2033 | Only hot-window rows return; UI notes older rows exist behind "Search archive" — the default query never touches cold storage |
| TC-2 | Toggle ON, same filter | Archived 2026 rows return, labeled "Archive", read-only, newest-first, paginated; drawer works identically (payload-complete) |
| TC-3 | Archive export, 4,200 rows | Same BR-SHL-016/IS-11 pipeline as US-AUD-006, filename period reflecting the archive range; `audit.exported` row written (hot) |
| TC-4 *(negative)* | API call attempts an unbounded archive scan (no date range, no pagination) | Rejected — no unbounded endpoint exists (NFR-3/BR-AUD-013); the API demands pagination |
| TC-5 *(negative)* | Priya Menon (Billing Clerk) attempts archive search | Denied server-side — same S61 role gate (A1: System Admin + Executive); archive grants nothing extra |
| TC-6 *(immutability)* | Probe for restore/rehydrate-into-hot or edit endpoints on archive rows | None exist — the archive is a read path, not a staging area (BR-AUD-002) |
| TC-7 *(isolation — zero-tolerance)* | J. Okafor archive-searches the shared `2026_08` archive partition | Only Lone Star Ridge rows return — archive reads run under `app.tenant_id` exactly like hot (isolation suite asserts zero foreign rows) |

**4 · Test Data** — Archived: `audit_log_2026_08` in cold store (2,318,407 rows, both tenants). Hot: 2031–2033 rows. Query fixture: A-10432 trail spanning 2026 (archived `invoice.issued` BL-2608-018410) → 2033 (hot). Export fixture: 4,200 archived rows, `brazosbend_audit-log_2026-08_event-time_20330902T0915.csv`. Actors: Alex Reed; Priya Menon (negative); J. Okafor (isolation).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| "Search archive" opt-in | S61 | BR-AUD-013 (BR-MET-055 pattern) | query-scope flag → archive reader (no schema) | boolean | user-input | default OFF |
| Archive reader | — | NFR-28 + US-MET-020 pattern | cold-store read path, RLS-identical — Eng-Lead 🔒 | rows | system-derived | read-only; paginated |
| "Archive" result label | S61 | derived (honest sourcing, A18 spirit) | render flag on archive rows | flag | computed-display | always shown |
| Archive export | file | BR-AUD-014 (US-AUD-006 path) | same streamed pipeline + guards | file | computed-display | 50k cap; audited |
| Role gate | S61 | A1 S61 | same server-side check as US-AUD-004 | — | reference-data | no extra grants |

**6 · Acceptance**
- Given the default, Then no query touches cold storage; given the explicit opt-in, Then archived rows return labeled, read-only, tenant-scoped.
- Given export from archive, Then the same guarded, audited pipeline produces the file.
- Given unbounded, unauthorized, or mutating attempts, Then each is rejected.
- Given the shared archive partition, Then each tenant sees only its own rows.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.

---
id: US-AUD-009
epic: EP-AUD-03
module: audit
screens: [S61, S44]
wave: 5
status: draft
blocked_by: []
depends_on: [US-AUD-004, US-AUD-006]
journeys: [J5]
rules: [BR-AUD-017, BR-AUD-014, BR-AUD-007]
golden_tests: []
finance_calc: none
---
### US-AUD-009 — "User activity audit" (A14 Compliance card): the IS-11 feed over the S61 dataset — owned here, reports dedups

**1 · Details** — As an Executive assembling compliance evidence (month-end close package — J5, PUC inquiry, SOC 2 CC7 walkthrough), I want the **A14 Compliance card "User activity audit"** served as a real feed instead of the column-unknown generic viewer: the S44 card routes to **this module's dataset** — S61's ratified columns (When · Actor · Action · Entity · Summary · Source — A1 S61 addendum) with S61's filter vocabulary as report parameters — delivered through the **IS-11 pipeline** (CSV always; **PDF** — compliance class per IS-11 "where a formatted layout matters": letterhead, period, filters echoed, generated-at + by whom, page X/Y; date-basis label = `event-time`, no money basis applies), schedulable via the reports scheduler like any report (US-REP-013/014 consume this feed's definition). **Ownership per pack assignment 2026-08-09: this story OWNS the card; the reports pack's R-2 flag is DEDUPED for this report** (US-REP-001's catalog routes the card here; the other four R-2 reports stay with reports). Bespoke columns **beyond** the S61 set remain unratified — still the R-2 candidate; nothing beyond A1 S61 is invented. The feed reads hot by default; archive ranges go through US-AUD-008's path. Entry: S44 card / scheduler. Exit: IS-11 files; run rows per US-REP-004.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-AUD-017 | "User activity audit" = an IS-11 CSV/PDF feed over the S61 dataset (S61's ratified columns + filters); owned by audit; reports dedups R-2 for this card; columns beyond the S61 set stay unratified (R-2 candidate). | CONFIRMED (feed + ownership) — A14 §Report library (Compliance) + A1 S61 addendum + pack assignment 2026-08-09; column extensions OPEN — reports R-2 |
| BR-AUD-014 *(shared)* | Feed files ride the IS-11/BR-SHL-016 pipeline; every generation writes its audit row. | CONFIRMED — IS-11 (PO 2026-08-08) + BR-SHL-016 (PO R1 A2) |
| BR-AUD-007 *(shared)* | The feed is tenant-scoped-only like every audit read. | CONFIRMED — OQ-029 closure + NFR-10 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Evan Ruiz opens S44 → Compliance → "User activity audit" | Routes to this feed (NOT the generic viewer — R-2 deduped for this card); parameters = S61's filter vocabulary; columns = the six S61 columns exactly |
| TC-2 | Run: July 2026, all actors, CSV + PDF | CSV per IS-11 contract (`brazosbend_user-activity-audit_2026-07_event-time_20260809T1710.csv`); PDF with letterhead, period, filters echoed, `event-time` basis label, generated-at CT + "Evan Ruiz", page X/Y |
| TC-3 | Scheduled monthly via S45 (US-REP-013 consumed) | Identical files land in the 3-day retention window (IS-11); run row per US-REP-004; generation writes `report.exported`-family audit row |
| TC-4 | J5 close package: feed filtered to July + action types `money`+`approval` | The month's money/approval trail (incl. `period.closed`) in one evidence file — the close-audit companion |
| TC-5 *(negative)* | Request for bespoke columns (e.g. "login duration") | Not available — beyond the ratified S61 set; surfaced as unsupported with the R-2 reference; nothing invented |
| TC-6 *(negative)* | Run matching 68,000 rows | Rejected per the 50k guard (BR-SHL-016) with "Narrow your filters" |
| TC-7 *(immutability)* | Attempt to edit a generated file's stored run record or re-write history via the feed | No path — run rows append-only (US-REP-004 contract); the feed reads, never writes audit_log except its own generation row |
| TC-8 *(isolation)* | Lone Star Ridge schedules the same report | Its files contain only LSR rows; definitions, runs and files never cross tenants (RLS + IS-11 filename tenant segment) |

**4 · Test Data** — July 2026: 9,840 Brazos Bend rows (1,124 issues, 214 payments recorded, 3 approvals, 1 close). Files per TC-2. Schedule: monthly, 1st 06:00 CT, recipients = Evan Ruiz (delivery W6 per BR-REP-017 — download window v1). Oversize fixture: 18-month unfiltered run. Isolation: LSR monthly schedule, 780 rows.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| S44 card routing | S44 | A14 §Compliance + BR-AUD-017 | route to this feed (US-REP-001 catalog consumes) | — | computed-display | generic viewer no longer used for THIS card |
| Report parameters | S46-style bar | A1 S61 filter vocabulary | query over `audit_log` (US-AUD-004 semantics) | mixed | user-input | live vocabularies (actors from users) |
| Columns | files | A1 S61 (the six columns) | S61 dataset — nothing beyond | text | computed-display | R-2 for extensions |
| CSV / PDF | files | IS-11 | streamed pipeline (BR-SHL-016) | file | computed-display | `event-time` basis label; 50k cap |
| Schedule + run rows | S45 | US-REP-013/014/004 contracts (consumed) | reports scheduler + run records (R-1 anchor pending at reports) | rows | system-derived | 3-day retention |
| Generation audit | S61 | BR-SHL-016 | `audit_log` generation row | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given the S44 Compliance card, Then it serves the S61 dataset through IS-11 (CSV + compliance PDF) — no generic viewer, no invented columns.
- Given a schedule, Then identical files land in the retention window with run rows, and generation is audited.
- Given the J5 filter, Then the month's money/approval trail exports as one evidence file.
- Given tenants, Then definitions, runs and files never cross.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None (bespoke-column ratification stays with reports R-2; noted in the pack report).
