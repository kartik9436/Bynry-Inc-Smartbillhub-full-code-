# CR-168-BRC10 round 2 · lane ORDERS-LIST — after-walk side by side (build 2.493.0)

Walked on PostgreSQL 16 (`sbh_wlist`: `migrate` + `seed_demo` + `load_sample_data --tenant brazosbend`, then
`10-scripts/cr168_orders_list_walk_prep.py` closed WO-0037, WO-0038 and WO-0021 as their technician so the
Approvals queue has rows). API `runserver 127.0.0.1:8361`, SPA `vite build --mode wolocal` served by `server.mjs`
on `5461`, Chromium at 1440 wide, signed in as Dana (System Admin). Script: `10-scripts/cr168_orders_list_after_walk.mjs`.
Every photograph below was opened and checked not blank.

| Drawing | After | Matches the drawing | Differs, and why |
|---|---|---|---|
| `images/01` Orders | `01-orders-work-orders.png` | *+ New work order* top right, accent; tab *Approvals*; search, *All*, *+ Filter*, ▦; the ten columns; eye and pencil per row | The five tiles wrap so *Overdue* sits on a second row at 1440 (not this lane's — the KPI strip's grid; recorded in §4 row 01). Priority reads *—* on every row: no demo order carries one (`DEF-WRK-9571`, SRV-1's P0.1) |
| `images/02` Assign in bulk | `02-orders-assign-in-bulk.png` | Title *Assign 2 orders*; Who is going, Date (date picker), Window (list); *Each person is told on their phone.*; Cancel / Assign | The advice line under *Who is going* (*all five have Meter I; M. Chen is off 25 Sep*) is lane ASSIGN's (P4.12, round 3). The bulk bar reads *2 orders selected* with three acts, as decided in round 1 (judgments 1 and 2) |
| — (DEF-WRK-9570) | `02b-orders-reschedule-in-bulk.png` | Reschedule takes *Date \** from a date picker and a *Window* list; the three free-text boxes are gone | — |
| `images/12` Assign a job | `12-orders-assign-a-job.png` | *Cancel · Cancel work order · Assign ✓* top right; Change effects under the title, naming the new holder; Status without *Complete*; Date with *Today*; *In the utility's time.*; *From the premises.* | *Assigned to* is a list of *Name · Kind* — the drawing's typeable picker with advice and *Best fit* is lane ASSIGN's (P4.12). The demo order has no priority or area, so those read *No priority* / *No area* |
| — (DEF-WRK-9563) | `12b-orders-crew-assigned.png` | WO-0018 now reads *Field crew A · Scheduled* on Orders after *Assign ✓* with a crew picked (it used to 404 silently) | The global search's suggestion box is open over the head (the walk typed into the top bar) |
| `images/13` Reassign a job | `13-orders-reassign-a-job.png` | Opens on its holder (*Field crew A (2) · Crew*); *Reassign ✓*; effects name both — *Field crew A — told it is taken off them.*, *D. Ortiz — told now, on the phone.* — and *Audit — both names, who and when.* | *Why it moves* is not built: the server has nowhere to keep a reason until round 3's reassign act (SRV-2). The crew's list name carries its head-count, the server's own wording |
| `images/21` Approvals | `21-approvals-approvals.png` | Title *Approvals*; Select column; Order · Connection · Premise · Service · Outcome · Completed · Waiting; eye and ✓ per row; pager; footer | ▦ kept (round 1 judgment 4). Every eye is live, including a job with no build (image 21's faded eye is an illustration — rule 37) |
| `images/22` Accept | `22-approvals-approvals-accept.png` | *Accept selected… (1)* top right once ticked; *Accept WO-0037?*; *The service goes live. / The customer is told.*; job name and *address · service*; *Keep waiting* / *Accept ✓* | The drawing's *closed by D. Ortiz* is not served on the queue row; not shown rather than guessed |
| `images/23` Accepted | `23-approvals-approvals-accepted.png` | The queue one row shorter (2 of 2); toast *WO-0037 accepted · service live* | — |

**Still not findable:** after this walk WO-0037 is accepted and is in neither Orders nor Approvals — `DEF-WRK-9569`,
the server half (SRV-1's P1.6 + P1.31). Its held test is `06-backend/tests/test_def_wrk_9569_accepted_order_findable.py`.

**Writes the walk made in `sbh_wlist`:** WO-0037, WO-0038, WO-0021 closed by their technician (prep); WO-0018 assigned to
Field crew A (step 12; step 13 previews a reassign and does not save); WO-0037 accepted (step 23).
