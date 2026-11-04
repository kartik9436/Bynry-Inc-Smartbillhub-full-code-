# One-time bill redesign — build plan (2026-09-30)

Status: ⚠ **2026-09-30: BUILT AND WALKED, 2.412.2 — J70 15 of 15 at 1440 and 1280 on PostgreSQL. C1 (version 2.412.2), C2 (review-ledger rows: the Send file's four decisions, the deposit refund, the catch-up stretch, each with what the PO was shown) and C4 (`18-rollback-2.412.md`, back to 2.411.4) are DONE; C3 — the PO's own browser walk-through — is the only task left.** ✅ **C3 CLOSED 2026-09-30: the PO accepted the walk-through of the eight checks on 2.412.4 (ten screenshots), verbatim *"ok"*. THE ONE-TIME BILL PLAN IS COMPLETE, 74 OF 74.** Later fixes (2.412.5, the PO's three reports DEF-BIL-8287/8288/8289) are maintenance on a finished build. (Originally: **PLAN, NOT STARTED.**) Builds `11-one-time-bill-redesign.md`, which the PO
confirmed on 2026-09-30 (*"your drawing is correct now"*). Every ruling it rests on is
in `12-governance/02-decision-log.md` under 2026-09-30.

**Which process:** the one-time bill exists today, so this is MAINTENANCE
(`12-governance/22-product-maintenance-process.md`) — a live screen redrawn end to end
— borrowing Build's drawing step. The eleven review gaps are filed as defects; the
rulings are changes to signed rules and are amended rule by rule.

**How every screen is built (PO, 2026-09-30):** *"all screeen sin product should be
completed using images of drawing and not text/contnet, and use uI skills"* — B14 rule
42 (build from the drawing as an IMAGE) and the `react-tailwind-css-ui-generator`
skill, run before the first line of TSX and again at close-out. The drawing is the
mock-up at https://claude.ai/artifact/DYnXV9VSuKxoRtXFhmFJrB, captured as PNGs into
the tree by task D1 so a lane without chat can open it.

## 0 · Records (before any code)

| # | Task | Where |
|---|---|---|
| R1 | File one defect per review gap (1–19), `escape_reason` filled | `10-scripts/file_defect.py --id-module BIL` |
| R2 | Amend rules: `BR-BIL-300` (no asset = not in service), `BR-BIL-301` (no bill line), `BR-BIL-1048` (sewer follows basis; no agreements = bill all + warn), `BR-RAT-088`/`BR-RAT-1025` (missing base = $0 + warning), `BR-RAT-090` (base per asset; one line per meter), `BR-RAT-015` (sewer has no service point) — each stamped with its 2026-09-30 ruling | `04-docs/05-modules/07-billing/02-business-rules.md`, `06-rating/02-business-rules.md` |
| R3 | **Finance re-sign of B4.2 ❄️** for fee-bill tax (`OQ-812`) via HUMAN-GUIDE §6 — **no fee-tax code before it** — ✅ **RECORDED 2026-09-30**: PO *"Yes, re-sign."*; stamp under B4.2 + ❄️ ADDENDUM 2026-09-30 in `04-money-math-rules.md`, `G61` B4 pin re-derived, review-ledger row | `04-docs/decisions` B4 |
| R4 | Re-check CR-063 fire worked figure ($84.00) under base-per-asset; re-sign if it moves — ✅ **2026-09-30: does not move**, `$84.00` on the code (`test_cr063_c3_fire_priced.py` + `test_cr063_fire_service.py`, 29 passed); *"on two lines"* stamped LAYOUT-superseded in `BR-RAT-024`, `EP-CWP-07` TC-6, `CR-063` and CLAUDE.md; the one-line layout itself is `14-bulk-bill-run-changes.md` row 5, not built | fire rule, golden tests |
| R5 | Stories and epic: one story per kind + one for Send, each with §3 test cases written BEFORE code; journeys file | `06-epics/EP-BIL-03`, `08-qa/01-e2e/journeys/` |
| R6 | Human-review-ledger rows for every 🔒 file touched (rating selectors, pricing stages, issue, release, fee_bill, gather) | `12-governance/09-human-review-ledger.md` |

## D · The drawing into the tree

| # | Task | Where |
|---|---|---|
| D1 | Capture every mock-up state as PNG at 1440 and 1280: 6 kind cards · Account (each kind) · account dropdown open · Services step (each kind, sections open and closed) · Review (each kind) · Send (unticked / ticked) · Sent · Problems · Already billed · Compare kinds | `05-prototype/one-time-bill-2026-09-30/*.png` + an index |
| D2 | Write the skill's §2.1 inventory from the images (every element, label, column, state, and what is ABSENT) | same folder, `inventory.md` |

## B · Backend — billing rules

| # | Task | Where |
|---|---|---|
| B1 | `%`-of-service needs no service point: skip it in "not connected"; it is taken iff its basis service is billed | `billing/gather.py` `_unconnected_plan_services`, `_plan_services_not_taken` |
| B2 | No asset = not in service, even if taken: metered point with no meter no longer refuses (`no_meter`); counted with no asset bills nothing, no base | `metering/selectors.py` `billing_reads_for_unit`, `billing/runs.py`, `gather.py` |
| B3 | Not in service prints **no bill line**; still on the review list and on the Services table | `gather._unconnected_plan_service_lines` + callers |
| B4 | Missing base charge (cases a–d) = $0.00 + a named warning; conflicts (e–g) still refuse | `rating/selectors.base_charge_from_charge_code` 🔒, `gather._base_charge_for` |
| B5 | Two meters on one metered service = one reading row, one tariff config and one line per meter, each with its own tiers and base | `metering.billing_reads_for_unit` (per asset), `runs.readings_for_account` (stop dropping), `gather` (per-meter configs), `measure_consumption` |
| B6 | Counted services: base charged per asset | `gather._per_size_configs`, `rating/pricing/stages/price_usage` 🔒 |
| B7 | Fee bill taxes a taxable charge code — R3 re-signed by PO 2026-09-30, unblocked — ✅ **BUILT 2026-09-30**: engine `price_fee_bill` (one tax pass, percent rules only), `fee_bill.price_charge_fee`; quote bills deliberately not yet (New Connect halted) — decision log 2026-09-30 | `billing/fee_bill.py`, rating tax pass |
| B8 | No service agreements on file: bill every connected service + a warning | `gather._services_taken_by_account` |
| B9 | A warnings channel: preview, draft and run results carry named warnings (base $0, no agreements, estimated) | `one_time.py`, `runs.py` |
| B10 | Penalty approval RECORDED, not enforced (PO 2026-09-30): clerk picks a staff user or types a name; stored in `bill_payload.penalty.approved_by`; Send never refused for it | `penalty.py`, send path |
| B11 | Hardening: issue gate refuses an already-released row; a non-rule failure breaks one bill, not the run | `issue.py` 🔒, `release.py` 🔒 |
| B12 | First bill's connection charge checked for a GL account at draft | `first_bill.connection_charge_line_for` |
| B13 | Retire `ONE_TIME_UNAVAILABLE` rows that become false; correct the stale comments (reason-code table, "no route creates a read", run-status note, "cycle" wording) | `one_time.py`, `runs.py`, `issue.py`, `OneTimeWhatStep.tsx` |

## A · API

| # | Task | Where |
|---|---|---|
| A1 | Account search for the dropdown: name / account no. / address, paginated, returns status, plan, balance, cycle days-to-pay | reuse `GET /accounts?q=` — add fields if missing |
| A2 | Preview accepts `due_days`, `charge_code` (penalty optional, fee required), required `bill_date`; `reason_code` checked against the tenant's `reason_codes` | `billing/api.py` `_one_time_request`, `one_time.py` |
| A3 | **All** step-1 problems returned at once, each with its field and its own catalogue key (no generic "billing run" sentence, no "cycle") | `api.py`, `one_time.checked_*` |
| A4 | Preview response adds: services table (status per service), rates table (per meter/service), readings rows per meter (previous reading + date), periods, move-in charges, settlement, grouped bill lines (group, service, meter, charge, qty, rate, amount), warnings, defaults (days to pay from cycle) | `one_time.preview` |
| A5 | Readings are saved through Meter Reads' `/read-batches` (stage → validate → post), one row per meter; first-bill move-in reading; catch-up last period | frontend calls existing routes; confirm they accept a single row with a date |
| A6 | **Send** in one call: `POST /billing/one-time/{run_id}/send` — authorises and issues this one run, idempotent, refuses without the acknowledgement | new route over `release.authorise_release` + `release.release_run` |
| A7 | Delivery choice (email / paper / both) carried to the send | `delivery_seam` |
| A8 | Duplicate refusal adds the existing bill number and a link | `one_time_create` |
| A9 | OpenAPI schema regenerated once | `openapi/schema.json` |

## DB · Database

| # | Task | Where |
|---|---|---|
| DB1 | `invoice_lines.asset_id` (nullable) so a line names its meter — a new cross-module FK, reviewed under B2 §2 | `billing/migrations/00xx` |
| DB2 | Penalty evidence: text in the bill snapshot; photos in the existing documents store if it fits, else a small billing table | decision first, then migration if needed |
| DB3 | Fee bill "note on bill" in the payload (no column) | `bill_payload` |
| DB4 | No other schema change: `bill_runs.due_days`/`bill_date`, `reason_codes`, `invoice_lines.period_start/end` already exist | — |

## F · Frontend (skill: `react-tailwind-css-ui-generator`, built from the D1 images)

| # | Task | Where |
|---|---|---|
| F1 | Pre-flight per skill §7: migration ledger, existing kit components, catalogue keys in all eleven languages, rules, what the screen does today | — |
| F2 | Page + route replacing `OneTimeBillTab` and `OneTimeWizardShell`; four-step rail **Account · Services · Review · Send** on `WizardFrame` | `features/billing/`, `App.tsx` |
| F3 | Kind cards (six) | component |
| F4 | **AccountCombobox** — searchable dropdown, highlight, ↑ ↓ Enter Esc, status pill; a kit component | `components/` |
| F5 | Step 1 fields by kind (§2 of the design): periods list with add/remove, reason dropdown, charge dropdown with read-only amount, bill date, days to pay, derived due date | component |
| F6 | Services table (collapsible) with the five statuses and warnings | component |
| F7 | Rates table (collapsible), per meter/service, per period for catch-up and penalty | component |
| F8 | Move-in charges (collapsible): deposit + fees | component |
| F9 | Readings table per meter (previous, read on, new date, new reading, usage, check) for Interim/First/Final; per-period blocks for Catch-up (last period input) and Penalty (read-only, Assessed) | component |
| F10 | Periods table, Settlement box with path choice, Evidence, Charge panel | components |
| F11 | Review: grouped bill table (group subtotal rows; Service · Meter · Charge · Quantity · Rate · Amount), warnings, delivery, Save draft | component |
| F12 | Send card: total, due, warnings, *Final once sent*, ⚠ **AMENDED 2026-09-30 (PO, option B): the FIVE release confirmations — compliance, email, text, autopay, final — each ticked by the clerk, all five unlocking Send** (was one acknowledgement tick); Sent state | component |
| F13 | Problems state (all problems, each on its field) and Already-billed banner | components |
| F14 | Summary side panel | component |
| F15 | Every string in all eleven catalogues, within B14 rule 33's caps; retire keys the old tab used | `i18n/locales/*` via `10-scripts/i18n_fanin.py` |
| F16 | Tailwind only (B14 rule 21); new files on `route-b-migrated.txt` | `styles/` |
| F17 | API client types and calls for A1–A8 | `api/billingOpsEndpoints.ts` |
| F18 | Delete the old tab and shell once the new page is live; grep for every link that pointed at them | — |

## T · Tests (written from each story's §3 before the code)

| # | Task | Where |
|---|---|---|
| T1 | Unit, one per ruling, red first: sewer with no point bills 40%; gas with no meter = not in service, no line, bill completes; missing base = $0 + warning; conflicts still refuse; 2 meters = 2 lines ($58.40); 2 carts = $36.00; no agreements = billed + warning; fee tax $81.19 (after R3) | `06-backend/tests/` |
| T2 | **PostgreSQL** proofs for every path that catches a DB error, and the money paths above (law 14) | `10-scripts/*_measure.py` |
| T3 | Golden tests for the new worked figures; `G64` record updated | `tests/golden/` |
| T4 | API tests: all problems at once, field keys, send idempotency, duplicate with bill number, reason code checked, tenant isolation on every new route | `tests/` |
| T5 | Frontend component tests per F-component, routed under the real path (law 2) | `*.test.tsx` |
| T6 | Hold-expiry test: the door to the new page opens the new page | `*.test.ts` |
| T7 | i18n and gate suite green (G31, G32, G33, G15, G7, G13) | `10-scripts/gates` |

## E · End-to-end (Playwright, seeded tenant, 1440 and 1280)

| # | Journey |
|---|---|
| E1 | Interim: 2 water meters + electric, readings typed, sewer follows water, gas/fire no line, electric base $0 warning → Review → Send → Sent; bill shows two water lines |
| E2 | First bill: move-in reading typed for the meter with none on file; deposit + CONN; send |
| E3 | Final: final reading on move-out date; settlement path chosen; send |
| E4 | Catch-up: three periods, split by a price change, one estimated; last period reading typed; send |
| E5 | Penalty: assessed reads, evidence, tamper charge; send refused until approved; approve; send |
| E6 | Fee: reconnection fee, taxed (after R3); send |
| E7 | Problems: empty days to pay + bad period + no reason → all shown at once, each on its field |
| E8 | Already billed: same account, kind and period → banner with bill number and link |
| E9 | Account with no agreements → bills and warns |
| E10 | A reading lower than the last one → refused on its row; bill cannot continue |
| E11 | Screenshot diff of every E-state against the D1 images (skill §4 checklist) |

## C · Close

| # | Task |
|---|---|
| C1 | Version bump (`allocate.py version --bump change`), recorded on every defect and change |
| C2 | Review-ledger rows state what was shown to the PO, with the figures |
| C3 | PO walk-through in a browser against the images; tell the PO which build to look in |
| C4 | Rollback stated before shipping |

## Order

R1–R6 → D1–D2 → DB1 → B1–B13 (B7 after R3) → A1–A9 → F1–F18 → T and E alongside
each piece → C1–C4. Push after every step.
