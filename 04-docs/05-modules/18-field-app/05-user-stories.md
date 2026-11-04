# 18 · Field app — the 84 stories

**Epics `EP-FLD-01` … `EP-FLD-14` · Stories `US-FLD-001` … `US-FLD-084`.** Both families are new (decision log 2026-10-21: module code FLD, *"unused before today"*). Stories are **zero-padded to three, chosen at birth**, the spelling `US-WRK-001` took; pattern `US-FLD-\d{3,5}(?!\d)`, and the lookahead is load-bearing (`DEF-2804`).

**One story per business requirement, and the number IS the requirement: `US-FLD-nnn` is requirement nnn (zero-padded to three)** of `01-overview.md` §6. Every story is in the canonical eight-section format (`_templates/01-story-template.md`) and lives in its epic's file under `06-epics/`, the way `16-work` does it.

**Test cases are written from the design's rules (R-numbers), its walkthrough (E2E-nn) and its boards — never invented.** Figures drawn on a board are illustrations (B14 rule 37) and are used as test data only. Every story carries at least one negative case and one tenant-isolation case.

**`wave:`** is the build order: **0** = the design's Phase 1 foundations and 1b telemetry (T-06–T-14, T-73–T-76) — engine work every screen sits behind; **1** = telemetry; **2–10** = the field screen waves (T-15–T-26); **11** = the reading screens; **12** = the tablet frames (T-27–T-29).

---

## 1 · The fourteen epics

