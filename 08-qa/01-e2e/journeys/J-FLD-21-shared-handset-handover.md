# J-FLD-21 — shared handset handover: Dana signs out with 62 items unsent, Marco works on the same handset, and every item reaches the office under the person who captured it

---
id: JFLD21
tier: 1
change: CR-187-BRC10 (design task T-65)
suite: J-FLD-TWENTYFOUR (case E2E-21)
modules: [work, identity, metering]
# ⚠ **WRITTEN BEFORE THE CODE, AS THE HANDOFF CONTRACT.** No `US-FLD-*` story, runner or
# spec exists at 2026-10-21; no `stories:` is declared rather than naming unissued ids.
---

**Intent.** *The case that loses data if it is wrong.* Source: the *SMART360 Next Field
App* design, page *End-to-end walkthrough*, §3 *"E2E-21 · Shared handset handover"*
(version of 2026-10-21). It is the proof of ADR-029 (the technician is a column, the tenant
is the file), ADR-026 (two credentials) and the B3 addendum of 2026-10-21 §2 (*captured_by*
is written at capture, never read from the current session).

**Upstream leaves (preconditions).** One handset, registered by name; Dana and Marco both
technicians of the same utility with work assigned to each; the handset holds
`field-<tenant>.sqlite` (R131).

| # | Where | Does | Sees | Record |
|---|---|---|---|---|
| 1 | Phone | Dana has worked a day with no signal | **62 items and 38 photographs unsent** | 62 outbox rows and 38 photo rows, each with `technician_id` = Dana and `captured_by` from her capture credential |
| 2 | Phone | Dana taps **FF-53 Logout** | It **tells her the number and warns her** | **It deletes nothing** (R64) |
| 3 | Phone | **Marco signs in** on the same handset (a password, never a thumb — switching technician always takes a password) | **His own day, and no trace of Dana's 62 items** | Every read of a work table goes through the one scoped helper (R133) |
| 4 | Phone | He works **four jobs**, capturing **31 items** of his own, and signs out | — | 31 rows with `technician_id` = Marco |
| 5 | Sync | The handset reaches depot wi-fi overnight, **signed in as nobody** | — | **All 93 items send** — each under the technician who captured it, because `captured_by` was written at capture and never reads the current session. Photographs follow |
| 6 | Web | The office opens the day | **Dana's 11 jobs are hers and Marco's 4 are his. Two timesheets, not one.** Nothing is attributed to whoever happened to be signed in last | `audit_log` and labour rows per person (R8) |

**What must hold.**
* **62 + 31 = 93** items arrive — a count read back from the server, split **62 / 31** by
  `captured_by`.
* The sync watermark is per technician per table (R134): Marco's pull never advances Dana's
  cursor, so she loses no delta when she next signs in.
* Nothing unsent is ever purged, at any age, under any sign-in (R60).
* A remote sign-out from the office at any point in this journey would drop the mirrored data
  and **keep** the 93 items, which still send (R115).

**Leaves (for downstream).** Two technicians' work on the server under the right names; an
empty outbox on the handset; Dana's and Marco's mirrored jobs still separate on the handset.
