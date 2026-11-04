# J-REP-01 — open the register, page to 3, sort, search one bill, export it

---
id: JREP01
tier: 1
rules: [BR-REP-001, BR-REP-002, BR-REP-006, BR-REP-018, BR-REP-024, BR-REP-033,
        BR-SHL-011, BR-SHL-013, BR-SHL-023, NFR-3, NFR-5]
stories: [US-REP-002, US-REP-003, US-REP-006]
change: CR-142-BRC07 · Phase 2 · P2.11
screens: [S46]
# ⚠ **ACTIVE, AND PARTLY UNPROVABLE ON THE DEMO TENANT.** See *What the seeded
# tenant cannot show* below — it is 45 bills, so steps 3 and 4 have no second
# page to turn to. The journey states that rather than skipping it, because a
# step silently dropped is hard-won law 7's fifth shape.
---

> **Read the drawings as IMAGES (B14 rule 42), never the text layer:**
> `python3 10-scripts/pdf/pdf_render.py "05-prototype/09 Reports Build Brief.pdf" <outdir> 3 24,25,26,27`
> 2·1a is **p024**, 2·1b (the billing register, which is what this journey
> walks) is **p025**, 2·1c and 2·1d are **p026**, and the screen's own field
> and control table is **p027**.

## WHAT THIS JOURNEY IS FOR

**Phase 2's DONE WHEN is a single sentence and this is the walk of it:** *"A
report of 38,412 rows opens in under two seconds showing 50, and no export is
refused for being large."*

Every step below was impossible on 2026-09-25. The viewer asked for `per=all`,
rendered one table with no pager, no sort, no search and no column chooser, and
the module held **four different table implementations**. There was nothing to
page to, nothing to sort by and nothing to search.

## THE HANDOFF CONTRACT

**What upstream leaves for this journey:** a tenant with issued bills in the
current accounting period. `manage.py seed_demo` then `manage.py
load_sample_data --tenant brazosbend` leaves **45**.

**What this journey leaves for downstream:** one `jobs` row per export, which
is the run record `J-REP-02` (Phase 3, the History tab) reads. **It writes
nothing else.** §8.1 of the brief: *"Reports writes to no module's tables — the
only rows it creates are a job, a definition, a schedule and an audit entry."*

## THE WALK

| # | Step | What must be true | Proved by |
|---|---|---|---|
| 1 | Sign in, open **Reports** | The catalogue lists the tenant's reports | `10-scripts/rep_p2_viewer_walkthrough.mjs` |
| 2 | Open **Billing Register** | The head names the window AND the basis (BR-REP-001). The line under the title says what one row is — *One row per bill* — in four words (P2.23) | idem |
| 3 | **Page to 3** | The URL carries `page=3`; the request carries it; the pager reads the SERVER's total, not the page's row count | idem — **see the caveat** |
| 4 | **Sort** by Amount, descending | A caret is drawn only on a column the DATASET declares sortable (`controls.sorts`); `sort` and `dir` reach the server and the ORDER changes | idem |
| 5 | **Search one bill** by its number | `q` reaches the server; the row count falls to 1; the bill is on screen | idem |
| 6 | **Export it** | `POST /exports` answers 202 with a job id, and the filters it carries are the clerk's WHOLE selection **minus the page** | idem |

### ⚠ STEP 6 IS THE ONE THAT SHIPS WRONG, AND IT HAS ALREADY NEARLY HAPPENED

§8.2, verbatim: *"The left path never fetches more than a page; the right path
never holds one."* When the billing register started paging, **its export
silently inherited the screen's fifty rows** — a clerk would have exported a
38,000-row register and received a file of fifty that looks perfectly valid. No
error, no gate, no test.

So step 6 asserts the FILTERS, not the file: `page` and `per` must be absent
from the export request and every other criterion must be present. The unit
half is `reportExportFilters` in
`07-frontend/src/features/reports/reportViewerControls.dom.test.tsx`; the server
half is `apps/reports/exports.py`'s `whole=True`.

## WHAT THE SEEDED TENANT CANNOT SHOW, AND THE NUMBER BESIDE IT

**`brazosbend` holds 45 issued bills.** At 50 rows a page that is ONE page, so:

* **Step 3 has no second page to turn to.** The walkthrough asserts what it can
  — that `?page=2` on a 45-row report CLAMPS to *1–45 of 45* rather than
  drawing *51–45 of 45*, which is what it drew on 2026-09-26 before the clamp.
  **The real paging proof is `P2.9`**, which seeds 40,000 rows against a real
  PostgreSQL and asserts the page-two query reads 50.
* The 38,412-row figure in Phase 2's DONE WHEN is **Killeen's**, not this
  tenant's. The backend half is measured: page 1 of the register is **0.211s**
  and the last page is **0.206s**.

**A journey that quietly skipped step 3 would report a clean walk over a step
it never performed.** This is that step, with its number beside it.

## WHAT RED MEANS

A red step here is a product defect, not a fixture problem, with two exceptions
stated above: step 3's second page and the 38,412 figure, which this tenant
cannot produce. Anything else — a caret on a column the query ignores, a pager
counting backwards, an export carrying `page` — is a defect and is filed as one.
