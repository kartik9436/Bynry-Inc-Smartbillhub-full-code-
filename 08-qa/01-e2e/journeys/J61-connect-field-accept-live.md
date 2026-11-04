# J61 — Connect → field → accept → live (extends `J27`: a technician between the raise and the completion; the phone's Close activates nothing, one person's Accept activates Electric, posts the read dated to the completion — and the letter is still refused with its reason)

---
id: J61
tier: 2
rules: [BR-WRK-003, BR-WRK-007, BR-WRK-008, BR-WRK-013, BR-WRK-015, BR-WRK-016, BR-WRK-025, BR-WRK-034, BR-WRK-035, BR-WRK-036, BR-WRK-037, BR-WRK-038, BR-WRK-039, BR-WRK-040, BR-WRK-041, BR-WRK-042, BR-WRK-043, BR-WRK-044, BR-WRK-046, BR-WRK-050, BR-WRK-051, BR-WRK-057, BR-MET-110, BR-MET-112, BR-MET-115, BR-SHL-025]
stories: [US-WRK-002, US-WRK-003, US-WRK-006, US-WRK-017, US-WRK-022, US-WRK-023, US-WRK-035, US-WRK-040, US-WRK-041, US-WRK-042, US-WRK-043, US-WRK-045, US-WRK-046]
# ✅ **ACTIVATED 2026-09-05** — `06-backend/tests/test_j61_connect_field_accept_live.py`,
# 8 cases, green. The banner it replaces said *"no `J61.spec.ts`"* and gave as its reason
# that this journey *"adds a phone that does not exist"*; CR-070 waves J–L built the
# phone, the offline store, the sync door and the acceptance, so the reason had expired
# and only the banner remained — hard-won law 2's mirror, in a document.
#
# ⚠ **IT IS A `.py`, NOT THE `.spec.ts` THE EXECUTION PLAN NAMES, AND THAT IS A
# DECISION RATHER THAN A SLIP.** No `.spec.ts` exists anywhere in this repository and
# nothing would run one, so writing one would have been a check that cannot fail — and
# the fourth wave in a row to claim an activation that did not happen (`E6`, `H3`, `I3`
# each claimed one; `J60`, `J62`, `J63`, `J66`, `J67` still carry their banners). A
# journey is a claim about **what upstream leaves in the database**, so the spec lives
# where that can be asserted. Decision log, 2026-09-05.
#
# ⚠ **WHAT THE SPEC ASSERTS** is this file's own *"This journey leaves (for
# downstream)"* paragraph and its INVARIANCE row, one case per clause — not the
# fifteen-step table, which would be a second copy of this document free to disagree
# with it. `J65`'s spec builds the day; this one picks it up through `J65`'s OWN
# helper, so the handoff itself is what goes red if either half moves.
#
# `stories:` = the stories this journey exercises; since 2026-09-03 (`DEF-WRK-3571`)
# `04-flows.md`'s index and every frontmatter agree with it. `US-WRK-044` — the offline
# close, `J65`'s — was listed for `J61` in the flows index and is exercised by no step
# here (every step runs online), so it left both. `US-WRK-006` names all eight.
#
# ⚠ THREE STORIES HERE ARE `status: blocked` AND THIS JOURNEY ASSERTS THEIR STUBS,
# NOT THEIR ANSWERS: `US-WRK-022` (`OQ-WRK-1492`, who may accept), `US-WRK-023`
# (`OQ-WRK-1494`, the web-blocked login) and `US-WRK-035` (`OQ-376`, the letter's
# source kind). Steps 9, 12 and 13 stop at each boundary and assert the boundary.
---

