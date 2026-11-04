# dispatcher-reassigns — a dispatcher moves a held job from one person to another, says why, is refused when the save cannot stand, and both people, the customer and the record hear exactly what changed

---
id: dispatcher-reassigns
tier: 2
change: CR-168-BRC10 P1.9 (written in round 9 by lane FIN-T, `2.520.3`) — CREATED, not extended: §7.1 found no such file
rules: [BR-WRK-023, BR-WRK-029, BR-WRK-031, BR-WRK-018, BR-NOT-017]
tasks: [P1.1, P1.3, P1.8, P1.26, P1.27, P4.1, P4.4, P4.5, P4.6, P4.12, P4.13]
modules: [work, notifications, identity]
spec: 07-frontend/src/features/work/cr168OrdersList.dom.test.tsx (P1.1 — the refused save and cancel, the refused bulk act) ·
      07-frontend/src/features/work/cr168Assign.dom.test.tsx (advice, Why it moves, bulk assign) ·
      06-backend/tests/test_cr168_srv2_assign.py (reassign = two rows, one reason; reason_required)
walk: 10-scripts/cr168_orders_list_after_walk.mjs · 10-scripts/cr168_assign_walk.mjs (browser, 1440)
---

**Intent.** Images 12 (*Assign a job*) and 13 (*Reassign a job*), and the beta's loudest
complaint: a save that failed said nothing and the dispatcher believed the job had moved.
This journey is one job changing hands — and the refusal path that P1.1 built, so a save
that cannot stand is SEEN, on the page, in the server's own sentence.

**Upstream leaves (preconditions).** A job on Work › Orders held by a technician
(*D. Ortiz*), raised with a job type so it carries a priority and a promise (`BR-WRK-018`;
`raise-a-job` leaves one); a second technician or a crew to give it to; the dispatcher
signed in with a role that may assign (System Admin or Clerk).

| # | Who | Does | Sees / is told | Record |
|---|---|---|---|---|
| 1 | Dispatcher | Opens the job's edit page (`/work/orders/{id}/edit`) | The page opens ON the holder — *D. Ortiz · Technician*; the commit reads *Reassign ✓* (a job nobody holds reads *Assign ✓*) | — |
| 2 | Dispatcher | Opens *Assigned to* | A searched, paged list — best fit first with its pill, each name with its kind and advice (*Water I ✓*, *Missing skill: Water I*, *Off that day*, *N jobs that day*). **No name is disabled** — *Advice only — any name can be chosen.* (ruling 2) | `GET /work-orders/{id}/candidates?q=&page=&per=` |
| 3 | Dispatcher | Picks *R. Patel* | *Was D. Ortiz. R. Patel · …* under the field; *Why it moves* appears — five reasons (*Closer to the job · Customer asked · Off sick · Needs another skill · Workload*) and a note | — |
| 4 | Dispatcher | Presses *Reassign ✓* without a reason | **Refused on the page**: *Choose why it moves.* under the field; nothing is sent | — |
| 5 | Dispatcher | Chooses *Off sick*, presses *Reassign ✓*, and the SERVER refuses (the job was cancelled a moment ago by someone else, or the window ends before it starts) | **The server's own sentence in a `role="alert"` line at the head of the page, and the page STAYS** with every value kept — e.g. *The window ends before it starts.* (`work.dispatch.window_backwards`). It never navigates away as if it saved (P1.1, proved by P1.8) | nothing written — the refusal is the whole answer |
| 6 | Dispatcher | Corrects the window, presses *Reassign ✓* | The order page; *R. Patel · Not accepted yet* under the technician (P4.1) | `PATCH /work-orders/{id}/edit` with `reason` → TWO history rows sharing the reason and an `act_group` (P4.4) |
| 7 | — | The *Change effects* box listed what this save does, and only that (P1.26) | *R. Patel — told now, on the phone.* · *D. Ortiz — told it is taken off them.* · *Technician phone — job updates immediately.* · *Customer — not told; visit unchanged.* (or *told the visit moved* when the day or window moved) · *Audit — both names, the reason, who and when.* | in-app rows to both technicians; a customer message only when the visit moved (`customer-told-about-a-visit`) |
| 8 | Dispatcher | Chose someone the advice said lacks the skill | Allowed; the history marks the line | `work.order.assigned_against_advice` audit (P4.6 🔒) |
| 9 | Dispatcher | Ticks five jobs on Orders, *Assign selected…* | *Assign 5 orders* — who, the date, the window; the UNION of candidates with one advice line (*Advice: 1 lacks a needed skill. Off that day: M. Chen.*); a refused bulk act shows the server's sentence IN the dialog (P1.1) | one assignment per order |

**Rules the journey holds.**
* **A refused save is visible and keeps the page** (P1.1, P1.8) — the server's sentence, by
  its `message_key`, in every catalogue; never a silent return to the list.
* **A reassign carries a reason, or it is refused** — `work.dispatch.reason_required` on the
  server, *Choose why it moves.* on the screen.
* **Advice never blocks** (ruling 2, `BR-WRK-029` as amended): a lapsed certificate or a
  missing skill is a line beside the name, never a disabled row.
* **The two axes move independently** (`BR-WRK-023`): a reassign moves the dispatch state
  (*scheduled*) and leaves the work state (*planned*) alone.
* **Who is told** is the effects box's list and nothing else; the customer only when the
  visit itself moved.
* **No id is a visible value** (B14 rule 31) — names and order numbers only.

**Leaves (for downstream).** The job held by its new person with `technician_acceptance`
*pending*; two `work_order_assignments` rows sharing one reason; the old holder's and new
holder's in-app rows; nothing changed on the customer unless the visit moved.
