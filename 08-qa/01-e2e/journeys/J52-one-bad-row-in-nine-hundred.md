# J52 — One bad row in nine hundred — PostgreSQL (`899 / 1 / 0`, row 412 named with its reason, and a fix that re-uploads just that one)

---
id: J52
tier: 2
rules: [BR-INT-023, BR-INT-018, BR-INT-020, BR-PAY-036, BR-PAY-028]
stories: [US-INT-032]
# Wiring: `US-INT-032` cites `J52` in its `journeys:` frontmatter. The flow
# document's index also lists US-INT-033 for J52; its frontmatter cites J51, J14,
# J19 — the hash rule it owns is asserted here through BR-INT-020. Filed as
# DEF-INT-3613; the index corrected 2026-09-03.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J52.spec.ts`. Wave I task I4 writes it
# with J51 (`cr069-i-same-file-twice.mjs`, steps 4–6). Phase 4.
# ⚠ HARD-WON LAW 14, FOUND INDEPENDENTLY BY TWO LANES ON 2026-08-29: on
# PostgreSQL a failed statement poisons the whole transaction; the test suite
# runs on SQLite, which does not; so `try/except IntegrityError: continue`
# passes the entire suite green and loses production data. A SAVEPOINT (a nested
# `transaction.atomic()`) is the ONLY option, and the code comment says so or the
# next lane simplifies it away. THIS JOURNEY RUNS ON REAL POSTGRESQL
# (`06-backend/tests/pg/test_us_int_032_savepoints_pg.py`, `JOBS_EAGER=false
# --reuse-db`, `DJANGO_SETTINGS_MODULE=config.settings.local`).
---

**Intent.** A 900-row lockbox file with one row that violates a constraint. The import
commits **row by row inside a savepoint**: row 412 is **recorded and skipped**, rows 1–411
and 413–900 are in, the run reads **`899 / 1 / 0`** — counts that **reconcile** to the row
count — and the receipt names the row **and the reason in words**: *row 412: account
4471-0021 is not on file*, the driver's SQLSTATE read **two or three hops down `__cause__`**,
not one. Priya fixes and re-uploads **just that one** row's file; the content-hash guard sees a
different file. **A payment is always accepted — a refused row is a row, never a refused
file.**

**Upstream leaves (handoff in).** J51's *Chase lockbox* connection on Brazos Bend; the
per-row savepoint at `payment_import.py:801-809` with its law-14 comment in place. **The
poison-row file**: 900 rows, BAI2, row 412 → account `4471-0021` (**absent** on Brazos Bend;
**present on Lone Star Ridge** for the isolation case). **The one-row fix file** for 412.
Actor **Priya Menon**. PostgreSQL 16.

**This journey leaves (handoff out).** **899** payments committed (payments'), ONE run row
`attempted 900 · succeeded 899 · failed 1 · skipped 0 · partial` with a receipt artifact
naming row 412; then ONE more run (a different `input_hash`) of **one** row → **900**
payments; the **original receipt unchanged**. J14's numbers on S35 (the batches by day ×
method) are the same arithmetic on a smaller file.

**Fixture.** S38 upload → S142 run → the receipt. Red-first fixture: the same file against a
handler with `try: … except IntegrityError: continue` and **no** savepoint.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (rows · counts · SQLSTATE · isolation) | Rule |
|---|---|---|---|---|
| 1 | Priya uploads the 900-row file through *Chase lockbox* (**PostgreSQL**) | Rows **1–411 and 413–900 committed**; row 412 **recorded refused and skipped**; the run reads **`899 / 1 / 0`** — `899 + 1 + 0 = 900` reconciles. The receipt artifact names *row 412: account 4471-0021 is not on file* | Each row commits inside a **nested `transaction.atomic()`** — a savepoint. **The code comment says a savepoint is the only option.** The file was hashed **before** parse (J51) | BR-INT-023 · BR-INT-018 |
| 2 | **red-first · the run this guard exists for (PostgreSQL)** — the same file against `try/except IntegrityError: continue` with **no** savepoint | `InFailedSqlTransaction` on row **413**; **zero** rows committed — the whole transaction is aborted and every later query raises `TransactionManagementError: You can't execute queries until the end of the 'atomic' block` | Recorded in the test as the RED run (law 7). This is the naive fix that **passes the SQLite suite green** | law 14 · `US-INT-032` TC-2 |
| 3 | **SQLite honesty** — step 1 on the default suite | Passes **with and without** the savepoint — asserted in the test's **docstring** as the reason the PG job exists. **The CI job is the proof, not this** (`.github/workflows/ci-backend.yml` gains the `tests/pg` step in wave A) | SQLite has no aborted-transaction state | law 14 · `US-INT-032` TC-3 |
| 4 | **the sentence** — read row 412's SQLSTATE | The driver exception is found by **walking `__cause__` until the driver exception** — `exc.__cause__` on a caught Django `IntegrityError` is *another* Django `IntegrityError`; the SQLSTATE is two or three hops down. The sentence is ***is not on file***, not the generic *could not be saved* | A first draft reading one hop returns the generic sentence for every row and **looks handled** — a check that cannot fail | law 14 · `US-INT-032` TC-4 |
| 5 | Priya fixes account `4471-0021` on Brazos Bend and uploads the **one-row** fix file | A **different content hash** → accepted; one more payment; the account now has its payment; **the original receipt is unchanged** — a correction is a new run, never an edit | The batch records its producing connection; J14's day × method grouping absorbs the extra row on its posting date | BR-INT-020 · hard rule 4's shape |
| 6 | **negative · a payment is always accepted** | No file was ever refused for a bad row; the 899 landed while 412 waited — *a refused row is a row, never a refused file* | The receipt is an artifact on the run (`artifact_link`), readable on S142 | BR-PAY-036 · BR-INT-039 |
| 7 | **tenant isolation** | Row 412 names an account that **exists on Lone Star Ridge** → still refused as ***not on file*** — RLS makes the other tenant's account invisible **and the message reveals nothing** about it | `app.tenant_id` set before the import; RLS `FORCE` | hard rule 1 · `US-INT-032` TC-6 |
| 8 | **INVARIANCE** | Every count reconciled (`899 + 1 + 0 = 900`); no row was lost; no row was applied twice; the refused row was named with the driver's reason; the original receipt never changed | The proof ran on PostgreSQL — a green SQLite run proves nothing here | BR-INT-023 · BR-INT-018 · law 14 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | The 899 payments' **allocation and books** | Payments' and the ledger's — `US-PAY-003`, `US-LED-016`; J14 asserts them. This journey moves files and keeps counts |
