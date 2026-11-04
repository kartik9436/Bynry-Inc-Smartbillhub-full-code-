# EP-INT-09 — Files out and files in: the guards that keep a bank file from paying a bill twice

**Module:** integrations · **Wave:** phase 4 · **Screens:** S142 · S35 / S38 (bank & lockbox pickers) · S42 / S43 (export target) · **Status:** draft (`CR-069`, 2026-09-03)

## Scope

**In:** phase 4 — *"highest business value and highest risk, deliberately after the pattern has been proved twice."* The per-item savepoint (`BR-INT-023`), the file-channel profiles of `EP-INT-03` becoming connections on the substrate with their two idempotency keys — period + target for a file out, **content hash before parse** for a file in (`BR-INT-020`) — idempotency with a **mode** so a vendor's instruction to re-read three days is not mistaken for a duplicate (`BR-INT-029`), the must-not-skip operation (`BR-INT-050`), safety-relevant parameters stated explicitly and a fetch that changes the partner's world recorded as a write (`BR-INT-050`), and the meter register sync that supplies a connection size the bill run is blocked for want of.

**Out:** `US-INT-008`/`009`/`010`'s profile screens and lifecycle — they stand; this epic moves what they describe onto the connection model. The Nacha and camt.053 codecs are `US-INT-038` (`EP-INT-10`). Nothing here reverses `OQ-144` (bank matching is exact-amount and one-to-one) — a settlement file becomes a third input to reconciliation, not a change to the matching rule.

**Exit test of the phase:** the same bank file uploaded twice records the second as a **refused duplicate naming the first** — ⚠ **proved against real PostgreSQL, because the SQLite suite cannot see this class of bug** (hard-won law 14).

⚠ **`T-8` (GIS) AND `T-7` (NEPTUNE 360) ALSO LAND ACROSS THIS PHASE AND THE NEXT, AND `T-8` IS BLOCKED ON `OQ-INT-1470`–`1472`.** Do not start those tasks before the rulings. They are `EP-INT-12`.

## Capability matrix (list screens only — B9 conformance)

No new list screen. Import receipts and export files are artifacts on S142's run rows; the pickers on S35/S38/S43 are `EP-INT-03`'s.

## Stories

---
id: US-INT-032
epic: EP-INT-09
module: integrations
screens: [S142, S38]
wave: 4
status: ready
blocked_by: []
depends_on: [US-INT-020, US-INT-033, US-PAY-003]
journeys: [J52]
rules: [BR-INT-023, BR-INT-018]
golden_tests: []
finance_calc: none
---
### US-INT-032 — Per-item savepoints on import: row 412 stops row 412 and nothing else — proved on real PostgreSQL

**1 · Details** — As **a clerk importing a bank file**, I want **row 412's constraint violation to stop row 412 and nothing else** — so that **one bad row does not lose the other 899**.

*"On PostgreSQL a failed statement poisons the entire transaction — and the test suite runs on SQLite, which does not. The naive handler passes every test and loses production data."* The FetchRunner and the upload path commit **row by row inside a SAVEPOINT** (a nested `transaction.atomic()`); a refused row is recorded with the driver's SQLSTATE read **two or three hops down `__cause__`**, not one, and skipped; the rest of the file continues; the run reports **899 / 1 / 0** and names the row and the reason in words — *row 412: account 4471-0021 is not on file*. **The comment in the code says a savepoint is the only option, or the next lane simplifies it away.** `T25`: a CI job runs this suite against real PostgreSQL with `JOBS_EAGER=false --reuse-db`. The clerk fixes and re-uploads **just that one** row's file; the content-hash guard sees a different file.

