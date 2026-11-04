# J64 — A move-out's field visit, and the final read posts through the same door (`A-10688 · Miller, Sarah` closes and settles exactly as today; the visit `WO-4910` arrives in the dispatcher stamped *Move-out · A-10688*; the read is taken, accepted, and posts dated to the visit — and never re-opens the account)

---
id: J64
tier: 2
rules: [BR-WRK-003, BR-WRK-006, BR-WRK-007, BR-WRK-015, BR-WRK-024, BR-WRK-039, BR-WRK-040, BR-WRK-041, BR-WRK-050, BR-WRK-055, BR-MET-110, BR-SHL-025]
stories: [US-WRK-003, US-WRK-006, US-WRK-039, US-WRK-046]
# ⚠ **NOT ACTIVATED** — no `J64.spec.ts`. At HEAD `apps/customers/disconnects.py`
# refuses to book a visit under `VISIT_NOT_SCHEDULED` (*"nothing books the visit"*),
# `work_orders.connection_id` is NOT NULL so an order on an ACCOUNT cannot exist, and
# there is no `Work-029` step in the move-out wizard. Written as the HANDOFF CONTRACT
# before the code.
#
# `stories:` = `04-flows.md`'s index for `J64` plus `US-WRK-006` (names all eight).
---

**Intent.** The third door (`EP-WRK-07`): a clerk closing an account. **Two calls from
one wizard step, never a cross-module write** (`BR-WRK-055`) — Customers closes and
settles the account **exactly as today**, and the SCREEN then asks Work to raise the
visit. The two halves are independent in both directions and the journey proves both:
**the move-out does not wait for the visit** (if the raise fails, the close still
completes and says so), and **the visit does not close the account** (when the final
read arrives and is accepted, the account is not re-opened, re-closed or re-settled).
The read itself takes the SAME approval path as every other reading — `Work-009`, a
person's Accept, metering's set-read door — **dated to the visit's completion**.

**Upstream leaves.** Account **`A-10688` · Miller, Sarah · `221 Oak Ave · Unit 3` ·
Electric**, meter **`E1P-77412`** (fitted 15 Mar 2026 by `WO-4822`, opening read
**1,204 kWh**), move-out date **28 Mar 2026**, **deposit on file `$150.00`** (the
tenant's residential deposit policy, `J27` step 7). A published template **Final read —
electric** (*ours — no card names the template the move-out visit is raised from;
`Work-029` draws the label "Final read & de-energise", which is neither a type nor a
template in any list*): Electric · job type **Read verification** · 1 task (*Record the
final read · 5 min · photo Required*) · 1 reading (**Final read · kWh · 0–99,999 · photo
Required · required · posts as meter read: Yes**) · est. 15 min · skill Reads; it is the
Read verification type's `default_template_id`. Technicians: **M. Chen** (Electric I ·
Reads · shift 07:00–16:00). Actors: **Priya Menon** (Billing Clerk — runs the move-out
wizard) · **M. Torres** (dispatcher and acceptor). Isolation tenant **Lone Star Ridge
WSC**. Order number: **`WO-4910`** — `03-field-map.md` D-8 gives the visit `WO-4910`
because the blueprint reuses `WO-4907` for both this visit and the gas light-up on
`CON-26-0117` (`J66`).

**Fixture the journey adds.** Wizard run **Thu 26 Mar 2026 14:10**; visit assigned to
M. Chen for **Sat 28 Mar 09:00**; final read **`1,297` kWh** (*ours*; 93 kWh over 13 days
on the new meter), photograph `IMG-8871`; acceptance **Mon 30 Mar 08:40**.

