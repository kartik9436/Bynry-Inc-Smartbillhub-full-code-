# J71 — Asset upload: template → fill → upload → carts and fire lines on the unit → the bill counts them

---
id: J71
tier: 2
rules: [BR-AST-541, BR-AST-034, BR-AST-012, BR-AST-045, BR-AST-538, BR-RAT-090, BR-MET-119, BR-MET-530]
stories: [US-AST-010]
# ⚠ NOT ACTIVATED — no `J71.spec.ts`. Written 2026-09-30 by the asset-upload lane as plan U14
# (`04-docs/05-modules/05-assets/12-asset-upload-fix-plan.md`). The backend half of every step is
# proved by `06-backend/tests/test_ast_upload_fix_u12.py` and `test_def_ast_8102_job_load.py`
# (default suite AND PostgreSQL 16).
# WALKED IN A BROWSER 2026-09-30 (plan U14) at 1440 and 1280 — see "Browser walk, 2026-09-30"
# at the foot of this file. Still no `J71.spec.ts`: the walk is
# `10-scripts/ast_u14_asset_upload_walkthrough.mjs`, screenshots in
# `08-qa/screens/asset-upload-2026-09-30/`.
---

**Intent.** A utility that bills trash per cart and fire per line loads its carts and fire lines
from a spreadsheet and sees them on the next bill — the tester's report that started this
(*"it won't work with the devices sheet, and it never can. That sheet has no Service or Size
column"*), walked as a person would. Every figure below is the PO's ruling or the seeded fixture.

**Sources.** Plan `12-asset-upload-fix-plan.md` (tables + U1–U15) · decision log 2026-09-30 (the
asset-upload rows) · `BR-AST-541` · CR-063 (fire counts like trash: one 6" line + two 2" lines =
`$60.00 + 2 × $12.00` = `$84.00`).

## Preconditions — the seed

Tenant **Brazos Bend Utilities** with **trash** and **fire** enabled; actor **Alex Reed** (System
Admin). Premises **1408 Elm St** offers water, electric, trash, sewer, gas, fire; its **Unit A**
has a published plan with trash **$15.00 per cart** and fire's per-size prices (FL-2 **$12.00**,
FL-6 **$60.00**). A second premises **9 Water Only Rd** offers water only, with **Unit W**.

## Steps

| # | Actor does | The screen / file shows | Proved by |
|---|---|---|---|
| 1 | Assets › Upload › **Behind the meter** › Download template | A CSV whose header is the plan's 19 devices columns **in six groups, in order**: Device number (existing only) · Device type · External reference · Serial number · Premises · Unit · Parent / linked meter · Service · Size · Unit of measure / capacity unit · Export capacity (kW) · Manufacturer · Model · Install date · Test frequency (months) · Next test due · Warranty end · Supplier · Purchase cost | `test_DOWNLOAD_the_template_header_follows_the_plan_order[assets_devices]` |
| 2 | Fills 5 rows: two carts (`container_cart`, Service **trash**, Size **CART-64**, Unit **Unit A**), one fire line (Service **fire**, Size **FL-6**, Unit A), two fire lines (**fire**, **FL-2**, Unit A); Unit of measure left blank | — | — |
| 3 | Adds a 6th row: a cart on **Unit W** (Service trash) and a 7th: a cart with Size **W-58**, Unit of measure **furlongs**, Parent **M-NOPE** | — | — |
| 4 | Uploads the file; stage 2 | The picker groups its targets under **Identity · Location · Service and billing · Device details · Dates and testing · Purchase**; every header maps itself | `groupTargets`/`assetGroupKey` (vitest) |
| 5 | Stage 3 (check) | Row 6 rejected: *"Unit Unit W has no Trash service."* Row 7 rejected with **all three** problems on one row: *"W-58 is a size for Water, not for Trash."* · *"furlongs is not a unit of measure on this tenant's list."* · *"Parent meter M-NOPE was not loaded."* Rows 1–5 clean | `test_U5_…refuses_the_row_by_name` · `test_U12_three_problems_on_one_row_are_all_reported` |
| 6 | Downloads the rejected rows | The failures file's columns are in the plan's order, each cell under its own header, then *why it failed* · *how to fix it* | `test_DOWNLOAD_the_failures_file_is_re_ordered_into_the_plan_order` |
| 7 | Loads (stage 4) | 5 loaded, 2 rejected. Each cart and line took the **service's own unit** (blank → default) | `test_U12_a_blank_unit_of_measure_takes_the_services_default` |
| 8 | Opens Unit A › Assets | Two carts on **Trash**, three lines on **Fire**, each with its size | `test_U6_device_service_size_and_uom_are_written_and_seat_on_the_trash_point` |
| 9 | One-time bill / bill preview for Unit A's account | Trash counts **2 carts** × `$15.00` = **`$30.00`** (plus base per cart **only once `DEF-BIL-8095` lands**: 2 × (`$15.00` + `$3.00`) = **`$36.00`**); fire **`$60.00` + 2 × `$12.00` = `$84.00`** | `test_U12_two_carts_uploaded_on_the_devices_sheet_are_COUNTED_on_the_unit` asserts the COUNT (2); the priced figure waits on `DEF-BIL-8095` |
| 10 | Re-uploads row 1 with its device number and Size **CART-96** (Insert & update) | Loaded as an update; the result file's `billing_changes` cell reads *"Size: CART-64 → CART-96"*; the asset's audit shows before/after; bills already issued are unchanged (forward-only) | `test_U12_re_upload_OVERRIDES_billing_fields_audited_and_forward_only` (meter case) |
| 11 | Uploads 250 carts (over the 200-row bar) | The load runs as a background job with its progress bar; all 250 land, 50 per unit, and each unit's trash count is 50 | `test_U13_250_carts_uploaded_by_the_worker_are_counted_on_their_units` (PostgreSQL 16) |