**Intent.** `J27` ends at *"if a job somehow reaches Completed"* — a field result
submitted from a Python shell, a person pressing Accept, the service going live. This
journey puts a **technician with a phone** between the raise and that completion, and
proves the one sentence the built half rests on (`BR-MET-110`, PO 2026-08-25): *"Work
order will send the data and confirm from field; utility staff will review these work
order, accept them and use data from them to activate these services."* So: **the
phone's Close moves nothing** (`BR-WRK-041`); **the supervisor's Accept is one human
act with four consequences** — data accepted, the read posted through metering's own
door dated to the completion, the service activated, the customer told — and **the
fourth is still refused at the door** (`OQ-376`), which this journey asserts rather than
papers over.

**Upstream leaves (`J27` step 10, on the build `J60` proposed).** Connection
**`CON-26-0129` · `12 Heron Way` · 1 unit · Electric + Water**, owner **Bell, Marcus**
(*ours — no card names this build's owner; `US-WRK-006` is where it should be written
once*), contact `(512) 555-0161`, committed 2 Mar 2026 with **four orders** from the
utility's own published starters (the 4 of `J60` step 11 after one removal), each
stamping `template_id` + `template_version` and its `is_gate`, `mode = our_crew`:
**`WO-4911`** Service drop · Electric · **`WO-4912`** Meter set 🚩 · Electric (**the
gate**) · **`WO-4913`** Tap and service line · Water · **`WO-4914`** Meter set 🚩 · Water
(the Water gate). *Numbers are this journey's fixture allocation from the free range
(`WO-4901`–`4910` and `4917` are taken by `J27`, `J63`, `J64`, `J66` and the queue
fixture); the series allocates at raise, so a spec asserts the ORDER and the keys, never
the drawn string (`J27` caveat e).* Unit 1 **vacant, no account** — the terminal state
`J27` step 13 describes. **D. Ortiz** has an `identity.User` (`dortiz@…`), a
`technicians` profile (Field technician · Water II · Meter I · Meter fitting · shift
07:00–16:00 · van Unit 12) and a registered device token `fxtr-ortiz-01`. **`WO-4911`**
was worked and closed *Passed* on 17 Mar by D. Ortiz (a non-gate order, used by step 9).

**Fixture the journey adds.** M. Torres assigns `WO-4912` to D. Ortiz for **Wed 18 Mar
2026 · 09:15** on 17 Mar at 16:40. The Electric *New connection* starter's bundle as
seeded: **2 tasks** (*Set meter and record serial* · *Record opening read* — *ours; the
starter's task titles are not in any card*), **1 reading** (*Opening read · kWh · 0–999 ·
photo Required · required · posts as meter read: Yes*), 0 parts, 2 safety rows (*Isolate
at the service head* · *Check for backfeed / on-site generation* — *ours*), signature
required, est. **40 min** (`Work-013`). New meter serial **`E1P-78003`** (*ours*).
Priya Menon (Billing Clerk) is the negative actor for step 9. Isolation tenant **Lone
Star Ridge WSC** (`lone-star-ridge`).

**Where two documents disagreed, and which one this journey follows.**
* `04-flows.md` says this journey leaves *"the connection re-derived to **Activated**"*.
  With two services and one gate accepted, `derive_connection_state()` (blueprint §9.1,
  seven tests, first match wins) yields **Partly activated** — Electric activated, Water's
  gate `WO-4914` still open. The journey asserts the **service** state *activated* and the
  **connection** state *Partly activated*, and reads the flows sentence as the service's.
  **Filed as `DEF-WRK-3574`**; the flows text was corrected 2026-09-03.
* `WO-4902` is claimed by three documents (`J27` puts `WO-4901`–`4907` on `CON-26-0117`;
  `US-WRK-035` puts `WO-4902 · Meter set` on `CON-26-0110`; `US-WRK-041`'s day list puts
  it at `3450 Oak Ridge Dr`). `04-flows.md` says *"`WO-4902`-shaped"*; this journey uses
  `WO-4912`. **Filed as `DEF-WRK-3575`**; `03-field-map.md` D-16 records every claim and the rule — keys, never drawn numbers.

