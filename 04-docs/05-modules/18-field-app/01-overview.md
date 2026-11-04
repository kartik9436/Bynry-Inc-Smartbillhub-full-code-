# 18 · Field app — module overview

**Module:** `field-app` (product name: **SMART360 Next Field**; the technician's and meter reader's app) · **Module code:** **FLD** (`BR-FLD-`, `OQ-FLD-`, `DEF-FLD-`, `EP-FLD-`, `US-FLD-`) · **Source:** the *SMART360 Next Field App* design canvas (11 pages, 193 boards), version of 2026-10-21, drawn at product version 2.587.0 · **Change request:** `CR-187-BRC10` · **Code:** `field-app/` at the repository root (React Native, Expo) · **Docs module:** the eighteenth folder, following `17-runbooks/`, laid out like `16-work/` (decision log 2026-10-21, *"Where the field-app design lives in the repo"*).

## 1 · What this app is

A native app — one React Native codebase, iOS and Android, both stores — for the people a utility sends out of the office: **field technicians** working service orders and **meter readers** walking or driving a route. It is the handset half of the Work module; the office half stays on the web. In the design's own words, *"A field app cannot be tested by itself. Every journey starts in the office on the web and ends in the office on the web, and the handset is the middle of the story, never the whole of it."*

It replaces the web field app at `07-frontend/src/features/work/mobile/` (`BR-WRK-045`, now SUPERSEDED by `CR-187-BRC10`), which stays live until the design's task T-72 decides retire or fallback. The reason for going native, as recorded in `CR-187-BRC10` §2: *"iPhone web push has no custom sound and Safari has no vibration API, so an emergency alert would be silent on half the fleet."*

**Three things decide how it behaves, and every screen follows from them:** it works a whole shift with no signal (requirement 2); several technicians share one handset and nothing unsent is ever deleted (requirements 3, 48); and money is read, never written (R16).

## 2 · Who uses it

| Who | What they do in the app | What they do not see |
|---|---|---|
| **Field technician (employee)** | The day, jobs, safety, tasks, readings, photographs, parts, signature, close; raise work; their profile, shifts and timesheet | — |
| **Contractor** | The same, and claims unassigned nearby work (R27) | A customer's money — balance, tariff and the cleared-payment check stay employee-only (R26) |
| **Meter reader** | Reads mode: routes, stops, readings with their evidence, turn-in. *"The same role does service orders and reads — at these sizes it is the same person"* (requirement 53) | — |
| **The office (web, not this app)** | Raises, schedules, dispatches, accepts, reopens, files documents against assets, reviews flagged reads — Work-001 to Work-009 | — |

A technician never self-registers: the office creates the account and the app claims it with a code that expires (R105). A technician's login opens the phone and is refused on the web (`BR-WRK-043`).

## 3 · Size, as delivered

| What | The design says | Delivered here | Delta and why |
|---|---|---|---|
| Business requirements | *"84 requirements"* (Requirements page); *"The fifty requirements"* (task T-61) | **84**, sections A–L, verbatim, §6 below | T-61's fifty is stale; the Requirements page counts 84 |
| Business rules | *"134 rules. 58 … 27 … 49"*; *"the sixty-five rules"* (task T-62) | **134** — `BR-FLD-00001`–`00134`: 58 PO ruled · 27 repo · 49 derived | T-62's sixty-five is stale |
| Screens | *"Phone and tablet, 55 screens each"* (Walkthrough §5) | **63** field screens (`FF-01`–`FF-63`) + **29** reading screens (`RW-01`–`RW-29`), each on phone and tablet: **184 images + the theme switch = 185** in `wireframes/` | +8 field screens since the walkthrough was written: `FF-56`–`FF-62` (the seven asks of 2026-10-20) and `FF-63` Home |
| Epics | — | **14**, the design's flow groups | — |
| Stories | one per requirement (task T-61) | **84**, `US-FLD-001`–`US-FLD-084`; **`US-FLD-nnn` is requirement nnn (zero-padded to three)** | 79 `ready`, 5 `blocked` on a collision with a signed rule (§7) |
| Every screen has a story (law 8) | — | **63 of 63** FF and **29 of 29** RW claimed by a story's `screens:` | proved by a script, `05-user-stories.md` §4 |

