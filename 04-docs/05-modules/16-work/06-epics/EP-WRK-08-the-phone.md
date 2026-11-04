# EP-WRK-08 — The technician's phone: the shell, today's jobs, the job, the safety gate on both sides, the offline queue, and the close that activates nothing

**Module:** work · **Wave:** phase **2** of `CR-070` · **Screens:** `Work-010` · `Work-011` · `Work-012` · **Status:** draft (`CR-070`, 2026-09-03; **§14 read as far as card `WM-35`; `WM-36` and `WM-38`'s cards are UNREAD**; §15–§21 unread)

## Scope

**In:** the phone shell (ours — a web app, `BR-WRK-045`) · `WM-32` today's jobs · `WM-33` the job on the phone · `WM-34` the safety gate on the phone AND the server · `WM-36` offline capture and sync · `WM-38` the technician closes the job.

**Out:** readings that post and out-of-range flags (`EP-WRK-09`) · the login scope (`EP-WRK-04`, `US-WRK-023`) · the push (`EP-WRK-05`, `US-WRK-030`).

**Blueprint §14:** *"Stage E of the flow happens on a phone, in the technician's hand, often with no signal. Nothing of it exists. There is no app, no service worker, no manifest, no native shell, no offline store and no technician role."* And what does exist is a design, in eight sentences — *"three of them are rules, not descriptions: safety is blocking, out-of-range readings flag rather than refuse, and help is available offline."* The field app *"is a plan feature, already sold on the pricing page."*

⚠ **TWO STORIES ARE WRITTEN FROM THE FLOW TABLE, THE WIREFRAME AND THE CARD LIST ONLY** — `US-WRK-044` (`WM-36`) and `US-WRK-045` (`WM-38`) — because their cards sit past the point the text could be read. Each is marked `[from cards only — §14 rest unread]`. **Nothing in them is invented past what `WS-10`, `WS-12`, §3's steps 10–14 and §7's `POST /work-orders/{id}/field-result` carry.**

## Capability matrix (list screens only — B9 conformance)

No B9 list screen. `Work-010` is a day list on a phone with no toolbar; its order is fixed by rule (`BR-WRK-035`).

## Stories

---
id: US-WRK-040
epic: EP-WRK-08
module: work
screens: [Work-010, Work-011, Work-012]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-005, US-WRK-023]
journeys: [J61, J62, J65]
rules: [BR-WRK-045]
golden_tests: []
finance_calc: none
---
### US-WRK-040 — The phone shell: a web app, installable and offline-first, under `/{tenant}/work/mobile/`, with the technician's identity from their login

**1 · Details** — As **a technician**, I want **the field app on the phone I already carry**, so that **there is one codebase, one login and no store to publish through**.