Entry: an upload on S38, or a scheduled fetch. Exit: a run row with the counts and the named row; an import receipt artifact.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-023` | Row-by-row inside a savepoint; refused row recorded and skipped; proved on PostgreSQL | CONFIRMED — hard-won law 14 |
| `BR-INT-018` | The counts must reconcile: 899 + 1 + 0 = 900 | PROPOSED |
| `BR-PAY-036` | A payment is ALWAYS accepted — a refused row is a row, never a refused file | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 · **PG** | 900-row lockbox file; row 412 violates a constraint | Rows 1–411 and 413–900 committed; row 412 recorded *refused*; run reads **899 / 1 / 0**; the receipt names row 412 and the reason (doc TC-INT-18) |
| TC-2 · **red-first · PG** | The same file against `try/except IntegrityError: continue` with no savepoint | `InFailedSqlTransaction` on row 413; **zero** rows committed — recorded as the red run this guard exists for |
| TC-3 · **SQLite honesty** | TC-1 on the default suite | Passes with **and without** the savepoint — asserted in the test's docstring as the reason the PG job exists; the CI job is the proof, not this |
| TC-4 | The SQLSTATE of row 412 | Read by walking `__cause__` until the driver exception; the sentence is *is not on file*, not the generic *could not be saved* |
| TC-5 | The clerk re-uploads a one-row file for 412 | Different content hash → accepted; the original receipt is unchanged; the account now has its payment |
| TC-6 · **tenant isolation** | Row 412 names an account that exists on **another tenant** | Refused as *not on file* — RLS makes the other tenant's account invisible, and the message reveals nothing |

**4 · Test Data** — Poison-row file: 900 rows, BAI2, Brazos Bend, row 412 → account `4471-0021` (absent); a one-row fix file. `JOBS_EAGER=false --reuse-db`; PostgreSQL 16 CI job `06-backend/tests/pg/test_int_savepoints.py`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| per-row outcome | S142 receipt | `BR-INT-023` | import receipt artifact (row · outcome · sentence) | list | system-derived | every refused row named |
| counts `899 / 1 / 0` | S142 | P4 | `integration_run` | int | system-derived | reconcile to the row count |
| savepoint | — | law 14 | `transaction.atomic()` per row | — | code | comment says why |

**6 · Acceptance**
- Given one bad row in nine hundred, then eight hundred and ninety-nine are in, the one is named, and the clerk fixes only that one — proved on PostgreSQL.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-INT-033
epic: EP-INT-09
module: integrations
screens: [S142, S35, S38, S42, S43]
wave: 4
status: ready
blocked_by: []
depends_on: [US-INT-008, US-INT-009, US-INT-010, US-INT-014, US-INT-019, US-INT-020]
journeys: [J51, J14, J19]
rules: [BR-INT-009, BR-INT-010, BR-INT-020, BR-INT-026, BR-LED-004, BR-PAY-028]
golden_tests: []
finance_calc: none
---
### US-INT-033 — Files out and files in on the substrate: the export target and the bank profile become connections, with period + target and a hash before parse

**1 · Details** — As **a finance clerk**, I want **the saved export target and the bank & lockbox profile to be connections like any other — with a run row, a test, a state and a history** — so that **the same bank file uploaded twice is refused naming the first, and a period regenerated produces the same file or refuses**.

`US-INT-008`/`009`/`010` describe the profiles; this story puts them on the substrate (`T23`, `T24`). **Accounting export target** — *"the only genuinely new object v1 needs"*: format · destination, **no credential at all for a download target**, `test()` writes a zero-row export; the file is never offered while accounts are unmapped (readiness *N unmapped*, `BR-LED-014`); key = **period + target** — regenerating a period produces the same file or the run refuses, never a different file silently. **Bank & lockbox profile**: bank label · file format · source (upload, or SFTP with a credential) · the CSV column mapping as a **second step** (`BR-INT-043`'s `mapping_editor`); `test()` lists one directory; key = **content hash, computed BEFORE parse** — *"by the time you have parsed it you have already spent the work."* The batch records its producing connection and editing the connection afterwards does not restate history (`US-INT-010`). ⚠ **The accounting target's `target` column today mixes a destination with a format** — two of its four values are places and two are file shapes (`CR-069` §0.3 defect 2); on the substrate that becomes `destination` (download · drop folder) × `codec` (`US-INT-039`).

Entry: S43 (export) · S38 (import) pickers naming a connection. Exit: a run row per file; `artifact_link` on it; the batch carrying its producing connection.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-009` · `BR-INT-010` | Bank side v1 = FILE import via profiles; accounting v1 = FILE targets | CONFIRMED — B7, BR-LED-020 |
| `BR-INT-020` | Period + target (out); content hash before parse (in) | PROPOSED |
| `BR-LED-004` · `BR-PAY-028` | Idempotency blocks on the owning flows survive every profile change | CONFIRMED |
| `BR-INT-026` | A sandbox target is never handed a real period | PROPOSED |
| `OQ-144` | Bank matching stays exact-amount, one-to-one — untouched | CLOSED, relied on |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 · **PG** | Tuesday's lockbox file uploaded; the byte-identical file uploaded Wednesday | Second run: **refused duplicate — the same file as Tuesday 06:10**, naming the first by date; `input_hash` equal on both rows; **the hash was computed before any parsing** (asserted by ordering); no payment applied twice (doc TC-INT-14) |
| TC-2 | July regenerated to the QuickBooks target | Byte-identical file, or the run refuses *July was already exported on 5 Aug* — never a different file (doc TC-INT-13) |
| TC-3 · **negative** | Export with 3 accounts unmapped | No file offered; S43 reads *3 accounts still need an export code*; the run is not created |
| TC-4 | The batch on S35 | Records its producing connection; renaming the connection afterwards leaves the batch's history reading the old label |
| TC-5 | `test()` on a download target | Writes a zero-row export and reads *Wrote an empty QuickBooks file* — no credential exists to test |
| TC-6 · **tenant isolation** | Lone Star Ridge uploads a file whose hash equals a Brazos Bend file | Accepted — the hash is scoped to the tenant; nothing about Brazos Bend's run is revealed |