## 4 · Rulings this module is built on

| Ruling (decision log 2026-10-21) | What it decides |
|---|---|
| *"The native field app (React Native) lives in this repo, in its own folder: twelve conflicts and how each is handled"* — PO: *"this is correct and i want to handle it as per your suggestion"* | Own `package.json`; shared `tokens.ts`; field words under `field.*`; one product version; gates learn `field-app/src`; `apps/work` reused; BR-WRK-045 superseded |
| *"The native field app's folder is `field-app/` at the repo root"* — PO: *"This is correct"* | The folder |
| *"Where the field-app design lives in the repo"* — PO: *"this is correct ; please go ahead update this details in repo"* | This docs module, code FLD, and which document holds what (§8) |
| *"Field app Phase 0 (T-05): every ruling and judgment of the design conversation, verbatim"* | The 58 PO rulings and 49 derived judgments behind `02-business-rules.md` |
| *"Native field-app screens are built from the drawings as IMAGES"* — PO: *"please ensure all native app screens are build using images not using text or contents"* | Every FF- and RW- screen is built by looking at its image in `wireframes/` (B14 rules 42, 44, 45) |

## 5 · Scope — the design's own list, verbatim (Walkthrough §5)

| In | Out |
|---|---|
| One codebase, iOS and Android, both stores | Taking payment on site — ruled out; the app reads money and never writes it |
| Phone and tablet, 55 screens each | Linear assets — no mains, poles or valves; meters only, for now |
| Three themes: light, dark, sunlight | Inspection rounds — left with the linear assets |
| A whole shift offline, up to 1,000 readings | Offline maps — tiles need a signal; the job does not |
| Meters and sub-meters | A separate dispatcher app — dispatch stays on the web |
| Eleven services, fire included | Live crew tracking on the handset — a dispatcher view, not a technician one |
| Shared handsets and multiple technicians | Inventory counts and van stock-takes — the van screen reads stock, it does not reconcile it |
| Contractors, claiming within their skills | Customer-facing features — the portal is its own product |
| Reading money, with its age shown | A watch app — kept for later, by ruling |
| Emergency alerts through silent mode |  |
| Field-raised orders |  |
| Eleven languages, switchable at runtime |  |

⚠ Two lines of that list are stated against the repository rather than repeated blindly: *"55 screens each"* is now 63 + 29 (§3), and *"Contractors, claiming within their skills"* collides with `BR-WRK-029` as superseded — the skill match advises and never blocks — which is one of the five gaps in §7.

**Two cases the design itself says cannot pass yet:** E2E-22 (an emergency through silent mode) needs Apple's Critical Alerts entitlement — applied for by the PO on 2026-10-21 (T-01), not yet granted; E2E-14 and E2E-15 reach into billing and reconciliation, *"signed and frozen in places. Anything they turn up is a re-sign, not a fix."*

## 6 · Business requirements, in the design's own words

*"Everything agreed in this conversation, in the order it arrived. Online marks the work that needs a signal; everything else works with none."* Every requirement below is verbatim; the last two columns are ours — the screens its story claims and the story itself. **`US-FLD-nnn` is requirement nnn (zero-padded to three).**

### A · The original brief

