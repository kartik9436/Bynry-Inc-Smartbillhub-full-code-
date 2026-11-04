# J55 — Backfill Tuesday — PostgreSQL (*1,240 read · 6 revised*, 1,238 rows untouched, and a reading already billed on `BL-2609-0044` that does not move)

---
id: J55
tier: 2
rules: [BR-INT-029, BR-INT-050, BR-INT-047, BR-INT-025, BR-INT-024, BR-INT-034, BR-INT-049, BR-INT-018, BR-INT-020]
stories: [US-INT-028, US-INT-029, US-INT-034, US-INT-035]
# Wiring: every story above cites `J55` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J55.spec.ts`. Wave L task L5 writes it
# with J57 (`cr069-l-backfill-tuesday.mjs`), ON POSTGRESQL. Phase 4.
# 🔒 SENSITIVE PATH — `runners/reconcile.py` writes TOWARD billed readings, and
# `US-INT-035`'s idempotency keys sit on a money-adjacent write. Both files are
# HUMAN-REVIEW-PENDING with review-ledger rows in plain English: "1,240 read ·
# 6 revised · 1,238 untouched, and a reading already billed does not move — the
# difference is a correction" (L4) and "an export carrying CloseOnExport closes
# their routes once and a retry is refused; one supplier has four request
# parameters that fail open, two of them on the money path" (K4).
# ⚠ FAILURE 11, "THE WORST OF THE FOUR": the vendor instructs us to re-fetch the
# last three days every night because readings arrive late; a refuse-only
# duplicate guard refuses the instruction, reports success, and silently never
# takes a backfilled reading. Step 2 is that red run.
---

