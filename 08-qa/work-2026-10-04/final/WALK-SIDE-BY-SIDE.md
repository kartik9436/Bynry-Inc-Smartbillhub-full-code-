# CR-168-BRC10 round 7 · lane WALK-A — the 65 drawings beside the built screens (build 2.518.0, fixes in 2.518.1)

**How.** PostgreSQL 16 (`sbh_wwalk`: `migrate` + `seed_demo` + `load_sample_data --tenant brazosbend`), API `runserver 127.0.0.1:8085`,
SPA `vite build --mode wolocal` served by `07-frontend/server.mjs` on `5217`, Chromium at **1440 wide**, signed in as Dana (System Admin).
Every drawing (`05-prototype/work-backoffice-2026-10-04/images/NN-*.png`) was opened as an image (B14 rule 42); every photograph here was
opened and checked not blank before it was cited. The photographs were taken by the group walks, re-run unchanged on this build except
where noted, and `10-scripts/cr168_r7_observations_walk.mjs` (written this round):

| Walk script | Images | Prep |
|---|---|---|
| `cr168_order_page_walk.mjs` | 03–11 | `cr168_order_page_seed.py` (WO-0041 open, WO-0042 closed by D. Ortiz) |
| `cr168_orders_list_after_walk.mjs` (`SKIP_ASSIGN=1`) | 21–23 | `cr168_orders_list_walk_prep.py` — **amended**: it now photographs required rows before the technician closes (the photo guard, P1.33, refused the old prep) |
| `cr168_assign_walk.mjs` | 02, 12, 13 | `cr168_assign_walk_prep.py` |
| `cr168_raise_after_walk.mjs` | 14–20 | — |
| `cr168_work_map_clusters_walk.mjs` | 24 | — |
| `cr168_crews_after_walk.mjs` | 25–33 | — (it stops at *Renew*, which CREWS-2 replaced with ✎ Edit; 34 is taken by the observations walk) |
| `cr168_parts_after_walk.mjs` | 35–37 | — |
| `cr168_templates_after_walk.mjs` | 43–55 | `ASSET_ID` = E-5000 |
| `cr168_rules_after_walk.mjs` | 56, 57, 59, 61–64 | a sweep script for the one rule |
| `cr168_perf_walk.mjs` | 65 | `cr168_perf_walk_prep.py` |
| `cr168_r7_observations_walk.mjs` | 01 (whole list), 34, 38–42 (each stage whole) | an import file whose new part numbers are not on file |

**Judging.** The drawing decides WHAT is on the screen and HOW it is arranged; our UI standard decides spacing, sizes, type and components
(B14 rule 44, rule 38 for forms). A difference of shape or content is a defect and is filed; a difference of spacing, type or component is
noted only. Every figure in a drawing is an illustration (rule 37); the walk's figures are the data's. The red dashed outlines in the
drawings mark the proposals that were to be built.