| # | Requirement | Connectivity | Standing | Screens | Story · status |
|---|---|---|---|---|---|
| 1 | Mobile and tablet — responsive for phones and tablets. Originally an installable PWA; superseded — see Decisions. | — | Changed | FF-09, FF-54, FF-55 | `US-FLD-001` · ready |
| 2 | Offline-first — jobs, checklists, premise notes and safety documents open with no signal. Instant open from local storage, with online / offline / pending-sync shown | Offline | Engine built | FF-08, FF-10, FF-28 | `US-FLD-002` · ready |
| 3 | Shared device — several technicians on one handset across shifts without mixing records. Unsent work and photos survive logout and stay attached to the technician who captured them | Offline | Engine built | FF-05, FF-09, FF-53 | `US-FLD-003` · ready |
| 4 | Two-phase sync — data records first, photos after in the background. Image compression. Local receipts so nothing is lost | Offline | Engine built | FF-50 | `US-FLD-004` · ready |
| 5 | GPS and watermarks — position captured when a job opens (lat, lng, accuracy). Photos stamped with date, time, coordinates, technician and work-order number | Offline | GPS built | FF-07, FF-15, FF-21, FF-22 | `US-FLD-005` · ready |
| 6 | Identity and availability — sign in, sign out, profile with photo, runtime language switching, Available / On break / Off duty, shift calendar, time off, utility holidays | Mixed | Partly | FF-44, FF-45, FF-46 | `US-FLD-006` · ready |
| 7 | Map — scheduled stops colour-coded by status, one-tap navigation to Google or Apple Maps | Online | Partly | FF-13, FF-14, RW-04 | `US-FLD-007` · ready |
| 8 | Service order execution — route ordered by appointment window, mandatory safety checks before work, departure and arrival tracking, automatic labour timer, four outcomes | Offline | Mostly built | FF-10, FF-14, FF-15, FF-16, FF-34 | `US-FLD-008` · ready |
| 9 | Meter readings — numeric and text with explicit units (kWh, gallons, CCF). Out-of-range flagged for review without blocking completion | Offline | Built | FF-20 | `US-FLD-009` · ready |
| 10 | Asset data and scanning — meter serial, device ID, badge, model. Camera scanning of 1D barcodes and 2D QR to verify equipment against records | Offline | Scan is new | FF-38, FF-39 | `US-FLD-010` · ready |
| 11 | Field-raised orders — new work orders from site for emergencies, leaks, damaged meters, broken seals and hazards, auto-filled with premise, account, customer and GPS | Offline | New on phone | FF-37, RW-21 | `US-FLD-011` · ready |
| 12 | Customer, balance and payment — profile, active tariffs, live balance, cleared-payment check before restoring service, restoration countdown. On-site payment collection removed by ruling | Online | Narrowed | FF-25, FF-26 | `US-FLD-012` · ready |
| 13 | Push and emergency alerts — distinct audio and vibration for urgent assignments, emergencies and schedule changes, on a locked device. In-app badges for dispatch messages | Online | Unblocked | FF-42, FF-43, FF-52, FF-07 | `US-FLD-013` · ready |

### B · Found in the repo, missing from the brief

| # | Requirement | Connectivity | Standing | Screens | Story · status |
|---|---|---|---|---|---|
| 14 | Customer signature, or a recorded refusal — printed name plus image with who captured it and when. A refusal records the decline reason and a photograph of the door hanger | Offline | Ruled | FF-33, FF-34 | `US-FLD-014` · ready |

### C · From the reference apps, confirmed into scope

| # | Requirement | Connectivity | Standing | Screens | Story · status |
|---|---|---|---|---|---|
| 15 | Mid-day route re-sequencing — an emergency arrives and the day re-orders | Online | New | FF-10, FF-42 | `US-FLD-015` · ready |
| 16 | Van stock and parts consumption on the phone | Offline | Backend only | FF-23, FF-24, FF-49 | `US-FLD-016` · ready |
| 17 | Labour timesheet, not only a timer — where the hours go for payroll | Offline | New | FF-47, FF-48 | `US-FLD-017` · ready |
| 18 | Conditional checklists — questions that branch on the answer | Offline | New | FF-19 | `US-FLD-018` · ready |
| 19 | Asset service history on site — work type, problem, solution, parts replaced, technician | Offline (cached) | New | FF-40 | `US-FLD-019` · ready |
| 20 | Crew jobs — more than one technician on an order | Mixed | Backend only | FF-29 | `US-FLD-020` · ready |
| 21 | SOPs riding with the job, opening offline | Offline | Ruled | FF-28, FF-15 | `US-FLD-021` · ready |
| 22 | Voice capture for notes — works with gloves on and wet hands | Offline | New | FF-30, FF-32, FF-18 | `US-FLD-022` · ready |

### D · Asked for by the technicians

| # | Requirement | Connectivity | Standing | Screens | Story · status |
|---|---|---|---|---|---|
| 23 | Pending and nearby work — see unassigned orders, and claim one near where you are standing | Online | New | FF-11, FF-12 | `US-FLD-023` · blocked |
| 24 | Reopen a closed job, or raise the next one — a disconnect becomes a reconnect once payment lands | Mixed | New | FF-35, FF-36, FF-37 | `US-FLD-024` · ready |
| 25 | Real-time check before an irreversible act — the balance must not be three days old when the valve closes | Online | New | FF-27 | `US-FLD-025` · ready |