**Intent.** Idempotency has a **mode**. `refuse` is right where a second arrival is an
accident (J51's bank file); `reconcile` by natural key is right where **a second read is the
instruction** — the meter supplier fills gaps and revises values after the fact, so Tuesday
re-reads the same three days as Monday **on purpose**. The run reports a **fifth count**,
`changed` — *1,240 read · 6 revised* — 1,238 rows do not move, and **a reading already billed
never moves**: the difference is handed to metering's service as a **correction**, never an
update (hard rule 4). Around it, the walk that gets the readings: a **ten-minute token
re-minted in memory across a two-hour collection with one credential row**, a **fetch plan
declared as data**, **safety parameters stated explicitly** so no vendor default is inherited
on a money path, and a **one-day flag whose missed night raises** instead of quietly catching
up.

**Upstream leaves (handoff in).** Brazos Bend's `meters_neptune360` connection: **sixteen
operations, one credential** (`auth.mode = token_exchange`, long-lived pair `••••N360`, token
TTL **600 s**); fetch plan `window = 7 days`, `page_size = {readings: 5000, meters: 150,
routes: 100}`; the `readings` operation `idempotency.mode = reconcile`, natural key `meter ·
register · read_at`, `safety_parameters = [actual_consumption, include_estimates=false, …]`
(four); the `register_changeout` operation `must_not_skip`; the `billing_export` operation
`completion = submit_poll_collect`, `poll = {every 30 s, max 40}`, `mutates_partner_state =
true` on `CloseOnExport`. Cadence nightly, `America/Chicago`. ***The backfill* fixture — the
design's single most important new fixture:** Monday **2026-08-31**'s collection of **1,240**
readings for **28–30 Aug**; Tuesday's response with **4 added** and **2 revised** —
`MTR-2210 register 1 · 2026-08-29 · 4,517 → 4,571 gal` and `MTR-0987 · 2026-08-30 · 12.3 →
12.8 kWh`; **`MTR-2210` already billed on `BL-2609-0044`**. The change-out flag published for
**one day only**. A two-year backfill fixture (**105** windows) with a fault at window **61**.
Actor **Priya Menon** (reading S142); the nightly collection.

**This journey leaves (handoff out).** Metering's rows: **4** new readings inserted, **2**
superseded **through `apps/metering/services.supersede_read`** (a new row with a supersedes
link — the old row kept), **1 correction** raised naming `BL-2609-0044`; `MTR-2210`'s billed
reading **byte-identical**; `1,238` rows with `updated_at` unchanged. Run rows: Monday
`1,240/1,240/0/0/0 · succeeded`; Tuesday `1,240/1,240/0/0/6 · succeeded` (*1,240 read · 6
revised*); a **raised** row for the missed change-out night; a refused-to-start row naming
`actual_consumption`; the export's key-and-receipt row and its refused retry. **One**
credential row before and after. J57 continues on the same connection with the register
sync.

**Fixture.** Frames `83.2` (*1,240 read · 1,234 unchanged · 6 changed · 0 refused* — **Nothing
already billed was touched.** — and the amber *2 meters had their register replaced yesterday
… This flag is published for one day only*), `83.1` (*what we ask them for* — the four
unsafe defaults), `53.2` (*They are building the file… asked them 4 times · checking again in
30 seconds*). `06-backend/tests/pg/test_us_int_034_reconcile_pg.py`. `JOBS_EAGER=false
--reuse-db`.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (rows · counts · immutability · isolation) | Rule |
|---|---|---|---|---|
| 1 | **Monday's nightly collection** (their midnight, `America/Chicago`) | 1,240 readings for 28–30 Aug **inserted through metering's service** — never by an adapter write. S142: *1,240 read*. Run `1,240/1,240/0/0/0 · succeeded` | The request carried **all four** safety parameters explicitly — `actual_consumption` among them — asserted on the fixture. `MTR-2210`'s 29 Aug reading (`4,517 gal`) is later billed on `BL-2609-0044` | BR-INT-050 · hard rule 3 |
| 2 | **Tuesday's collection · PostgreSQL · the red run first** — the same three days against a **refuse-only** guard | *1,240 duplicates refused*, **six readings lost, run green** — recorded as the RED run this guard exists for (law 7). This is the naive build that passes every test | The vendor's instruction was refused and reported as success | `US-INT-034` TC-2 |
| 3 | **Tuesday's collection · PostgreSQL · reconcile mode** | Run reads ***1,240 read · 6 revised*** (`changed = 6`); **4 new** readings inserted; **2 revised** — `MTR-0987 12.3 → 12.8 kWh` **superseded through metering's service** (a new row, the old kept with a supersedes link); **1,238 rows untouched** — `updated_at` unchanged on every one | The `changed` count is rendered **only** for an operation whose mode is `reconcile`. Every reading carries its **unit** (`gal`, `kWh`) — a value without its declared unit is refused **by name** (the measurement frame) | BR-INT-029 · BR-INT-049 · hard rule 3 |
| 4 | **🔒 the billed reading** — `MTR-2210 · 4,517 → 4,571 gal`, already on `BL-2609-0044` | **The reading is not touched.** A **correction** is raised through metering's correction path **naming the bill**; the run's summary says so; frame `83.2`'s note ***Nothing already billed was touched*** | Hard rule 4: no UPDATE on a billed reading, an issued invoice or its lines — corrections are new rows. Billing's money on the correction is **billing's** (EP-BIL-04), not this run's | BR-INT-029 · hard rule 4 · `US-INT-034` TC-3 |
| 5 | **negative · the night that must not be skipped** — workers down on 2 Sep; the `register_changeout` operation misses its window | A **raised** row: *missed 2 Sep — the change-out flag for that day cannot be refetched*; the S8 panel shows attention; **no silent catch-up** — a refetch a week later honestly returns nothing | Frame `83.2`'s amber box: *2 meters had their register replaced yesterday … This flag is published for one day only.* Skipping is about two runs at once; re-reading is about the same days twice, deliberately | BR-INT-050 · BR-INT-024 |
| 6 | **negative · a safety parameter unset** — the request template omits `actual_consumption` | **The run does not start.** S142 reads *not started — actual_consumption was not set*; **no request left**. A manifest marking an operation `mutates_partner_state = true` with no idempotency source is refused **at load** | One supplier has **four** request parameters that fail open, two on the money path — a collection omitting `actual_consumption` returns estimates that look like reads. *Never inherit a supplier's default on anything that touches money* (frame `83.1`) | BR-INT-050 · `US-INT-035` TC-1/4 |
| 7 | **the fetch that changes their world** — `billing_export` with `CloseOnExport = true`; then the same period again | A run row with an **idempotency key and a receipt written before the call**; their routes close **once**. The retry is **refused** — *already closed on 1 Sep* — one close, not two | S142 while running: *They are building the file. We will collect it when it is ready · asked them 4 times · checking again in 30 seconds* — the clerk can leave the page; the run is `succeeded` **only when the file is collected**; 40 polls never ready → `unconfirmed` *they never finished the file*, never succeeded, never silently failed | BR-INT-050 · BR-INT-046 · BR-INT-018 |
| 8 | **the walk** — the two-year backfill: 105 windows, two hours, a fault at window 61 | The token is **re-minted ≥ 11 times mid-walk, in memory**; `integration_credential` row count for the connection is **1 before and after** — not 144 a day. The runner requests **exactly** the declared page sizes (`5000 / 150 / 100`); the fault at window 61 **resumes at 61** from the job checkpoint — windows 1–60 are not re-fetched. Captured logs carry **neither the pair nor any token** | Changing a page size or the window in the **manifest** changes the request with **no code change**; a window of 30 days against a provider capped at 7 is refused **naming the parameter** — no silent narrowing | BR-INT-047 · BR-INT-025 · BR-INT-003 |
| 9 | **the budget underneath** | The 105-window walk spends **105** calls, incremented **once, atomically with the run row**. At 9,980 of 10,000 with 40 due the sweep **declines to start** (J56) | A run still going when the next is due → **skipped and recorded**; nightly is **their midnight** on both sides of the DST change | BR-INT-034 · BR-INT-024 |
| 10 | **tenant isolation** | Two tenants collect from the **same vendor**: reconcile keys **carry the tenant** — one tenant's backfill **never supersedes another's rows**; two token caches — neither can present the other's token; two budgets | RLS `FORCE` on `integration_run`; metering's rows tenant-scoped | hard rule 1 · `US-INT-034` TC-6 · `US-INT-028` TC-6 |
| 11 | **INVARIANCE** | Six rows moved, 1,238 did not, **none of the billed ones was touched**; every write to readings went through metering's service; every reading had its unit; no vendor default was inherited; one credential row survived a two-hour walk; the route-closing export happened once; the missed night raised rather than caught up | The correction is a **new row** naming the bill — the customer is never charged twice for the same water, and never silently re-billed | BR-INT-029 · hard rule 4 · B1 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | The register sync **writing** a meter's size | `OQ-INT-1485` — which system is master of the meter-to-account link. That is **J57**, which ends one step early |
| b | **Hourly interval** data collected | `OQ-INT-1484` — about 26 million rows a year at 3,000 meters, half a billion at the top of the range; NFR-27's storage re-run and partition sign-off first. Readings only here |
| c | The 🔒 files reaching lifecycle RATIFIED | A recorded human sign-off with the figures shown (L4, K4) — never a lane's own |