| Epic | Name | Stories | Screens (the design's flow group) | Design tasks |
|---|---|---|---|---|
| [`EP-FLD-01`](06-epics/EP-FLD-01-getting-in.md) | Getting in — splash, sign in, activation, the shared handset and the security underneath | 4 | FF-01 to FF-08, FF-53, FF-56, FF-57 | T-15 (FF-01–FF-08), T-12 |
| [`EP-FLD-02`](06-epics/EP-FLD-02-the-day.md) | The day — Home, Today, Nearby, refresh and the day staying true | 7 | FF-09 to FF-12, FF-63 | T-16 |
| [`EP-FLD-03`](06-epics/EP-FLD-03-the-job.md) | The job — getting there, opening it, the template, the clocks, handing it back | 6 | FF-13 to FF-16, FF-28, FF-58 | T-17, T-18 |
| [`EP-FLD-04`](06-epics/EP-FLD-04-doing-the-work.md) | Doing the work — tasks, checklists, readings, photographs, materials and parts | 8 | FF-17 to FF-24, FF-59 | T-19 |
| [`EP-FLD-05`](06-epics/EP-FLD-05-customer-and-money.md) | The customer, the money and the record on site | 8 | FF-25 to FF-31, FF-60, FF-61 | T-20 |
| [`EP-FLD-06`](06-epics/EP-FLD-06-closing.md) | Closing — signature, the four outcomes, reopen and what comes back | 2 | FF-32 to FF-36 | T-21 |
| [`EP-FLD-07`](06-epics/EP-FLD-07-raising-work-assets-alerts.md) | Raising work, assets and alerts | 8 | FF-37 to FF-43, FF-62 | T-22, T-23 |
| [`EP-FLD-08`](06-epics/EP-FLD-08-the-technician.md) | The technician — profile, availability, shifts, timesheet, admin time | 2 | FF-44 to FF-48 | T-24 |
| [`EP-FLD-09`](06-epics/EP-FLD-09-kit-sync-settings.md) | Kit, sync, settings and themes — and the engine underneath every screen | 20 | FF-49 to FF-55 | T-25, T-26, T-10, T-11, T-73–T-76 |
| [`EP-FLD-10`](06-epics/EP-FLD-10-reads-the-route.md) | Reads — getting a route | 4 | RW-01 to RW-05 | Reads tab §1 |
| [`EP-FLD-11`](06-epics/EP-FLD-11-reads-the-stop.md) | Reads — the stop | 3 | RW-06 to RW-12 | Reads tab §2 |
| [`EP-FLD-12`](06-epics/EP-FLD-12-reading-and-evidence.md) | Reads — the reading and its evidence | 8 | RW-13 to RW-17 | Reads tab §3 |
| [`EP-FLD-13`](06-epics/EP-FLD-13-off-the-list.md) | Reads — what does not fit the list | 2 | RW-18 to RW-21 | Reads tab §4 |
| [`EP-FLD-14`](06-epics/EP-FLD-14-turning-in.md) | Reads — progress and turning it in | 2 | RW-22 to RW-29 | Reads tab §5 |

## 2 · Every story

| Story | Requirement (short title) | Epic | Wave | Status | Screens |
|---|---|---|---|---|---|
| `US-FLD-001` | Phones and tablets — one native app, four tablet frames | `EP-FLD-09` | 0 | ready | FF-09, FF-54, FF-55 |
| `US-FLD-002` | Offline-first — the day opens instantly with no signal, and the phone says how far it is in step | `EP-FLD-02` | 0 | ready | FF-08, FF-10, FF-28 |
| `US-FLD-003` | One handset, several technicians in turn — unsent work stays with whoever captured it | `EP-FLD-01` | 0 | ready | FF-05, FF-09, FF-53 |
| `US-FLD-004` | Two-phase sync — data first, then photographs, compressed, with local receipts | `EP-FLD-09` | 0 | ready | FF-50 |
| `US-FLD-005` | Position when a job opens, and every photograph stamped with date, time, coordinates, technician and order | `EP-FLD-04` | 5 | ready | FF-07, FF-15, FF-21, FF-22 |
| `US-FLD-006` | Identity and availability — profile with photo, language, availability, shifts, time off, holidays | `EP-FLD-08` | 9 | ready | FF-44, FF-45, FF-46 |
| `US-FLD-007` | Map — stops coloured by status, one tap out to Google or Apple Maps | `EP-FLD-03` | 4 | ready | FF-13, FF-14, RW-04 |
| `US-FLD-008` | Service order execution — window order, safety first, depart and arrive, the labour clock, four outcomes | `EP-FLD-03` | 4 | ready | FF-10, FF-14, FF-15, FF-16, FF-34 |
| `US-FLD-009` | Meter readings with explicit units — out of range is flagged, never blocks | `EP-FLD-04` | 5 | ready | FF-20 |
| `US-FLD-010` | Asset data and scanning — verify the meter against the record | `EP-FLD-07` | 8 | ready | FF-38, FF-39 |
| `US-FLD-011` | Field-raised orders — auto-filled with premise, account, customer and position | `EP-FLD-07` | 8 | ready | FF-37, RW-21 |
| `US-FLD-012` | Customer, tariff, live balance and the cleared-payment check — read only | `EP-FLD-05` | 6 | ready | FF-25, FF-26 |
| `US-FLD-013` | Push and emergency alerts — distinct sound and vibration, on a locked device | `EP-FLD-07` | 8 | ready | FF-42, FF-43, FF-52, FF-07 |
| `US-FLD-014` | Customer signature, or a recorded refusal | `EP-FLD-06` | 7 | ready | FF-33, FF-34 |
| `US-FLD-015` | Mid-day re-sequencing — an emergency arrives and the day re-orders | `EP-FLD-02` | 3 | ready | FF-10, FF-42 |
| `US-FLD-016` | Van stock and parts consumption on the phone | `EP-FLD-04` | 5 | ready | FF-23, FF-24, FF-49 |
| `US-FLD-017` | Labour timesheet, not only a timer — where the hours go | `EP-FLD-08` | 9 | ready | FF-47, FF-48 |
| `US-FLD-018` | Conditional checklists — questions that branch on the answer | `EP-FLD-04` | 5 | ready | FF-19 |
| `US-FLD-019` | Asset service history on site | `EP-FLD-07` | 8 | ready | FF-40 |
| `US-FLD-020` | Crew jobs — more than one technician on an order | `EP-FLD-05` | 6 | ready | FF-29 |
| `US-FLD-021` | SOPs and safety documents ride with the job and open offline | `EP-FLD-03` | 4 | ready | FF-28, FF-15 |
| `US-FLD-022` | Voice capture for notes — works with gloves on and wet hands | `EP-FLD-05` | 6 | ready | FF-30, FF-32, FF-18 |
| `US-FLD-023` | Pending and nearby work — see unassigned orders and claim one where I am standing | `EP-FLD-02` | 3 | blocked | FF-11, FF-12 |
| `US-FLD-024` | Reopen my own closed job before the office accepts it, or raise the next one | `EP-FLD-06` | 7 | ready | FF-35, FF-36, FF-37 |
| `US-FLD-025` | A real-time check before an irreversible act — stale money is warned, never blocked | `EP-FLD-05` | 6 | ready | FF-27 |
| `US-FLD-026` | The job shows the whole template — safety, tasks, materials, readings and help, each with a count and a state | `EP-FLD-03` | 4 | ready | FF-15 |
| `US-FLD-027` | Photos belong to the task and the reading, as the template defines — the gallery is a review | `EP-FLD-04` | 5 | ready | FF-17, FF-20, FF-21, FF-22 |
| `US-FLD-028` | Add a task or a material in the field, with a reason, shown as a variance | `EP-FLD-04` | 5 | ready | FF-18, FF-23, FF-17 |
| `US-FLD-029` | Travel and time on the job — depart, arrive, start, pause, correct | `EP-FLD-03` | 4 | ready | FF-15, FF-47 |
| `US-FLD-030` | Notes, remarks and a stamped status history | `EP-FLD-05` | 6 | ready | FF-30, FF-31 |
| `US-FLD-031` | A second technician on the job, with their own time | `EP-FLD-05` | 6 | ready | FF-29 |
| `US-FLD-032` | Splash, three intro screens, sign in, forgot password and sign out | `EP-FLD-01` | 2 | ready | FF-01, FF-02, FF-03, FF-04, FF-05, FF-06, FF-53 |
| `US-FLD-033` | Settings in full | `EP-FLD-09` | 10 | ready | FF-51, FF-52, RW-29 |
| `US-FLD-034` | A technician taps, never types | `EP-FLD-09` | 10 | ready | FF-06, FF-18, FF-51 |
| `US-FLD-035` | Built for gloves and weather — 56 pt primary, 48 pt any control, 8 pt clear; three themes | `EP-FLD-09` | 10 | ready | FF-54, FF-55, FF-51 |
| `US-FLD-036` | The app version is visible, so a defect report names a build | `EP-FLD-09` | 10 | ready | FF-01, FF-09, FF-51 |
| `US-FLD-037` | Search and filter on every list, with criteria declared per screen | `EP-FLD-02` | 3 | ready | FF-10, FF-11, FF-35, FF-41 |
| `US-FLD-038` | Scanning is the first-class way to find an asset; typing is the fallback | `EP-FLD-07` | 8 | ready | FF-38, FF-41, RW-08, RW-11 |
| `US-FLD-039` | A search that cannot see everything says so | `EP-FLD-07` | 8 | ready | FF-41, RW-08 |
| `US-FLD-040` | A route of 500 to 1,000 readings captured offline and sent at once | `EP-FLD-14` | 11 | ready | RW-22, RW-23, RW-25, RW-26, RW-27, RW-28 |
| `US-FLD-041` | Captured work sent in batches of fifty, in capture order, resumably | `EP-FLD-09` | 0 | ready | FF-50, RW-26 |
| `US-FLD-042` | The server answers for every item — accepted, duplicate or refused | `EP-FLD-09` | 0 | blocked | FF-50, RW-26, RW-27 |
| `US-FLD-043` | Four refresh triggers — pull, coming forward, a push for one record, every fifteen minutes on shift | `EP-FLD-02` | 0 | ready | FF-10, FF-50 |
| `US-FLD-044` | A refresh is a delta, never a re-download | `EP-FLD-09` | 0 | ready | FF-50, FF-08 |
| `US-FLD-045` | A delta carries removals — a job reassigned away leaves the handset | `EP-FLD-02` | 0 | ready | FF-10 |
| `US-FLD-046` | Photographs upload after the data, one at a time, resumably, even with the app closed | `EP-FLD-09` | 0 | ready | FF-50, FF-21 |
| `US-FLD-047` | Photographs wait for wi-fi by default, compressed before queueing | `EP-FLD-09` | 0 | blocked | FF-51, FF-50 |
| `US-FLD-048` | Nothing unsent is ever deleted | `EP-FLD-09` | 0 | ready | FF-53, FF-50 |
| `US-FLD-049` | Data leaves the handset once it is safely on the server | `EP-FLD-09` | 0 | ready | FF-50, FF-35, RW-27 |
| `US-FLD-050` | The mobile allowance is budgeted and visible; the sync screen counts items, not bytes | `EP-FLD-09` | 0 | ready | FF-50 |
| `US-FLD-051` | Crash reporting that survives a shift offline | `EP-FLD-09` | 1 | ready | FF-51 |
| `US-FLD-052` | Product analytics and feature flags, with no customer data and never ahead of the work | `EP-FLD-09` | 1 | ready | FF-51 |
| `US-FLD-053` | Meter reading is a mode of the same app | `EP-FLD-10` | 11 | ready | RW-01, FF-63, FF-09 |
| `US-FLD-054` | A route is downloaded whole, at the depot, and reaches 100% before leaving | `EP-FLD-10` | 11 | ready | RW-02, RW-03, RW-01 |
| `US-FLD-055` | The unit of work is the address — a stop holds every meter at it | `EP-FLD-11` | 11 | ready | RW-05, RW-06, RW-07, RW-12 |
| `US-FLD-056` | Nearest first by default, the office's walk order one tap away | `EP-FLD-10` | 11 | ready | RW-05, RW-04 |
| `US-FLD-057` | The previous reading and the expected range are both on screen | `EP-FLD-11` | 11 | ready | RW-09, RW-10 |
| `US-FLD-058` | The customer's name, the unit label and the account number are shown at the stop | `EP-FLD-11` | 11 | ready | RW-06, RW-09, RW-11 |
| `US-FLD-059` | An out-of-range reading is warned and then accepted | `EP-FLD-12` | 11 | ready | RW-15, RW-16, RW-09 |
| `US-FLD-060` | Eight seeded reasons a meter cannot be read — the utility's own list | `EP-FLD-13` | 11 | ready | RW-17 |
| `US-FLD-061` | A meter not on the route is scanned — read it if known, add it if not | `EP-FLD-13` | 11 | ready | RW-18, RW-19, RW-20, RW-21 |
| `US-FLD-062` | One reader per route for now — nothing that forbids splitting later | `EP-FLD-10` | 11 | ready | RW-01 |
| `US-FLD-063` | Position at the moment the reading is saved, with its distance to the meter's recorded place | `EP-FLD-12` | 11 | ready | RW-13, RW-09 |
| `US-FLD-064` | A poor fix or no fix warns and still accepts | `EP-FLD-12` | 11 | ready | RW-13, RW-09 |
| `US-FLD-065` | Date and time stamped automatically, both clocks kept | `EP-FLD-12` | 11 | ready | RW-13 |
| `US-FLD-066` | The reader's status comes from what they already did | `EP-FLD-12` | 11 | ready | RW-13, RW-09, RW-17 |
| `US-FLD-067` | A photograph comes from the camera only, with the stamp burned in | `EP-FLD-12` | 11 | ready | RW-14, RW-24 |
| `US-FLD-068` | A remark is spoken by default, typed as the fallback, never mandatory | `EP-FLD-12` | 11 | ready | RW-09, RW-13 |
| `US-FLD-069` | The reading prompt decides when a photograph is required | `EP-FLD-12` | 11 | ready | RW-09, RW-15, RW-17 |
| `US-FLD-070` | Activate an account the office created — a six-character code, my own password, this device by name | `EP-FLD-01` | 2 | ready | FF-56, FF-57 |
| `US-FLD-071` | Hand an assigned job back, with a reason | `EP-FLD-03` | 4 | ready | FF-58, FF-15 |
| `US-FLD-072` | Add a reading the template did not ask for | `EP-FLD-04` | 5 | ready | FF-59 |
| `US-FLD-073` | Asset papers for a new asset — camera, file or typed, travelling with the job | `EP-FLD-05` | 6 | ready | FF-60 |
| `US-FLD-074` | Several photographs on one task, as many as the template says | `EP-FLD-04` | 5 | blocked | FF-17, FF-20, FF-21 |
| `US-FLD-075` | A reconnect checks the reconnect fee as its own question, beside the arrears | `EP-FLD-05` | 6 | ready | FF-61 |
| `US-FLD-076` | Raising a work order starts by picking a template | `EP-FLD-07` | 8 | ready | FF-62, FF-37 |
| `US-FLD-077` | Every reading screen works on a tablet | `EP-FLD-14` | 12 | ready | RW-05, RW-09, RW-22, RW-28 |
| `US-FLD-078` | Home — both modules at a glance: what is left and what is next | `EP-FLD-02` | 3 | ready | FF-63, FF-09 |
| `US-FLD-079` | The code mirrors the server's module boundaries, and every screen has a door | `EP-FLD-09` | 0 | ready | FF-09 |
| `US-FLD-080` | Security that never stops capture — two credentials, encryption at rest, scoping on the handset, device registration, auto-lock | `EP-FLD-01` | 0 | blocked | FF-05, FF-56, FF-57, FF-53, FF-51 |
| `US-FLD-081` | Every screen's tables are written down, as a matrix | `EP-FLD-09` | 0 | ready | — |
| `US-FLD-082` | Queried means a column; the wire shape and the local shape are two declared things | `EP-FLD-09` | 0 | ready | — |
| `US-FLD-083` | Deleting after sync is specified, not implied | `EP-FLD-09` | 0 | ready | FF-50 |
| `US-FLD-084` | Barcode, QR and Data Matrix — local first, torch, continuous mode, manual entry | `EP-FLD-07` | 8 | ready | FF-38, RW-11 |

## 3 · The 5 blocked stories — gaps for the open-questions lane (DOC-C)

Each is a place where the design collides with a rule already signed in this repository. Law 13 says a collision with a signed rule is the one thing that goes to the PO, so none is decided here. Each story's §8 names the gap in plain words; DOC-C mints the `OQ-FLD-` id, and `blocked_by` is then filled in.

| Story | The gap, in plain words |
|---|---|
| `US-FLD-023` | Whether a contractor's claim is refused outside their skills: walkthrough E2E-19 says *within their skills*, but the signed `BR-WRK-029` was superseded on 2026-09-23 so that the skill match advises and never blocks. Which applies to a claim from the handset is unruled. |
| `US-FLD-042` | What the technician sees for an item the server cannot apply: the design (R42, R48, E2E-07, RW-27 *1 refused — needs you*) says REFUSED and shown until acted on; the signed `BR-WRK-063` (PO 2026-10-04) says the server STORES anything it cannot apply, flagged needs-review, and acknowledges it — only the safety lock and an unverifiable caller go unacknowledged. Whether a refusal the technician must act on still exists is unruled. |
| `US-FLD-047` | The compression target: requirement 47 says a 1,600 px long edge and about 300 KB each; the signed `BR-WRK-047` (PO 2026-10-04) says compress to 70–100 KB, with 1,600 px only the mechanism. The design's size, and the mobile-data budgets built on it (requirement 50, R110), collide with a signed rule. |
| `US-FLD-074` | Whether a REQUIRED photograph that was never taken stops the close: R110 and requirement 74 say short of the count warns and never blocks; the signed `BR-WRK-040` says a missing required photograph stops the job closing (and `BR-WRK-062` lets a close through while required photos are still uploading). Which rule governs a required photo with zero taken is unruled. |
| `US-FLD-080` | The capture credential's lifetime: the design's R113 says 36 hours; the signed rule `BR-WRK-060` (PO 2026-10-04) says the capture token outlives sign-out by seven days. Which one the native app uses is a collision with a signed rule, so it goes to the PO. |

## 4 · Every screen has a story (law 8) — proved, not asserted

**FF: 63 of 63 claimed · RW: 29 of 29 claimed.** Missing: **none**.

The check reads every `screens: [...]` line in `06-epics/EP-FLD-*.md` and compares the ids against the 63 `FF-` and 29 `RW-` boards on disk in `wireframes/phone/` and `wireframes/reads/`, so a story naming a screen that has no image, or an image no story claims, both fail. The script and its output are in the lane's report (the folder `10-scripts/` is outside this lane). Each screen and the stories that claim it:

| Screen | Stories |
|---|---|
| `FF-01` Splash | US-FLD-032, US-FLD-036 |
| `FF-02` Intro 1 | US-FLD-032 |
| `FF-03` Intro 2 | US-FLD-032 |
| `FF-04` Intro 3 | US-FLD-032 |
| `FF-05` Sign in | US-FLD-003, US-FLD-032, US-FLD-080 |
| `FF-06` Forgot password | US-FLD-032, US-FLD-034 |
| `FF-07` Permissions | US-FLD-005, US-FLD-013 |
| `FF-08` First sync | US-FLD-002, US-FLD-044 |
| `FF-09` Menu | US-FLD-001, US-FLD-003, US-FLD-036, US-FLD-053, US-FLD-078, US-FLD-079 |
| `FF-10` Today | US-FLD-002, US-FLD-008, US-FLD-015, US-FLD-037, US-FLD-043, US-FLD-045 |
| `FF-11` Nearby | US-FLD-023, US-FLD-037 |
| `FF-12` Claim | US-FLD-023 |
| `FF-13` Map | US-FLD-007 |
| `FF-14` Stop | US-FLD-007, US-FLD-008 |
| `FF-15` Job | US-FLD-005, US-FLD-008, US-FLD-021, US-FLD-026, US-FLD-029, US-FLD-071 |
| `FF-16` Safety | US-FLD-008 |
| `FF-17` Tasks | US-FLD-027, US-FLD-028, US-FLD-074 |
| `FF-18` Add step | US-FLD-022, US-FLD-028, US-FLD-034 |
| `FF-19` Checklist | US-FLD-018 |
| `FF-20` Readings | US-FLD-009, US-FLD-027, US-FLD-074 |
| `FF-21` Photos | US-FLD-005, US-FLD-027, US-FLD-046, US-FLD-074 |
| `FF-22` Compare | US-FLD-005, US-FLD-027 |
| `FF-23` Materials | US-FLD-016, US-FLD-028 |
| `FF-24` Parts used | US-FLD-016 |
| `FF-25` Customer | US-FLD-012 |
| `FF-26` Restoration | US-FLD-012 |
| `FF-27` Stale money | US-FLD-025 |
| `FF-28` Documents | US-FLD-002, US-FLD-021 |
| `FF-29` Crew | US-FLD-020, US-FLD-031 |
| `FF-30` Notes | US-FLD-022, US-FLD-030 |
| `FF-31` Activity | US-FLD-030 |
| `FF-32` Debrief | US-FLD-022 |
| `FF-33` Signature | US-FLD-014 |
| `FF-34` Close | US-FLD-008, US-FLD-014 |
| `FF-35` Completed | US-FLD-024, US-FLD-037, US-FLD-049 |
| `FF-36` Reopen | US-FLD-024 |
| `FF-37` Raise | US-FLD-011, US-FLD-024, US-FLD-076 |
| `FF-38` Scan | US-FLD-010, US-FLD-038, US-FLD-084 |
| `FF-39` Asset | US-FLD-010 |
| `FF-40` Asset history | US-FLD-019 |
| `FF-41` Asset search | US-FLD-037, US-FLD-038, US-FLD-039 |
| `FF-42` Alerts | US-FLD-013, US-FLD-015 |
| `FF-43` Emergency | US-FLD-013 |
| `FF-44` Profile | US-FLD-006 |
| `FF-45` Availability | US-FLD-006 |
| `FF-46` Shifts | US-FLD-006 |
| `FF-47` Timesheet | US-FLD-017, US-FLD-029 |
| `FF-48` Admin tasks | US-FLD-017 |
| `FF-49` Van | US-FLD-016 |
| `FF-50` Sync | US-FLD-004, US-FLD-041, US-FLD-042, US-FLD-043, US-FLD-044, US-FLD-046, US-FLD-047, US-FLD-048, US-FLD-049, US-FLD-050, US-FLD-083 |
| `FF-51` Settings | US-FLD-033, US-FLD-034, US-FLD-035, US-FLD-036, US-FLD-047, US-FLD-051, US-FLD-052, US-FLD-080 |
| `FF-52` Notifications | US-FLD-013, US-FLD-033 |
| `FF-53` Sign out | US-FLD-003, US-FLD-032, US-FLD-048, US-FLD-080 |
| `FF-54` Dark theme | US-FLD-001, US-FLD-035 |
| `FF-55` Sunlight theme | US-FLD-001, US-FLD-035 |
| `FF-56` Activate | US-FLD-070, US-FLD-080 |
| `FF-57` Your password | US-FLD-070, US-FLD-080 |
| `FF-58` Hand it back | US-FLD-071 |
| `FF-59` Add a reading | US-FLD-072 |
| `FF-60` Asset papers | US-FLD-073 |
| `FF-61` Reconnect | US-FLD-075 |
| `FF-62` Pick a template | US-FLD-076 |
| `FF-63` Home | US-FLD-053, US-FLD-078 |
| `RW-01` My routes | US-FLD-053, US-FLD-054, US-FLD-062 |
| `RW-02` Route summary | US-FLD-054 |
| `RW-03` Download | US-FLD-054 |
| `RW-04` Route map | US-FLD-007, US-FLD-056 |
| `RW-05` The walk | US-FLD-055, US-FLD-056, US-FLD-077 |
| `RW-06` The stop | US-FLD-055, US-FLD-058 |
| `RW-07` Getting in | US-FLD-055 |
| `RW-08` Find a meter | US-FLD-038, US-FLD-039 |
| `RW-09` Read entry | US-FLD-057, US-FLD-058, US-FLD-059, US-FLD-063, US-FLD-064, US-FLD-066, US-FLD-068, US-FLD-069, US-FLD-077 |
| `RW-10` Dials | US-FLD-057 |
| `RW-11` Scan to confirm | US-FLD-038, US-FLD-058, US-FLD-084 |
| `RW-12` Master and subs | US-FLD-055 |
| `RW-13` The reading | US-FLD-063, US-FLD-064, US-FLD-065, US-FLD-066, US-FLD-068 |
| `RW-14` The camera | US-FLD-067 |
| `RW-15` High or low | US-FLD-059, US-FLD-069 |
| `RW-16` Second look | US-FLD-059 |
| `RW-17` Can't read | US-FLD-060, US-FLD-066, US-FLD-069 |
| `RW-18` Different meter | US-FLD-061 |
| `RW-19` Not on the route | US-FLD-061 |
| `RW-20` Add a meter | US-FLD-061 |
| `RW-21` Raise it | US-FLD-011, US-FLD-061 |
| `RW-22` Where you are | US-FLD-040, US-FLD-077 |
| `RW-23` Still to do | US-FLD-040 |
| `RW-24` Photos | US-FLD-067 |
| `RW-25` Turn it in | US-FLD-040 |
| `RW-26` Sending | US-FLD-040, US-FLD-041, US-FLD-042 |
| `RW-27` Turned in | US-FLD-040, US-FLD-042, US-FLD-049 |
| `RW-28` My reads | US-FLD-040, US-FLD-077 |
| `RW-29` Reading settings | US-FLD-033 |