**Ours to decide, and decided (law 13):** the phone is a **web app** — a manifest, a service worker and an offline store, served by the staff app's build at its own route family — **not a native shell**. The reasoning is the decision-log draft in `governance-rows.md`: no service worker or manifest exists today; the product is React and one build; a native shell is a second release train for a one-or-two-person utility's two technicians; and *"field app"* on the pricing page promises a capability, not a store listing. **Three surfaces:** `Work-010` Today · `Work-011` the job (safety, then work) · `Work-012` readings, parts, signature, close. Bottom tabs *Today · Week · Parts · Help* as `WS-10` draws them. `features/work/mobile/**` goes on `route-b-migrated.txt` in its first commit.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-045` | The phone is a web app, installable, offline-first | PROPOSED — decision-log draft |
| `BR-WRK-043` | Login scope OPEN — the shell signs in with the ordinary session and the surface refusal is `US-WRK-023`'s stub | OPEN |
| B14 rule 21 | Tailwind only, on the migrated list | CONFIRMED |
| hard rule 1 | The phone's every read is tenant-scoped through the same API | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open `/{tenant}/work/mobile/` on a phone | The manifest offers *Add to home screen*; the service worker registers; Today renders |
| TC-2 | Sign in as D. Ortiz | The technician profile resolves from the user (`US-WRK-020`); Today reads *D. Ortiz* |
| TC-3 · **negative** | Sign in as a user with no technician profile | An empty day and one sentence — *"No field work for this login"* (six words) — never an error page |
| TC-4 · **negative** | Airplane mode after first load | Today, the job and help render from the offline store; the marker reads *◍ offline · synced 08:12* |
| TC-5 · **tenant isolation** | D. Ortiz's phone points at `/lone-star-ridge/work/mobile/` | Refused — the session is Brazos Bend's |
| TC-6 · **UI law** | `features/work/mobile/**` | On `route-b-migrated.txt`; no `WS-`/`WM-`/`BR-` in rendered copy; every refusal ≤ 6 words |
| TC-7 | The four bottom tabs | *Today · Week · Parts · Help*; Week is Today's list for the week ahead; Parts is the job's planned parts (`US-WRK-050`); Help is the offline pack (`US-WRK-042`) |

**4 · Test Data** — D. Ortiz, Sun 15 Mar · 4 jobs · 2 done; a user `clerk@brazosbend.example` with no profile.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| manifest · service worker · offline store | phone | ours | none — client assets; IndexedDB for the store | — | — | the store holds the day's job bundles and the outbound queue |
| identity | phone | `WS-24` | `technicians.user_id` | — | session | one profile per user |

**6 · Acceptance** — **Given** a technician with a login and a profile, **when** they open the field app on their phone, **then** it installs, signs in, shows today, and keeps working with no signal.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None new; `OQ-WRK-1494` is `US-WRK-023`'s.

---
id: US-WRK-041
epic: EP-WRK-08
module: work
screens: [Work-010]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-040, US-WRK-025, US-WRK-032]
journeys: [J61, J62, J65]
rules: [BR-WRK-035, BR-WRK-036]
golden_tests: []
finance_calc: none
---
### US-WRK-041 — Today's jobs on the phone: a route-ordered day, an honest offline state, and the dog and the gate code carried to the point of work (`WM-32`)

**1 · Details** — As **D. Ortiz at 09:41 with no signal**, I want **to see *4 jobs · 2 done* for Sun 15 Mar with the next card reading `WO-4822 · Meter exchange · 221 Oak Ave · 15:30 · 45 min · ⚠ Access: dog in rear yard · gate code 4417`**, so that **I drive my route and know what is behind the gate**.

*"Sorted by appointment time, not priority — a technician drives a route, and an Urgent job across town does not jump the one they are standing outside. Priority shows as a pill; it does not reorder."* *"The offline marker is always visible. 'synced 08:12' is the last time the phone reached the server, and it is the single most important thing on this screen."* Access notes and hazards come from the template's Details section (`US-WRK-032`) and the premises' own access notes. The restoration clock on a reconnect is r10's own: *"⏱ restoration clock running · 1h 20m"*.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-035` | Ordered by appointment time; priority is a pill | CONFIRMED — `WM-32` |
| `BR-WRK-036` | The offline marker with the last sync time is always visible | CONFIRMED — `WS-10` |
| `BR-WRK-008` | Details ride with the job as the order's copy | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Four jobs: `WO-4901` 08:30 done · `WO-4902` 09:15 done · `WO-4824` due 12:00 Urgent · `WO-4822` 15:30 Normal | Order on screen: 4901 · 4902 · **4824 · 4822** — by time; `WO-4824`'s Urgent is a pill |
| TC-2 · **negative** | Move `WO-4822` to Urgent | It **does not** move above `WO-4824` — the pill changes, the order does not |
| TC-3 | Offline since 08:12 | *◍ offline · synced 08:12* visible on every card and the header; never hidden by scroll |
| TC-4 · **negative** | The phone has never synced | *◍ offline · never synced* — the marker never reads a time it does not have |
| TC-5 | `WO-4822`'s card | *⚠ Access: dog in rear yard · gate code 4417* from the order's details row |
| TC-6 · **tenant isolation** | The day bundle | Contains only orders assigned to this technician on this tenant; a query for another technician's day is `403` |
| TC-7 | The reconnect | `WO-4824` shows *⏱ restoration clock running · 1h 20m* — from the payment-cleared time, r10's own sentence |

**4 · Test Data** — Sun 15 Mar 2026 (the prototype's *Wed*; 15 March 2026 is a Sunday — `DEF-WRK-3576`) · D. Ortiz: `WO-4901` Service drop · Electric · `3450 Oak Ridge Dr` · 08:30 · Done · `WO-4902` Meter set 🚩 · 09:15 · Done · `WO-4824` Reconnect · `903 Birch Ln · A-10222` · due 12:00 · Urgent · `WO-4822` Meter exchange · `221 Oak Ave · A-10688` · 15:30 · North · Route 1 · 45 min · dog · gate 4417. Synced 08:12.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| the day | `Work-010` | `WM-32` | `GET /work/mobile/today` → the technician's assigned orders with their bundles | list | computed | ordered by `window_start` then `due_at` |
| synced at | `Work-010` | `WS-10` | client store: last successful sync timestamp | ts | client | shown in words |
| access · hazards · gate code | `Work-010` | `WS-10` | `work_order_details` + premises access notes via `customers_seam` | text | copied | — |
| restoration clock | `Work-010` | r10 | derived: now − the source event's time (payment cleared) | duration | computed | reconnect orders only |

**6 · Acceptance** — **Given** four jobs, **when** the technician opens Today offline, **then** the jobs are in appointment order, the marker says when the phone last reached the server, and the next card carries the dog and the gate code.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-042
epic: EP-WRK-08
module: work
screens: [Work-011, Work-012]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-041, US-WRK-032]
journeys: [J61, J62]
rules: [BR-WRK-038]
golden_tests: []
finance_calc: none
---
### US-WRK-042 — The job on the phone: everything copied from the template, and nothing on the screen was fetched because it arrived with the job (`WM-33`)

**1 · Details** — As **a technician tapping `WO-4822`**, I want **to see *Miller, Sarah · (512) 555-0114*, three safety checks, seven tasks totalling 45 min, three readings, three parts and three help items**, so that **the job is doable in a meter pit with no signal**.

*"One screen per job carrying everything copied from the template: customer and contact, safety, tasks with their minutes and photo flags, readings with their bounds, parts planned, and the help pack."* **HELP — 3 ITEMS, OFFLINE:** *Meter exchange SOP v4 · Supervisor · M. Torres · (512) 555-0138 · AMI activation hotline · ext 44*. *"A meter pit in a rural service area has no signal, and the SOP is the thing that tells the technician what to do when the job does not match the template."*

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-038` | Help is carried with the job and available offline | CONFIRMED — r10 verbatim |
| `BR-WRK-008` | The job is the order's copy | CONFIRMED |
| `BR-WRK-042` | The bundle is fetched at sync, never on tap | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Tap `WO-4822` offline | Customer, contact, 3 safety, 7 tasks · 45 min, 3 readings, 3 parts, 3 help — **zero network requests** during the tap |
| TC-2 | Tap the SOP | The PDF opens from the offline store — it came with the bundle at sync |
| TC-3 · **negative** | A help document was added to the template after the job synced | The phone shows the job's copy (two items, say) — not the template's three — until the job is re-synced, and the copy rule says the job's copy is right |
| TC-4 · **negative** | The bundle exceeds the store's budget (a 40 MB SOP) | The document is listed with *download when online*; the job still opens; nothing silently dropped |
| TC-5 | The customer's phone number | A tap-to-call link; the number is the account's contact via `customers_seam`, never typed onto the order |
| TC-6 · **tenant isolation** | A bundle id from another tenant | `404` on sync |

**4 · Test Data** — `WO-4822`'s bundle from `US-WRK-032`; customer Miller, Sarah · `(512) 555-0114`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| the bundle | `Work-011` | `WM-33` | `GET /work/mobile/jobs/{id}` → the order + its six copy tables + customer contact + help documents (as pre-signed GETs, fetched into the store at sync) | json | computed at sync | versioned by the order's `updated_at` |
| help documents | `Work-011` | `WS-11` | `work_order_help.ref` → `stored_documents` | files | copied | cached in the offline store |

**6 · Acceptance** — **Given** the day synced at 08:12, **when** the technician opens a job at 15:34 with no signal, **then** everything the template put on it is there, including the SOP.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-043
epic: EP-WRK-08
module: work
screens: [Work-011]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-042]
journeys: [J61, J62]
rules: [BR-WRK-037]
golden_tests: []
finance_calc: none
---
### US-WRK-043 — Safety checks block the task list — on the phone AND on the server, or you have built neither (`WM-34`)

**1 · Details** — As **the utility**, I want **two of three safety checks ticked to mean LOCKED, on the phone and at the API**, so that **a completion with an unticked mandatory safety row is refused by the server naming the row**.

r10, verbatim: *"Safety checks are blocking on the phone — the task list stays locked until all are ticked."* *"Two of three ticked is not two-thirds unlocked; it is locked."* *"The lock is on the phone, and it must also be on the server. A screen that greys a list is a convenience; a server that refuses a completion with an unticked mandatory safety row is the guarantee. Build both or you have built neither."* **`CR-070` §12 gate 2** asserts the server half. The Close button reads *"Close job — finish safety first"* (five words, B14 rule 33).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-037` | Safety blocks on the phone and the server refuses, naming the row | CONFIRMED — `WM-34`; `CR-070` §12 gate 2 |
| `BR-SHL-025` | The server independently enforces every mutating call | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | 2 of 3 safety ticked | **SAFETY — 2 OF 3 · TASKS LOCKED**; the seven tasks visibly locked; Close reads *Close job — finish safety first* |
| TC-2 | Tick the third | Tasks unlock; the header reads **TASKS — 7 STEPS · 45 MIN** |
| TC-3 · **negative · server** | `POST /work-orders/WO-4822/field-result` directly, with `safety[2].ticked = false` | Refused, naming *Confined space check where pit-set*; `state` unchanged; no audit of a completion |
| TC-4 · **negative · server** | The same with a NON-mandatory safety row unticked | Accepted — only mandatory rows gate |
| TC-5 · **gate** | Remove the server check | `g7x_safety_gate_server_side.py` FAILS — **proved RED first** (law 7) |
| TC-6 · **negative** | Tick a task while locked, by tampering with the client store | The tick is refused at sync — the server re-derives the lock from the safety rows' timestamps, never from the client's word |
| TC-7 · **tenant isolation** | The field-result route for another tenant's order | `404` |

**4 · Test Data** — `WO-4822` safety: *Isolate at the service head before removal* ☑ · *Check for backfeed / on-site generation* ☑ · *Confined space check where pit-set* ☐ (all three mandatory).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| safety tick | `Work-011` | `WM-34` | `work_order_safety.ticked_at`, `.ticked_by` | ts · uuid | phone | append at sync |
| the lock | `Work-011` | `WM-34` | derived: all `is_mandatory` rows ticked | bool | computed on both sides | the server's derivation wins |
| the gate | — | `CR-070` §12 | `10-scripts/gates/g7x_safety_gate_server_side.py` | check | — | asserts the refusal path exists and is tested |

**6 · Acceptance** — **Given** two of three safety checks ticked, **when** the technician looks at the tasks, **then** they are locked — **and when** a completion is posted straight to the API with one unticked, **then** it is refused naming the row.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-044
epic: EP-WRK-08
module: work
screens: [Work-010, Work-012]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-040, US-WRK-048]
journeys: [J65]
rules: [BR-WRK-042]
golden_tests: []
finance_calc: none
---
### US-WRK-044 — Offline capture and sync: the queue that never loses a day's work and never adds it twice (`WM-36`) `[from cards only — §14 rest unread]`

**1 · Details** — As **a technician after a day with no signal**, I want **three closed jobs to send when I am back online, once**, so that **nine photographs land once each and a re-sync of the same three jobs adds nothing**.

**`WM-36`'s own card is past the readable text.** What is readable: §3 step 10 *"working offline"*; §7's *"The only offline in the codebase is network-error handling in the API client"*; `WS-10`'s marker *◍ offline · synced 08:12*; `WS-12`'s *◍ offline · 1 job to send* and the button *Close job · send when back online*; `WM-48`'s *"the row is written on sync with a per-image idempotency key"* and its worked figure: *"A technician syncs three jobs after a day with no signal; nine photographs land once each … and a re-sync of the same three jobs adds nothing."* **This story is built from those and nothing more.** Every captured act — a safety tick, a task tick, a reading, a part used, a photo, a signature, a close — is a queued item with its own idempotency key; the sync posts them in order; the server accepts each once. ⚠ **PROVE IT ON POSTGRESQL** (law 14): a duplicate key refused inside a batch must not poison the rest — a savepoint per item, and the comment must say so.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-042` | Queued locally with a per-item idempotency key; a re-sync adds nothing | PROPOSED — from `WM-48`; `WM-36` unread |
| `BR-WRK-036` | The marker says what is waiting to send | CONFIRMED |
| law 14 | A refused item inside a batch needs a savepoint | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Close three jobs offline with nine photos; go online | One sync; three `field-result`s, nine attachment rows, each once; the marker clears to *synced 17:40* |
| TC-2 · **negative** | Sync the same queue again | **Zero** new rows anywhere — every item's key was seen |
| TC-3 · **negative · PostgreSQL** | Item 5 of 20 carries a key already accepted | Items 1–4 and 6–20 commit; item 5 is reported as a duplicate; **run under `config.settings.local` on real PostgreSQL** — the SQLite suite cannot see the aborted-transaction trap |
| TC-4 · **negative** | The connection drops after item 12 of 20 is acknowledged | The next sync starts at 13; items 1–12 are not re-sent because their acknowledgements are in the store |
| TC-5 | Order of application | Safety ticks before task ticks before the close — the server refuses a close whose safety rows arrive later (`US-WRK-043`), so the queue preserves capture order |
| TC-6 · **tenant isolation** | A queued item for another tenant's order (a swapped phone) | `404`; the item is marked failed and shown, never silently dropped |
| TC-7 | *◍ offline · 1 job to send* | Counts jobs with a queued close; reads *2 jobs to send* for two |

**4 · Test Data** — Three jobs (`WO-4902`, `WO-4824`, `WO-4822`) closed 10:20, 12:05 and 16:07 (⚠ this read `WO-4821` closed 15:10–17:35 until 2026-09-03 — r10's *Disconnect for non-payment* of 16 August, which is not on `US-WRK-041`'s day list; the day list wins, `DEF-WRK-3577`); nine photographs at 1,600 px; keys `ortiz-01-2026-03-15-…-001` … `-020`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| the queue | phone | `WM-36` (unread) · `WM-48` | client store: ordered items `{key, order_id, kind, payload, captured_at}` | — | client | one key per act |
| sync | — | `WM-36` (unread) | `POST /work/mobile/jobs/{id}/sync` — a batch; per-item results | — | phone | `work_sync_receipts(key)` unique — the server's memory of what it accepted `[our table — §16 unread]` |
| photo upload | — | `WM-48` | direct pre-signed PUT, then the row on sync | — | phone | per-image key |

**6 · Acceptance** — **Given** three jobs closed offline, **when** the phone comes online, **then** everything lands once, **and** syncing again changes nothing — proved on PostgreSQL.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None minted. ⚠ **`WM-36`'s card is unread**; if §14's remaining text states a rule this story does not, that text wins and the story is amended before code.

---
id: US-WRK-045
epic: EP-WRK-08
module: work
screens: [Work-012]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-043, US-WRK-044, US-WRK-047]
journeys: [J61, J62, J65]
rules: [BR-WRK-041]
golden_tests: []
finance_calc: none
---
### US-WRK-045 — The technician closes the job from the phone: `submit_field_result` and nothing more (`WM-38`) `[from cards only — §14 rest unread]`

**1 · Details** — As **a technician at 16:08 with 7 of 7 done**, I want **to pick an outcome and press *Close job · send when back online***, so that **the office reviews it — because closing does not switch the supply on**.

**`WM-38`'s card is past the readable text.** What is readable: §3 step 14 *"The technician closes the job on the phone; it syncs and becomes Completed — ENGINE ONLY"*; §7 *"Field sends its result — `POST /work-orders/{id}/field-result` — REACHABLE"*; `WS-12` in full. *"Proves the phone's close is the same act as `submit_field_result`, and nothing more. Everything captured here maps onto columns and tables the build specification already names… the outcome to the five tokens that already ship. The phone adds no new vocabulary; it adds a surface."* The last line is the contract: *"Closing does not switch the supply on. The office reviews this and accepts it."* Outcomes: *Passed · Partly done · Failed · Waiting on someone* (four drawn; the fifth token, `cancelled`, is the dispatcher's, not the phone's).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-041` | The close is `submit_field_result`; activates nothing; offline label | CONFIRMED — `WS-12`, `BR-MET-110` |
| `BR-WRK-040` | A missing required photograph stops the close | CONFIRMED |
| `BR-WRK-046` | A required signature or its refusal is needed to close | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | 7 of 7, readings captured, parts recorded, signed, *Passed*, Close (online) | `submit_field_result`: `state = completed`, `outcome = passed`, `completed_at = 16:07`, `accepted_by` NULL; the order is on `Work-009`; **the connection's service state is unchanged** |
| TC-2 | The same offline | The button reads *Close job · send when back online*; the item queues; the marker reads *1 job to send* |
| TC-3 · **negative** | Close with a mandatory task unticked | Refused on the phone and by the server, naming the task |
| TC-4 · **negative** | Close with a required photograph missing (`US-WRK-049`) | Refused naming the reading; an out-of-range value does **not** refuse |
| TC-5 · **negative** | Close, then tap Close again | Idempotent — the second is a no-op on the same key |
| TC-6 · **tenant isolation** | The close for another tenant's order | `404` |
| TC-7 | *Waiting on someone* | `outcome = waiting_on_someone_else`; a reason required; the order still completes and queues for review — the office decides what to wait on |

**4 · Test Data** — `WO-4822` at 16:08: readings 48,221 kWh in range · 1,204 kWh out of range 0–999 flagged · serial `E-5099-114` 📷; parts `MTR-E1P` 1 of 1 · `SEAL-01` 1 of 1 · `GSKT-STD` 0 of 1 not used; signed Sarah Miller 16:07; outcome Passed.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| outcome | `Work-012` | `WS-12` | `work_orders.outcome` — the five tokens that ship | enum | phone | four offered on the phone |
| close | `Work-012` | `WM-38` | `POST /work-orders/{id}/field-result` (exists) — via the sync batch | — | phone | safety, mandatory tasks, required photos, signature-or-refusal |
| `field_data` | — | exists | `work_orders.field_data` — kept as the free JSON the built acceptance reads (`set_reads` etc.), populated from the copy tables at close | jsonb | system | so `accept_field_result` keeps working unchanged |

**6 · Acceptance** — **Given** a finished job, **when** the technician closes it, **then** it is completed and awaiting approval and no supply has changed state — **and** offline, the button says what will happen.

**7 · Finance Calculation** — N/A. (The report and its arithmetic are generated on ACCEPTANCE, `US-WRK-053`, never on close.)

**8 · Open Questions** — None minted. ⚠ **`WM-38`'s card is unread**; the same caveat as `US-WRK-044`.
