# Plan details — built screen beside images 24–37 (CR-167-BRC10 round 3 task 7)

Build 2.485.0 (plus the 2.485.1 fixes in the same lane), PostgreSQL 16 database `sbh_plandetail`
(`migrate` + `seed_demo` + `load_sample_data --tenant brazosbend`), API `runserver 127.0.0.1:8201`, SPA
`vite build --mode wolocal` served by `07-frontend/server.mjs` on 5301, Chromium at 1440, signed in as
Dana (System Admin). Script: `10-scripts/cr167_plan_detail_walk.mjs`; its printed checks are
`walk-output.txt` (all PASS). Each photograph was opened and is not blank.

Plan photographed: the sample tenant's **Sample — Residential** (`SCW-RES`): electric and water, 75
units, two taxes (8.25%), three discounts, no deposit code, no minimum bill. The walk publishes a v2
from 01/01/2027 (minimum bill $12.00) and renames the description on the same version, so the banner,
*Priced as of* and Audit have real later versions. Every figure in the images is an illustration
(B14 rule 37); the photographs carry this tenant's own.

| # | Image | Photograph | Same | Different, and why |
|---|---|---|---|---|
| 24 | Overview | `24-detail-overview.png` | ← Plans; name + code; *Published · V1 · Residential · window*; Edit + More ▾; six tabs with counts; banner; four tiles that open their tab; Details (nine facts); versions table; *See every change in Audit* | Banner names the PLAN's v2 (the earliest later version on this data) — the drawing's is a water schedule; a schedule banner is in 28. Tiles, labels, facts and table are the kit's (`KPIStrip`, `FactBlock`, `PlainTable`, rule 44). Status pill words are the product's (*Published*, *Active*, *Scheduled*). *Intended for* and *Notes* read — (none stored). |
| 25 | More ▾ | `25-detail-more.png` | Duplicate, Retire | Duplicate is disabled with its reason (`DEF-RAT-9352`: nothing copies a plan yet). A DRAFT shows *Delete draft* instead of Retire (§5.5 L13). |
| 26 | Services folded | `26-detail-services-folded.png` | Priced as of + Today; Expand all; each service: strip (Rate schedule · Base charges · Outside city) with version pill and *from*, GL and Edit, one line *Base charges … · Usage charges …*, *Show sizes and blocks*; totals strip | The date field is the kit's (label above the box, calendar button, Today beside it — rule 44). Two services where the drawing has four (this tenant sells electric and water). |
| 27 | Expand all | `27-detail-services-open.png` | Collapse all; *Hide sizes and blocks*; base table (Base charge · Minimum) beside usage table (Rate) | This plan's bases are flat (*Every size*), so no size rows. |
| 28 | Priced as of 01/15/2027 | `28-detail-services-asof-2027.png` | Date in the box and the address (`as_of=2027-01-15`); the page re-read on that date | The banner now names the WATER SCHEDULE's v3 from 03/01/2027 with its own later rates (*Usage charges $4.50 · $7.31 · $9.00 per kgal*) — read from the page as of that date, never guessed. The drawing hides the banner at 2027; here a later version still exists after 01/15/2027, so it shows. |
| 29 | Charges | `29-detail-charges.png` | Charge codes (Code · Priced by · Class or size · Amount · GL · When) with Edit; Taxes with *8.25% combined* and Edit; names are links | Each tax shows its authority under the name (CR-167 §5.5 — the details page loses no fact). |
| 30 | Billing | `30-detail-billing.png` | Deposits, Discounts (Offered from/until, GL), Billing terms (Monthly base charges · Minimum bill · Budget billing), each with Edit | This plan names no deposit code: the kit's empty line *No deposits.* Discounts carry an *Enrolled* column (§5.5). |
| 31 | Units | `31-detail-units.png` | Units; *Search unit or premises*; All · Occupied · Vacant; ⤓; Unit · Premises · Services · Account · Occupancy · On this plan since; unit, premises and account are links; no selection, no Move | The kit's table adds the column chooser beside ⤓ and its pager (*1–50 of 75*, rows per page). |
| 32 | Units searched | `32-detail-units-search.png` | Searched *Unit 1*, answered by the server (`u.q=`) | — |
| 33 | Vacant only | `33-detail-units-vacant.png` | Vacant chip on; 8 of 75 rows; `u.f.occupancy=vacant` | One unit reads *Occupied* among the vacant: the server's occupancy filter and the row's account read disagree for `Apt 102` — filed as `DEF-RAT-9361` (two definitions of occupied on the server); the row shows what the server served. |
| 34 | Audit | `34-detail-audit.png` | Audit; ⤓; All · Plan changes · Changes underneath; From / To; ▸ · When · Who · What · Change · Reason; words, no ids, no JSON | From/To start empty (the drawing's dates are illustrations). Three server wordings still read like data — `DEF-RAT-9360`. |
| 35 | Changes underneath | `35-detail-audit-underneath.png` | Only discounts, schedules and taxes; `a.f.kind=underneath` | — |
| 36 | A row opened | `36-detail-audit-open.png` | Before · After · Version under the row | The version names the plan's head number (`DEF-RAT-9360`). |
| 37 | Section Edit | `37-detail-section-edit.png` | Charge codes › Edit lands on `…/edit?change=change&step=2` — the address agreed with lane PLAN-EDIT | The edit route still mounts the old 8-step `PlanWizard`, which ignores the parameters; lane PLAN-EDIT's *What to change* form (task 8) is what reads them. |

## Found by this walk, filed first and fixed in the lane
- `DEF-RAT-9359` — Units and Audit CSV answered 404 (`?format=csv` refused by DRF before the view). Fixed: a CSV format renderer on both views; walk now reads `200 text/csv`.
- `DEF-RAT-9353` follow-up — the first fix served `account_id` as `null` on every row (the seam popped it); found here, test red first, fixed: accounts are links in 31–33.
- A schedule with no code was matched to the first service with no code in the banner; fixed (match by name), test red first.
