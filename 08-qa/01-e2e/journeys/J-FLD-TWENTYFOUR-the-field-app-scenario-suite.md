# J-FLD-TWENTYFOUR — twenty-four field-app scenarios, office to handset to office

---
id: JFLDTWENTYFOUR
tier: 1
change: CR-187-BRC10 (design task T-65)
modules: [work, metering, assets, customers, payments, billing, identity, notifications]
# ⚠ **WRITTEN BEFORE THE CODE, AS THE HANDOFF CONTRACT.** At 2026-10-21 `field-app/src`
# holds only `App.tsx`; no runner, no spec and no `US-FLD-*` story exists yet, so this
# file declares no `stories:` rather than naming ids that are not issued. Wire the
# stories in when `04-docs/05-modules/18-field-app/05-user-stories.md` lands.
# ⚠ **NOT ACTIVATED.** Nothing executes it today.
---

**Source.** The *SMART360 Next Field App* design canvas, page *End-to-end walkthrough*, §2
*"The twenty-four cases"* (version of 2026-10-21). PO ruling: decision log 2026-10-21,
*"Where the field-app design lives in the repo"* — *"walkthrough → `08-qa/01-e2e/journeys/J-FLD-TWENTYFOUR-the-field-app-scenario-suite.md` + the three full cases as their own journeys"*.
The three written in full are `J-FLD-01-dispatch-to-close.md`, `J-FLD-03-the-thousand-reading-route.md`
and `J-FLD-21-shared-handset-handover.md`.

**The design's premise, which is the reason this is a suite of crossings and not a
handset test plan:** *"A field app cannot be tested by itself. Every journey starts in the
office on the web and ends in the office on the web, and the handset is the middle of the
story, never the whole of it."* Every crossing passes through five hops:

| Hop | Where | What happens |
|---|---|---|
| 1 | Web | Order raised, templated, scheduled, dispatched |
| 2 | Phone | Pulled down, accepted, travelled to |
| 3 | Phone | Worked offline, captured, signed, closed |
| 4 | Sync | Data in batches, then photographs |
| 5 | Web | Reviewed, accepted, costed, billed |

⚠ **HOP 4 IS WHERE ALMOST EVERY REAL DEFECT LIVES — and it is the only hop with no screen on
either side of it.** That is why it has four cases of its own (E2E-07 to E2E-10). A sync
case passes only on a COUNT read back from the server's tables, never on what the handset
screen says (law 7: a check that reads the wrong thing).

**Numbered to the business flow, so E2E-01 is the one to build first.** *Crosses*: Web =
office screens only · Phone = the handset only · Both = crosses back and forth.

## The ordinary day

| Case | Journey | Crosses | What it proves |
|---|---|---|---|
| E2E-01 | **Dispatch to close, happy path.** Office raises a meter-exchange order from a template, schedules it for a window, dispatches it. Dana accepts, travels, arrives, ticks four safety rows, works six steps with two photographs, takes a final reading, uses two parts, gets a signature and closes it Passed. Office accepts it. In full: `J-FLD-01-dispatch-to-close.md` | Both | The spine. If this breaks, nothing else matters |
| E2E-02 | **The whole day offline.** Handset in airplane mode from 07:45. Eleven jobs opened, worked and closed. One sync at 17:10 | Phone | Nothing lost, nothing doubled, nothing needing a signal mid-day |
| E2E-03 | **The thousand-reading route.** A read route of 1,000 meters captured with no signal, sent in 20 batches, the connection killed twice mid-batch. In full: `J-FLD-03-the-thousand-reading-route.md` | Both | Capture stays instant at volume; the send resumes; the count at the far end is exactly 1,000 |
| E2E-04 | **Partly done.** Four of six steps complete, a reason recorded, closed Partly done. Office sees which steps remain and decides | Both | A partial outcome carries through the order, the cost and the office queue |
| E2E-05 | **Failed.** The work itself cannot be done — the meter is seized. Closed Failed with a photograph | Both | Failed means the work failed, and is distinguishable from being blocked |
| E2E-06 | **Waiting on someone.** No access — the dog is out. Closed Waiting on someone with the blocker named | Both | A blocked job is not a failure and does not read as one in the office |