| # | Drawing | Our screen | Verdict |
|---|---|---|---|
| 01 | `01-orders-work-orders.png` | `01-orders-work-orders.png` | **Differs** — the five tiles wrap at 1440 and *Overdue* sits alone on a second row (`DEF-WRK-9680`: the shared tile track grew to 240px for a money value, `DEF-LED-6498`). Everything else matches: *+ New work order* top right, tabs, search, *All*, *+ Filter*, ▦, the ten columns, eye and pencil per row, footer |
| 02 | `02-orders-assign-in-bulk.png` | `02-orders-assign-in-bulk.png` | **Differs (data)** — the dialog, its fields and the per-name advice match; the advice line under *Who is going* is empty until a name is chosen because the demo's build jobs carry no template, so no skill is asked (`DEF-WRK-9676`) |
| 03 | `03-orders-order-overview-not-completed.png` | `03-orders-order-overview-not-completed.png` | **Differs** — Due reads *—* on a job raised with no priority while the server serves its 72 h promise (`DEF-WRK-9677`); Holder lacks the customer number *C-00001* (`DEF-WRK-9678`). Head, four tabs, Meter, Unit, Location and Customer panels match; *Print* is ruling 3's (P6) |
| 04 | `04-orders-order-overview-completed.png` | `04-orders-order-overview-completed.png` | **Differs** — no *Send back…* beside *Accept ✓*, though its endpoint is served (`DEF-WRK-9675`); no *Complete* status chip (`DEF-WRK-9681`); Holder without customer number (`DEF-WRK-9678`). Outcome, Closed by and the Signature panel match |
| 05 | `05-orders-order-checklist-not-completed.png` | `05-orders-order-checklist-not-completed.png` | **Matches** — safety as the plan, tasks as a table (ruling 14), readings, help |
| 06 | `06-orders-order-checklist-completed.png` | `06-orders-order-checklist-completed.png` | **Differs** — the record (ticks with who and when, photographs, values, *2 of 2 required photos*) matches; the head lacks *Send back…* (`DEF-WRK-9675`). *not taken* for a text reading where the drawing says *cannot be recorded* is right: text readings are recorded since SRV-1 |
| 07 | `07-orders-order-parts.png` | `07-orders-order-parts.png` | **Matches** — Part · Planned · Used |
| 08 | `08-orders-order-audit.png` | `08-orders-order-audit.png` | **Matches** — Act · To · By · When · Window (one row: only the assignment has happened) |
| 09 | `09-orders-order-photo-viewer-completed.png` | `09-orders-order-photo-viewer-completed.png` | **Matches** — task title, the picture, Taken by · When · For, *1 of 3*, Previous / Next |
| 10 | `10-orders-order-put-on-hold.png` | `10-orders-order-put-on-hold.png` | **Matches** — Reason*, Back on, Note, *The due time pauses while held.*, Back / Put on hold |
| 11 | `11-orders-order-cancel-order.png` | `11-orders-order-cancel-order.png` | **Matches** — *Cancel WO-0041?*, the consequence, *Keep the order* / *Cancel this order* on the danger tier |
| 12 | `12-orders-assign-a-job.png` | `12-orders-assign-a-job.png` | **Matches** — actions top right, Change effects, Status without *Complete*, the typeable picker with *Best fit* and advice at the right, none greyed. (M. Chen reads *Same area* rather than *Missing skill*: the demo job has no template — `DEF-WRK-9676`) |
| 13 | `13-orders-reassign-a-job.png` | `13-orders-reassign-a-job.png` | **Matches** — *Reassign ✓*, effects naming both people, *Was M. Chen* with the new name's advice, *Why it moves** with its reason |
| 14 | `14-orders-raise-job-on-units.png` | `14-orders-raise-job-on-units.png` | **Matches** — three-step rail, premises dropdown, units table with chips, job type, template, asset type, priority, *Raises 31 jobs — one per unit.* (chips are the tenant's five unit types — RAISE's recorded judgment) |
| 15 | `15-orders-raise-job-an-asset-type-chosen.png` | `15-orders-raise-job-an-asset-type-chosen.png` | **Matches** — assets with their own search, *Choose one* on Apt 101, the refusal named |
| 16 | `16-orders-raise-schedule-and-crew.png` | `16-orders-raise-schedule-and-crew.png` | **Matches** — due date picker from the priority, visit date and window, Assign to open with advice; no Area (ruling 24). Kind words after each name, not group headings (component — rule 44, noted) |
| 17 | `17-orders-raise-confirm.png` | `17-orders-raise-confirm.png` | **Matches** — summary, the jobs table, EFFECT, *Raise 6 jobs ✓* (shot as the press began: *Working…*) |
| 18 | `18-orders-raise-result.png` | `18-orders-raise-result.png` | **Matches** — *1 job raised*, Job · Unit · Asset · Result, *Raise more · Open work orders* (the one-job raise; the six-job result passed straight to the list) |
| 19 | `19-orders-raise-from-an-account.png` | `19-orders-raise-from-an-account.png` | **Matches** — *From the account*, filled; *Raises 1 job — on W-5000.* |
| 20 | `20-orders-raise-from-an-asset.png` | `20-orders-raise-from-an-asset.png` | **Matches** — *From the asset*, filled (ruling 35). No *Last read* row — RAISE's recorded difference |
| 21 | `21-approvals-approvals.png` | `21-approvals-approvals.png` | **Matches** — *Approvals*, Select column, Order · Connection · Premise · Service · Outcome · Completed · Waiting, eye and ✓, footer |
| 22 | `22-approvals-approvals-accept.png` | `22-approvals-approvals-accept.png` | **Differs → fixed in 2.518.1** — the question lacked *closed by D. Ortiz* (`DEF-WRK-9679`); it now names the closer. *Accept selected… (1)* top right, consequence, Keep waiting / Accept ✓ matched |
| 23 | `23-approvals-approvals-accepted.png` | `23-approvals-approvals-accepted.png` | **Matches** — queue one shorter, toast *WO-0037 accepted · service live* |
| 24 | `24-map-the-day-on-the-ground.png` | `24-map-the-day-on-the-ground.png` | **Matches in shape** — pins and clusters, the key, zoom, *Tiles © Esri*; all 24 orders reach their own page by mouse and by keyboard. The street ground **asks** for 18 Esri tiles and draws 0 **in this sandbox only**: its egress proxy refuses `server.arcgisonline.com` (403) though the page's CSP allows it. Not provable here; `DEF-WRK-9561` stays open for a check on a deployed build |
| 25 | `25-crews-crews-technicians.png` | `25-crews-crews-technicians.png` | **Matches** — three segments, the technicians table, *cert expiring / expired* pills, Certification watch, *+ Add crew member* |
| 26 | `26-crews-add-crew-member.png` | `26-crews-add-crew-member.png` | **Matches** — Person list with role · status, *on Field crew A* beside a crewed login (CREWS-2) |
| 27 | `27-crews-crews-crews.png` | `27-crews-crews-crews.png` | **Matches** — members by name then the count, both add buttons; the print icon per crew is FIX-7's day pack |
| 28 | `28-crews-crews-contractors.png` | `28-crews-crews-contractors.png` | **Matches** |
| 29 | `29-crews-add-a-crew.png` | `29-crews-add-a-crew.png` | **Matches** |
| 30 | `30-crews-add-a-contractor.png` | `30-crews-add-a-contractor.png` | **Matches** — Hours is the kit's segmented control (component, rule 38/44, noted) |
| 31 | `31-crews-one-technician-overview.png` | `31-crews-one-technician-overview.png` | **Matches** — Skills, Certifications, This month; *Print day…* is P6 |
| 32 | `32-crews-one-technician-jobs.png` | `32-crews-one-technician-jobs.png` | **Matches** — the CLOSED column is built now (it was a round-4 difference) |
| 33 | `33-crews-one-technician-certifications.png` | `33-crews-one-technician-certifications.png` | **Matches** — the PROOF column is built now; the row action is ✎ Edit |
| 34 | `34-crews-one-technician-performance.png` | `34-crews-one-technician-performance.png` | **Matches** — period, four tiles, *By job type* |
| 35 | `35-parts-parts.png` | `35-parts-parts.png` | **Matches** (ruling 32's Name; P3.8–P3.11's filter and row actions; Issue log live) |
| 36 | `36-parts-add-a-part.png` | `36-parts-add-a-part.png` | **Matches** |
| 37 | `37-parts-add-a-part-refused.png` | `37-parts-add-a-part-refused.png` | **Matches** — three *This is required.*, *Unit cost must be a number.*, *Fix 4 fields to continue.* |
| 38 | `38-parts-import-parts-extract.png` | `38-parts-import-parts-extract.png` | **Matches** |
| 39 | `39-parts-import-parts-transform.png` | `39-parts-import-parts-transform.png` | **Matches** — sample values, rows forward 5 |
| 40 | `40-parts-import-parts-validate.png` | `40-parts-import-parts-validate.png` | **Matches** — 5 · 3 · 2 · 0 · 3 |
| 41 | `41-parts-import-parts-load.png` | `41-parts-import-parts-load.png` | **Matches** — dry run 3 · 0 · 2, approval |
| 42 | `42-parts-import-parts-result.png` | `42-parts-import-parts-result.png` | **Matches** — 3 loaded, 2 rejected with their fixes |
| 43 | `43-templates-templates.png` | `43-templates-templates.png` | **Matches** (+ *Done to*, P3.12) |
| 44 | `44-templates-template-overview.png` | `44-templates-template-overview.png` | **Matches** — every panel with its rows (ruling 8) |
| 45 | `45-templates-template-usage.png` | `45-templates-template-usage.png` | **Matches** |
| 46 | `46-templates-template-versions.png` | `46-templates-template-versions.png` | **Matches** — v2's *What changed* is the note typed at publish |
| 47 | `47-templates-template-audit.png` | `47-templates-template-audit.png` | **Matches** — the history, in words |
| 48 | `48-templates-builder-details.png` | `48-templates-builder-details.png` | **Matches** |
| 49 | `49-templates-builder-safety.png` | `49-templates-builder-safety.png` | **Matches** — rows edit in place (ruling 5) |
| 50 | `50-templates-builder-tasks.png` | `50-templates-builder-tasks.png` | **Matches** |
| 51 | `51-templates-builder-materials.png` | `51-templates-builder-materials.png` | **Matches** |
| 52 | `52-templates-builder-readings.png` | `52-templates-builder-readings.png` | **Matches** |
| 53 | `53-templates-builder-help.png` | `53-templates-builder-help.png` | **Matches** — document upload, link, video badge (ruling 6) |
| 54 | `54-templates-builder-signature.png` | `54-templates-builder-signature.png` | **Matches** |
| 55 | `55-templates-builder-review.png` | `55-templates-builder-review.png` | **Matches** — one panel per section (rulings 7, 9) |
| 56 | `56-rules-rules.png` | `56-rules-rules.png` | **Matches** |
| 57 | `57-rules-rule-trigger.png` | `57-rules-rule-trigger.png` | **Matches** — three steps, several triggers |
| 58 | `58-rules-rule-assignment-retired.png` | — | **Not built, by ruling** — the Assignment step is retired (PO 2026-09-26, three steps); the drawing is tagged *Remove* |
| 59 | `59-rules-rule-notify.png` | `59-rules-rule-notify.png` | **Matches** |
| 60 | `60-rules-rule-escalation-retired.png` | — | **Not built, by ruling** — the separate Escalation step is retired; escalations are rows on Notify (59), tagged *Remove* |
| 61 | `61-rules-rule-review.png` | `61-rules-rule-review.png` | **Matches** |
| 62 | `62-rules-one-rule-overview.png` | `62-rules-one-rule-overview.png` | **Matches** |
| 63 | `63-rules-one-rule-jobs.png` | `63-rules-one-rule-jobs.png` | **Matches** — three rows read *—* for Premise: those meters stand in no building (FIX-7's report to the PO), not a missing read |
| 64 | `64-rules-one-rule-audit.png` | `64-rules-one-rule-audit.png` | **Matches** |
| 65 | `65-performance-performance.png` | `65-performance-performance.png` | **Matches** — the headline adds up (*27 of 27 kept*, 72 h promise). ⚠ **At risk is moving by PO ruling** (decision log *"FOUR PO ANSWERS ON WORK"*, 2026-10-05): it becomes its own Work tab beside Orders, while Schedule and Raise across buildings stay inside Performance (lane BOARDS). Photographed as it is on this build; not a defect |

**Count (65):** **Matches 57** · **Differs 6** — 01, 02, 03, 04, 06 still differ (`DEF-WRK-9675`–`9678`, `9680`, `9681`, all filed and open) and 22 differed and is **fixed in 2.518.1** (`DEF-WRK-9679`, re-shot as `22b-approvals-accept-closed-by.png`) · **Not built, by ruling 2** (58, 60). Spacing, type and component differences noted under rule 44, not filed: 16, 30.
