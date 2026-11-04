# J65 — The offline day, and one sync (D. Ortiz works three jobs on 15 Mar 2026 with no signal after 08:12; nine photographs and one out-of-range reading land ONCE at 17:40; a second sync adds nothing; a duplicate key inside the batch poisons nothing — proved on PostgreSQL)

---
id: J65
tier: 2
rules: [BR-WRK-008, BR-WRK-035, BR-WRK-036, BR-WRK-037, BR-WRK-038, BR-WRK-039, BR-WRK-040, BR-WRK-041, BR-WRK-042, BR-WRK-045, BR-WRK-046, BR-WRK-047, BR-WRK-048, BR-MET-110, BR-SHL-025]
stories: [US-WRK-006, US-WRK-023, US-WRK-040, US-WRK-041, US-WRK-044, US-WRK-045, US-WRK-048, US-WRK-049]
# ✅ **ACTIVATED 2026-09-05** — `06-backend/tests/test_j65_offline_day_one_sync.py`,
# 6 cases, green. The banner it replaces gave as its reason that there was *"no service
# worker, no manifest, no offline store and no `work_sync_receipts` table"*. Every one of
# those now exists (CR-070 waves J–L; `work/0018` is the receipts table), so the reason
# had expired and only the banner remained.
#
# ⚠ **IT IS A `.py`, NOT THE `.spec.ts` THE EXECUTION PLAN NAMES** — the argument is
# written out in the spec's own docstring and in the decision log of 2026-09-05. Short
# form: nothing in this repository runs a `.spec.ts`, so one would have been a check that
# cannot fail, and a journey is a claim about what upstream leaves in the DATABASE.
#
# ⚠ **WHAT IT DOES NOT ASSERT, STATED RATHER THAN SKIPPED:** the SAVEPOINT (law 14) —
# SQLite has no aborted-transaction state and `tests/test_us_wrk_044_sync_pg.py` holds it
# on real PostgreSQL — and the screens, which are `10-scripts/render-checks/
# cr070-l-the-offline-day-and-the-read.mjs`'s.
#
# ⚠ TWO OF THESE STORIES ARE WRITTEN FROM UNREAD CARDS — `US-WRK-044` (`WM-36`) and
# `US-WRK-045` (`WM-38`) sit past the text the documentation lane could read. Nothing
# in this file goes past what `WS-10`, `WS-12`, blueprint §3 steps 10–14, §7's
# `POST /work-orders/{id}/field-result` and `WM-48`'s worked figure carry. If §14's
# remaining text states a rule this file does not, that text wins and this file is
# amended before code.
#
# `stories:` = `04-flows.md`'s index for `J65` plus `US-WRK-006` (names all eight).
---

**Intent.** *"Stage E of the flow happens on a phone, in the technician's hand, often
with no signal."* This journey is that day: the phone reaches the server once at 08:12
and not again until 17:40, and in between a technician ticks safety rows, works tasks,
records a reading that is outside its range, takes nine photographs, captures a signature
and closes three jobs. Then one sync. **What it proves is `WM-48`'s own worked figure:**
*"A technician syncs three jobs after a day with no signal; nine photographs land once
each … and a re-sync of the same three jobs adds nothing."* And the trap law 14 names:
**a duplicate key inside the batch must not poison the rest — a savepoint per item, on
PostgreSQL, because the SQLite suite cannot see the aborted-transaction state.**

