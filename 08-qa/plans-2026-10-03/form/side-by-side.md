# New plan form — built states beside images 04–23 (CR-167-BRC10 round 2, lane PLAN-FORM)

Build **2.482.0**, Chromium at 1440, signed in as Dana (Brazos Bend) on a private PostgreSQL 16
database (`sbh_planform`: `migrate` + `seed_demo` + `load_sample_data --tenant brazosbend`).
Walk: `10-scripts/cr167_plan_form_walk.mjs`; printed output `walk-output-contract.txt`,
`walk-output-server.txt`. Every photograph below was opened and checked not blank.

**Two sets, and the suffix says which.**
* `…-server.png` — everything from the real server. On this build the server lane has not yet
  served `GET /plans/form-options` (it answers **404**, `walk-output-server.txt`), so every
  dropdown is empty; the form keeps working and refuses by name (`10b-…`).
* `…-contract.png` — the real server for sign-in, the frame, permissions and the currency; ONLY
  `GET /plans/form-options` and `POST /plans` answered by the walk with the agreed §7.3/§7.6 shape,
  filled with the images' own (illustrative) figures. The two bodies the form posted are printed in
  `walk-output-contract.txt` (`POSTED (publish)` / `POSTED (draft)`). **Re-run without `CONTRACT=1`
  once task 3 lands** — that is the photograph task 10 compares.

| Image | Built | Same | Different (and why) |
|---|---|---|---|
| 04 | `04-…-contract`, `04-…-server` | Back link *← Plans*, title, *Save draft & exit*, five steps, Plan + Intended for, *This plan* $0.00 and eight facts | The page sits inside the app frame (sidebar, top bar) — the drawing omits the frame. An empty notes table shows *None* with no header row (kit `EditableTable`). *Charge codes 1* on the panel: the utility's late fee is a row from the start (DEF-RAT-9328). |
| 05 | `05-…` | *Fix 2 things first.* beside Continue; *Enter the plan name.* / *Enter a code.* under the boxes | Boxes are not pink-filled: the kit marks the message, not the box (B14 rule 44). |
| 06 | `06-…-contract` | One tick dropdown, *Every customer class* first, then the classes | — |
| 07 | `07-…-contract` | Classes *Residential*, description, the three ticks, a note *Customer class · is · Residential* with a red × | — |
| 08 | `08-…-contract` | Service · Rate schedule · Base charges · Minimum · Surcharge; GL under the service; V-pill and from-date under the schedule and the base code; *Monthly base charges $19.00*; *Switch more services on ↗*; Outside city limits | *3 of 4 switched on* counts chosen rows only. |
| 09–10 | `09-…`, `10-…` | Empty row with *Pick the service first*; *Choose a service in each row.*; *Fix 1 thing first.* | The drawing's 10 reads *4 of 4* with three chosen; we count chosen rows (B14 rule 37: figures are illustrations). |
| 11–12 | `11-…`, `12-…` | Fire picked; *+ Add service* greyed with *All added.*; Surcharge ticked on Water and Sewer | — |
| 13–16 | `13-…` to `16-…` | Charge codes (LATE pre-filled, RECON), Amount *by customer class* / *$75.00*, GL, Type, When; *Not listed? Define it ↗*; Taxes with *8.25% combined* → *11.25%*; *All added.*; the empty row refused; removed with × | Refusal reads *Choose a code, or remove it.* (rule 33's six words; the drawing has nine). In 15 *+ Add charge code* is greyed because the walk's list holds three codes; the drawing's list holds more. |
| 17–19 | `17-…` to `19-…` | Deposits (Customer class, *Residential $150.00 · Commercial $300.00*, GL), Discounts offered with Enrolled and offered from/until, Budget billing, `$` Minimum bill with its help; the empty deposit row refused | Discount rows carry a red × (ruling 6); the drawing's rows are cut at the right. |
| 20–21 | `20-…`, `21-…` | Plan facts; four service sections (strip + base/minimum by size beside usage); Charge codes by class; Taxes with *11.25% combined*; Deposits; Discounts (with *Enrolled*); Billing terms *$19.00 · $10.00 · Not offered*; Dates; footer **Back** left, **Save as draft · Publish plan** right | Section *Edit* links on every section (drawn too). Discounts carry *Enrolled* (§5.5). |
| 22 | `22-…-contract` | ✓, *Residential City Plan published*, *Live from 11/01/2026. Assign units from the plan.*, *Open plan*, rail all ticked | *Save draft & exit* is hidden after saving (a second press would make a second plan). Second sentence shortened for rule 33. |
| 23 | `23-…-contract` | ✓, *Residential City Plan saved*, *Saved as a draft. Publish it from the plan.*, *Open plan* | As 22. |
| — | `10b-new-2-no-service-server` | Real server, no lists served: *0 of 0 switched on*, *+ Add service* greyed *All added.*, Continue refused *Add at least one service.* | The state a clerk meets until task 3 serves `form-options`. |

## Re-taken on `2.484.3` against the real server (lane PLAN-FORMFIX, 2026-10-03)

Every `…-server.png` 04–23 was re-taken on build **2.484.3** (`sbh_planformfix`, API `:8191`, SPA `:5291`,
Dana, 1440) and opened; `walk-output-server.txt` is that run. The server now serves `form-options`, so the
dropdowns are full: Brazos Bend's water and electric, two taxes, `DEPOSIT` and `DEPO-C` (created in the lane
database for steps 17–19). **08 · 21 · 20:** a *Residential* water row reads **$8.00 · BASE-W**; with
electric, *Monthly base charges*, *This plan* and Review's *Billing terms* read **$20.00** (it read **$0.00**
and *Several base codes* before `DEF-RAT-9351`). **08b** (new): the same row after unticking *Residential* —
the row is kept, the base names *BASE-W, BASE-W-COM*, and the totals read **—**, never $0.00.
**13:** Type reads *Penalty* / *One-time* (`DEF-RAT-9356`). **20:** *This plan* follows the page
(`DEF-RAT-9355`). **08, 11, 12:** *Tick the services above.* (`DEF-RAT-9357`). `10b` was not re-taken: with
services served there is no empty state to photograph; the file is the 2.484.0 one.
