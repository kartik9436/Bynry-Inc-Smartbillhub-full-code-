# 16 · Work — the endpoints

**95 new endpoints, plus 5 that exist and are unchanged.** *(94 until 2026-09-03; the 95th is #44a — `DEF-WRK-3579`.)* ⚠ **`CR-070` §3 estimated
*"roughly 30"*; the predecessor lane's table estimated ~70; writing the list out gives 95**
— see the note at the foot of this file. Nothing was added to scope; the estimates were
low in the same two places.

⚠ **§16 — the build specification, with its own endpoint list — IS UNREAD.** Every route
below is derived from a card, a wireframe's controls or a story's flow, and each is marked:
**C** the card names or directly implies it · **W** a wireframe's control needs it · **S**
a story's flow needs it and nothing drawn names it. **When §16 is read, its list is
reconciled against this one and this file is stamped.**

**All routes are path-tenanted: `/{tenant}/…`** (PO 2026-08-10). Work's routes live in
`apps/work/api.py`, included from `config/urls.py` once (law 11: one include, one line).
**Every mutating route is enforced server-side regardless of the button** (`BR-SHL-025`),
and every refusal is a catalogue sentence of five or six words (B14 rule 33, `g33`) present
in all eleven catalogues (`g15`).

| Group | Count | Phase |
|---|---|---|
| Existing, unchanged | 5 | — |
| §1 The fourteen writers mounted, and the queue | **15** | 0 |
| §2 Reference data | **21** | 1 (`labour_rates` 2) |
| §3 Templates and the wizard's proposal | **14** | 1 |
| §4 Workforce | **11** | 2 |
| §5 Dispatch | **10** | 2 |
| §6 The order in hand and its evidence | **11** | 2 |
| §7 Rules | **6** | 2 |
| §8 The phone | **4** | 2 |
| §9 Parts issues and performance | **3** | 2 |
| **New, total** | **95** | |

---

## 0 · Existing, unchanged — 5

`GET /connections` (`Work-001`) · `GET /connections/{id}` (`Work-002`) ·
`POST /connections/{id}/commit` (`Work-004`) · `POST /work-orders/{id}/field-result`
(`Work-012`, `Work-008`) · `POST /work-orders/{id}/accept` (`Work-003`, `Work-009`).

⚠ **`accept_field_result` gains consequences and loses none:** the report generation
(`US-WRK-053`), the failed-outcome chain (`US-WRK-034`), the permission check that today
resolves to *any staff* (`US-WRK-022`) — all inside its one transaction, and *"a refusal
anywhere in step 3 rolls the whole acceptance back."*

## 1 · Phase 0 — the fourteen finished writers, and the queue — 15

| # | Endpoint | Service function (exists, unchanged) | Screen | Mark |
|---|---|---|---|---|
| 1 | `POST /connections` | `create_connection` | `Work-004` | C `WM-02` |
| 2 | `POST /connections/{id}/services` | `add_connection_service` | `Work-002` | C |
| 3 | `POST /connections/{id}/services/{sid}/transition` | `transition_service` | `Work-002` | C |
| 4 | `POST /connections/{id}/submit` | `submit_connection` | `Work-002` | C |
| 5 | `POST /connections/{id}/hold` | `hold_connection` | `Work-002` | C |
| 6 | `POST /connections/{id}/release` | `release_connection` | `Work-002` | C |
| 7 | `POST /connections/{id}/cancel` | `cancel_connection` | `Work-002` | C |
| 8 | `POST /connections/{id}/waiting-on` | `set_waiting_on` | `Work-002` | C |
| 9 | `POST /connections/{id}/outstanding-work` | `mark_outstanding_work` | `Work-002` | C |
| 10 | `POST /connections/{id}/outstanding-work/{tid}/close` | `close_outstanding_work` | `Work-002` | C |
| 11 | `POST /connections/{id}/owner-account` | `create_owner_account` | `Work-002` | C |
| 12 | `POST /connections/{id}/charges/tag` | `tag_charges_to_account` | `Work-002` | C |
| 13 | `PUT /connections/{id}/units/{uid}/characteristics/{key}` | `set_characteristic` | `Work-002` | C |
| 14 | `POST /work-orders` | `create_work_order` — **the one raise** every door uses (`WM-20`, `WM-43`, `WM-44`, the rules engine) | `Work-002`, `Work-007`, `Work-028`, `Work-029` | C |
| 15 | `GET /work-orders/awaiting-approval` | a selector: `accepted_by IS NULL AND state = completed`, across connections | `Work-009` | C `WM-03` |

The two readers — `characteristic()` and `outstanding_work()` — ride inside `GET /connections/{id}`.

**Wave A, as built (2026-09-03):** `GET /work-orders` — every OPEN order across every anchor, `q` · `page` · `per`,
the one list envelope — is mounted from `apps/work/api.py` (task A3) ahead of row 61's six filters, which arrive with
the columns they filter (wave G). Row 14's `POST /work-orders` is NOT mounted yet: the raise exists as
`apps.work.services.raise_work_order` and the terminal is its door until wave B's screen presses it.

## 2 · Phase 1 — reference data — 21

Three per simple lookup (list · create · patch, with `active` toggled by patch); the parts
register needs a detail; labour rates are dated and append-only, so a change is a POST.
⚠ **If `BR-SHL-035`'s generic `kind: "list"` routes can serve the four Reference-data
cards, the fifteen simple-lookup routes collapse onto them** — a phase-1 lane checks
before writing fifteen handlers, and this count comes down. Recorded, not assumed.

| # | Endpoint | Screen | Mark |
|---|---|---|---|
| 16–18 | `GET · POST /work/types` · `PATCH /work/types/{id}` | `Work-018` | C `WM-04` |
| 19–21 | `GET · POST /work/priorities` · `PATCH /work/priorities/{id}` | `Work-018` | C `WM-05` |
| 22–24 | `GET · POST /work/skills` · `PATCH /work/skills/{id}` | `Work-018` | C `WM-06` |
| 25–27 | `GET · POST /work/safety-kits` · `PATCH /work/safety-kits/{id}` | `Work-018` | C `WM-06` |
| 28–30 | `GET · POST /work/part-categories` · `PATCH /work/part-categories/{id}` | `Work-018` | C `WM-06` |
| 31–34 | `GET · POST /work/parts` · `GET · PATCH /work/parts/{id}` | `Work-025`, `Work-018` | C `WM-07` |
| 35–36 | `GET /work/labour-rates` · `POST /work/labour-rates` (a new dated row; the old one `superseded_on`) | `Work-030` | C `WM-45` |

⚠ `GET /work/parts` and `GET /work/parts/{id}` carry **no** `on_hand`, `reorder_at` or
`location` key — asserted by name (`US-WRK-010` TC-5), so a lane cannot add stock quietly.

## 3 · Phase 1 — templates, and the wizard's proposal — 14

| # | Endpoint | Screen | Mark |
|---|---|---|---|
| 37 | `GET /work/templates` | `Work-013` | C `WM-10` *"read and list"* |
| 38 | `POST /work/templates` — a draft | `Work-014` | C `WM-10` |
| 39 | `GET /work/templates/{id}` | `Work-022` | C |
| 40 | `PATCH /work/templates/{id}` — header fields on a draft or current version | `Work-014`, `Work-022` | C |
| 41 | `DELETE /work/templates/{id}` — **refused while any version is referenced** | `Work-017`, `Work-022` | C `WM-40` |
| 42 | `POST /work/templates/{id}/publish` — **the one write**; allocates `ST-{0000}`; sets version | `Work-017` | C `WM-10` |
| 43 | `POST /work/templates/{id}/duplicate` | `Work-022` | C `WM-10` |
| 44 | `POST /work/templates/{id}/deactivate` | `Work-022` | C |
| 44a | `POST /work/templates/{id}/reactivate` — the mirror of #44: `active = true`, the template is proposed and offered again, existing orders untouched; **`PATCH` (#40) never touches `active`**, so both moves are audited by name (decision log 2026-09-03; `DEF-WRK-3579`) | `Work-022` | S |
| 45 | `PUT /work/templates/{id}/{collection}` — `collection ∈ {details, safety, tasks, materials, readings, help, asset-types}`; **one route, seven collections**, replaces the collection on a draft | `Work-014`–`016` | C `WM-10` *"nested CRUD"* |
| 46 | `GET /work/templates/{id}/versions` | `Work-022` | C `WM-40` |
| 47 | `GET /work/templates/{id}/usage` — orders raised per version | `Work-022` | W `WS-22` |
| 48 | `GET /work/template-packs` — the three platform starter packs | `Work-014` | W `WS-14` |
| 49 | `GET /connections/proposed-work-orders?services=` — from the enabled services' published templates | `Work-004` | C `WM-12` |

## 4 · Phase 2 — workforce — 11

| # | Endpoint | Screen | Mark |
|---|---|---|---|
| 50–52 | `GET · POST /work/crews` · `PATCH /work/crews/{id}` | `Work-023` | C `WM-13` |
| 53–56 | `GET · POST /work/technicians` · `GET · PATCH /work/technicians/{id}` — `POST` refuses a user with no `identity.User` | `Work-023`, `Work-024` | C `WM-13` |
| 57 | `PUT /work/technicians/{id}/skills` — the skills wizard's confirm | `Work-024` | C `WM-21` |
| 58 | `PUT /work/technicians/{id}/certifications` | `Work-024` | C `WM-21` |
| 59 | `POST /work/technicians/{id}/unavailable` | `Work-024` | W `WS-24` *Set unavailable* |
| 60 | `GET /work/certification-watch` — expiries within 30 and 60 days | `Work-023` | W `WS-23` |

⚠ **Two stories add no route and change identity's own:** `US-WRK-022` declares
`work_accept` in identity's permission catalogue and `US-WRK-023` adds the
`field_technician` role and `surface_scope` — **identity owns those writes**; Work only
asks `identity_seam.may(...)` and `identity_seam.enforce_surface(...)`, both stubbed on
their questions.

## 5 · Phase 2 — dispatch — 10

| # | Endpoint | Screen | Mark |
|---|---|---|---|
| 61 | `GET /work-orders?q=&type=&status=&priority=&technician=&area=` — **exactly six filters**; **`422`** on a seventh ⚠ **AMENDED 2026-09-05 (wave G, BUILT): the status is `422`, not the `400` this row said.** Every `VAL_*` refusal in this product answers 422 by law IS-7 / `OQ-004`'s closure, and one route answering 400 for a validation error would be the second error shape the B12 §3 envelope exists to prevent. What this row signs is *refused rather than silently ignored*, and that is what is built. ⚠ **AND IT IS THE BARE NAMES THAT ARE COUNTED:** `f.<name>` is the shared table framework's grammar, this route declares nothing in it, and `BR-SHL-011` keeps governing there — which is what wave O's shipped test asserts. Decision log 2026-09-05 | `Work-007` | C `WM-16` |
| 62 | `GET /work-orders/{id}` | `Work-008` | S |
| 63 | `PATCH /work-orders/{id}` — priority · due · window · area · notes; refuses priority on Complete | `Work-021` | C `WM-39` |
| 64 | `POST /work-orders/{id}/assignments` — `act ∈ {assign, unassign, schedule, depart, arrive}`; **appends a row, never updates** | `Work-007`, `Work-021`, phone | C `WM-15` |
| 65 | `POST /work-orders/{id}/hold` — *Put on hold…*; `dispatch_state = on_hold` | `Work-008` | W `WS-08` |
| 66 | `POST /work-orders/{id}/cancel` — danger tier; nothing deleted | `Work-021`, `Work-008` | C `WM-39` |
| 67 | `POST /work-orders/bulk` — `act ∈ {assign, reschedule, priority}` + ids; **per-order results, never a boolean** | `Work-007` | C `WM-17` |
| 68 | `GET /work-orders/map` — pins with coordinates via `customers_seam`; the not-on-the-map strip | `Work-007` | C `WM-23` |
| 69 | `GET /work/kpis` — the five tiles | `Work-007` | W `WS-07` |
| 70 | `GET /work-orders/{id}/audit` | `Work-008` | W `WS-08` |

⚠ **`WM-37`'s push is a JOB, not a route** — `jobs.kind = work.push` on queue `work`, a
job row before the broker message (`US-WRK-030`). The device token it needs is §8's #91.

## 6 · Phase 2 — the order in hand and its evidence — 11

| # | Endpoint | Screen | Mark |
|---|---|---|---|
| 71 | `GET /work-orders/{id}/checklist` — the six copy collections | `Work-008` | C `WM-19` |
| 72 | `POST /work-orders/{id}/safety/{sid}/tick` | `Work-011`, `Work-008` | C `WM-34` |
| 73 | `POST /work-orders/{id}/tasks/{tid}/tick` — refused while the safety lock holds | `Work-008`, `Work-011` | C `WM-19` |
| 74 | `PUT /work-orders/{id}/readings/{rid}` — value + unit; `in_range` server-derived; **never refused for range** | `Work-012`, `Work-008` | C `WM-35` |
| 75 | `PUT /work-orders/{id}/materials/{mid}/used` | `Work-012`, `Work-008` | C `WM-22` |
| 76 | `POST /work-orders/{id}/attachments/upload-url` — ⚠ **AMENDED 2026-09-05: NOT a pre-signed PUT.** It answers with a ticket addressed at THIS application's own `POST …/attachments`, plus `max_bytes` (**102400**) and the long edge the handset aims for. `BR-WRK-047a`: at the PO's 100 KB cap a direct-to-store PUT buys one fewer hop and costs the content hash, the `byte_length > 0` CHECK, the tenant check, the audit row and the ceiling itself — because the server never sees the bytes. The route is KEPT rather than deleted so the ceiling is told to the phone BY THE SERVER instead of living as a constant an old build can get wrong | phone | **BUILT** `WM-48` |
| 77 | `POST /work-orders/{id}/attachments` — the row, on sync, with its idempotency key | phone | C `WM-48` |
| 78 | `GET /work-orders/{id}/attachments/{aid}` — a link that **expires in four hours** | `Work-033`, `Work-008` | C `WM-48` |
| 79 | `POST /work-orders/{id}/signature` — or the refusal with its reason and door-hanger photo | `Work-012` | C `WM-30` |
| 79a | `GET /work-orders/{id}/close-readiness` — **two SEPARATE lists**: `blocking` (a missing REQUIRED photograph, which stops the close) and `flagged` (an out-of-range value, which never does), plus the server's own `can_close` and the footer counts. ⚠ **ADDED 2026-09-05 and not in the original row set.** `BR-WRK-040` says *two different rules, two different sentences*, and a single list would have let every caller quietly undo it; `can_close` is served rather than derived so the phone and the office cannot disagree about whether a job may be finished — `BR-WRK-037`'s one-evaluator argument, applied again | `Work-012`, `Work-033` | **BUILT** `WM-35` · `WM-49` |
| 80 | `GET /work-orders/{id}/reports` — the versions | `Work-008` | C `WM-47` |
| 81 | `GET /work-orders/{id}/reports/{v}.pdf` — frozen; served from the document store | `Work-032` | C `WM-47` |

On the phone, #72–#75, #77 and #79 arrive **inside the sync batch** (#90) rather than one
call each; the routes exist for the staff app's `Work-008` and for a phone with signal.

## 7 · Phase 2 — rules — 6

| # | Endpoint | Screen | Mark |
|---|---|---|---|
| 82–85 | `GET · POST /work/rules` · `GET · PATCH /work/rules/{id}` — the five-step builder's *Review & activate* is the POST | `Work-026` | C `WM-24` |
| 86–87 | `POST /work/rules/{id}/enable` · `POST /work/rules/{id}/disable` | `Work-026` | C `WM-24` |

The sweep itself is a nightly job, `jobs.kind = work.rules_sweep`, idempotent per
(rule, subject).

## 8 · Phase 2 — the phone — 4

| # | Endpoint | Screen | Mark |
|---|---|---|---|
| 88 | `GET /work/mobile/today` — the technician's day, ordered by appointment time, with the bundles | `Work-010` | C `WM-32` |
| 89 | `GET /work/mobile/jobs/{id}` — the bundle: the order, its six copies, the customer contact, help documents as pre-signed GETs | `Work-011` | C `WM-33` |
| 90 | `POST /work/mobile/jobs/{id}/sync` — a batch of captured items in capture order, each with its key; per-item results; **a savepoint per item on PostgreSQL** (law 14); the close inside it is `submit_field_result` | `Work-012` | C `WM-36` (unread) · `WM-38` (unread) |
| 91 | `POST /work/mobile/devices` — register the push token | phone | C `WM-37` |

## 9 · Phase 2 — parts issues and performance — 3

| # | Endpoint | Screen | Mark |
|---|---|---|---|
| 92–93 | `GET · POST /work/parts/issues` — an issue is a negative quantity, a return positive; `order_ref` is plain text | `Work-025` | C `WM-22` |
| 94 | `GET /work/performance?period=` — the four tiles and the by-job-type table; **no posting** | `Work-027` | C `WM-41` |

## 10 · What adds NO route, on purpose

| Card | Why no route |
|---|---|
| `WM-43` the Assets door | The screen posts `POST /work-orders` (#14) with `asset_id`; Assets serves no Work route and Work serves no Assets route |
| `WM-44` the Customers door | Two calls from one step: Customers' own move-out route (exists) and `POST /work-orders` (#14) |
| `WM-26`, `WM-31` | Identity's catalogue and role, written by identity; both stubbed on their questions |
| `WM-46` tax | **Not built** — PO 2026-09-03 |
| `WM-37` push, `WM-24` sweep | Jobs, not routes |
| `WM-01`, `WM-08`, `WM-09`, `WM-14`, `WM-18`, `WM-25`, `WM-40`, `WM-42`, `WM-49` | Schema and behaviour behind routes already listed |

---

## Why the count moved from ~30 to 95

`CR-070`'s *"roughly 30"* was made from the card count before any list was written. The
predecessor lane's ~70 was an estimate against the screens. Writing the routes out added
in two places, and neither is new scope (the 95th, #44a `reactivate`, was added 2026-09-03 — `DEF-WRK-3579`):

* **Reference data needed 21, not 6.** Six lookups with a list, a create and a patch each
  is eighteen before the parts detail and the dated rate row. **This is also the number
  most likely to fall**: if `BR-SHL-035`'s generic reference-data routes can carry the
  four cards, fifteen of these collapse onto them. A phase-1 lane checks that first.
* **The order's own copies needed eleven, not three.** A tick on a safety row, a tick on a
  task, a reading with its unit, a part used, an upload URL, the attachment row, the
  four-hour link, the signature, and two report reads — every one is a thing the phone
  captures or the supervisor opens, and each is a distinct write or read with its own
  refusal.

The template routes (13), the dispatch routes (10) and the phone's four are close to what
the cards imply directly. **The counts of specifications, screens, stories, rules and
tables are unchanged by this file.**