## Hop 4 — the sync

| Case | Journey | Crosses | What it proves |
|---|---|---|---|
| E2E-07 | **A refused item.** One reading of 180 is refused by the server as impossible for that meter. The other 49 in its batch are accepted | Both | Per-item receipts. The refusal reaches Dana with its reason and stays until she acts |
| E2E-08 | **A re-send after a crash.** The app is killed between sending a batch and recording its receipt. It sends again on launch | Both | The idempotency key holds: 50 duplicate replies and not one doubled reading |
| E2E-09 | **A photograph backlog over two days.** Thirty-eight photographs queued on Monday with no wi-fi; the handset is charged overnight and they go up on Tuesday morning | Phone | Photographs outlive a shift, a sign-out and an app restart, and attach to the right items |
| E2E-10 | **Reassigned away.** Office moves job 7 to another technician while Dana's handset is offline. She refreshes at noon | Both | The tombstone. The job leaves her list. Without this she drives to it — and nothing on screen ever looks wrong |

## Money and service

| Case | Journey | Crosses | What it proves |
|---|---|---|---|
| E2E-11 | **Disconnect on a stale figure.** Dana opens a disconnect order with a balance read eleven minutes ago. She is warned, taps Check now, the balance has cleared, and the order closes not required | Both | The four freshness layers work, and the common case is caught before the mistake |
| E2E-12 | **Disconnect anyway.** No signal at all. The figure is three days old. She is warned, proceeds, and it is recorded as unverified | Both | The technician is never blocked. The office sees the word unverified on the order |
| E2E-13 | **Restoration after a cleared payment.** The customer pays at the counter while Dana is outside. A push reaches her; the restoration countdown starts | Both | Money moving in the office reaches the handset without her asking |
| E2E-14 | **Meter exchange into a bill.** The old meter's final read and the new meter's start read flow through to the next bill run, split at the exchange | Web | The field's readings are billable, which is the whole point of the product |
| E2E-15 | **Sub-meter reconciliation.** A parent meter and three sub-meters read on one visit; the office reconciliation runs | Both | Sub-meters are first-class on the handset, not a special case |

## Work that moves

| Case | Journey | Crosses | What it proves |
|---|---|---|---|
| E2E-16 | **Field-raised order.** Dana finds a leaking service at the kerb, raises an order on the spot with premise, account, customer and position filled in, and photographs it. It is sent at once with signal and ASSIGNED to Dana — on her Today, numbered — and the office sees it on *Raised on site* for review (⚠ AMENDED 2026-10-31, FB-028: this read *"pending acceptance"*; R23 superseded) | Both | The technician raises and does the work with no office wait, and the office is never surprised by it |
| E2E-17 | **Reopen.** A closed job is found to be wrong. The office reopens the same order | Both | The original order carries its history and its new work, with nothing overwritten |
| E2E-18 | **Follow-on.** A closed job needs different work. The office raises a linked order instead | Both | Reopen and follow-on are distinguishable, and the office chooses which |
| E2E-19 | **A contractor claims unassigned work.** An external crew member picks up a nearby unassigned order within their skills | Both | Claiming works for a contractor, within the tenant and within their skills, and the office can see who took it |
| E2E-20 | **A second technician joins.** Dana adds Marco to a job at 11:20; he records 90 minutes; she closes it | Both | Labour is per person, the cost is the sum, and the lead closes it |

## People, devices and the edges