**Upstream leaves.** Tenant **Brazos Bend Utilities**. **D. Ortiz**'s day for **15 Mar
2026** — four jobs assigned, in appointment order (`US-WRK-041`): **`WO-4901`** Service
drop · Electric · `3450 Oak Ridge Dr` · 08:30 (**closed 08:10, online, arrived early**) ·
**`WO-4902`** Meter set 🚩 · Electric · `3450 Oak Ridge Dr` · 09:15 · **`WO-4824`**
Reconnect after payment · Electric · `903 Birch Ln · A-10222` · due 12:00 · **Urgent** ·
*⏱ restoration clock running* · **`WO-4822`** Meter exchange — residential (`ST-0002 v2`)
· Electric · `221 Oak Ave · A-10688` · Miller, Sarah · `(512) 555-0114` · 15:30 · 45 min ·
*⚠ Access: dog in rear yard · gate code 4417*. `WO-4822`'s copies: **3 safety** (all
mandatory) · **7 tasks** (tasks 2 and 5 *photo Required*) · **3 readings** (*Final read on
old meter · kWh · 0–99,999 · photo Required · posts* · *Opening read on new meter · kWh ·
0–999 · photo Required · posts* · *New meter serial · optional · recorded only*) · **3
materials** (`MTR-E1P` ×1 · `SEAL-01` ×1 · `GSKT-STD` ×1) · 3 help · details (dog, gate
4417); old meter `E1P-33107`, new meter `E1P-77412`. Device token `fxtr-ortiz-01`; the
phone **synced at 08:12** and then had **no signal until 17:40**. Isolation tenant
**Lone Star Ridge WSC** (`lone-star-ridge`). Supervisor **M. Torres**.

**Fixture the journey adds (*ours* where a template is not itemised in any card).**
`WO-4902` (Electric *New connection* starter: 2 safety · 2 tasks · 1 reading · 0 parts ·
signature) worked 09:15–10:20, **3 photographs** `IMG-8831`–`8833`, signed. `WO-4824`
(Reconnect: 2 safety · 4 tasks · 1 reading · 0 parts · signature) worked 11:40–12:05,
**4 photographs** `IMG-8835`–`8838`, signed. `WO-4822` worked 15:15–16:07, **2
photographs** `IMG-8841` (15:12) · `IMG-8842` (16:02), signed *S. Miller* 16:07. Total
**nine** photographs, each **3,000 × 4,000 px · 3.1 MB** on the camera → **1,600 px on
the long side · ≈ 250 KB** before it leaves the phone. Idempotency keys
`ortiz-01-2026-03-15-<order>-<nnn>`; `WO-4822`'s batch is **20 items**: 3 safety ticks
· 7 task ticks · 3 readings · 3 materials · 2 photographs · 1 signature · 1 close.

**Where two documents disagreed, and which one this journey follows.**
* **The weekday.** The prototype's day is *Wed 15 Mar*; the report is dated *15 Mar
  2026*; **15 March 2026 is a Sunday.** The journey asserts the DATE and treats the
  weekday label as derived from the date on screen; every document now reads *Sun 15 Mar* (`DEF-WRK-3576`, 2026-09-03; `03-field-map.md` D-17).
* **Which three jobs.** `US-WRK-044`'s test data closes `WO-4822`, `WO-4824`, `WO-4821`;
  `US-WRK-041`'s day list has no `WO-4821` and has `WO-4901`/`WO-4902`. The day list
  (the screen story) wins; the three closed offline are `WO-4902`, `WO-4824`, `WO-4822`,
  and `WO-4901` was closed online before the last sync. **Filed as `DEF-WRK-3577`; `US-WRK-044` and `US-WRK-049` corrected 2026-09-03.**
* **`IMG-8841 · 15:12` against *On site 15:15*.** The photograph precedes the `arrive`
  tap by three minutes. Read as: D. Ortiz photographed the old meter walking up, then
  tapped *arrive*; `arrive` is the tap, not the footfall, and the report's *52 min* is
  `arrive → completed_at`. No change to the drawn values.
* **The fourth reading.** `Work-033` draws *Voltage at socket · V · 110–125 · Required ·
  not taken · missing — job cannot close*; the template and the report carry three
  readings (`03-field-map.md` D-9). The required-missing refusal is exercised here on
  reading 2 before its photograph is attached; the drawn fourth row is not added.