### E · From the walkthrough of the drawings

| # | Requirement | Connectivity | Standing | Screens | Story · status |
|---|---|---|---|---|---|
| 26 | The job shows the whole template — safety, tasks, materials, readings and help, each with a count and a state | Offline | New | FF-15 | `US-FLD-026` · ready |
| 27 | Photos belong to the task and to the reading, as the template defines — not to a loose gallery | Offline | New | FF-17, FF-20, FF-21, FF-22 | `US-FLD-027` · ready |
| 28 | Add a task or a material in the field, with a reason, shown as a variance against the template | Offline | New | FF-18, FF-23, FF-17 | `US-FLD-028` · ready |
| 29 | Travel time and time on the job — depart, arrive, start, pause, correct | Offline | New | FF-15, FF-47 | `US-FLD-029` · ready |
| 30 | Notes, remarks, and a stamped status history — who, what, when, for every change | Offline | New | FF-30, FF-31 | `US-FLD-030` · ready |
| 31 | A second technician on the job, with their own time | Offline | New | FF-29 | `US-FLD-031` · ready |

### F · Getting in, and the field conditions

| # | Requirement | Connectivity | Standing | Screens | Story · status |
|---|---|---|---|---|---|
| 32 | Splash and three intro screens, sign in, forgot password, sign out | — | New | FF-01, FF-02, FF-03, FF-04, FF-05, FF-06, FF-53 | `US-FLD-032` · ready |
| 33 | Settings in full — language, date format, clock, units, four screen modes, bigger text, keep-awake, nearby radius, notifications per alert kind, sync over mobile data, version | — | New | FF-51, FF-52, RW-29 | `US-FLD-033` · ready |
| 34 | A technician taps, never types — choices on screen instead of keyboards, steppers instead of number fields, dictation beside every note | — | Design rule | FF-06, FF-18, FF-51 | `US-FLD-034` · ready |
| 35 | Built for gloves and weather — primary action 56pt, any control 48pt, 8pt clear between targets | — | Design rule | FF-54, FF-55, FF-51 | `US-FLD-035` · ready |
| 36 | The app version is visible to the technician, so a defect report names a build | — | New | FF-01, FF-09, FF-51 | `US-FLD-036` · ready |

### G · Search, large volumes, refresh and the handset's data

*The mechanics are set out in full on the Mobile data tab. These are the requirements they answer.*