## What must NOT happen

* A cart loads with no service point and bills nothing (the defect, `DEF-AST-8097`).
* A row shows only its first problem (`DEF-AST-8100`).
* An upload over 200 rows writes nothing (`DEF-AST-8102`).
* A re-upload silently skips a billing field (`DEF-AST-8099`).

## Browser walk, 2026-09-30 (plan U14)

**Walked** on build `2.411.0` → fixed in `2.411.1`, PostgreSQL 16 on its own port, `seed_demo`
(Brazos Bend), `JOBS_EAGER=false` with a real Celery worker on Redis (so the over-200 loads ran
as background jobs, not in the request), the `--mode compose` bundle behind `server.mjs`, Chromium
at **1440 and 1280**. Driver: `10-scripts/ast_u14_asset_upload_walkthrough.mjs`; screenshots:
`08-qa/screens/asset-upload-2026-09-30/<width>-<step>-….png`.

⚠ **The seed does not carry this journey's preconditions** — trash and fire are not switched on and
there is no *1408 Elm St* — so they were made through the service functions before walking:
trash + fire enabled; *1408 Elm St* (water · electric · trash · fire) with Unit A `U-00001`,
Unit B `U-00003`, Bulk 1–5 `U-00004…8`; *9 Water Only Rd* (water) with Unit W `U-00002`; later
*1410 Elm St* with Unit C `U-00009` and Unit D `U-00010` (clean units for the re-walks after the
fixes). No plan was attached, so step 9's priced bill was NOT walked; the COUNT the bill multiplies
was read with `assets.selectors.billable_asset_count` (Unit A: trash **2**, fire **3**).

| Walk step | Journey step(s) | Result |
|---|---|---|
| 1 · Download the three samples; header order and groups | 1 | **PASS** at both widths — meters 19, sub-meters 21, devices 19, each in the plan's order |
| 2 · Devices sheet, 2 carts + 3 fire lines, Insert new only → result file; unit shows them | 2, 7, 8 | **PASS** after fix. First walk: loaded correctly (all five on the trash/fire service point) but the receipt said *"Wired to no services 5 … nothing to bill them for yet"* → **`DEF-AST-8360`, fixed in 2.411.1**. Re-walked on Units C and D: receipt clean, result file 5 rows, Assets tab shows 2 × Trash 64-gallon cart and 3 fire lines |
| 3 · Re-upload with a changed billing field, Insert & update | 10 | **PASS** — dry run *5 updated, 0 created*; result file `billing_changes` = *"Size: CART-64 → CART-96"*; `audit_log` holds `asset.updated` `{"size_class": "CART-64"}` → `{"size_class": "CART-96"}` (the devices sheet has no Multiplier, so Size — also 💲 — was the field moved) |
| 4 · A row with several errors | 3, 5, 6 | **PASS** — Unit W row *"Unit U-00002 has no Trash service."*; the bad row shows all three problems at once on stage 3 and in the receipt; *"Download the 2 rows that failed"* carries all three, in plan column order, then `why_it_failed` · `how_to_fix_it` (the rejected-rows file is offered on the receipt, not at stage 3) |
| 5 · 250 rows (over the 200 bar) | 11 | **PASS** — progress panel *0% … 86% complete* (*"Loading… 0 of 250"*, runs in the background), 250 loaded, each Bulk unit counts **50** trash carts; ~14–21 s click-to-receipt, worker 12–19 s |
| 6 · 500-row Insert & update (250 updates + 250 creates) | — | **PASS** — 500 loaded, 250 flagged *"already on file … will update"*, sizes moved; **33.1 s** click-to-receipt, worker **30.8 s** |
| 7 · Stage-2 picker groups | 4 | **PASS** — optgroups Identity · Location · Service and billing · Meter details / Device details · Dates / Dates and testing · Purchase; `— ignore —` was offered **twice** → **`DEF-AST-8361`, fixed in 2.411.1**, re-walked: once |

**Found and filed, not fixed (outside the upload files):** `DEF-MET-8362` — once the bulk uploads put
~1,000 assets on *1408 Elm St*, Unit B's Assets tab listed its five devices with **"—"** for
service, size and status (`1280-DEF-MET-8362-unit-B-assets-tab-dashes.png`): the tab reads the
premises' registry at `per=200` and filters it in the browser.

**Noticed on the walk, filed and fixed afterwards in 2.411.3** (PO 2026-09-30: *"fix it if there is
a bug"*): the result file's header was field names (`asset_number`, `unit_assigned`) while the
template and the rejected-rows file use the column labels — `DEF-AST-8363`; the devices sample row
paired a `backflow` device with `electric` and size `E-1P-100` — `DEF-AST-8364`. `DEF-MET-8362`
above is fixed in the same build: the unit's Assets tab asks `GET /assets?f.unit_id=` for its own
page. The same first-page-then-filter shape remains on the property's Assets tab and tile
(`DEF-MET-8365`) and in two wizard pickers (`DEF-AST-8366`), filed and open.