**4 · Test Data** — J14's 40-row lockbox CSV (Brazos Bend, 8 Aug) uploaded twice; J19's July export to `accounting_file` target `QuickBooks · IIF · monthly · download`; 3 unmapped accounts fixture; Lone Star Ridge hash-collision fixture.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| export target: `destination` · `codec` | S43 · S141 | Figure 10 · defect 2 | `integration_connection.config` | enum | user-input | destination `download \| drop`; codec registered |
| readiness *N unmapped* | S43 | `BR-LED-014` | computed over `ledger_accounts` export codes / `integration_target_reference` | int | computed-display | file offered only at 0 |
| `input_hash` | S142 | `BR-INT-020` (C) | `integration_run.input_hash` | sha-256 | system-derived | before parse; UNIQUE per (tenant, connection) with a refused-duplicate row pointing at the first |
| period + target key | S142 | `BR-INT-020` (B) | idempotency record (existing kernel shape) | text | system-derived | same file or refuse |
| producing connection on the batch | S35 · S42 | `US-INT-010` | `payment_import_batches` profile ref → connection id | uuid | system-derived | history never restated |

**6 · Acceptance**
- Given the same bank file twice, then the second is refused naming the first, and money moves once — on PostgreSQL.
- Given a period regenerated, then the file is the same or the run says why not.

**7 · Finance Calculation** — N/A — the money is the owning flow's (`US-PAY-003`, `US-LED-016`); this story moves files and keeps keys.