| # | Requirement | Connectivity | Standing | Screens | Story · status |
|---|---|---|---|---|---|
| 37 | Search and filter on every list, with criteria per screen. Today searches customer, address, work-order number, status, service and window. Assets search serial, badge, device ID, address and account number. Completed searches a date range, an outcome and a customer. Nearby filters a radius, a job type, a priority and a due date | Mixed | New | FF-10, FF-11, FF-35, FF-41 | `US-FLD-037` · ready |
| 38 | Scanning is the first-class way to find an asset, typing the fallback. A scanned code matches serial, then badge, then device ID | Offline | New | FF-38, FF-41, RW-08, RW-11 | `US-FLD-038` · ready |
| 39 | A search that cannot see everything says so. Offline, asset search states that only the day's assets are on the handset and that a signal searches the whole utility. A silent subset is worse than a refusal — the technician concludes the meter does not exist | Offline | New | FF-41, RW-08 | `US-FLD-039` · ready |
| 40 | A reading route of 500 to 1,000 readings in one day is a supported case, captured with no signal and sent at once. Capture must stay instant at that volume and the send must be resumable | Offline | New | RW-22, RW-23, RW-25, RW-26, RW-27, RW-28 | `US-FLD-040` · ready |
| 41 | Captured work is sent in batches, in capture order, item by item. Fifty to a request — not one request of a thousand, which a sixty-second worker timeout kills, and not a thousand requests. A batch that dies halfway leaves the rest pending, and only the rest is re-sent | Offline | Engine built | FF-50, RW-26 | `US-FLD-041` · ready |
| 42 | The server answers for every item, never for the batch — accepted, duplicate or refused. One bad reading cannot cost the other forty-nine. A refusal is surfaced with its reason and stays until the technician acts on it | Offline | Built | FF-50, RW-26, RW-27 | `US-FLD-042` · blocked |
| 43 | Four refresh triggers: pull-to-refresh on any list · the app coming forward after five minutes · a push from the server for one changed record · every fifteen minutes while on shift and connected | Online | New | FF-10, FF-50 | `US-FLD-043` · ready |
| 44 | A refresh is a delta, never a re-download. A watermark per table asks only for what changed. A full pull happens on first sign-in and after a schema change, and nowhere else | Online | New | FF-50, FF-08 | `US-FLD-044` · ready |
| 45 | A delta must carry removals as well as changes — a job reassigned, an order cancelled, an asset off the route. Without that, a job the technician no longer owns stays on their phone and they drive to it | Online | New | FF-10 | `US-FLD-045` · ready |
| 46 | Photographs upload after the data, asynchronously, one at a time, resumably, continuing when the app is closed. The record must exist on the server before the photograph that attaches to it. One failed photo never blocks the next | Offline | Engine built | FF-50, FF-21 | `US-FLD-046` · ready |
| 47 | Photographs wait for wi-fi by default, with a setting to send them on mobile data. Compressed to a 1,600 px long edge before queueing, around 300 KB each | Offline | Built | FF-51, FF-50 | `US-FLD-047` · blocked |
| 48 | Nothing unsent is ever deleted — at any age, under any sign-in, including another technician's work on a shared handset. A sign-out deletes nothing | Offline | Ruled | FF-53, FF-50 | `US-FLD-048` · ready |
| 49 | Data leaves the handset once it is safely on the server. A photograph's file is deleted the moment receipt is confirmed — not when it is sent. Sent work is kept seven days so the technician can see it; closed jobs fourteen so Completed works offline. Target footprint under 500 MB | Offline | New | FF-50, FF-35, RW-27 | `US-FLD-049` · ready |
| 50 | The mobile allowance is budgeted and the technician can see it. A realistic day is 15–18 MB, or 4–6 MB with photographs on wi-fi only. The sync screen counts items, not bytes, so one large photograph cannot make a finished day look unfinished | Mixed | New | FF-50 | `US-FLD-050` · ready |

### H · Knowing how it behaves in the field

*A handset we cannot see is a handset we cannot fix. The constraints are on the Technology tab and the rules are R66–R72.*

| # | Requirement | Connectivity | Standing | Screens | Story · status |
|---|---|---|---|---|---|
| 51 | Crash reporting that survives a shift offline. JavaScript errors and native crashes with source maps and the breadcrumbs leading up to the fault, queued locally and sent later. Performance tracing on the four paths that hurt — app start, the day pull, a batch send, a photo upload | Offline | New | FF-51 | `US-FLD-051` · ready |
| 52 | Product analytics and feature flags. Which screens are used, where a technician abandons a flow, how long a job really takes — and flags, because an app-store review takes days and a held feature otherwise cannot be released without a build. No customer data, no named technician, no session replay, and never ahead of the work queue | Offline | New | FF-51 | `US-FLD-052` · ready |

### I · Reading meters on a route

*Ten requirements from the eight rulings of 2026-10-20. The screens are on the Reads tab. Two of these reverse a recommendation of mine, and both are marked.*

