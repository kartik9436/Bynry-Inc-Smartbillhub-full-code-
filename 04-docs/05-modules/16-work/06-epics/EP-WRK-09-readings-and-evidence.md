# EP-WRK-09 — Readings and evidence: the reading that becomes a meter read through metering's own door, the flag that never refuses, three document kinds, and the photograph's two columns

**Module:** work · **Wave:** phase **2** of `CR-070` · **Screens:** `Work-016` · `Work-008` · `Work-012` · `Work-032` · `Work-033` · **Status:** draft (`CR-070`, 2026-09-03; `WM-35`'s card partly read; §15–§21 unread)

## Scope

**In:** `WM-29` readings that post as meter reads · `WM-35` out-of-range flags, never refuses · `WM-48` three document kinds and the phone resize · `WM-49` the rule and the file are different columns.

**Out:** the reading specification's authoring (`EP-WRK-03`, `US-WRK-014`) · the close (`EP-WRK-08`).

⚠ **THIS IS WHERE FIELD WORK TOUCHES BILLING, AND IT TOUCHES IT IN EXACTLY ONE PLACE.** `WS-16`'s caption: *"'Becomes a meter read' is the switch that turns a note into billing data. When it is on, the value the technician captures posts to the meter's read history when a supervisor accepts the job — dated to when the work was finished, not when it was approved."* The path is metering's existing set-read door — `field_data.set_reads` → the event-read door — *"the posting path itself (WM-29)… the event-read door, which already dates a read to the order's completion (exists) · hard rule 3 — an explicit unit, always (exists)."* **Flagged by the predecessor lane as money-adjacent: the unit and the flag-never-refuse rule need metering-side tests, and they are here.**

## Capability matrix (list screens only — B9 conformance)

No B9 list screen.

## Stories

---
id: US-WRK-046
epic: EP-WRK-09
module: work
screens: [Work-016, Work-008]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-014, US-WRK-032, US-WRK-003]
journeys: [J61, J62, J64]
rules: [BR-WRK-003, BR-WRK-015]
golden_tests: []
finance_calc: proposed
---
### US-WRK-046 — Readings that post as meter reads, through metering's set-read door, dated to completion — and the unit is always explicit (`WM-29`)

**1 · Details** — As **a supervisor accepting `WO-4822`**, I want **the 48,221 kWh the technician recorded to appear on that meter's history dated 15 Mar — the completion — not the approval date**, so that **a field reading becomes billing data exactly once, through the one door billing already trusts**.