**8 · Open Questions** — None. (Whether a **scheduled** SFTP fetch — credentials, a poller, and a failure nobody watches — is in phase 4 or later is the design's own *scope call*; upload is the working path either way, and the connection records an SFTP source from `US-INT-008` as today.)

---
id: US-INT-034
epic: EP-INT-09
module: integrations
screens: [S142]
wave: 4
status: ready
blocked_by: []
depends_on: [US-INT-020, US-INT-028, US-INT-029]
journeys: [J55]
rules: [BR-INT-029, BR-INT-050]
golden_tests: []
finance_calc: none
---
### US-INT-034 — Readings that arrive late: idempotency with a mode, a reading already billed that does not move, and the night that must not be skipped (C13, C21) 🔒

**1 · Details** — As **a billing clerk**, I want **last night's collection to pick up readings that only reached the meter supplier this morning — without treating them as duplicates and without ever touching a reading already billed** — so that **a backfilled reading is neither lost nor allowed to move a bill**.

Failure 11, *"the worst of the four"*: the vendor instructs us to re-fetch the last three days every night because readings arrive late; a refuse-only duplicate guard **refuses the instruction, reports success, and silently never takes a backfilled reading.** So idempotency has a **mode** (`BR-INT-029`): `reconcile` by natural key (`meter · register · read_at`) for this operation. Monday collects three days; Tuesday collects the same three days after the supplier filled four gaps and revised two values: the run reads **1,240 read · 6 revised**, 1,238 rows are untouched, and **a reading already billed does not move** — the difference is handed to metering's service function as a **correction**, never an update (hard rule 4). **Proved on PostgreSQL.** `C21`: one field the collection carries — a register change-out flag — is published for a single day, after which a refetch honestly returns nothing; that operation is declared **`must_not_skip`**, and a missed night **raises** on S142 and the S8 panel rather than quietly catching up. *"Skipping is about two runs at once; re-reading is about the same days twice, deliberately."*

🔒 **Sensitive path** — this writes toward billed readings. `HUMAN-REVIEW-PENDING`; the ledger row shows the PO the 1,240 / 6 / 1,238 figure and the sentence *a reading already billed does not move*.

Entry: the nightly collection. Exit: a run row with five counts; corrections raised through `apps.metering` services; a raised row for a missed must-not-skip night.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-029` | Idempotency has a mode; reconcile reports `changed`; a billed reading never moves — a correction | PROPOSED — design §2.18.3, `C13`; immutability half CONFIRMED (hard rule 4) |
| `BR-INT-050` | An ephemeral fact makes its operation must-not-skip; a missed night raises | PROPOSED — `C21` |
| `BR-MET-*` (metering's own) | The load is performed by the owning module's service function, never by an adapter | CONFIRMED — B1 boundary |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 · **PG** | Monday: 3 days, 1,240 readings. Tuesday: same 3 days; 4 previously missing now present, 2 values revised | Run reads **1,240 read · 6 revised**; 1,238 rows untouched (`updated_at` unchanged); the 4 new are inserted, the 2 revised superseded through metering's service (doc TC-INT-31) |
| TC-2 · **red-first** | TC-1 against a refuse-only guard | *1,240 duplicates refused*, six readings lost, run green — recorded as the red run |
| TC-3 | One of the two revised readings has already been billed | **The reading is not touched**; a correction is raised naming the bill; the run's summary says so (doc TC-INT-32) |
| TC-4 | The register change-out operation misses a night (workers down) | A **raised** row *missed 2 Sep — the change-out flag for that day cannot be refetched*; the S8 panel shows attention; no silent catch-up |
| TC-5 · **negative** | A manifest declares `idempotency.mode = reconcile` with no natural key | Refused at load |
| TC-6 · **tenant isolation** | Two tenants collect from the same vendor tenant-scoped | Reconcile keys carry the tenant; one tenant's backfill never supersedes another's rows |

**4 · Test Data** — *The backfill* fixture (the design's *"single most important new fixture"*): Monday 2026-08-31 collection of 1,240 readings for 2026-08-28..30; Tuesday's response with 4 added and 2 revised (`MTR-2210 register 1 · 2026-08-29 · 4,517 → 4,571 gal`, `MTR-0987 · 2026-08-30 · 12.3 → 12.8 kWh`); one of the two (`MTR-2210`) billed on bill `BL-2609-0044`. Change-out flag fixture published for one day only.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `idempotency.mode` · `natural_key` | — | `C13` | manifest per operation | enum/list | reference-data | `refuse \| reconcile`; reconcile needs a key |
| `changed` count | S142 | §2.18.3 | `integration_run.changed` | int | system-derived | shown only for reconcile operations |
| superseded reading | metering | hard rule 4 | `meter_readings` via metering service (new row, supersedes link) | row | integration → metering service | billed reading untouched |
| correction | metering / billing | hard rule 4 | metering correction path | row | integration → service | names the bill |
| `must_not_skip` | S142 · S8 panel | `C21` | manifest per operation; raised row in `integration_run` | bool/row | reference-data / system-derived | raised, never caught up |

**6 · Acceptance**
- Given the same three days collected twice with six changes at source, then six rows move, 1,238 do not, and none of the billed ones is touched — on PostgreSQL.
- Given a missed night on a must-not-skip operation, then it is raised, not caught up.

**7 · Finance Calculation** — N/A — no rating math; the correction's money is billing's.

**8 · Open Questions** — None. (`OQ-INT-1485`, which system is master of the meter-to-account link, blocks `US-INT-036`, not the readings feed.)

---
id: US-INT-035
epic: EP-INT-09
module: integrations
screens: [S142]
wave: 4
status: ready
blocked_by: []
depends_on: [US-INT-020, US-INT-028]
journeys: [J55]
rules: [BR-INT-050, BR-INT-020]
golden_tests: []
finance_calc: none
---
### US-INT-035 — Safety-relevant parameters stated explicitly, and a fetch that changes their world recorded as a write (C18, C19) 🔒

**1 · Details** — As **a billing clerk**, I want **a collection whose request omits `actual_consumption` not to run — and to say which parameter was unset** — so that **no vendor default is inherited on a money path**.

Two things the head-end specification taught. **`C18`**: one supplier has **four** request parameters whose default is unsafe, two of them on the money path — a collection that omits `actual_consumption` returns estimated figures that look like reads. Every operation therefore declares its `safety_parameters`, the runner refuses to start a request that leaves one unset, and the run says which. **`C19`**: a *fetch* that carries `CloseOnExport` **changes the partner's state** — it closes billing routes on their side. Such an operation is declared `mutates_partner_state = true`; the runner records it with an idempotency key and a receipt **before** the call, and a retry is refused as a duplicate rather than closing routes twice. *"Any request parameter whose default is unsafe, and any amount field whose units are not stated"* — the two things to look for in every specification, both of which have already bitten this design once.

🔒 **Sensitive path** — idempotency keys on a money-adjacent write. `HUMAN-REVIEW-PENDING`.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-050` | Safety parameters explicit — no vendor default on a money path; `mutates_partner_state` recorded with key and receipt; retry refused | PROPOSED — design §2.25.9, `C18`, `C19` |
| `BR-INT-020` | The key is generated before the call | PROPOSED |
| CLAUDE.md hard rule 3 | Consumption always with an explicit unit — a request that returns estimates as reads is the same failure | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | The readings operation's request template omits `actual_consumption` | The run **does not start**; S142 reads *not started — `actual_consumption` was not set*; no request left |
| TC-2 | All four safety parameters set | The run starts; the request carries all four explicitly, asserted on the fixture |
| TC-3 | An export request carrying `CloseOnExport = true` | A run row with an idempotency key and a receipt is written **before** the call; the retry of the same period is refused *already closed on 1 Sep* — one close, not two |
| TC-4 · **negative** | A manifest marks an operation `mutates_partner_state = true` and declares no idempotency source | Refused at load |
| TC-5 · **units** | A response amount field with no declared unit in the projection | Refused by name rather than written (the measurement frame of `BR-INT-049`) |
| TC-6 · **tenant isolation** | Two tenants export the same period | Two keys; neither refuses the other |

**4 · Test Data** — `meters_neptune360` `readings` operation with `safety_parameters = [actual_consumption, include_estimates=false, …]` (four); `billing_export` with `CloseOnExport`; a request template fixture missing one parameter.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `safety_parameters[]` | S142 refusal sentence | `C18` | manifest per operation | list | reference-data | every one set or the run does not start |
| `mutates_partner_state` | — | `C19` | manifest per operation | bool | reference-data | needs an idempotency source |
| receipt | S142 | `C19` | `integration_run.artifact_link` (the partner's acknowledgement) | url | system-derived | written before the call completes |

**6 · Acceptance**
- Given a request missing a safety parameter, then nothing leaves and the parameter is named.
- Given a fetch that closes routes on their side, then it happens once, with a key and a receipt.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-INT-036
epic: EP-INT-09
module: integrations
screens: [S142]
wave: 4
status: blocked
blocked_by: [OQ-INT-1485]
depends_on: [US-INT-028, US-INT-034, US-INT-037]
journeys: [J57]
rules: [BR-INT-031, BR-INT-032, BR-INT-049]
golden_tests: []
finance_calc: none
---
### US-INT-036 — The meter list, kept in step: the supplier's own record of each meter fills the details we are missing ⚠ blocked on who is master

**1 · Details** — As **a billing clerk**, I want **the meter supplier's own record of each meter — its size, type and route — to fill the details we are missing** — so that **bills stop being blocked for want of a connection size**.

*"The most concrete value in the document":* an account cannot be billed for want of a connection size; a register sync runs; the size arrives from the system that installed the meter, and the run goes from **blocked** to drafted. The head-end holds a meter-to-account link **and so do we**. ⚠ **Getting it wrong bills the wrong customer**, which makes *which system is master* a ruling rather than a mapping — **`OQ-INT-1485`, OPEN**. Until it is ruled this story is built **to the boundary**: the sync collects the supplier's meter records into a staging table on the run, shows the differences on S142 (*size 5/8" for `MTR-2210`, we hold none*), and **writes nothing to `assets`** — `apps/integrations/seams/metering.py` raises `NotImplementedError("OQ-INT-1485")` at the write. Route and type names arriving in the supplier's vocabulary are mapping rows (`BR-INT-032`); an unmapped one records as `other` (`BR-INT-031`).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `OQ-INT-1485` | Which system is master of the meter-to-account link | **OPEN** — blocks every write of this story |
| `BR-INT-032` | Route and type vocabularies are rows | PROPOSED |
| `BR-INT-031` | Unknown inbound value → `other`, shown in red | PROPOSED |
| `BR-INT-049` | A size arriving without its unit is refused by name | PROPOSED — 🔒 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Register sync runs; `MTR-2210` has no size on our side; the supplier reports `5/8"` | S142 lists the difference; **no `assets` row changes**; the write path raises `NotImplementedError("OQ-INT-1485")` — asserted |
| TC-2 · **after ruling (written now, skipped until `OQ-INT-1485` closes)** | Same, with the ruling applied | The size is written through `apps.assets`' service; the blocked bill run for that account drafts on its next attempt |
| TC-3 | The supplier names route `RT-NORTH-07` with no mapping row | Recorded as `other`; the row is red on S143 |
| TC-4 · **negative** | The supplier reports size `20` with no unit | Refused by name — *size arrived without a unit* — not written even to staging |
| TC-5 · **tenant isolation** | Two tenants' meters at the same supplier | Staging rows tenant-scoped; a serial present on both tenants is never cross-linked |

**4 · Test Data** — *A meter with no size*: Brazos Bend account `ACC-1048`, meter `MTR-2210`, no connection size, bill run blocked *needs a connection size*; supplier record `5/8" · positive displacement · route RT-NORTH-07`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| supplier meter record | S142 differences | design §2.18 | run artifact (staging), **not** `assets` until `OQ-INT-1485` | struct | integration | unit required on size |
| size · type · route | S142 | — | `assets` via service — **STUBBED** | text/enum | integration → service | `NotImplementedError("OQ-INT-1485")` |
| route / type mapping | S143 | `BR-INT-032` | `integration_target_reference` `entity_type = route \| meter_type` | row | user-input | UNIQUE external side |

**6 · Acceptance**
- Given the ruling is open, then the sync shows what would change and changes nothing.
- Given the ruling, then a missing size arrives from the supplier and a blocked bill drafts.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-INT-1485` | Which system is master of the meter-to-account link — the head-end or us? | Every write of this story | PO | OPEN |
| `OQ-INT-1484` | Is hourly interval data switched on (about half a billion rows a year at the top of the range; the NFR-27 gate re-runs storage first)? | Interval consumption only — not the readings feed and not this sync | PO + Eng-Lead | OPEN |