| # | Requirement | Connectivity | Standing | Screens | Story · status |
|---|---|---|---|---|---|
| 53 | Meter reading is a mode of the same app, not a second app. One sign-in, one sync engine, one outbox, one photo queue. The same role does service orders and reads — at these sizes it is the same person | Offline | Ruled | RW-01, FF-63, FF-09 | `US-FLD-053` · ready |
| 54 | A route is downloaded whole, at the depot. Stops in order, meters with last month's reads, access notes, map tiles, customer names — and the number has to reach 100% before leaving | Offline | New | RW-02, RW-03, RW-01 | `US-FLD-054` · ready |
| 55 | The unit of work is the address, not the meter. Walk order is held per premises, so the walk is a list of stops and a stop holds every meter at it — master and sub-meters included | Offline | Signed rule | RW-05, RW-06, RW-07, RW-12 | `US-FLD-055` · ready |
| 56 | Nearest first by default, with the office's walk order one tap away. Reading out of sequence is normal and never refused; the order actually walked is recorded | Offline | Ruled | RW-05, RW-04 | `US-FLD-056` · ready |
| 57 | The previous reading and the expected range are both on screen. I recommended showing only the range, to stop the number anchoring the reader. Overruled — show both | Offline | Ruled | RW-09, RW-10 | `US-FLD-057` · ready |
| 58 | The customer's name, the unit label and the account number are all shown at the stop. I recommended label and account only, to keep names off a handset that can be lost. Overruled — show the name | Offline | Ruled | RW-06, RW-09, RW-11 | `US-FLD-058` · ready |
| 59 | An out-of-range reading is warned and then accepted. The warning names the consumption it implies and offers a re-read; the reader can always proceed, and the office gets it flagged | Offline | Ruled | RW-15, RW-16, RW-09 | `US-FLD-059` · ready |
| 60 | Eight seeded reasons a meter cannot be read — locked, no access, dog, buried or covered, obstructed, meter not found, unsafe, illegible — tenant-extensible, never hardcoded and never counted in code | Offline | Ruled | RW-17 | `US-FLD-060` · ready |
| 61 | A meter not on the route is scanned. Known to the system → read it, marked off-route. Unknown → add it, with a photograph, pending the office's acceptance. The reading is taken either way | Offline | New scope | RW-18, RW-19, RW-20, RW-21 | `US-FLD-061` · ready |
| 62 | One reader per route for now — and nothing is built that would have to be removed to split a route between two readers later. No constraint, no single-reader assumption in a code path | — | Ruled | RW-01 | `US-FLD-062` · ready |

### J · What a reading actually carries

*A reading is a record, not a number. On a screen used a thousand times a day, how these are captured decides whether the app is usable — so three of them cost nothing and only two cost a tap.*

| # | Requirement | Taps it costs | Standing | Screens | Story · status |
|---|---|---|---|---|---|
| 63 | Position is captured at the moment the reading is saved — latitude, longitude and accuracy, automatically, never typed. Shown as one line, never as a field. It also measures the distance to where the meter is recorded, which catches a wrong meter before the office has to | None | New | RW-13, RW-09 | `US-FLD-063` · ready |
| 64 | A poor fix or no fix warns and still accepts. A meter in a basement or a pit has no sky; refusing the reading there would refuse it exactly where it is hardest to get | None | New | RW-13, RW-09 | `US-FLD-064` · ready |
| 65 | Date and time are stamped automatically, and both clocks are kept — the phone's at capture and the server's on arrival — so a wrong device clock is visible instead of silently believed | None | New | RW-13 | `US-FLD-065` · ready |
| 66 | The reader's status comes from what they already did. Typing a number is read; choosing a reason is could not read; accepting a warning is read with a problem. No separate status control exists | None | New | RW-13, RW-09, RW-17 | `US-FLD-066` · ready |
| 67 | A photograph comes from the camera and nowhere else. The gallery is never offered — a picture from the camera roll could be any meter on any day. Date, time, position with accuracy, reader, meter and route are burned into the pixels, not laid over them, so the stamp survives export, cropping and email | One | Engine built | RW-14, RW-24 | `US-FLD-067` · ready |
| 68 | A remark is spoken by default, typed as the fallback, and never mandatory. Readers push buttons; they do not type | One | New | RW-09, RW-13 | `US-FLD-068` · ready |
| 69 | The reading prompt decides when a photograph is required, the way a job step already does — so a utility that wants one on every read can have it and one that wants them only on exceptions can have that, with no code knowing the difference. An out-of-range reading or a could-not-read makes the photo button prominent on its own | — | New | RW-09, RW-15, RW-17 | `US-FLD-069` · ready |

### K · The seven asks of 2026-10-20

*Seven gaps you found by looking at the screens. FF-56–FF-62 on phone and tablet.*