| # | Actor · action · screen | Expected outcome (contract — what this step leaves) | Downstream assertions (record · account · queue · audit · books) | Rule |
|---|---|---|---|---|
| 1 | **26 Mar 14:10 · Priya Menon** runs the move-out wizard on `A-10688` to **step 4 of 6** (`Work-029`, *Does somebody have to attend?*) | Kicker *ACCOUNTS › A-10688 · MILLER, SARAH*; three `CheckRow`s: ☑ **Raise a work order for the final read** — *Electric · Final read & **deactivate** · due 28 Mar 2026* · ☐ *Raise a work order to lock the water curb stop — Water · Disconnect at curb* · ☐ *No visit needed — the customer will send a photo of the meter*; WHAT HAPPENS ON SAVE table (*1 Close the account, settle the deposit, cut the final bill · Customers · as today* / *2 The screen calls Work to raise the work order · Work · Queued · unassigned* / *3 The order carries its source · Work · Move-out · A-10688*); `ConsequenceBox` **The move-out does not wait for the visit, and the visit does not close the account.** **Nothing is written at step 4** — the frame reads *step 4 of 6 · nothing is written until step 6* | ⛔ The drawn copy *de-energise* is **not rendered** — the product word is *deactivate* (`CR-032`); `grep` of the rendered step for *energise* = 0. ⛔ **Continue with none of the three ticked is REFUSED** — `field_visit` is a required choice at step 4 (≤ 6 words), so a move-out nobody attended can never be mistaken for one nobody decided. One sentence per section; no id in copy (B14 rule 32) | **BR-WRK-055** · `CR-032` · `US-WRK-039` TC-4/TC-7 · B14 rule 32 |
| 2 | Priya completes **step 6** | **Two calls from one step, in order:** **(1) Customers** — the move-out commits: `A-10688` **closed**, the **`$150.00` deposit settled** against the final balance, the final bill cut — *as today*, Customers' and Billing's existing arithmetic, **untouched by this journey**; `disconnect_cases.field_visit = final_read` recorded (Customers owns that write — its own wizard's record). **(2) The screen** posts **`POST /work-orders`** (Work's one raise): **ONE `work_orders` row — `WO-4910`**: **`account_id = A-10688` · `connection_id` NULL** · `premises_id` 221 Oak Ave · `type` Read verification · `template_id` Final read — electric `v1` · **`source = move_out`** (*Move-out · A-10688*) · `due_at` **28 Mar 2026** · `dispatch_state = queued` · assignee NULL · its own copies (1 task · 1 reading with unit kWh · details); one `audit_log` row naming Priya Menon | ✅ The account's close wrote **its own** audit and ledger rows through Customers and the ledger posting service — **Work wrote none of them** (hard rule 5; `BR-WRK-002`). ⛔ **`grep apps/customers/** for `WorkOrder.objects`** = **0**; `VISIT_NOT_SCHEDULED` stays as the refusal for any path that is not the screen. ✅ The step's result panel reads *WO-4910 · Queued · unassigned*. ⛔ A raise naming no anchor is refused by `ck_work_orders_has_anchor` on PostgreSQL — an account IS an anchor (`US-WRK-001` TC-2) | **BR-WRK-055** · **BR-WRK-006** · **BR-WRK-024** · **BR-WRK-002** · hard rule 5 · `US-WRK-039` TC-1/TC-5 |
| 3 | **Negative — the raise fails.** Re-run on a fixture where Work's route is down at step 6 | **The move-out STILL COMPLETES** — `A-10688` closed and settled exactly as in step 2; `disconnect_cases.field_visit = final_read` recorded; **no `work_orders` row**; the step reports **the visit was not raised** and offers to raise it from the dispatcher (`Work-007` → *+ New work order* with the account pre-filled) | The close does not wait for the visit. The failure is stated on screen in one sentence and carried on the wizard's response; **nothing pretends a visit exists**. A later manual raise from the dispatcher stamps `source = dispatcher`, not `move_out` — the record says who raised it | **BR-WRK-055** · `US-WRK-039` TC-2 |
| 4 | **Negative — *No visit needed*.** Re-run with the third box ticked | `disconnect_cases.field_visit = **not_needed**` — **a recorded VALUE, not an unticked box**; the account closes and settles as today; **no `work_orders` row**; the result panel says so | The three values `final_read · curb_stop · not_needed` are the column's whole vocabulary; a case with `field_visit` NULL after step 6 cannot exist | **BR-WRK-055** · `US-WRK-039` TC-4 |
| 5 | **26 Mar 15:00 · M. Torres** on `Work-007` | `WO-4910 · Read verification · 221 Oak Ave · A-10688 · E · Normal · Unassigned · Mar 28 · Queued · **Move-out · A-10688**` — the Connection is a dash, the anchor is the account; M. Torres assigns **M. Chen** for **28 Mar 09:00** (`assign` + `schedule` rows; push job; Audit *Dispatched · pushed to phone · 15:00*) | ⛔ Assigning to Crew B (Water III · Excavation) is refused — the template's skill is Reads. Search `A-10688` finds `WO-4910` (and the fixture's `WO-4822`, the meter exchange on the same account) | **BR-WRK-024** · BR-WRK-025 · BR-WRK-029 |
| 6 | **Sat 28 Mar 09:00 · M. Chen** works the visit on the phone: arrives 09:02; ticks the task; reading **Final read = `1,297` kWh** on `E1P-77412`, photograph `IMG-8871` (09:19); **Close job · Passed** 09:24 | `submit_field_result`: `state = completed` · `outcome = passed` · **`completed_at` 28 Mar 09:24** · `accepted_by` NULL · `field_data.set_reads = [{meter_no: E1P-77412, value: 1297, unit: kWh, read_at: 2026-03-28T09:24-05:00, channel: total}]` (channel amended 2026-10-05, `DEF-WRK-4073`: it read `field`, a source and not a register — `BR-MET-059`) — assembled from the copy row with `posts_as_meter_read = true`; `in_range = true` (0 ≤ 1,297 ≤ 99,999, server-derived) | ⛔ Close without `IMG-8871` is refused naming *Final read* (a required photograph blocks; range never does). ⛔ A value with no unit is refused (hard rule 3). ✅ **The account is untouched by the close** — still closed, still settled, no second settlement. ✅ **Zero `meter_reads` rows** for `1,297` yet — the phone's Close activates and posts nothing | **BR-WRK-041** · **BR-WRK-040** · **BR-WRK-015** · **BR-WRK-039** · BR-MET-110 · hard rule 3 |
| 7 | **Mon 30 Mar 08:40 · M. Torres** opens **Work › Awaiting approval** (`Work-009`) | `WO-4910 · Read verification · **—** · 221 Oak Ave · Electric · Passed · 28 Mar 2026 · 2 days` — Connection a dash, Premise the anchor; `NoteBar` *nobody has accepted them* (no `accepted_by` in clerk copy) | The queue is `accepted_by IS NULL AND state = completed` **across every anchor** — an account-anchored order is in it like any other | **BR-WRK-007** · `US-WRK-003` TC-7 · B14 rule 32 |
| 8 | M. Torres presses **Accept** (`Work-003` / `Work-008`) | ONE transaction: `accepted_by` M. Torres · `accepted_at` 30 Mar 08:40; `metering_seam.post_set_reads()` → **`metering_services.commit_event_reads()`** writes ONE `meter_reads` row: **`E1P-77412` · `1,297` · `kWh` · `read_at` = 28 Mar 09:24 (the visit's completion, NOT the acceptance) · channel *field***; the report `WO-4910-v1.pdf` generated (15 min est. · 09:02–09:24 = 22 min → `0.37 h × 48.50 = 17.95`, no parts, **Total `17.95`, no tax line**); audit rows per act | ✅ **The meter's history** reads the read on **28 Mar**, after the 15 Mar opening read of `1,204` — the two serials' chain is intact. ✅ **The account is NOT re-opened, re-closed or re-settled** — `accounts` row unchanged, `disconnect_cases` unchanged, **no second deposit application, no second final bill from this act**; a final-bill true-up on a later read is **Billing's existing behaviour, untouched here**. ⛔ Metering-side: a read **below** the previous (`1,100 < 1,204`) → metering's door REFUSES → **the whole acceptance rolls back**, the order stays on `Work-009`, the refusal shown in words. ⛔ Accept twice → refused; no second read; no `v2`. ✅ No letter attempted — not a gate | **BR-WRK-003** · **BR-WRK-050** · BR-MET-110 · `US-WRK-046` TC-1/TC-4/TC-5 · `US-WRK-039` TC-3 · `US-WRK-003` TC-2/TC-4 |
| 9 | **The same door, from the other side.** Compare with `J61` step 10 | Both reads — the new-connect opening read (`J61`) and this final read — reached `meter_reads` through **`commit_event_reads`**, dated to their completions, carrying their units, written by metering, on a person's Accept | **Work never writes `meter_reads`**: `grep apps/work/** for MeterRead.objects.create` = 0; the boundary gate fails on a hit. One validation, two sources: metering's high/low check applies to a field read exactly as to a staff-entered one | **BR-WRK-003** · **BR-WRK-002** · `US-WRK-046` TC-3/TC-7 |
| 10 | **ISOLATION — Lone Star Ridge WSC** (`app.tenant_id` = Lone Star's) | Its move-out wizard raises on **Lone Star's tenant only**; `/lone-star-ridge/work/orders/WO-4910` → **`404`**; its `Work-009` does not show `WO-4910`; its `meter_reads` holds no `E1P-77412`; `POST /lone-star-ridge/work-orders/{WO-4910}/accept` → `404` before any chain | The Customers-side close of a Lone Star account raises through Lone Star's own `POST /work-orders` under its own `app.tenant_id` | hard rule 1 · `US-WRK-039` TC-6 · `US-WRK-046` TC-6 |
| 11 | **INVARIANCE** | — | The account closed **once**, at step 2 (or step 3/4's variants), by Customers; **nothing in Work's chain touched `accounts`, `disconnect_cases`, `invoices`, `payments` or the ledger** — the boundary gate passes. The read is dated to the visit, carries its unit, and exists exactly once. `field_visit` is one of three values on every completed move-out. The word is *deactivate* everywhere. Every act audited. `WO-4910` never renumbered | **BR-WRK-002** · **BR-WRK-055** · hard rules 1, 4 (shape), 5, 7 · `CR-032` · BR-TEN-035 |

**This journey leaves (for downstream).** `A-10688` **closed and settled** on 26 Mar,
its close having waited for nothing · `disconnect_cases.field_visit = final_read` ·
**`WO-4910`** accepted, `account_id = A-10688`, `connection_id` NULL, `source = move_out`
· ONE `meter_reads` row `E1P-77412 · 1,297 · kWh · 28 Mar 09:24 · field` on the meter's
history after the `1,204` opening read · `WO-4910-v1.pdf` at `$17.95`, no tax line · no
journal line by Work · Lone Star Ridge untouched. **Downstream:** `J08` (final-bill
settlement) reads a closed account whose final read arrived later — Billing's true-up
behaviour, not Work's.

## Boundaries — what this journey stops at, and why

| # | Not asserted | Because |
|---|---|---|
| a | The settlement arithmetic — the final bill's figure, the deposit's application | Customers' and Billing's **existing** behaviour (`J08`, `T4-06`); this journey asserts it happened ONCE and that Work's chain never touched it. The `$150.00` is the tenant's deposit policy figure from `J27` step 7, not a computation of this file |
| b | Which template a move-out visit is raised from | **No card or wireframe names it.** *Final read — electric* is this journey's fixture (*ours*) and the gap was filed as `DEF-WRK-3578` and closed 2026-09-03 — `US-WRK-039` §4 now states this template as the story's own, raised through the *Read verification* type's default template: `Work-029` draws the label *Final read & de-energise*, which is neither a type in the catalogue nor a template in `Work-013` |
| c | The curb-stop visit (the second box) | The same door, a Water template; not walked here. `field_visit = curb_stop` is one of the three lawful values |
| d | Who may accept | **`OQ-WRK-1492`** — `J61` step 9; here M. Torres accepts as any staff may today |
| e | The `WO-4910` string and the `1,297` read | The series allocates at raise (`BR-TEN-035`); the read is this journey's fixture value on a meter whose opening read is the fixture's `1,204` — both should be written once in `US-WRK-006` |
