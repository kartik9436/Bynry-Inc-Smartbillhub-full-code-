# J66 — A failed outcome → a follow-up order and a hold (`WO-4907 · Pressure test and light-up 🚩 · Gas` on `CON-26-0117` comes back *Failed · pressure test failed at 2.1 bar*; one Accept raises `WO-4909`, blocked by it, and puts the build **On hold** with the reason in Waiting on — and gas stays off)

---
id: J66
tier: 2
rules: [BR-WRK-003, BR-WRK-007, BR-WRK-008, BR-WRK-013, BR-WRK-023, BR-WRK-024, BR-WRK-054, BR-MET-110, BR-SHL-025, BR-TEN-035]
stories: [US-WRK-006, US-WRK-034]
# ⚠ **NOT ACTIVATED** — no `J66.spec.ts`. At HEAD `failed` is one of five outcome tokens
# that ship, and *"the design says it raises a follow-up order and puts the connection on
# hold; neither happens"* (`WM-25`, *"Newly specified by this document"*). `J27`'s own
# caveat c names TC-NCT-5 — this consequence — as un-exercisable because no outcome
# endpoint is mounted. Written as the HANDOFF CONTRACT before the code.
#
# `stories:` = `04-flows.md`'s index for `J66` plus `US-WRK-006` (names all eight).
---

**Intent.** The counterpart of `J61`: what one person's Accept does when the field says
**no**. The chain runs **inside the acceptance transaction** — a follow-up order copied
from the same template (`BR-WRK-008`), `blocked_by` the failed one, stamped *Failed
outcome*; and `hold_connection` with the technician's stated reason in Waiting on — and
*"a refusal anywhere in step 3 rolls the whole acceptance back."* Three negatives carry
the weight: a *passed* outcome raises nothing and holds nothing; a follow-up that cannot
be raised leaves the failed order **in the queue**, unaccepted; and **a failed one-off
job with no connection gets a follow-up and no hold**, because there is no build to
hold. Underneath all of it, the rule a copying lane gets wrong: **gas is gated on the
light-up, not the meter set** (`BR-WRK-013`) — so accepting the passed meter set first
activates nothing, and the failed light-up leaves gas exactly where it was.