| # | Requirement | Screen | Standing | Screens | Story · status |
|---|---|---|---|---|---|
| 70 | A technician activates an account the office created — a six-character code good for seven days, their own password, and the device registered by name. Technicians never self-register; this claims an account that already exists | FF-56, FF-57 | Ruled | FF-56, FF-57 | `US-FLD-070` · ready |
| 71 | A technician can hand an assigned job back, with a reason from a short list and optional dictation. It returns to Queued, unassigned, carrying their name and reason — no eighth dispatch state is invented. An emergency cannot be handed back from the app; that takes a call to dispatch | FF-58 | Ruled | FF-58, FF-15 | `US-FLD-071` · ready |
| 72 | A reading the template did not ask for can be added on a service order — the mirror of adding a step or a part. A reason is required and it shows as a variance. A first reading on a new meter has no expected range, so nothing is flagged | FF-59 | New | FF-59 | `US-FLD-072` · ready |
| 73 | Documents about a newly installed asset are attached in the field — a certificate, a permit, an inspection sheet, a seal number. They may come from the camera, from a file, or be typed, and the source is recorded on each one. They travel with the job; the office files them against the asset on acceptance | FF-60 | Ruled | FF-60 | `US-FLD-073` · ready |
| 74 | Several photographs on one task, with the template saying how many — typically three for before, during and after. A thumbnail strip, not one thumbnail. Short of the count is a warning, never a block | FF-17, FF-20 | Ruled | FF-17, FF-20, FF-21 | `US-FLD-074` · blocked |
| 75 | A reconnect checks the reconnect FEE as its own question, beside the arrears. A customer can clear their balance and still not have paid the fee — a single balance would read $0.00 and say nothing. Same five-minute freshness and same warn-never-block as a disconnect | FF-61 | New | FF-61 | `US-FLD-075` · ready |
| 76 | Raising a work order starts by picking a template, because the template is what carries the steps, safety checks, materials and readings. Every published template the back office made, recently-used first, with search. The order takes its own copy and stamps the version | FF-62 | Ruled | FF-62, FF-37 | `US-FLD-076` · ready |

### L · The nine of 2026-10-21

*Two screens and seven pieces of engineering definition. The screen-to-table map found two tables nobody had designed.*

| # | Requirement | Where it lives | Standing | Screens | Story · status |
|---|---|---|---|---|---|
| 77 | Every reading screen works on a tablet — all 29, in the same four frames as the field app. Capture is still a phone job and the design says so; the tablet earns its width on the walk, the read entry and the route progress | Tablet tab | Built | RW-05, RW-09, RW-22, RW-28 | `US-FLD-077` · ready |
| 78 | A landing screen showing both modules — jobs left and next, meters left and nearest, waiting to send, hours today. What to do next, never how fast anybody is going. The bottom bar becomes Home, Jobs, Reads | Phone + Tablet | Built | FF-63, FF-09 | `US-FLD-078` · ready |
| 79 | The code mirrors the server's module boundaries — screens by flow stage, no SQL in a screen, one read-only seam file per server module, and a doors.test.ts that asserts every screen has something that opens it | Technology | New | FF-09 | `US-FLD-079` · ready |
| 80 | Security as a first-class concern — and the one that decides whether the app works: a token expiring mid-shift must never stop a technician capturing. Two credentials, encryption at rest, tenant scoping on the handset, device registration, auto-lock | Security tab | New | FF-05, FF-56, FF-57, FF-53, FF-51 | `US-FLD-080` · blocked |
| 81 | Every screen's tables are written down — what it reads and what it writes, as a matrix. It caught asset_document and template, neither of which had a table or a download | Mobile data §11 | New | — (no screen of its own) | `US-FLD-081` · ready |
| 82 | Queried, sorted or filtered becomes a column; only ever displayed stays a JSON blob. And the half that bites: the wire shape and the local shape are two declared things with a versioned mapping, because a handset cannot ship a fix the same hour a web app can | Mobile data §9 | New | — (no screen of its own) | `US-FLD-082` · ready |
| 83 | Deleting after sync is specified, not implied — the file before the row, cascades in one transaction, on app start never a timer, and nothing unsent at any age | Mobile data §10 | New | FF-50 | `US-FLD-083` · ready |
| 84 | Barcode and QR, including Data Matrix — which is what fits on a meter plate. Resolved locally first, torch because meters live in pits, continuous mode because 151 meters is 151 camera launches otherwise, and manual entry when the label is damaged | Technology | New | FF-38, RW-11 | `US-FLD-084` · ready |