| # | Actor · action · screen | Expected outcome (contract — what this step leaves) | Downstream assertions (phone · record · queue · audit · books) | Rule |
|---|---|---|---|---|
| 1 | **08:12 · the last sync.** D. Ortiz opens `/brazosbend/work/mobile/` (`Work-010`); `WO-4901` is already closed (08:10, online) | `GET /work/mobile/today` → the four jobs with their bundles into the offline store; marker **◍ online · synced 08:12**. Day order **by appointment time**: `4901 · Done` → `4902 · 09:15` → **`4824 · due 12:00` (Urgent, a pill) → `4822 · 15:30`**; `4822`'s card carries *⚠ Access: dog in rear yard · gate code 4417* from the order's details row and the premises' notes; `4824`'s card *⏱ restoration clock running · 1h 20m* (now − payment cleared). **08:13: no signal** | ⛔ Moving `WO-4822` to Urgent changes its pill and **does not** move it above `WO-4824`. The marker is on every card and the header, **never hidden by scroll**; a phone that has never synced reads *◍ offline · never synced*. The manifest offered *Add to home screen*; the service worker registered; `features/work/mobile/**` is on `route-b-migrated.txt`. D. Ortiz's identity resolved from the login to the profile; the ordinary session, the surface refusal stubbed on `OQ-WRK-1494` | **BR-WRK-035** · **BR-WRK-036** · **BR-WRK-045** · **BR-WRK-008** · `US-WRK-041` TC-1–TC-5/TC-7 · `US-WRK-040` TC-1–TC-4 |
| 2 | **09:15–10:20 · `WO-4902`** worked offline (`Work-011` → `Work-012`): 2 safety ticks, 2 task ticks, 1 reading (serial + opening read **`0` kWh**), 3 photographs, signature, **Close job · send when back online · Passed** | Every act is a **queued item in the offline store** with its own key (`…-4902-001` … `-010`, ten items, in **capture order**); the photographs are **resized to 1,600 px** and held; the marker reads **◍ offline · 1 job to send** | The tap opened the job with **zero network requests**; the help SOP opens from the store. The button reads *Close job · send when back online* (the offline label). Nothing has reached the server | **BR-WRK-042** · **BR-WRK-041** · **BR-WRK-038** · **BR-WRK-047** · `US-WRK-044` TC-7 · `US-WRK-045` TC-2 |
| 3 | **11:40–12:05 · `WO-4824`** worked offline: 2 safety, 4 tasks, 1 reading, 4 photographs, signature, Close *Passed* | Thirteen queued items (`…-4824-001` … `-013`); marker **◍ offline · 2 jobs to send** | The restoration clock keeps counting from the payment-cleared time (r10's own sentence) until the server learns of the close at 17:40 | **BR-WRK-042** · **BR-WRK-036** |
| 4 | **15:15 · `WO-4822`, the safety gate.** Two of three mandatory rows ticked | **SAFETY — 2 OF 3 · TASKS LOCKED** — *two of three ticked is locked, not two-thirds unlocked*; the seven tasks visibly locked; Close reads **Close job — finish safety first**. Third tick → **TASKS — 7 STEPS · 45 MIN** | ⛔ A task tick forced into the store while locked (a tampered client) is **refused at sync** — the server re-derives the lock from the safety rows' `ticked_at`, never from the client's word (step 9). The order of items in the queue is the order of capture, and safety ticks precede task ticks | **BR-WRK-037** · `US-WRK-043` TC-1/TC-2/TC-6 |
| 5 | **15:15–16:07 · `WO-4822`, the work** (`Work-012`): task 2 → *Final read on old meter* **`48,221` kWh** · `IMG-8841` (15:12); task 5 → *Opening read on new meter* **`1,204` kWh** against **0–999**; task 6 → seal `4417882`; *New meter serial* `E1P-77412`; parts `MTR-E1P` **1 of 1** · `SEAL-01` **1 of 1** · `GSKT-STD` **0 of 1 · not used**; **Sarah Miller signs 16:07** (`SIG-4822`); note *Customer present throughout. Old meter left for collection.* | Reading 2 shows **⚠ Expected 0–999 kWh. Flagged, not blocked. You can still close. The office will see this.** — four clauses, each ≤ 6 words — and is **recorded**, `in_range = false` (server-derived at sync); reading 1 `in_range = true`; reading 3 optional, no photograph, *none — not required* | ⛔ **16:01 · Close is REFUSED on the phone, before any send, naming *Opening read on new meter*: photograph required, not taken.** 16:02 `IMG-8842` taken and attached; 16:07 Close accepted. **Two rules, two sentences:** a missing REQUIRED photograph stops the job; an out-of-range value never does. ⛔ A value with no unit is refused (the one refusal). The unused gasket is a real outcome, kept (`BR-WRK-049`). No on-hand count anywhere moves (`OQ-WRK-1490`) | **BR-WRK-039** · **BR-WRK-040** · **BR-WRK-015** · **BR-WRK-046** · **BR-WRK-049** · `US-WRK-047` TC-1/TC-2/TC-5/TC-7 · `US-WRK-049` TC-2/TC-3/TC-4 · `US-WRK-045` TC-4 |
| 6 | **16:07 · Close job · send when back online · Passed** | The close is queued as **item 20 of `WO-4822`'s 20** (`…-4822-020`), after the three safety ticks, seven task ticks, three readings, three materials, two photographs and the signature; marker **◍ offline · 3 jobs to send**. **Nothing on the server has changed since 08:12** — the three orders still read `state = planned`, `dispatch_state = scheduled`/`on_site`; `WO-4822`'s `labour_rate_snapshot` is not yet stamped | ⛔ Tapping Close again queues **nothing** — idempotent on the same key. The marker counts **jobs with a queued close**, not items | **BR-WRK-041** · **BR-WRK-042** · **BR-WRK-036** · `US-WRK-045` TC-5 · `US-WRK-044` TC-7 |
| 7 | **17:40 · signal.** The phone syncs — **one `POST /work/mobile/jobs/{id}/sync` per job**, each a batch of items in capture order, each item with its key | Per job, the server applies items **in order, one savepoint per item**, and answers **per-item results**: `WO-4902` 10 of 10 accepted · `WO-4824` 13 of 13 · `WO-4822` **20 of 20**. Each close inside its batch **is `submit_field_result`** — three orders now `state = completed` · `outcome = passed` · `completed_at` = the phone's captured time **(10:20 · 12:05 · 16:07 — not 17:40)** · `accepted_by` NULL · `labour_rate_snapshot = 48.5000` stamped at each close. Photographs: the pre-signed PUTs complete, then **nine `work_order_attachments` rows and nine `stored_documents` rows of kind `work_order_photo`, ONCE EACH**, ≈ 250 KB each; one `work_order_signatures` row per job; every key in **`work_sync_receipts`** (the server's memory of what it accepted). Marker → **◍ online · synced 17:40** | ✅ **Nothing activated.** The Meter set `WO-4902` is a gate and its close moved no `connection_services` row (`BR-MET-110`); zero `meter_reads` rows exist for any of the three. ✅ All three appear on **`Work-009`** with their outcomes. ✅ `work_order_readings` for `WO-4822`: `48,221 · kWh · in_range true · IMG-8841`; `1,204 · kWh · **in_range false** · IMG-8842` — the flag rides to `Work-008`, `Work-009` and later the report. ✅ **`captured_at` (device) and the server's receipt time are two columns** — the audit rows carry both. ✅ Every stored photograph is within the store's size cap; the fixture image proves the resize (3,000 px → 1,600 px, ≈ 250 KB) | **BR-WRK-042** · **BR-WRK-041** · **BR-WRK-047** · **BR-WRK-020** · BR-MET-110 · `US-WRK-044` TC-1/TC-5 · `US-WRK-048` TC-1/TC-4 · `US-WRK-045` TC-1 |
| 8 | **17:41 · a second sync** of the same three queues (the phone retries before it has read its acknowledgements) | **ZERO new rows anywhere** — every key was seen: no second `field-result`, no tenth attachment, no second signature; the receipts table has no new row; the per-item results read *duplicate* for all 43 | This is `WM-48`'s sentence, asserted: *a re-sync of the same three jobs adds nothing*. `stored_documents` count for `work_order_photo` on this tenant is exactly **9** | **BR-WRK-042** · **BR-WRK-047** · `US-WRK-044` TC-2 · `US-WRK-048` TC-2 |
| 9 | **PostgreSQL — the trap (law 14).** A fixture batch of 20 for `WO-4822` where **item 5 carries a key already accepted** | **Items 1–4 and 6–20 COMMIT; item 5 is reported as a duplicate; the batch answers 19 accepted · 1 duplicate.** Run under **`config.settings.local` on real PostgreSQL 16**, not the default suite — `config/settings/test.py` hardcodes in-memory SQLite, which has **no aborted-transaction state**, so the broken version (`try/except IntegrityError: continue` with no savepoint) passes the whole suite green and loses the other nineteen in production | The code comment on the savepoint says WHY it is there, or the next lane simplifies it away. ⛔ **Ordering:** a batch whose close arrives before one of its mandatory safety ticks → the close item is **refused naming the row** (`US-WRK-043`), the ticks are applied, and the phone re-queues the close — the server never trusts the client's order for the lock. ⛔ A queued **task tick captured while the lock held** (step 4's tamper) is refused at this point, by the same derivation | **BR-WRK-042** · **BR-WRK-037** · law 14 · `US-WRK-044` TC-3/TC-5 · `US-WRK-043` TC-6 |
| 10 | **The connection drops after item 12 of 20 is acknowledged** (a second fixture run) | The phone's store marks 1–12 acknowledged; **the next sync starts at item 13**; items 1–12 are not re-sent; the server, had they been, would answer *duplicate* for each | Nothing is lost and nothing is added twice — the two halves of the same promise | **BR-WRK-042** · `US-WRK-044` TC-4 |
| 11 | **17:55 · M. Torres** opens `WO-4822` → **Readings** (`Work-033`) | READINGS: *Final read on old meter · kWh · 0–99,999 · Required · 48,221 · ▣ IMG-8841 · D. Ortiz · 15:12* · *Opening read on new meter · kWh · 0–999 · Required · **1,204 out of range** (red `FlagText`) · ▣ IMG-8842 · D. Ortiz · 16:02* · *New meter serial · — · — · Optional · E1P-77412 · none — not required*; footer **3 of 3 readings captured · 2 of 2 required photographs · Click a thumbnail for the full image, taken at, and device**; `ConsequenceBox` **Required means the job will not close without it; out of range never blocks.** | **`photo_required` and `photo_attachment_id` are TWO columns**, and a schema test asserts neither is derived from the other. Click ▣ IMG-8842 → the full image with *taken at 16:02 · device* from **a link that expires in four hours** (`GET /work-orders/{id}/attachments/{aid}`). ⛔ An order still open with a required photograph untaken shows the amber pill **missing — job cannot close** in this column — the state `WO-4822` was in at 16:01 and the phone refused; the drawn fourth row (*Voltage at socket*) is D-9 and is not asserted | **BR-WRK-040** · **BR-WRK-039** · **BR-WRK-047** · `US-WRK-049` TC-1/TC-5/TC-7 |
| 12 | **Retention (boundary — `OQ-WRK-1496`, ⚠ CLOSED 2026-09-04; THIS ROW DESCRIBED THE PRE-RULING WORLD UNTIL 2026-09-05).** | ⚠ **AMENDED — `retention_policy()` RETURNS AND DOES NOT RAISE.** The PO ruled **twelve months**, then an **export before deletion**, and a photograph **compressed at capture to 100 KB**. So: the period IS written down (`BR-WRK-048`), `work_documents.retention_policy()` answers it, and what still refuses is `prune_due()` — **for the ruling rather than for want of one**: the export path does not exist, so nothing may be deleted and the pruning job for Work kinds is **still not scheduled**. A spec asserting the old stub would assert a question the PO had already answered, which is `DEF-WRK-4030` exactly and is why this row is dated. | ⛔ A test asserting *photographs are kept seven years* **does not exist**, and `grep` of `apps/work/` for *seven years* / *retention* returns **0** — the blueprint's *"728 GB → 59 GB over seven years"* is its arithmetic, not a ruling. ⛔ `INSERT` of a `stored_documents` row with kind `work_order_note` is **refused by the CHECK** on PostgreSQL — the constraint is real (33 → 36 values) and the kind is not | **BR-WRK-048 (OPEN)** · **BR-WRK-047** · **OQ-WRK-1496** · `US-WRK-048` TC-3/TC-5/TC-7 |
| 13 | **ISOLATION — Lone Star Ridge WSC** | A queued item for a **Lone Star Ridge order on D. Ortiz's phone** (a swapped phone) → **`404`** on sync; the item is **marked failed and shown**, never silently dropped; Lone Star **cannot fetch a photograph**: the four-hour link for `IMG-8842` used under Lone Star's `app.tenant_id` → `404`; a pre-signed URL minted on Brazos Bend used on Lone Star's row → `404`; `/lone-star-ridge/work/mobile/` refuses D. Ortiz's session; Lone Star's `Work-033` for `WO-4822` → `404` | Lone Star's own photographs are its own nine or none; the receipts table is tenant-scoped, so a Lone Star key equal to a Brazos Bend key is **not** a duplicate | hard rule 1 · `US-WRK-044` TC-6 · `US-WRK-048` TC-6 · `US-WRK-049` TC-6 · `US-WRK-040` TC-5 |
| 14 | **INVARIANCE** | — | **No close activated anything; `accepted_by` is NULL on all three; zero `meter_reads` rows** — acceptance is `J61`/`J62`/`J64`'s act, the next morning. Nine photographs, nine rows, once. `completed_at` is the phone's time, the receipt time the server's, both kept. **No journal line, no money moved** — the rate snapshot is a stamp, not a posting (`BR-WRK-004`). Every act audited; the audit rows for the three closes carry the device's captured time | BR-MET-110 · **BR-WRK-042** · BR-WRK-004 · hard rules 1, 7 |