**Upstream leaves (`J27`).** **`CON-26-0117` · `500 Main St` · 25 units · E · W · G · S ·
Partly activated · 5 of 7**, owner Ridge Property LLC, orders `WO-4901`–`WO-4907`
(`J27` step 14; the numbering collision with `US-WRK-041`'s day list is `J61`'s finding).
**`WO-4906` · Meter set · Gas · `500 Main St · Unit 14` · Passed · completed 28 Mar 2026 ·
crew M. Chen · their reference `NGX-88410`** sits on `Work-009`, *6 days*, with
`field_data.set_reads = [{meter_no: G-4417-882, value: 0, unit: ccf, …}]` (*the unit is
this journey's fixture value — the drawn row carries none, `03-field-map.md` D-13*) and
`photo_ref img/2026-03-28/4417.jpg`. **`WO-4907` · Pressure test and light-up 🚩 · Gas ·
Per premise · `mode = external` (Apex Utility Svc) · `blocked_by = WO-4906` · `is_gate`
TRUE** (stamped at creation — for gas the gate is the light-up). Also on `Work-009`:
`WO-4903 · Tap and service line · CON-26-0122 · Ridgeway Mews · Water · Partially done ·
31 Mar · 3 days` and `WO-4917 · Container delivery · CON-26-0128 · 91 Fen Close · Trash ·
Passed · 02 Apr · 1 day`. The connection's `waiting_on` reads *inspection*. Templates:
the Gas *New connection* starters (4 tasks · 2 parts · 2 readings; the light-up row
`is_gate`). For the one-off negative: **`WO-4823` · Leak investigation · `77 Cedar Ct` ·
`A-10891` · High · rule-raised (*High-usage alert*) · `connection_id` NULL**, assigned to
D. Ortiz. Actors: **an external crew** (Apex Utility Svc, `mode = external`) · **M.
Torres**. Isolation tenant **Lone Star Ridge WSC**.

**The journey's clock.** **Fri 3 Apr 2026** — `Work-009`'s *6 days · 3 days · 1 day*
against 28 Mar · 31 Mar · 02 Apr. Follow-up number **`WO-4909`** (per `04-flows.md`); the
one-off follow-up **`WO-4922`** (*this journey's allocation from the free range*).

**Where two documents disagreed, and which one this journey follows.**
* **`WO-4907` is two orders in the blueprint** — the gas light-up on `CON-26-0117` (§9,
  §12, `US-WRK-034`) and the move-out visit on `A-10688` (`WS-29`). `03-field-map.md` D-8
  gives the visit `WO-4910` (`J64`); here `WO-4907` is the light-up.
* **The set read's unit.** The built fixture's shape is `[{meter_no, value, read_at,
  channel}]` — **no unit** (D-13). Hard rule 3 and `US-WRK-046` say the seam call carries
  `unit` and metering's door refuses a bare value; the fixture row here carries `ccf`
  (*ours*). If metering's door does not take a unit today, that is **metering's story,
  filed not worked around** (`US-WRK-046` §1).

| # | Actor · action · screen | Expected outcome (contract — what this step leaves) | Downstream assertions (record · connection · queue · audit · books) | Rule |
|---|---|---|---|---|
| 1 | **3 Apr 09:10 · M. Torres** opens **Work › Awaiting approval** (`Work-009`) | Three rows, oldest first: `WO-4906 · Meter set · CON-26-0117 · 500 Main St · Unit 14 · Gas · Passed · 28 Mar 2026 · 6 days` · `WO-4903 … Partially done · 3 days` · `WO-4917 … Passed · 1 day`; `CountFooter` **3 orders · oldest waiting 6 days**; the row action 👁 → `Work-003` | The queue is one query — `accepted_by IS NULL AND state = completed` — across every connection. `WO-4907` is **not** here: it has not been worked; its `dispatch_state` is Queued and it is **blocked** by `WO-4906` (`Work-002` draws *Waits for WO-4906*) | **BR-WRK-007** · `US-WRK-003` TC-1 |
| 2 | M. Torres accepts **`WO-4906`** (the gas **meter set**, Passed) | ONE transaction: `accepted_by` M. Torres · `accepted_at` 3 Apr 09:12; `metering_seam.post_set_reads()` → `commit_event_reads()` writes ONE `meter_reads` row **`G-4417-882 · 0 · ccf · read_at 28 Mar · field`**; `refresh_connection_state()` re-derives — **and the Gas service on Unit 14 does NOT activate**: `is_gate` is FALSE on a gas meter set; **gas gates on the light-up** (`WO-4907`). `WO-4907`'s `blocked_by` is now satisfied → it becomes workable (Queued, assigned to Apex Utility Svc) | ⛔ **THE ROW A COPYING LANE GETS WRONG**: a test asserts the gas *Meter set* row's `is_gate` is false and that this acceptance leaves `connection_services` for Gas unchanged — *"A lane that copies electric's shape onto gas will bill a customer who has no gas."* ✅ No letter is attempted — not the gate's acceptance (`US-WRK-035` TC-3). ✅ `Work-009` now reads **2 orders**; `Work-002` PROGRESS **6 of 7**; state still *Partly activated*. Accepting `WO-4906` twice → refused idempotently | **BR-WRK-013** · **BR-WRK-003** · BR-MET-110 · TC-NCT-3 · `US-WRK-019` TC-2 · `US-WRK-003` TC-2/TC-4 |
| 3 | **The crew's result arrives.** Apex Utility Svc's result for **`WO-4907`** is entered — `POST /work-orders/{WO-4907}/field-result`: **`outcome = failed` · reason *pressure test failed at 2.1 bar*** · `external_ref` `APX-2026-0311` · the crew's test sheet as an attachment · `completed_at` 3 Apr 11:30 | `submit_field_result` — and nothing more: `state = completed` · **`outcome = failed`** · `accepted_by` NULL · `field_data.reason` = the sentence · `dispatch_state` Complete. `Work-009` gains the row `WO-4907 · Pressure test and light-up · CON-26-0117 · 500 Main St · Gas · **Failed** (red pill) · 03 Apr 2026 · 0 days` | ✅ **Nothing has happened to the build yet** — no follow-up, no hold: a failed result is data the office has not accepted. ⛔ A field result with `outcome = failed` and **no reason** is refused — the reason is what Waiting on will carry. `mode = external` is per order (`J27` step 14) and stays | **BR-WRK-041** · **BR-WRK-007** · BR-MET-110 |
| 4 | **3 Apr 14:30 · M. Torres** opens `WO-4907` on `Work-003`, reads *Nobody has accepted this yet.* and the outcome *Failed · pressure test failed at 2.1 bar*, presses **Accept** | **ONE transaction, the chain:** (1) `accepted_by` M. Torres · `accepted_at` 14:30; (2) **`create_work_order`** raises **`WO-4909`** on `CON-26-0117` — *Pressure test and light-up* copied from the **same template and version** (its own 4 tasks · 2 parts · 2 readings · safety · help — `BR-WRK-008`), **`blocked_by = WO-4907` · `follows_order_id = WO-4907` · `source = failed_outcome`** (*Failed outcome · WO-4907*) · `is_gate` TRUE (the follow-up carries the gate) · `mode = external` · Queued · unassigned · `due_at` = raise + the priority's SLA; (3) **`hold_connection(reason = "pressure test failed at 2.1 bar")`** — **metering's own writer, through the seam** — `connections.held_at` stamped, **`waiting_on` = the reason**; `refresh_connection_state()` → **On hold**; (4) audit: **three rows — accept, raise, hold — one actor, one moment**; the report `WO-4907-v1.pdf` generated (an external crew's job carries no labour line of ours — the contractor rate `95.0000` applies only where hours are booked; none are; COST section empty of labour, no tax line) | ✅ `Work-002`: **`WO-4909` is an eighth row, *Waits for WO-4907*; PROGRESS `6 of 8`** (the flows text's *5 of 8* counts before step 2's acceptance — both are the same arithmetic); the Gas block reads the hold. ✅ `Work-001`: `CON-26-0117 · 500 Main St · 25 · E W G S · 6 of 8 · 02 Apr · **pressure test failed at 2.1 bar** · **On hold**`. ✅ **Gas on Unit 14 is still NOT activated** — a failed gate activates nothing. ✅ No letter attempted — the gate did not pass. ⛔ Accepting `WO-4907` twice → refused; no second follow-up, no second hold. The visible references are `WO-4909`, `WO-4907` — never a uuid | **BR-WRK-054** · **BR-WRK-024** · **BR-WRK-008** · **BR-WRK-023** · **BR-WRK-013** · BR-MET-110 · BR-TEN-035 · `US-WRK-034` TC-1/TC-6 |
| 5 | **Hold outranks progress.** Read `CON-26-0117`'s derived state | **On hold**, although 6 of 8 orders are complete and four services are part-way — blueprint §9.1's seven tests, **first match wins**, and hold is tested before progress. `connections.state` is a CACHE written only by `refresh_connection_state()`; it is **never a WHERE clause on a derived value** | Later, **`release_connection`** (from `Work-002`, `US-WRK-002` #6) re-derives to **Partly activated** with `waiting_on` cleared — and `WO-4909` is still blocked until `WO-4907`… ⚠ which is terminal (`completed · failed`). **The follow-up's `blocked_by` names WHAT FAILED, not what must pass**: the dispatcher unblocks `WO-4909` by releasing the hold and scheduling it; the chain is a record, not a lock on the follow-up. Asserted so a lane does not build a deadlock | **BR-WRK-054** · blueprint §9.1 · `US-WRK-002` TC-2 |
| 6 | **Negative — a *passed* outcome.** M. Torres accepts **`WO-4917`** (Container delivery · Trash · Passed) | `accepted_by` stamped; the Trash service on `CON-26-0128` activates (Trash's gate is Container delivery — `US-WRK-019` §4); **no follow-up raised, no hold**; `Work-009` reads **1 order** (`WO-4903`) | The chain fires on `failed` only. `partially_done` (`WO-4903`) also fires no chain — it is not a failure; the office decides what to do with it | **BR-WRK-054** · `US-WRK-034` TC-2 |
| 7 | **Negative — the follow-up cannot be raised.** A fixture variant: the gas light-up template was **deactivated** before M. Torres presses Accept on a failed light-up | `create_work_order` REFUSES (a raise from a deactivated template fails) → **the WHOLE acceptance rolls back**: `accepted_by` still NULL, **no follow-up row, no hold, `waiting_on` unchanged**, the order **stays on `Work-009`**; the refusal is shown to M. Torres **in words**, naming the template | *"A refusal anywhere in step 3 rolls the whole acceptance back — the order stays in the queue."* One transaction or none. The same rollback applies when `hold_connection` refuses (a cancelled connection cannot be held) | **BR-WRK-054** · `US-WRK-034` TC-3 |
| 8 | **Negative — a failed one-off with no connection.** D. Ortiz closes **`WO-4823`** (Leak investigation · `77 Cedar Ct` · `connection_id` NULL) as **Failed · could not access the meter box — locked**; M. Torres accepts | **A follow-up IS raised** — **`WO-4922`** · Leak investigation copied from the same template · `blocked_by = WO-4823` · `follows_order_id = WO-4823` · `source = failed_outcome` · `premises_id`/`account_id` carried from the failed order · Queued; **NO hold** — there is no build to hold; **the response says so** (*no connection to hold*) | The follow-up's anchors satisfy `ck_work_orders_has_anchor` without a connection (`BR-WRK-006`). `Work-007` shows `WO-4922 · Leak investigation · 77 Cedar Ct · A-10891 · … · Raised by: Failed outcome · WO-4823`. Performance's FIRST-TIME FIX counts `WO-4823` as a return visit (`follows_order_id` points at it) | **BR-WRK-054** · **BR-WRK-024** · BR-WRK-006 · `US-WRK-034` TC-4 · `US-WRK-054` TC-5 |
| 9 | **ISOLATION — Lone Star Ridge WSC** (`app.tenant_id` = Lone Star's) | `POST /lone-star-ridge/work-orders/{WO-4907}/accept` → **`404` before any chain runs** — no follow-up, no hold, no audit on Brazos Bend; Lone Star's `Work-002` never shows `CON-26-0117`; its `Work-009` shows its own queue | A Lone Star failed order chains on Lone Star only; `hold_connection` under Lone Star's `app.tenant_id` cannot see a Brazos Bend connection | hard rule 1 · `US-WRK-034` TC-5 |
| 10 | **INVARIANCE** | — | **Gas on Unit 14 never activated** in this journey — not at the meter set's acceptance, not at the failed light-up's. The failed order is never re-opened: `state = completed · outcome = failed` is terminal and immutable; the follow-up is a NEW row with its own copies and no link to the template's tables. **Work asked metering to write the connection exactly once — `hold_connection` — and it was metering's function that wrote.** No journal line, no money (`BR-WRK-004`). Three audit rows for one press. `WO-4909` and `WO-4922` are never renumbered | **BR-WRK-002** · **BR-WRK-008** · **BR-WRK-013** · BR-WRK-004 · hard rules 4 (shape), 7 · BR-TEN-035 |

**This journey leaves (for downstream).** **`WO-4909`** on `CON-26-0117`, `blocked_by =
WO-4907`, `follows_order_id = WO-4907`, `source = failed_outcome`, `is_gate` TRUE, Queued
· `CON-26-0117` **On hold** with *pressure test failed at 2.1 bar* in Waiting on ·
`Work-002` reading **6 of 8** · `WO-4906` accepted with its `0 ccf` read posted and **gas
still not activated** · `WO-4917` accepted, Trash on `CON-26-0128` activated, no chain ·
`WO-4922` as the one-off follow-up with no hold · Lone Star Ridge untouched.
**Downstream:** `J61`'s acceptance path on a PASSED light-up is what eventually
activates gas; `J62`'s performance tab counts `WO-4823` as a return visit.

## Boundaries — what this journey stops at, and why

| # | Not asserted | Because |
|---|---|---|
| a | The customer letter, on any acceptance here | No gate passed; `OQ-376` is `J61` step 11's boundary |
| b | Who may accept | **`OQ-WRK-1492`** — `J61` step 9 |
| c | Whether the follow-up's `blocked_by` should point at what FAILED or at what must PASS | The card says *blocked_by the failed one*; step 5 asserts that reading and its consequence (release + schedule unblocks). If §16 or the PO says otherwise, this row is stamped — reported to the parent as a design question the card leaves implicit |
| d | The external crew's labour cost | Contractors carry one rate and *"an agency invoices its own overtime"* (`BR-WRK-020`); no hours are booked by our phone for an external order, so the report's COST has no labour line. What an external invoice does is `OQ-WRK-1491`'s neighbour and is not asked here |
| e | The set read's unit `ccf` | This journey's fixture value (D-13); the rule is that a unit travels, not which one — the gas starter's reading spec carries the real value once phase 1 makes the starters bundles |
