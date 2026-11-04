# J-FLD-03 — the thousand-reading route: 1,000 meters read with no signal, sent in twenty batches with the connection killed twice, and the office counts exactly 1,000

---
id: JFLD03
tier: 1
change: CR-187-BRC10 (design task T-65)
suite: J-FLD-TWENTYFOUR (case E2E-03)
modules: [metering, work, assets]
# ⚠ **WRITTEN BEFORE THE CODE, AS THE HANDOFF CONTRACT.** No `US-FLD-*` story, runner or
# spec exists at 2026-10-21; no `stories:` is declared rather than naming unissued ids.
---

**Intent.** *Volume, with the connection against you.* Source: the *SMART360 Next Field
App* design, page *End-to-end walkthrough*, §3 *"E2E-03 · The thousand-reading route"*
(version of 2026-10-21). Reading screens RW-01…RW-29 (ADR-025), images in
`04-docs/05-modules/18-field-app/wireframes/reads/`.

**Upstream leaves (preconditions).** A read route of **1,000 meters** at the premises that
hold them, each premises carrying its own point so nearest-first works with no signal (R76);
the can't-read reasons catalogue (eight seeded, tenant-extensible, R82); Dana with a
registered device.

| # | Where | Does | Sees | Record |
|---|---|---|---|---|
| 1 | Web | The office schedules the 1,000-meter route to Dana for one day | — | Route assignment (one reader per route for now, nothing preventing a split later, R87) |
| 2 | Phone | **FF-08 First sync** at the depot on wi-fi — **6–10 MB** | The number must reach **100%** before she leaves | Route, stops, meters, previous readings and expected ranges on the handset |
| 3 | Phone | Airplane mode. She reads **1,000 meters** over the day — scanning the badge, typing the figure, moving on | **Capture never slows** | **Each reading is one outbox row** |
| 4 | Phone | **Eleven** readings are out of range | Flagged and accepted, never refused (R80) | Reader status *read*; the flag for the office |
| 5 | Phone | **Three** meters cannot be read | Recorded as **unable to read**, with a photograph | Reader status *could not read*, a reason from the catalogue (R13, R82) |
| 6 | Sync | Back at the depot | **FF-50 Sync** shows **items, not bytes** (R33) | **Twenty batches of fifty, two in flight, in capture order** (R45, R50) |
| 7 | Sync | **The connection dies during batch 7, and again during batch 14** | — | Each time, the accepted rows settle and the rest stay pending; **the next attempt sends only those** (R49). A re-sent accepted item comes back *duplicate* and doubles nothing |
| 8 | Sync | Photographs | **Three** photographs follow in the second phase (R53) | Photo files deleted on the handset only on confirmed receipt (R61, ADR-028) |
| 9 | Web | The office reviews the route | **Exactly 1,000 readings — not 1,048 from the re-sent batches, not 963.** Eleven flagged for review, three recorded as unread | Readings review is **paged** (`NFR-3`) |

**The pass condition is a number, and the design says so:** *"Total data sync time about 30
seconds. That figure is the test, not a hope."* And the count is read back from the server's
tables — **1,000 / 11 / 3** — never from the handset's screen.

**What must hold.**
* Fifty items to a request: a thousand in one request is killed by the 60-second worker
  timeout (`GUNICORN_TIMEOUT:-60`), a thousand requests is a thousand round trips (R45).
* The server applies each item under its own SAVEPOINT, so one refused row does not poison
  the batch (hard-won law 14) — **prove the interrupted-batch path on PostgreSQL, not SQLite**.
* Idempotency keys scoped to (tenant, work order, key) (R128).

**Leaves (for downstream).** 1,000 field readings on `meter_reads` with position, accuracy,
both clocks and reader status; 11 flagged and 3 unread awaiting office review; nothing pending
on the handset.