| # | Actor · action · screen | Expected outcome (contract — what this step leaves) | Downstream assertions (record · phone · queue · audit · books) | Rule |
|---|---|---|---|---|
| 1 | **17 Mar 16:40 · M. Torres** assigns `WO-4912` to D. Ortiz for 18 Mar 09:15 (`Work-007` row action ✓ assign, or `Work-021`) | ONE `work_order_assignments` row `act = assign` (technician D. Ortiz · scheduled_for 18 Mar 09:15 · actor M. Torres · at 16:40) — **never an UPDATE**; the order's `assignee_technician_id` / `assigned_at` cache refreshed; `dispatch_state` Queued → **Scheduled**; `state` still `planned` — two axes | A `jobs` row `kind = work.push` exists **before** the broker message; on the phone's next sync the bundle lands; the order's Audit tab reads **Dispatched · pushed to phone · 16:40** (the token `fxtr-ortiz-01` is registered — were it not, the line reads *Dispatched · waiting for the phone*, never *pushed*). ⛔ Assigning `WO-4912` (skill Meter fitting) to R. Patel (Water I · Reads) is REFUSED naming the skill, ≤ 6 words. ⛔ `UPDATE work_order_assignments SET technician_id = … ` is refused by trigger on PostgreSQL | **BR-WRK-025** · **BR-WRK-029** · **BR-WRK-034** · **BR-WRK-023** |
| 2 | **18 Mar 07:55 · D. Ortiz** opens `/brazosbend/work/mobile/` (`Work-010`) on the phone, online | The day for 18 Mar in **appointment order**: `WO-4912 · Meter set 🚩 · 12 Heron Way · 09:15 · 40 min`; the bundle (`GET /work/mobile/jobs/{id}`) is fetched **at sync** into the offline store — the order's six copies, the customer contact *Bell, Marcus · (512) 555-0161* via `customers_seam`, the help documents as pre-signed GETs cached locally. Marker: **◍ online · synced 07:55** | The identity resolves from the login to the `technicians` profile (`US-WRK-020`); a login with no profile sees *No field work for this login* (six words), never an error. Priority renders as a pill and **does not reorder** the day. **Airplane mode after this load: the job, its safety rows, tasks, reading spec and help all render with zero network requests** (`US-WRK-042` TC-1). `features/work/mobile/**` is on `route-b-migrated.txt` (B14 rule 21) | **BR-WRK-035** · **BR-WRK-036** · **BR-WRK-038** · **BR-WRK-042** · **BR-WRK-045** · **BR-WRK-008** |
| 3 | **08:58 depart · 09:14 arrive** — two taps on the phone | Two more `work_order_assignments` rows, `act = depart` then `arrive`, each with the phone's captured time; `dispatch_state` Scheduled → **En route** → **On site**; `Work-007`'s IN THE FIELD tile counts him | `depart` and `arrive` are accepted **only from the assignee** — a different technician's tap is refused. The report's *On site 09:14* (step 11) is this `arrive` row, not a hand-typed time | **BR-WRK-025** · **BR-WRK-023** |
| 4 | **The safety gate** (`Work-011`) — D. Ortiz ticks ONE of the two mandatory safety rows | Header **SAFETY — 1 OF 2 · TASKS LOCKED**; the two tasks visibly locked; the Close button reads **Close job — finish safety first** (five words) | ⛔ **Server half:** `POST /work-orders/{WO-4912}/field-result` posted directly with the second safety row unticked is REFUSED **naming the row**, `state` unchanged, no completion audited — *"build both or you have built neither"*. Ticking the second row unlocks the tasks: header **TASKS — 2 STEPS · 40 MIN**. ⛔ A task tick smuggled into the client store while locked is refused at sync — the server re-derives the lock from the safety rows' `ticked_at`, never from the client's word. Gate `g7x_safety_gate_server_side.py` fails when the server check is removed — **proved RED first** | **BR-WRK-037** · BR-SHL-025 · `CR-070` §12 gate 2 |
| 5 | **The work** (`Work-011` → `Work-012`): task 1 *Set meter and record serial* → `E1P-78003`; task 2 → reading *Opening read* = **`0` kWh**, photograph `IMG-8901` (09:41); customer **Bell, Marcus** signs 09:52 → `SIG-4912` | `work_order_tasks` ×2 `ticked_at/by`; `work_order_readings` row `value = 0 · unit_of_measure = kWh · in_range = true` (0 ≤ 0 ≤ 999, **derived by the server**) · `photo_attachment_id` → `IMG-8901`; `work_order_signatures` one row (`printed_name` *Marcus Bell* · image · `signed_at` 09:52 · `captured_by` D. Ortiz); the photograph resized to **1,600 px** before upload, pre-signed PUT, its row keyed `ortiz-01-2026-03-18-4912-…` | ⛔ A value with **no unit** is REFUSED — a bare `0` is exactly the value most likely to travel without one, and this is the ONE refusal on a reading (hard rule 3, `US-WRK-047` TC-4). An out-of-range value would be **flagged, never refused** (`BR-WRK-039`; exercised in `J65`). ⛔ Pressing Close before `IMG-8901` is attached is REFUSED on the phone and by the server **naming *Opening read*** — a missing REQUIRED photograph is the rule that blocks; range is not (`BR-WRK-040`). The signature image is a `stored_documents` row of kind `work_order_signature`; the screen shows `SIG-4912`, never a uuid | **BR-WRK-015** · **BR-WRK-039** · **BR-WRK-040** · **BR-WRK-046** · **BR-WRK-047** · hard rule 3 · B14 rule 31 |
| 6 | **09:55 · Close job · Passed** (online, so the button reads *Close job*; offline it would read *Close job · send when back online*) | `submit_field_result` — **and nothing more**: `state = completed` · `outcome = passed` · `completed_at = 18 Mar 09:55` · `accepted_by` **NULL** · `field_data.set_reads = [{meter_no: E1P-78003, value: 0, unit: kWh, read_at: 2026-03-18T09:55-05:00, channel: total}]` (channel amended 2026-10-05, `DEF-WRK-4073`: it read `field`, a source and not a register — `BR-MET-059`) assembled from the copy row that carries `posts_as_meter_read = true`; `labour_rate_snapshot = 48.5000`, `labour_role = field_technician` stamped at close; `dispatch_state` → Complete | ✅ **`connection_services` for Electric on unit 1 is UNCHANGED** — nothing activated; `CON-26-0129` still *In progress*. ✅ **Zero `meter_reads` rows** for `E1P-78003`. ✅ No report yet (`BR-WRK-050`: generated by Accept, never by Close). ⛔ A second Close on the same key is a no-op. `Work-003` (the drawer on `Work-002`) renders the NULL as the sentence **"Nobody has accepted this yet."** — never a dash | **BR-WRK-041** · **BR-WRK-007** · BR-MET-110 · **BR-WRK-050** · **BR-WRK-020** |
| 7 | **19 Mar 08:50 · M. Torres** opens **Work › Awaiting approval** (`Work-009`) | One query, no new table: `accepted_by IS NULL AND state = completed`, across every connection and anchor, oldest first. Row: **`WO-4912 · Meter set` · `CON-26-0129` · `12 Heron Way` · Electric · `Passed` · 18 Mar 2026 · 1 day**; `CountFooter` *N orders · oldest waiting …*; `NoteBar` reads *nobody has accepted them* — **not** the drawn `accepted_by` (B14 rule 32) | ⛔ An order in `state = planned` is NOT here — the null alone is not enough. ✅ A completed order with **no connection** (`J62`'s `WO-4832`) appears with a dash under Connection and its premises under Premise. The row action 👁 opens `Work-003` / `Work-008` | **BR-WRK-007** · `US-WRK-003` TC-1/TC-3/TC-7 · B14 rule 32 |
| 8 | **The Field-technician login, on the web (⚠ `OQ-WRK-1494` CLOSED 2026-09-04 — NO LONGER A BOUNDARY).** D. Ortiz signs into the staff web app on a laptop | ⚠ **AMENDED 2026-09-05 — THIS ROW DESCRIBED THE PRE-RULING WORLD.** It read *“Lands on the dashboard today”* over a stub that raised. **The PO ruled option (a): a surface scope on the user, and the web sign-in is REFUSED** — *“Sign in on the field app.”*, six words per B14 rule 33 and one shorter than the prototype's seven. The refusal lives in `identity.services.sign_in`, the one place that knows which app a request came from; `identity_seam.enforce_surface` is a READ and raises nothing. The role `field_technician` holds **no staff permission**: `POST /payments` as D. Ortiz → `403` from the ordinary catalogue | ⚠ **THE xfail IS GONE WITH THE QUESTION.** The refusal is asserted outright, and one `users` table holds both kinds of login — PO, *“will you keep them in user table?”* answered YES with a `surface_scope` column, because a second table would fork invite, deactivate, reset and audit for one role. `users.surface_scope` defaults `both` and D. Ortiz's reads `mobile`; **nothing on the phone waits on this question**. On Lone Star Ridge D. Ortiz's phone login is refused — the user belongs to Brazos Bend | **BR-WRK-043** · `OQ-WRK-1494` (CLOSED) · `US-WRK-023` TC-2/TC-3/TC-4/TC-5 |
| 9 | **Who may accept (⚠ `OQ-WRK-1492` CLOSED 2026-09-04 — NO LONGER A BOUNDARY).** **Priya Menon, Billing Clerk**, opens `WO-4911` (Service drop, non-gate, closed 17 Mar) on `Work-003` and presses **Accept** | ⚠ **AMENDED 2026-09-05 — IT STILL SUCCEEDS, AND NOW IT SUCCEEDS BY RULING RATHER THAN BY FALLBACK.** PO: *“clark can do it sicne it s a day to day work”* — accepting a finished job is ordinary daily work and must not queue behind a supervisor, because a two-person utility has none sitting by the screen. The named permission `work_accept` is **held by the three office roles** and checked in `accept_field_result`; nothing is caught into a fallback and nothing is logged as unruled. `WO-4911.accepted_by` = Priya Menon | ⚠ **THE CASE IS INVERTED, NOT xfail.** `work_accept` is held by the office roles and NOT by `field_technician`, so the assertion worth making is that a **technician's login never reaches the endpoint** — and that is a consequence of `OQ-WRK-1494`'s surface scope rather than a second rule, so no lane should build a second check that goes stale the day the phone gains an approval screen; `Work-003`'s copy promises **no** restriction (grep = 0). ✅ **A non-gate order's Accept attempts NO letter** — only the gate's service is live (`US-WRK-035` TC-3). `CON-26-0129` reads *1 of 4* | **BR-WRK-044** · `OQ-WRK-1492` (CLOSED) · `US-WRK-022` TC-1–TC-4 · `US-WRK-035` TC-3 |
| 10 | **19 Mar 09:05 · M. Torres** opens `WO-4912` on `Work-003`, reads *"Nobody has accepted this yet."*, presses **Accept** | **ONE transaction, four consequences, in this order:** (1) `accepted_by` = M. Torres · `accepted_at` = 19 Mar 09:05; (2) `metering_seam.post_set_reads()` → **`metering_services.commit_event_reads()`** — metering's own door — writes ONE `meter_reads` row: `E1P-78003` · **`0` · `kWh`** · **`read_at` = 18 Mar 09:55 (the completion, NOT the acceptance)** · channel *field*; (3) the Electric `connection_services` row on unit 1 → **`activated`**; `refresh_connection_state()` re-derives `CON-26-0129` → **Partly activated** (Water's gate `WO-4914` open); (4) `dispatch_communication()` queues the letter — see step 11. `audit_log`: one row per act, one actor, one moment | ✅ **Work wrote NO `meter_reads` row itself** — the boundary gate fails on `MeterRead.objects.create` under `apps/work/`. ✅ The read carries its unit on both sides of the seam (`D-13`). ⛔ **Accepting twice does nothing** — refused idempotently; no second read, no second letter attempt. ⛔ Metering-side variant: the seam called with a value and **no unit** → metering's door REFUSES → **the whole acceptance rolls back, the order stays on `Work-009`**, the refusal shown in words. ⛔ The read pipeline refusing the value (a serial not on the unit) → the same rollback (*"Accepting field data the read pipeline refuses would activate a service off a reading that does not exist"*). `Work-002`'s History: *Electric activated — gate WO-4912 passed*, and the gate passed because a PERSON accepted (`J27` step 17) | **BR-WRK-003** · **BR-WRK-015** · BR-MET-110 · `US-WRK-046` TC-1/TC-3/TC-4/TC-5 · `US-WRK-003` TC-4 |
| 11 | **The letter (boundary — `OQ-376`).** The same press, its fourth consequence | `notifications.queue_document` is asked for source kind **`connection`**, which the platform constant (**ten** kinds — `invoice · payment · notice · plan · report · ledger · test · bulk_action · move · account`; this said eight until 2026-09-03, `DEF-WRK-3602`) does not hold → **refused with the platform's own sentence**; the response carries `queued: false` and `tracks: "OQ-376"`; `raise NotImplementedError("OQ-376")` sits where the source kind would be chosen. **`outbound_messages` gains nothing.** The toast says **the customer has NOT been told** | ⛔ **The tempting fix — sending it as `notice` — makes the test FAIL**: the source kind is asserted by name, because `notice` is the disconnect ladder's kind and a connect letter filed there is counted among dunning notices in every monthly report. No *sent once* marker is written on a send that did not happen. Marcus Bell's **Customer · Messages** tab shows nothing. The day the ruling lands: one constant value and one template, and this row turns to *Your electric service is live* | **BR-WRK-057 (OPEN)** · BR-MET-115 · **OQ-376** · `US-WRK-035` TC-1/TC-2 |
| 12 | **The report** (`Work-032`, `WO-4912-v1.pdf`) — generated by the Accept in step 10 | ONE `work_order_reports` row (`version = 1`), ONE `stored_documents` row kind `work_order_report`, frozen. COST: **on site 09:14 → completed 09:55 = 41 min · 41 ÷ 60 = 0.6833 → `0.68 h`** · Labour · Field technician · `0.68 h` · `48.50` · **`32.98`** (stored `32.9800`); no parts planned or used; **Total `32.98` — the sum of the rounded lines; NO tax line** | `apps/work/costing.work_order_cost_lines()` is the ONE function; hours at four decimals would give `0.6833 × 48.5000 = 33.14` — the test asserts **not `33.14`**. The rate is the snapshot from step 6, so the 1 Apr rate change to `50.0000` leaves this report at `48.5000`. A second Accept produces **no `v2`**. The reading row reads *0 · kWh · in range yes · ▣ IMG-8901*. The signature line *Signed Marcus Bell · 18 Mar 2026 09:52 · SIG-4912* | **BR-WRK-050** · **BR-WRK-051** · **BR-WRK-052** · **BR-WRK-020** · hard rule 2 |
| 13 | **What the build now reads.** `Work-002` for `CON-26-0129` → Overview and Orders tab; `Work-001` | PROGRESS **2 of 4**; the Electric block *Activated*, the Water block pending — **a state per service, side by side**, derived by the SAME function as the connection's; the connection row on `Work-001` reads `CON-26-0129 · 12 Heron Way · 1 · E W · 2 of 4 · … · Partly activated` — the product word is **activated** (`CR-032`); *energised* appears nowhere | Unit 1 is still **vacant, no account** — `J27` step 13's terminal state; the owner's account carries the connection charges (`BR-MET-113`) and **nothing here billed anybody**: no invoice, no journal line (`BR-WRK-004`'s shape). The opening read `0 kWh` on `E1P-78003` is what the first bill's consumption will run from when a move-in arrives — **`J07` (first-bill life) is downstream of this read** | BR-MET-110 · `CR-032` · BR-MET-113 · BR-WRK-004 |
| 14 | **ISOLATION — Lone Star Ridge WSC** (`app.tenant_id` = Lone Star's; RLS `FORCE`) | Its `Work-009` is **empty** — Brazos Bend's completed orders are invisible; `POST /lone-star-ridge/work-orders/{WO-4912}/accept` → **`404`**, byte-identical to an absent row, **before any chain runs**; its `meter_reads` holds no `E1P-78003`; its day bundle for any technician contains only its own assigned orders — a query for another technician's day is `403` | The refusal reason on Lone Star's own gate acceptance is its own; no Brazos Bend message row anywhere. D. Ortiz's session pointed at `/lone-star-ridge/work/mobile/` is refused | hard rule 1 · `US-WRK-003` TC-5 · `US-WRK-035` TC-4 · `US-WRK-041` TC-6 · `US-WRK-046` TC-6 |
| 15 | **INVARIANCE** | — | The service state moved **exactly once, at Accept, never at Close**. The read is dated to the completion, carries its unit, and was written by metering. Every act — assign · depart · arrive · each tick · close · accept · the refused letter — has an `audit_log` row with actor and time. Nothing money-bearing exists; no tax anywhere; the report is frozen at v1. The connection number `CON-26-0129` and the order numbers are never renumbered (`BR-TEN-035`) | BR-MET-110 · hard rules 1, 7 · BR-TEN-035 |

**This journey leaves (for downstream).** `WO-4912` accepted by M. Torres · `WO-4911`
accepted by Priya Menon (the stub's evidence) · one `meter_reads` row `E1P-78003 · 0 ·
kWh · 18 Mar 09:55 · field` · Electric on `CON-26-0129` **activated**, the connection
**Partly activated** with `WO-4913`/`WO-4914` open · `WO-4912-v1.pdf` at **$32.98** ·
one refused letter with `tracks: "OQ-376"` and **no `outbound_messages` row** · audit
rows per act · Lone Star Ridge's queue empty. **Downstream:** `J07` runs a first bill
from this opening read; `J66` is the failed-gate counterpart on `CON-26-0117`.

## Boundaries — what this journey stops at, and why

| # | Not asserted | Because |
|---|---|---|
| a | The letter reaching anybody | **`OQ-376`, OPEN — *"blocking the send only"*.** Cited, not re-minted (law 13). Step 11 asserts the refusal, the `tracks` value, the absence of an `outbound_messages` row and that `notice` is NOT used |
| b | A Billing Clerk being REFUSED the Accept | ⚠ **AMENDED 2026-09-05 — `OQ-WRK-1492` is CLOSED (2026-09-04) and a clerk MAY accept.** There is nothing to refuse, so the boundary is gone; step 9 asserts the permission as ruled |
| c | The web refusing a Field technician's login | ⚠ **AMENDED 2026-09-05 — `OQ-WRK-1494` is CLOSED (2026-09-04, option (a)) and the refusal is REAL.** Step 8 asserts it outright; it is no longer a boundary |
| d | Any drawn `WO-` number | The series allocates at raise (`BR-TEN-035`); this file's `WO-4911`–`4914` are the fixture's expected values on a fresh seed, and the spec asserts by position and key (`J27` caveat e) |
| e | Background push while the app is closed | The phone is a web app (`BR-WRK-045`); where no token is registered the audit line reads *waiting for the phone*, never *pushed* (`US-WRK-030` TC-2). Asserted in `J62` |
| f | The connection reading *Activated* (whole) | Water's gate is open; the connection is *Partly activated* until `WO-4914` is accepted. See the disagreement note above the table |