`wot_readings.posts_as_meter_read`. *"When true the captured value flows into the existing set-read path and posts a real meter read on approval, dated to the order's completion."* The copy on the order (`work_order_readings.posts_as_meter_read`, `.unit_of_measure`, `.value`) is assembled into `field_data.set_reads = [{meter_no, value, unit, read_at = completed_at, channel = total}]` (⚠ amended 2026-10-05, `DEF-WRK-4073`: this read *channel = field* — a channel names WHICH REGISTER was read, `BR-MET-059`, and `field` is a source, not a register; who read it is already on the read as `imported_by`) at close, and `accept_field_result` — **built, tested, unchanged** — hands it to the event-read door. **Work never writes `meter_reads`.** ⚠ The blueprint's own set-read shape is `[{meter_no, value, read_at, channel}]` — **no unit**; hard rule 3 says a consumption never travels bare, so the seam call carries `unit` and the metering side is asserted to refuse a read without one. If the door does not take a unit today, **that is metering's story and it is filed, not worked around here.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-003` | A reading posts only through metering's set-read door, on acceptance, dated to completion | CONFIRMED — `WM-29` |
| `BR-WRK-015` | The unit is a column; a read never travels bare | CONFIRMED — hard rule 3 |
| `BR-WRK-039` | An out-of-range value still posts — flagged, never refused by Work (metering's own validation then runs as for any read) | CONFIRMED |
| `BR-MET-110` | Only acceptance makes it real | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Accept `WO-4822` with *Final read on old meter* = 48,221 kWh, `posts_as_meter_read = true`, completed 15 Mar 16:07, accepted 16 Mar 09:12 | A `meter_reads` row for the old meter: value 48,221, unit kWh, `read_at` **15 Mar**, channel *total* (amended 2026-10-05, `DEF-WRK-4073` — was *field*, which is a source and not a register), written by metering's own service |
| TC-2 · **negative** | The reading *New meter serial*, `posts_as_meter_read = false` | **No** meter read; the value stays on the order as an observation |
| TC-3 · **negative** | `apps/work/**` writes `MeterRead.objects.create` | The boundary gate FAILS (`US-WRK-005`) |
| TC-4 · **negative · metering-side** | The seam is called with a value and no unit | Metering's door refuses (hard rule 3); the acceptance rolls back; the order stays in the queue — *"Accepting field data the read pipeline refuses would activate a service off a reading that does not exist"* |
| TC-5 · **negative** | The read pipeline refuses the value (say, below the previous read) | The whole acceptance rolls back; the order stays on `Work-009`; the refusal is shown to the supervisor in words |
| TC-6 · **tenant isolation** | The meter belongs to another tenant | `404` before any set-read is attempted |
| TC-7 | An out-of-range but real value, 1,204 kWh against 0–999, `posts_as_meter_read = true` | Posted with the flag on the order; metering's own high/low validation then applies exactly as it would to a staff-entered read — one validation, two sources |

**4 · Test Data** — `WO-4822` completed 15 Mar 2026 16:07 by D. Ortiz; accepted 16 Mar 2026 09:12 by M. Torres. Old meter `E1P-33107` final read 48,221 kWh; new meter `E1P-77412` opening read 1,204 kWh (expected 0–999).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| posts as meter read | `Work-016` | `WM-29` | `wot_readings.posts_as_meter_read` → copied to `work_order_readings.posts_as_meter_read` | bool | user-input at template | — |
| the set read | — | `WM-29` | `work_orders.field_data.set_reads[]` `{meter_no, value, unit, read_at, channel}` | jsonb | system at close | unit required |
| the post | meter history | exists | metering's event-read door via `metering_seam.post_set_reads()` | — | `accept_field_result` | dated `completed_at` |

**6 · Acceptance** — **Given** a reading marked *becomes a meter read*, **when** the supervisor accepts the order, **then** the meter's history carries the value with its unit, dated to the completion — **and** a refusal anywhere rolls the acceptance back.

**7 · Finance Calculation** — No arithmetic here; the read is the input billing consumes. The consequence is real — a wrong read is a wrong bill — which is why the door is metering's and the unit is asserted on both sides. No GT; the read pipeline's own tests apply.

**8 · Open Questions** — None.

---
id: US-WRK-047
epic: EP-WRK-09
module: work
screens: [Work-012, Work-008]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-032, US-WRK-042]
journeys: [J62]
rules: [BR-WRK-039]
golden_tests: []
finance_calc: none
---
### US-WRK-047 — Out-of-range readings flag, and never refuse: a technician standing at a meter that reads 1,204 must be able to record 1,204 (`WM-35`)

**1 · Details** — As **a technician**, I want **1,204 kWh against an expected 0–999 to be flagged, not blocked**, so that **I am never taught to type a number the app will accept**.

r10: *"an out-of-range entry flags on the phone and on the completed order."* `WS-12`: *"⚠ Expected 0–999 kWh. Flagged, not blocked — you can still close. The office will see this."* *"Refusing would teach them to type a number the app will accept, which is worse than a flag."* The flag is stored on the order's copy (`in_range = false`) and shown on `Work-008`, `Work-033` and the report. **`WM-35`'s card is read only as far as its header and *"waits on WM-29 · WM-33 · changes WS-12, WS-08"*.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-039` | Out-of-range flags; never refuses; the job can still close | CONFIRMED — `WM-35`, r10 |
| `BR-WRK-040` | Distinct from a missing required photograph, which does refuse | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Type 1,204 kWh for *Opening read on new meter* (0–999) | *⚠ Expected 0–999 kWh. Flagged, not blocked — you can still close. The office will see this.*; `in_range = false` |
| TC-2 | Close the job | Accepted; the flag rides to `Work-008` and `Work-009` |
| TC-3 · **negative** | The server is posted a value of 1,204 with `in_range = true` from a tampered client | The server **re-derives** `in_range` from the copy's min/max — false — and never trusts the client's flag |
| TC-4 · **negative** | A value with no unit | Refused — a bare number is never a reading (hard rule 3); this is the one refusal, and it is not a range refusal |
| TC-5 | 48,221 kWh against 0–99,999 | *in range*; no flag |
| TC-6 · **tenant isolation** | Reading capture on another tenant's order | `404` |
| TC-7 · **copy** | The flag sentence | The r10 sentence is three sentences; on the phone it is kept as drawn because it is a FACT plus an instruction, and each clause ≤ 6 words — *Expected 0–999 kWh.* · *Flagged, not blocked.* · *You can still close.* · *The office will see this.* |

**4 · Test Data** — As `US-WRK-046`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| value · in range | `Work-012`, `Work-008` | `WM-35` | `work_order_readings.value`, `.in_range` | numeric · bool | phone; `in_range` server-derived | min ≤ value ≤ max |

**6 · Acceptance** — **Given** a reading outside its bounds, **when** the technician records it, **then** it is flagged, the job can close, and the office sees the flag — **and** the server derives the flag itself.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-WRK-048
epic: EP-WRK-09
module: work
screens: [Work-032, Work-033, Work-012]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-005]
journeys: [J65]
rules: [BR-WRK-047, BR-WRK-048]
golden_tests: []
finance_calc: none
---
### US-WRK-048 — Three document kinds, and the phone resize that pays for them: `work_order_photo`, `work_order_signature`, `work_order_report` (`WM-48`)

**1 · Details** — As **the utility**, I want **a technician's photographs, the customer's signature and the report to live in the document store under their own kinds**, so that **nine photographs land once each after a day offline and 3 MB becomes 250 KB before it leaves the phone**.

*"`work_order_photo`, `work_order_signature` and `work_order_report` added to `DOCUMENT_KINDS` — thirty-three values today and not one is Work, and it is a CHECK constraint, so an unknown kind is refused by the database. Upload is a direct pre-signed PUT, the row is written on sync with a per-image idempotency key, and the phone resizes to 1,600 px before sending: 3 MB → 250 KB is 728 GB → 59 GB over seven years for one utility."* `service_appointment` and `service_work_completed` exist as kinds and are not these.

⚠ **THREE SENTENCES OF THE PARAGRAPH ABOVE ARE SUPERSEDED, AND IT IS THE PARAGRAPH THIS STORY WAS BUILT FROM.** `OQ-WRK-1496` CLOSED on 2026-09-04 and the blueprint's arithmetic went with it. **(1) The size is `100 KB` AT CAPTURE, not 250 KB** — the PO named the failure they had already lived through, *"image sizes are 1Gb 2 GB and then suggesdenly stroage is not enough"*, so the raw original never leaves the handset and 1,600 px is the mechanism rather than the target. **(2) Retention is TWELVE MONTHS and then an EXPORT BEFORE DELETION** — not the *"seven years"* assumed above, and not the legal-document regime. **(3) The storage figure it replaces is the blueprint's own: 59 GB over seven years for one utility becomes about 3.4 GB standing** — roughly one seventeenth, and it stops growing. ⚠ **AND THE PRE-SIGNED PUT IS NOT BUILT** (`BR-WRK-047a`): at 100 KB the bytes go through the application, which is what keeps the content hash, the tenant check and the ceiling honest. ⚠ **NOTHING IS DELETED YET AND NOTHING MAY BE** — an export that does not exist is not a retention policy, so the pruning job is written last and refuses while the download path is absent.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-047` | Three kinds; row on sync with a per-image key; **compressed at capture to 100 KB max** | CONFIRMED — `WM-48`, **amended 2026-09-05** by `OQ-WRK-1496` |
| `BR-WRK-047a` | The upload goes through the application, not straight to the object store | CONFIRMED — engineering judgment following the 100 KB cap; decision log 2026-09-05 |
| `BR-WRK-048` | **Twelve months, then an export before deletion**; nothing deleted while the export is absent; nothing deleted while a dispute is open | ⚠ **CONFIRMED 2026-09-04** (was OPEN) — PO ruling on `OQ-WRK-1496` |
| existing | `stored_documents`' immutability trigger and its allow-list, size cap and scan apply | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Sync three jobs with nine photographs | Nine `stored_documents` rows, kind `work_order_photo`, each once; the supervisor opens one from a link that **expires in four hours** |
| TC-2 · **negative** | Re-sync the same three jobs | **Zero** new rows |
| TC-3 · **negative · PostgreSQL** | Insert a `stored_documents` row with kind `work_order_note` | Refused by the CHECK — the constraint is real and the kind is not |
| TC-4 · **negative** | A 3 MB photograph posted without the phone compression | **Refused, naming both numbers** — the server is the ceiling, so *"the raw original is never uploaded"* is a guarantee rather than a hope (hard-won law 1). The phone's own compression is asserted separately on a fixture image: 3,000 × 4,000 px, 3.1 MB → ≤ 100 KB |
| TC-5 · **negative** | A test that asserts *photographs are kept seven years* | **Does not exist** — seven years was the blueprint's assumption and the PO ruled **twelve months**. What IS asserted: `retention_policy()` names twelve months, and `prune_due()` **refuses** while the export path is absent |
| TC-6 · **tenant isolation** | A pre-signed URL from Brazos Bend used on Lone Star Ridge's row | `404` |
| TC-7 · **the regime, and the refusal** | `work_documents.retention_policy()` and `work_documents.prune_due()` | ⚠ **AMENDED 2026-09-05 — `OQ-WRK-1496` IS CLOSED, so this is no longer a stub.** `retention_policy()` returns twelve months, export-before-delete and the open-matter hold. `prune_due()` **raises** while no export path exists, and the pruning job for Work kinds is still **not scheduled** — for the ruled reason now, rather than for want of an answer |

**4 · Test Data** — `IMG-8841`, `IMG-8842` (`WO-4822`), seven more across `WO-4824`, `WO-4902` (⚠ read `WO-4821` until 2026-09-03 — `DEF-WRK-3577`); `SIG-4822`; report `WO-4822-v1.pdf`. Fixture image 3,000 × 4,000 px, 3.1 MB → 1,600 px on the long side, ≈ 250 KB.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| kinds | — | `WM-48` | `DOCUMENT_KINDS` (`apps/tenancy/document_models.py:295`) + 3; the CHECK constraint on `stored_documents.kind` widened in a **tenancy** migration (tenancy owns the table) | enum | — | 33 → 36 |
| upload | phone | `WM-48` | `POST /work-orders/{id}/attachments/upload-url` → a ticket addressed at our own `PUT` route → `POST …/attachments` on sync | — | phone | `idempotency_key` unique per (tenant, work order) |
| compression | phone | `WM-48` + `OQ-WRK-1496` | client, **and a server ceiling** | bytes | client | **≤ 100 KB**; 1,600 px on the long side is the mechanism, not the target |
| retention | — | `WM-48` + `OQ-WRK-1496` | `work_documents.retention_policy()` | months | ruling | **12**, export before deletion; nothing pruned while the export is absent |

**6 · Acceptance** — **Given** nine photographs taken offline, **when** the phone syncs, **then** nine rows exist once each under the Work kinds and a re-sync adds nothing — **and** nothing anywhere says how long they are kept.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-WRK-1496` | How long are photographs and reports kept? | — (nothing waits on it) | PO | ⚠ **CLOSED 2026-09-04** — twelve months, an export before deletion, and compression at capture to 100 KB. What is still NOT built is the export and the pruning job, and that is the ruling rather than a gap |

---
id: US-WRK-049
epic: EP-WRK-09
module: work
screens: [Work-033, Work-016, Work-012]
wave: 2
status: ready
blocked_by: []
depends_on: [US-WRK-047, US-WRK-048]
journeys: [J62, J65]
rules: [BR-WRK-040]
golden_tests: []
finance_calc: none
---
### US-WRK-049 — A reading's photograph: the RULE is one column set on the template, the FILE is another that came back from the phone — and a missing required photograph stops the close while an out-of-range value never does (`WM-49`)

**1 · Details** — As **a supervisor opening `WO-4822`**, I want **to read *2 of 3 required photographs*, see 1,204 kWh flagged with its photograph attached, and see the voltage reading refused — required, missing — with the phone having said so before Close**, so that **I can tell a photograph was demanded AND whether one arrived**.

`Work-033` — *"What the template asked for, and what the phone sent back."* Columns: Reading · Unit · Range · Photo required · Value · Photograph · Captured. The fourth row is the case that matters: *Voltage at socket · V · 110–125 · Required · not taken · missing — job cannot close*. *"Required means the job will not close without it; out of range never blocks. Those are two different rules and they must not be confused."* *"The photo requirement is two columns in two places, and the document had only one of them."*

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-WRK-040` | Missing required photograph blocks the close; out-of-range never does | CONFIRMED — `WM-49` |
| `BR-WRK-015` | `photo_required` is a template column | CONFIRMED |
| `BR-WRK-047` | The file is a `work_order_photo` document | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `WO-4822` with three of four readings captured, two of three required photographs | Header *3 of 4 readings captured · 2 of 3 required photographs*; row four reads *not taken · missing — job cannot close* |
| TC-2 · **negative** | Close with the voltage photograph missing | Refused on the phone before Close and by the server, naming *Voltage at socket* |
| TC-3 | 1,204 kWh out of range with `IMG-8842` attached | Flagged **and** accepted; its photograph shows *▣ IMG-8842 · D. Ortiz · 16:02* |
| TC-4 · **negative** | An optional reading with no photograph | *none — not required*; nothing blocks |
| TC-5 | Click a thumbnail | The full image with *taken at* and *device* — from a four-hour link |
| TC-6 · **tenant isolation** | `Work-033` for another tenant's order | `404` |
| TC-7 · **schema** | `work_order_readings.photo_required` and `.photo_attachment_id` | Two columns; a test asserts neither is derived from the other |

**4 · Test Data** — `WO-4822` readings: Final read on old meter · kWh · 0–99,999 · Required · 48,221 · `IMG-8841` · D. Ortiz · 15:12 · Opening read on new meter · kWh · 0–999 · Required · **1,204 out of range** · `IMG-8842` · D. Ortiz · 16:02 · New meter serial · — · — · Optional · `E1P-77412` · none — not required · **Voltage at socket · V · 110–125 · Required · not taken · missing — job cannot close** (a fourth reading the wireframe adds to the three the template carries — recorded in `03-field-map.md` §5).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| the rule | `Work-016`, `Work-033` | `WM-49` | `wot_readings.photo_required` → `work_order_readings.photo_required` | bool | template | copied |
| the file | `Work-033`, `Work-012` | `WM-49` | `work_order_readings.photo_attachment_id` FK → `work_order_attachments` (→ `stored_documents`) | uuid NULL | phone | required at close iff `photo_required` |
| taken at · device | `Work-033` | `WS-33` | `work_order_attachments.taken_at`, `.device` | ts · text | phone | — |

**6 · Acceptance** — **Given** a required photograph not taken, **when** the technician tries to close, **then** the phone says so and the server refuses — **and** an out-of-range value with its photograph closes fine, flagged.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
