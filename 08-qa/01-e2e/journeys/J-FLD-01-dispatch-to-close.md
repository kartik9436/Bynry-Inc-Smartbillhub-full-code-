# J-FLD-01 — dispatch to close: the office raises a meter exchange, Dana works it on the handset, the office accepts it and its readings reach the bill run

---
id: JFLD01
tier: 1
change: CR-187-BRC10 (design task T-65)
suite: J-FLD-TWENTYFOUR (case E2E-01)
modules: [work, metering, assets, notifications, billing]
# ⚠ **WRITTEN BEFORE THE CODE, AS THE HANDOFF CONTRACT.** No `US-FLD-*` story, runner or
# spec exists at 2026-10-21; no `stories:` is declared rather than naming unissued ids.
---

**Intent.** *The spine. If this breaks, nothing else matters.* Source: the *SMART360 Next
Field App* design, page *End-to-end walkthrough*, §3 *"E2E-01 · Dispatch to close"*
(version of 2026-10-21). Screens are built from the images in
`04-docs/05-modules/18-field-app/wireframes/phone/` (B14 rule 42).

**Upstream leaves (preconditions).** Premises **1400 Elm Street** with a meter that takes
service; a PUBLISHED meter-exchange template with four safety rows, six steps (step 2 and
step 5 require a photograph, step 4 a note), a final read on the old meter and a start read
on the new one, and two planned parts; Dana, a field technician with a registered device and
an issued capture credential (ADR-026 — ⚠ the server endpoint does not exist yet, `OQ-FLD-12798`).

| # | Where | Who | Does | Sees | Record |
|---|---|---|---|---|---|
| 1 | Web | Office | Raises a meter-exchange order against 1400 Elm Street, picks the template, schedules **09:00–11:00**, assigns Dana, dispatches | The order Dispatched | Work order with the template's own copy and version (R112); dispatch state *Scheduled* → dispatched |
| 2 | Phone | Dana | Push arrives; opens **FF-42 Alerts**, acknowledges on **FF-10 Today** | The job sits in its window — **not at the top, because it is a P2**; priority is a badge and never reorders (R1/R2) | Acknowledgement stamped who/when (R10) |
| 3 | Phone | Dana | Taps it — **FF-15 Job** opens **offline** with the whole template (safety, tasks, materials, readings, help, each with a count, R5); taps **Depart** | Travel clock running | Travel clock start, separate from labour (R9) |
| 4 | Phone | Dana | **FF-13 Map**, one tap out to Apple Maps; arrives, taps **Arrive** | — | Position captured with its accuracy |
| 5 | Phone | Dana | **FF-16 Safety**: ticks all four rows | Only then does **Start work** become live | Labour clock starts |
| 6 | Phone | Dana | **FF-17 Tasks**: six steps; photographs on step 2 and step 5 **taken on the step**, camera only (R6, R93); a note on step 4 | Each step's state and photo count | One outbox row per item; photo rows declared with id and sha256 (ADR-028) |
| 7 | Phone | Dana | **FF-20 Readings**: final read on the old meter, start read on the new | The second is **out of range — flagged, never blocking** (R11, R80) | Reading with value and unit (hard rule 3), the flag, both clocks |
| 8 | Phone | Dana | **FF-23 Materials**: two planned parts used; one extra added **with a reason** | The extra part shown as a **variance** against the template (R7) | Material items, `added_in_field` with reason |
| 9 | Phone | Dana | **FF-32 Debrief**, **FF-33 Signature**, **FF-34 Close** as **Passed** | Labour clock stops | Outcome *Passed* (one of four, R4) |
| 10 | Sync | — | The handset reaches a signal | Sync number falls to zero | **Twenty-three outbox items in one batch, all accepted**; then **four photographs** follow on their own line (R33, R65) |
| 11 | Web | Office | Opens the order | Complete, with its **variance**, its **flagged reading** and **2 h 10 m of labour** | — |
| 12 | Web | Office | **Accepts** it | Accepted | The readings are available to the next bill run |

**What must hold.**
* The server re-derives the safety gate; the handset's lock is a convenience, never the
  guarantee (E2E-23).
* Exactly 23 data items and 4 photographs arrive — read back as a COUNT from the server, not
  from the handset's screen.
* An out-of-range reading never blocks completion (R11).

**Leaves (for downstream).** An accepted work order with its outcome, per-person labour,
variance and flagged reading; the old meter's final read and the new meter's start read on
`meter_reads`, which `E2E-14` (meter exchange into a bill) carries into the bill run.
