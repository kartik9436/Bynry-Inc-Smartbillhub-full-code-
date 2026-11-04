# J-REP-02 — export a report, find the run on History, download the file

---
id: JREP02
tier: 1
rules: [BR-REP-018, BR-SHL-011, BR-SHL-021, BR-SHL-023, NFR-3, NFR-5]
stories: [US-REP-003]
change: CR-142-BRC07 · Phase 3 · P3.6
screens: ["5·1", "5·2"]
depends_on: [JREP01]
# ⚠ **ACTIVE.** Every step below was impossible on 2026-09-26: `/reports/
# history` answered `422 VAL-005 reports.viewer.unknown_key {"key":"history"}`
# through the real URLconf, because the `/reports/<key>` catch-all swallowed
# the word. Quoted from the run, not from the document.
---

> **Read the drawings as IMAGES (B14 rule 42), never the text layer:**
> `python3 10-scripts/pdf/pdf_render.py "05-prototype/09 Reports Build Brief.pdf" <outdir> 3 39,42,43,91`
> `5·1` is **p039**, `5·2` is drawn at the foot of **p042** and its field table
> is **p043**, and §8.2's two read paths — the drawing this journey is the end
> of — are **p091**.

## WHAT THIS JOURNEY IS FOR

**Phase 3's DONE WHEN, verbatim:** *"An export made on `2·1` is findable on
`5·1` within a second, and downloadable for three days."*

And the reason it matters more than a list screen usually does: until this
lands, the product tells a clerk their file *"appears in Jobs when it is
ready"* and **there is no Jobs screen anywhere in the product** — no route, no
nav word, no component. p039's own DOORS row counts three ways in and then
says: **TODAY THE COUNT IS ZERO.** This journey is the walk of that sentence
stopping being true.

## THE HANDOFF CONTRACT

**What upstream (`J-REP-01`) leaves for this journey:** one `jobs` row per
export, which **IS the run record** — there is no `report_runs` table and there
must not be one. `apps/reports/exports.py:60` has said so in prose since
2026-08-16 (*"A stored run row … the JOB record is the run record"*); Phase 3
turns that sentence into a read.

**What this journey leaves for downstream:** nothing new. It writes one further
`jobs` row if step 6 is walked, and an `audit_log` row with it. **No ledger, no
bill, no payment, no account** — p043 callout ④ states that explicitly.

## THE WALK

| # | Step | What must be true | Proved by |
|---|---|---|---|
| 1 | Sign in, open **Reports** | The tab strip is drawn — **Catalogue · History**. ⚠ It was not drawn at all before this phase: `SubTabs` returns `null` below two tabs and History was the second | `10-scripts/rep_p3_history_walkthrough.mjs` |
| 2 | Open a report and **export** it | `POST /exports` answers **202 with a job id**, and the toast says *"Your CSV is being written. Find it on History."* ⚠ It said *"It appears in Jobs when it is ready"* in all eleven catalogues | idem |
| 3 | Click **History** | The address is `/{tenant}/reports/history` and the screen carries `data-screen="5.1"` | idem |
| 4 | **Find the run** | The newest row is the export from step 2 — the report's NAME, the time, **Dana Whitfield**, its parameters, **Ready**, its row count, and a download control | idem |
| 5 | **Download it** | The control's `href` is `/api/exports/{job_id}/file`; the response is `200 text/csv` with the IS-11 five-segment filename | idem |
| 6 | Open the run (`5·2`) and **Re-run** | A NEW `jobs` row with **the original parameters, unchanged**; the old run and its file untouched; a new row at the top of `5·1` | idem |
| 7 | Find a run whose **file has been swept** | The row says **Expired**, keeps every fact it had, and **offers no download control at all** | idem + `tests/test_cr142_p3_run_history.py` |

### ⚠ STEP 7 IS THE ONE THIS PHASE EXISTS TO GET RIGHT

**A row outliving its file is the DESIGNED state, not an edge case.** Retention
is evaluated against the RUN'S TIMESTAMP, and nothing deletes the `jobs` row —
so a run from last month is a true, complete record of something that happened
whose file is gone. The only wrong thing to draw over it is a download control.

**That is the same defect as the toast in step 2**: a live control pointing at
nothing. Shipping a download button over a purged file would close one instance
of the fault while opening another, on the same screen, in the same release.

⚠ **THE TWO REASONS A ROW EXPIRES ARE PROVED SEPARATELY.** The backend case
`test_a_run_older_than_the_window_expires_even_with_its_file_present` ages the
row and **leaves the file on disk**, so it fails if the timestamp rule is
removed. A case that also deleted the file would prove the other half and hide
this one.

## WHAT THE SEEDED TENANT CANNOT SHOW, AND THE NUMBER BESIDE IT

* **`brazosbend` has no run older than three days** unless the walkthrough ages
  one, because every job in it was created by the walkthrough itself. So step 7
  **ages a run's `created_at` by four days** and says so out loud rather than
  reporting a clean walk over a state it never reached. Measured on real
  PostgreSQL 16 on 2026-09-27: a run aged four days and swept read
  `status: "expired", file: null`, and `GET /api/exports/{id}/file` answered
  **404**.
* **A `Running` row cannot be walked at all on this machine.** `JOBS_EAGER`
  defaults to true and Celery cannot reach Redis on :6379, so a job is
  `succeeded` before the 202 returns — the drawing's *Running 62%* row has no
  live state to photograph here. **The percentage would read 0% even if it
  could**: `P2.4` deleted the export pre-count, so `progress.total` is `null`
  for a streamed export and a stream honestly has no denominator. Stated, not
  skipped.
* **The drawing's 38,412-row Billing Register is Killeen's**, not this
  tenant's. Measured here on 2026-09-27: `ar_aging` exported **30 rows in
  0.117s** end to end, 2,396 bytes of CSV.

## WHAT RED MEANS

A red step is a product defect, with the two exceptions named above — an aged
run and a running job, neither of which this machine can produce on its own.
Anything else is filed: a download control over an expired row, a toast naming
a screen that does not resolve, a row whose *Started by* reads *Schedule* for a
run a person started (that one was real, and is recorded in
`apps/tenancy/selectors.py`'s `_report_run_row` docstring).