| Case | Journey | Crosses | What it proves |
|---|---|---|---|
| E2E-21 | **Shared handset handover.** Dana signs out at 15:00 with 62 items and 38 photographs unsent. Marco signs in on the same handset, works four jobs, signs out. The handset reaches wi-fi. In full: `J-FLD-21-shared-handset-handover.md` | Both | Dana's work sends under Dana's name, Marco's under his, and neither can see the other's as their own |
| E2E-22 | **Emergency on a locked phone.** A gas odour is dispatched to the nearest crew. The handset is locked and on silent | Both | The alert breaks silent mode — which needs the Apple Critical Alerts entitlement |
| E2E-23 | **A safety gate refusal.** A completion is submitted with three of four safety rows ticked, by a handset whose clock was wrong | Both | The server re-derives the gate and refuses, naming the row. The handset's lock is a convenience, never the guarantee |
| E2E-24 | **A signature refused, and the field conditions.** The customer declines; the reason and a photograph of the door hanger are recorded. Walked in sunlight, outdoors, with gloves, on the cheapest handset the utility issues | Both | A refusal is a recorded outcome, and the app is usable in the conditions it is actually used in |

## Cases that could not pass when the design was written — and where each stands now

- **E2E-22** needed Apple's Critical Alerts entitlement, *"days to weeks at Apple's pace"*.
  ⚠ **That blocker is GONE:** PO 2026-10-21, *"we have taken this permission"*
  (`CR-187-BRC10` §4, T-01; ADR-012). The design's sentence that it *"cannot pass until
  that is granted"* is stale from that date.
- **E2E-14 and E2E-15** reach into billing and reconciliation, which are signed and frozen in
  places (❄️ B4/B5). **Anything they turn up is a re-sign via HUMAN-GUIDE §6, not a fix.**

## What the office (web) side has to change for these to pass

The office screens exist — Work-001 to Work-009. The design asks these changes of them:

| Office surface | What has to change | Cases |
|---|---|---|
| Dispatch board | Show the dispatch state as its own axis — Queued, Scheduled, En route, On site, Complete, On hold, Cancelled — and whether a handset has acknowledged | 01, 22 |
| Work order detail | The four outcomes with their reasons; field-added steps and materials as variances; per-person labour; the *unverified* stamp; the activity trail | 04–06, 12, 20 |
| Office acceptance queue | Review and accept completed work; reopen or raise a follow-on; see what a partial left undone | 04, 17, 18 |
| Field-raised queue | Orders raised on site awaiting acceptance, with their photographs and position | 16 |
| Templates | Which steps and readings demand a photograph (and how many, R110), and which steps demand a fresh figure and how fresh — the setting that makes the disconnect warning work without any code knowing what a disconnect is | 01, 11, 12 |
| Readings review | Flagged and unreadable readings from the field, at route volume, **paged** — 1,000 rows is a normal day, not an edge case (`NFR-3`) | 03, 15 |
| Crews and skills | Which contractors may claim which unassigned work | 19 |
| Timesheets | Travel and labour per person per order, correctable, the technician's own corrections visible | 01, 20 |
| Asset detail | Visit history written from the field, and the field's photographs against the asset | 01, 14, 15 |
| The field-app button | Repointed from the web address to the app store — with the test that fires on the day the app ships (ADR-021; hard-won law 2) | — |

## Scope the suite tests against (design §5)

**In:** one codebase, iOS and Android, both stores · phone and tablet · three themes (light,
dark, sunlight) · a whole shift offline, up to 1,000 readings · meters and sub-meters ·
eleven services, fire included · shared handsets and multiple technicians · contractors,
claiming within their skills · reading money, with its age shown · emergency alerts through
silent mode · field-raised orders · eleven languages, switchable at runtime.

**Out — a case that needs one of these is out of scope, not failing:** taking payment on site
(the app reads money and never writes it, R16) · linear assets · inspection rounds · offline
maps · a separate dispatcher app · live crew tracking on the handset · inventory counts and
van stock-takes · customer-facing features · a watch app.