**This journey leaves (for downstream).** Three completed orders (`WO-4902`, `WO-4824`,
`WO-4822`) on `Work-009`, `accepted_by` NULL, `completed_at` at the phone's times · nine
`work_order_photo` documents at 1,600 px, once each · one reading flagged `in_range =
false` and accepted (`1,204 kWh`) · `WO-4822`'s `labour_rate_snapshot = 48.5000` stamped
at 16:07 · 43 receipts in `work_sync_receipts` · Lone Star Ridge unable to fetch any of
it. **Downstream:** `J62` step 14's acceptance of `WO-4822` (16 Mar 09:12) prices this
day's 52 minutes at **`$138.42`**, posts the `48,221 kWh` final read and the flagged
`1,204 kWh` opening read through metering's door, and generates `WO-4822-v1.pdf`.

## Boundaries — what this journey stops at, and why

| # | Not asserted | Because |
|---|---|---|
| a | The pruning job actually deleting anything | ⚠ **AMENDED 2026-09-05 — `OQ-WRK-1496` is CLOSED (2026-09-04), and this row used to say it was open.** How long is now RULED: twelve months, with an export first. What is not asserted is a DELETION, because `prune_due()` refuses while no export path exists — a boundary the ruling itself draws rather than a gap in it |
| b | A refused web sign-in for D. Ortiz | ⚠ **AMENDED 2026-09-05 — `OQ-WRK-1494` is CLOSED (2026-09-04, option (a)).** The refusal is real and reads *“Sign in on the field app.”*; it lives in `identity.services.sign_in`, which is the one place that knows which app a request came from. It is `J61` step 8's to assert, not this journey's — nothing on the phone waits on it |
| c | `WM-36`'s and `WM-38`'s exact wording | Unread cards. Everything here is from `WS-10`, `WS-12`, §3 steps 10–14 and `WM-48`'s worked figure. When read, the cards win and this file is stamped |
| d | Background push while the app is closed | The phone is a web app (`BR-WRK-045`); no push reached the phone between 08:13 and 17:40 and none was needed — the day was already in the store |
| e | Acceptance, activation, the report, the meter reads | The next morning's acts — `J61` step 10, `J62` steps 12–14, `J64` step 8 |
| f | The prototype's weekday, the three-job identity, the fourth reading | Recorded above as document disagreements; reported to the parent rather than corrected here |