**The design's count, verbatim:** *"84 requirements. Of the original 13, five were already built, seven were partly built and one was absent. The fourteen in section G are the data mechanics — search, volume, refresh, photographs and retention — set out in full on the Mobile data tab; the two in section H are diagnostics, on the Technology tab; the ten in section I are route reading and the seven in section J are what a reading carries, both on the Reads tab."*

## 7 · Step 0 — what the design says against what the repository already holds

Read on 2026-10-21 against this branch. Each line is a place where the design and a signed rule meet; **the five marked ⚠ are collisions, which law 13 sends to the PO, so none is decided here** — each blocks one story and is named in plain words in its §8 for the open-questions lane (DOC-C) to mint as `OQ-FLD-`.

| The design says | The repository holds | Consequence |
|---|---|---|
| The phone is a native app (AD-01) | `BR-WRK-045`: *"The phone is a WEB APP"* | Superseded by `CR-187-BRC10`, stated — not a gap |
| ⚠ R113: a device-bound **36-hour** capture credential | `BR-WRK-060`: the capture token outlives sign-out by **seven days** | `US-FLD-080` blocked |
| ⚠ R110 / requirement 74: short of the photo count **warns, never blocks** | `BR-WRK-040`: a missing **required** photograph **stops the job closing** (and `BR-WRK-062` lets a close through while required photos upload) | `US-FLD-074` blocked — a required photo with zero taken |
| ⚠ R48 / E2E-07 / RW-27: an item is **refused** and shown until the technician acts | `BR-WRK-063`: the server **stores** what it cannot apply, flagged needs-review, and **acknowledges** it | `US-FLD-042` blocked |
| ⚠ Requirement 47: compressed to a 1,600 px long edge, **around 300 KB** | `BR-WRK-047` (superseded clauses, PO 2026-10-04): **70–100 KB**, 1,600 px only the mechanism | `US-FLD-047` blocked; the design's MB budgets (requirement 50, R110) rest on the 300 KB figure |
| ⚠ E2E-19 / Scope: contractors claim **within their skills** | `BR-WRK-029` SUPERSEDED 2026-09-23: the skill match **advises and never blocks** | `US-FLD-023` blocked |
| R114: every local table carries `tenant_id` | R131 (PO ruled, same design): the tenant is the database **file**, zero columns | R131 governs; stated in `02-business-rules.md` Part 0 |
| R51: data before photographs | R123 (same design): a photograph is **declared** with the data, bytes after — *"supersedes the earlier … framing"*; matches `BR-WRK-062` | R123 governs |
| R102: two tabs, Jobs and Reads | Requirement 78 / FF-63: *Home · Jobs · Reads* | Requirement 78 governs; stated on R102's row |
| T-61 *"fifty requirements"*, T-62 *"sixty-five rules"*, T-05 *"Twenty-six PO rulings and twenty-one derived"*, Walkthrough *"55 screens each"* | The pages themselves: 84 · 134 · 58 + 49 · 63 + 29 | Stale counts in the design; the pages' own counts are used |

## 8 · Where the rest of the design lives

Planned by the decision log of 2026-10-21 (*"Where the field-app design lives in the repo"*) and written by sibling lanes of this write-up; listed so a reader knows where to look, not as a claim that each file is already present.

| Design page | Home in the repository |
|---|---|
| Requirements | this file §6 + `05-user-stories.md` + `06-epics/EP-FLD-*.md` |
| Business rules | `02-business-rules.md` |
| Decisions (AD-01 …) | `04-docs/04-adr/ADR-006…`, one per decision, with an index row in `04-docs/02-decisions/01-architecture-decisions.md`; the phone type ramp is B14 rule 45 |
| Technology | `11-technology.md`; token rules into `13-component-registry.md` |
| Mobile data | `03-field-map.md`; server additions in `07-endpoints.md` |
| Work to be done | `10-execution-plan.md` |
| Walkthrough | `08-qa/01-e2e/journeys/J-FLD-TWENTYFOUR-the-field-app-scenario-suite.md` + the three full cases as journeys |
| Security | `12-security.md` + an addendum to `04-docs/02-decisions/03-tenancy-and-security.md` |
| Screens | `wireframes/` (the images — the specification) + `08-screen-layouts.md` + `09-component-inventory.md` |
| Open questions | `OQ-FLD-nnnn` in `12-governance/01-open-questions.md`, through the allocator |
