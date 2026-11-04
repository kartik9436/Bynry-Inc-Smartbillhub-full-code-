# 18 · Field app — field map (the data on the handset)

**Source:** the *SMART360 Next Field App* design canvas, page *Data on the handset* (board `Data.dc.html`,
design version `2.587.0`, read 2026-10-21), with `AD-17` and `AD-24` from its *Architecture decisions* page and
`R116`–`R134` from its *Business rules* page (recorded verbatim in `12-governance/02-decision-log.md`,
2026-10-21, *"Field app Phase 0 (T-05)"*). The design's figures and its reasons are kept as the design wrote
them. **Every server name below was checked against the code at this branch's HEAD on 2026-10-21** —
`06-backend/apps/work/models.py`, `sync_models.py`, `evidence_models.py`, `apps/metering/connections.py`,
`apps/metering/models.py`, `apps/assets/models.py`, `apps/customers/models.py` — and where the design names a
field the server does not have, the cell says **NEW** and names the module that must own it.

⚠ **THIS FILE DESCRIBES THE HANDSET. THE SERVER'S RULES STILL HOLD THERE** — every server table is tenant-scoped
with RLS `FORCE` (CLAUDE.md hard rule 1), money is `NUMERIC(18,4)` and displays at 2 (hard rule 2), a quantity
carries its unit (hard rule 3), and the field app **reads money and never writes it** (`R16`).

⚠ **TWO DESIGN FIGURES DISAGREE WITH A SIGNED RULE, AND THE SIGNED RULE STANDS UNTIL THE PO SAYS OTHERWISE** —
§12 below. The design sizes every photograph at **~300 KB**; `BR-WRK-047` (PO, amended 2026-09-05 and
2026-10-04) has the phone compress to **70–100 KB** and the server store at most **100 KB**
(`apps/work/work_documents.py:101`, `MAX_PHOTO_BYTES = 100 * 1024`). The design's capture-credential life is
**36 hours**; the server's capture token lives **7 days** (`apps/work/mobile.py:660`,
`CAPTURE_TOKEN_MAX_AGE_S = 7 * 24 * 3600`). Neither is resolved here.

---

## 1 · SQL, not NoSQL — `AD-17`

> **SQLite on the handset. MMKV for preferences. Nothing else.**

**Why relational.** The data is relational — an order has tasks, tasks have photos, an asset has sub-meters and a
history. The server is PostgreSQL, so mirroring its shape removes a whole class of translation bug. The queries the
app actually runs are joins with ordering: today's jobs by window, unsent items in capture order, readings for this
order.

**Why not NoSQL.** A document store would force us to re-implement joins and ordering in JavaScript, over up to
1,000 rows a day, on a mid-range Android handset. And the capture queue needs real transactions: a reading, its
photo row and its idempotency key must land together or not at all.

**Why not a sync engine.** The server already owns a per-item sync contract with idempotency keys and a savepoint per
item (`apps/work/sync.py`, hard-won law 14). A generic replication library would duplicate that and hide it.

**MMKV holds** only the active technician, the capture token, the theme, the language and the last-sync clock —
things with no relationships and no queries.

**Photos are files on disk, never blobs in the database.** 38 photos a day at 300 KB each would bloat every query in
the app for no benefit. The table holds a path (`R52`).

### The six options weighed, against what this app actually does

Scored on the work in front of us, not in the abstract. **The decisive column is the last one.**

| Option | Joins & sort | Real transactions | 1,000 rows a day | Text search | Fits OUR sync contract |
|---|---|---|---|---|---|
| **SQLite** (op-sqlite / expo-sqlite) | Yes, in SQL | Yes | Yes, ms | Yes, FTS5 | **Yes** — it has no opinion about sync, which is exactly what we need. The outbox, the keys and the per-item receipts are ours |
| **WatermelonDB** (SQLite underneath) | Yes | Yes | Yes | Partly, bring your own | **No** — the closest rival, and it loses on one thing: its sync protocol is its own, built around last-write-wins pull/push. Our server answers accepted / duplicate / refused per item. We would be fighting it from week one |
| **Realm** (Atlas Device SDK) | Partly, object links | Yes | Yes | Partly | **No** — its selling point is its own sync, to Atlas. We have a Django/PostgreSQL server with a signed contract. Buying a sync engine and then not using it is paying for the part we must not have |
| **PouchDB** (CouchDB replication) | No, map/reduce views | Partly | Partly, slow at volume | No | **No** — replication-first by design, and it wants a CouchDB at the other end. Revision trees and conflict documents are a model this product does not have |
| **MMKV / AsyncStorage** (key–value) | No | No | No | No | **No** — not a database. We still use MMKV, for the five things that have no relationships and no queries |
| **JSON files** (the thing people reach for) | No | No — a crash mid-write corrupts it | No | No | **No** — rewriting a file to append one reading is how a day of work is lost to a flat battery |

**The argument in one line.** Every NoSQL option on that list is really a sync product with a database attached. We
do not need one — the server already owns the sync contract, with idempotency keys minted at capture and a savepoint
per item. What we need is a fast local store that stays out of the way. That is SQLite, and the fact that it is also
relational, like the PostgreSQL it mirrors, is the second reason rather than the first.

**Where NoSQL would have been the right answer** — said plainly, so this reads as a decision rather than a
preference. A document store wins when the shape of the data changes per tenant or per record, when documents are
deeply nested and always read whole, when there are no joins to do, and when you want replication handed to you.
Three of those four are nearly true here — a work order really is a deep document, read whole, and its template
varies. **It is the joins and the ordering that decide it**: today's jobs by window, unsent items in capture order,
every meter at this address. Those are the queries this app lives on, and they are the ones a document store makes
you write by hand in JavaScript.

---

## 2 · The tables

**Nineteen tables in five groups** (the design's own count on this page; `WorkToDo` T-09 and `AD-17` say *twenty*,
and the canvas note says *"Twenty tables, an FTS5 search index"* — the twentieth is `work_order_templates`, added
by §11's screen map after the first count was written; **this file lists all twenty**): a mirror of the server
slice, a local-only outbox, the bookkeeping that joins them, the route-reading set, and one downloaded catalogue.

**Ten carry a `technician_id` column, `sync_state` carries it in its key and `search_index` is built from scoped
rows** — the handset is shared, so whose row it is has to be stored, not assumed. **tech** below means scoped that
way.

### 2.1 · Mirror — a slice of the server, read-mostly

| Handset table | Holds (the design's words) | Rows, typical day | Server table and fields it mirrors |
|---|---|---|---|
| `work_order` **tech** | The day and the next three. Number, window, status, outcome, priority, template id, premise, customer, asset | 11 — up to 300 on a read route | **`work_orders`** (`apps/metering/connections.py`, class `WorkOrder` — one of the six Work tables still in metering, T-43): `order_no` · `window_start`, `window_end`, `due_at` · **status = THREE server axes** (`AD-14`): `state` (planned · in_progress · blocked · completed · cancelled), `dispatch_state`, and the technician's own `accepted_by_technician` / `declined_at` · `outcome` · `priority` · `template`, `template_version` · `premises` · `asset` · customer **by walking** `account` → `customer_accounts` → `customers` (no customer column on the order; hard rule 8's spirit). Closed-at = `completed_at`. Served by `GET /work/mobile/today` and `/work/mobile/jobs/{id}` |
| `wo_item` **tech** | One row per thing to do on the job, whatever kind. `kind` = task · material · safety · checklist · position, label, must_do, photo_required, added_in_field, reason, state · `detail` JSON for what only that kind carries | ~209 | **Three server tables, one handset table** (`R130`): `work_order_tasks` (`seq`, `title`, `is_mandatory`, `photo_required`, `instruction`, `est_minutes`, `ticked_at`/`ticked_by`, `photo_attachment_id`) · `work_order_materials` (`part`, `planned_qty`, `used_qty`, `unit_of_measure`, **`unplanned`** = added_in_field for a material, `issued_at`) · `work_order_safety` (`seq`, `text`, `is_mandatory`, `ticked_at`/`ticked_by`). **NEW (work):** `added_in_field` + `reason` on a TASK (FF-18 *Add step*, `R7`) — the server has `unplanned` on materials only · the material's *reason* (FF-23) · **checklist questions that branch** (FF-19) — no server table holds them · **photographs per task as a COUNT** (`R110`; `photo_required` is a boolean today) · **freshness on a step** (`R18`, T-35) |
| `wo_reading` **tech** | Prompt, unit, min, max, photo_required, captured value, flagged, unable_to_read. Deliberately not folded into `wo_item` — tolerance compares min and max as columns | ~35 — up to 1,000 | **`work_order_readings`**: `prompt`, `unit_of_measure`, `min_value`, `max_value`, `photo_required`, `required`, `value` (+ `value_text`, `kind`), `in_range` = flagged, `captured_at`, `captured_by`, `photo_attachment_id`, `posts_as_meter_read`. **NEW (work):** `unable_to_read` as a reading-level answer (`R13`) — no column; the photo COUNT per reading (`R110`, `R97`) |
| `asset` | Meters and sub-meters in scope. Serial, badge, device id, model, size, parent · history JSON — past visits, rendered whole, never queried across | ~40 | **`assets`** (`apps/assets/models.py`): `serial_no`, `asset_no`, `model`, `manufacturer`, `size_class`, `parent_asset` (sub-meter), `unit` (of measure), `register_digits`, `meter_type`, `read_method`, `service_point` → `units` → `premises`. ⚠ **NEW (assets): `badge` and `device id`** — the design matches a scan *serial, then badge, then device ID* (`R43`) and the server has `serial_no`, `asset_no` and `external_ref` only; which of these is the badge is **not decided here** (an `OQ-FLD` to mint — the design's FF-38 shows serial `MTR-0471` and badge `88241` as two different values). **History JSON** — no single server source: `asset_maintenance`, past `meter_reads`, past `work_orders` on the asset; a server read that composes it is **NEW** (`07-endpoints.md` §3) |
| `premise` | Address and coordinates. The one place an address lives | ~30 | **`premises`**: `address_line`, `city`, `state`, `postal_code`, `lat`, `lng` (hard rule 8). A unit refines it by label (`units.label`) and **may carry its own `lat`/`lng`** (`BR-MET-1162`) — the handset must keep the unit's point where it has one, and say which it is showing. **NEW (metering):** premises-level access notes, hazard and gate code for a READ route (RW-07: *"Held on the property, so a job and a read can never disagree about the same gate"*) — today `access_notes`, `hazards`, `gate_code` live on `work_order_details`, per ORDER |
| `customer` | Name, account number, contact. **No balance, no tariff — those are online-only** | ~30 | **`customers.display_name`** · **`accounts.account_no`** · **`contacts`** (`full_name`, `phone`, `email`, `is_primary`). The bundle's `_customer_contact` serves the contact today. Balance and tariff are never stored on the handset (`AD-04`, `R16`) |
| `document` | SOPs, safety sheets and asset papers. `owner_kind` + `owner_id` say what it hangs off · title, kind, source, local file path, bytes | 19 | **`work_order_help`** (`kind`, `label`, `ref` — served as pre-signed links in the bundle, `BR-WRK-038`) and **`work_order_attachments`** (`document` link, `kind`). **NEW (work, with documents):** `owner_kind` + `owner_id` + `source` (camera · file · typed) — FF-60's permits and certificates on an ASSET, *"each with its source recorded"* (`R108`); `work_order_attachments` *"is close but has no source field and no asset link"* |
| `technician` | Everyone who has used this handset. Name, role, employment, photo path. The roster, so it is not scoped | 2–6 | **`technicians`** (`user`, `crew`, `role_label`, `van`, `status`, `shift_start`/`shift_end`) + the identity user's name. **NEW (work):** employment (employee · contractor — `R26` hides money from a contractor; the server has no such column on `technicians`) · profile photo (FF-44 *Change photo*) |

### 2.2 · Capture — local-only, written by the technician

| Handset table | Holds | Rows, typical day | Where it lands on the server |
|---|---|---|---|
| `outbox` **Critical · tech** | Every act the technician performed, one row each, with its idempotency key and capture order | ~180 — up to 1,000+ | **`work_sync_receipts`** (`key`, `kind`, `seq`, `captured_at`, `accepted_at`, `accepted_by`, `captured_by_technician`, `lat`, `lng`, `accuracy_m`, `fix_at`, `needs_review`, `received`) — one receipt per item, written BEFORE the act inside the same savepoint (`sync.py`). The act itself lands in its own table. **Kind gap — see §2.6** |
| `photo` **Critical · tech** | One row per photograph. Local path, bytes, watermark values, upload state | ~38 | **`work_photo_links`** (the declaration: `photo_id`, `sha256`, `reading_id` / `task_id`, `required`, `state` pending · staged · landed, `taken_at`, `captured_by`, `bytes_received`, `bytes_stored`, `landed_at`), then **`work_order_attachments`** once the background job files it (`idempotency_key` unique per `(tenant, work_order, key)`, `taken_at`, `device`) |
| `activity` **tech** | Every timestamped event on the job, one table. `kind` = status · remark · status events are dispatched, accepted, departed, arrived, started, each step, closed; a remark carries its text and author | ~88 | Status: **`work_order_assignments`** (append-only, `act`, `actor`, `at`, `reason` — `POST /work/mobile/jobs/{id}/acts` writes *depart* and *arrive*) + `audit_log`. Remarks: **`work_orders.technician_notes`** is ONE text field. **NEW (work):** a remark per row with its author and time (FF-30 *Notes — remarks, stamped with who and when*, `R10`) |
| `crew_time` **tech** | Travel and labour, per person per order | ~15 | **`work_orders.minutes_on_site`** + the close's `labour_time {arrived_at, finished_at, minutes}` in `field_data` (decision log 2026-10-05, `DEF-WRK-4127`) — **one pair per ORDER. NEW (work): per PERSON** (`R8`, FF-29, T-38 — *"Two technicians on one order are two time records and the cost is their sum"*) and **travel as its own clock** (`R9`) |

### 2.3 · Bookkeeping

| Handset table | Holds | Rows | Server counterpart |
|---|---|---|---|
| `sync_state` **tech (in the key)** | Per technician per table: last server cursor, last successful pull, last push, pending count. **The pair is the key** — one cursor per table would let the second technician's pull advance the first's and lose their deltas silently (`R134`) | 10 per technician | `GET /work/mobile/changes` returns an opaque `next_cursor` — **one feed, per technician by construction, jobs only.** **NEW (work, T-32):** a watermark per TABLE |
| `search_index` **tech** | An FTS5 virtual table over customer name, address, asset serial and badge, carrying `technician_id` — built from scoped rows, so a search cannot surface the other technician's customers | mirrors scope | local only |
| `settings` | Anything that must survive a reinstall and is not a preference. Device-level, so not scoped | ~15 | local; the can't-read reasons it caches come from a **NEW** server catalogue (§2.4) |

### 2.4 · Route reading — three more tables

| Handset table | Holds | Rows, typical day | Server table and fields it mirrors |
|---|---|---|---|
| `route` **tech** | Code, service, area, read type, cycle, window, notes, the reader it is assigned to | 1–2 | **`routes`** (`code`, `name`, `route_type`, `service`, `area`, `notes`, `assigned_to`, `cycle`, `status`) + **`read_windows`** (`period_start`, `period_end`, `read_on`, `expected_count`). `R87`: one reader per route for now, and *"the assignment stays a row that could become many"* — `routes.assigned_to` is one FK today, which is fine provided nothing is built that assumes it |
| `route_stop` **tech** | One row per premises — walk-order position, point, access notes, hazard. **The stop is the unit of work** | 47 — up to 300 | **`route_premises_orders`** (`premises`, `walk_order`) + `premises.lat/lng`. Access notes and hazard on a premises are **NEW** (see `premise` above) |
| `route_read` **Critical · tech** | One row per meter on the route, carrying everything a reading is — below | 151 — up to 1,000 | **`meter_reads`** — column by column in §2.5 |

### 2.5 · `route_read` — a reading is a RECORD; the number is one of its columns (`R88`)

The design's DDL, kept as drawn, with the server column each lands in:

```sql
-- A reading is a RECORD. The number is one of its columns.
CREATE TABLE route_read (
 id TEXT PRIMARY KEY,              -- idempotency key, minted at capture
 technician_id TEXT NOT NULL,      -- whose row it is; the scoping column
 route_id TEXT NOT NULL,
 stop_id TEXT NOT NULL,            -- the premises, not the meter
 asset_id TEXT NOT NULL,
 parent_asset_id TEXT,             -- set on a sub-meter
 account_id TEXT,                  -- STAMPED at collection, never the unit's current occupant
 -- what was read
 value NUMERIC,                    -- null when it could not be read
 unit TEXT NOT NULL,               -- always explicit, never assumed
 register TEXT,                    -- tou_on / tou_mid / demand / null
 -- THE READER'S status, and the reason when there is one
 reader_status TEXT NOT NULL,      -- read | could_not_read | read_with_problem
 no_read_reason TEXT,              -- one of the tenant's own eight-or-more
 warned_accepted INTEGER NOT NULL, -- 1 when out of range and taken anyway
 -- caught automatically, ZERO taps
 lat REAL, lng REAL, accuracy_m REAL,
 fix_quality TEXT,                 -- good | poor | none
 metres_from_record REAL,          -- distance to where the meter is recorded
 captured_at TEXT NOT NULL,        -- the device clock
 captured_by TEXT NOT NULL,
 identified_by TEXT NOT NULL,      -- scan | listed | typed
 off_route INTEGER NOT NULL DEFAULT 0,
 read_method TEXT NOT NULL,        -- from the tenant's list, never a hardcoded set
 -- added by the reader, ONE tap each
 remark TEXT,                      -- spoken by default
 remark_source TEXT,               -- voice | typed
 state TEXT NOT NULL               -- pending | sending | accepted | duplicate | refused
);
CREATE INDEX ix_read_send ON route_read (state, route_id, captured_at);
CREATE INDEX ix_read_stop ON route_read (stop_id);
-- Photographs stay in the one `photo` table, pointing at the reading.
-- Camera only; the stamp is burned into the pixels, not stored beside them.
```

| Handset column | Server `meter_reads` today | |
|---|---|---|
| `id` (the key) | — | **NEW (metering)** — an idempotency key on a field read; `meter_reads` has none, and `work_sync_receipts` is per ORDER (§2.6) |
| `asset_id`, `parent_asset_id` | `asset` (parent via `assets.parent_asset`) | exists |
| `account_id` (stamped) | `account` | exists — stamped at collection, never re-derived (`R88`) |
| `value`, `unit`, `register` | `current_value`, `unit`, `channel` | exists (`channel` is the register) |
| `route_id` | `route` | exists |
| `read_method` | `read_method` → the tenant's **`read_methods`** list (`apps/assets`, eight seeded, extensible — `BR-AST-043`) | exists |
| `captured_at` (device clock) | `read_at` | ⚠ **the server's clock is not stored separately** — `R92` wants both (*"the phone's at capture, the server's on arrival"*). **NEW** |
| `reader_status` | `status` / `rule_outcomes` are the ENGINE's verdict | **NEW** — `R96`: *"Two statuses, never merged. The reader says what happened … The engine decides what it means"* |
| `no_read_reason` | — | **NEW (metering)** + a **NEW catalogue** of can't-read reasons, *"eight seeded, tenant-extensible — the same pattern as `read_methods`"* (`R82`; the RW-17 image draws Dog · Locked · No access · Buried or covered · Obstructed · Meter not found · Unsafe · Illegible) |
| `warned_accepted` | — | **NEW** |
| `lat`, `lng`, `accuracy_m`, `fix_quality`, `metres_from_record` | — | **NEW** — Data §12: *"It has status, rule outcomes, route and read method — and no position, no accuracy, no device clock, no can't-read reason, no off-route flag"* |
| `captured_by`, `identified_by` | `imported_by` is an importer, not a reader | **NEW** |
| `off_route` | — | **NEW** (`R84`: accepted and marked) |
| `remark`, `remark_source` | — | **NEW** |
| `state` | — | handset only |

**A meter added in the field** (RW-20) is an `assets` row *pending until the office accepts it, and a photograph is
required* (`R85`) — **NEW (assets): a pending state that bills nothing until accepted**; today an asset's `status`
is a lookup with no such meaning recorded.

### 2.6 · The outbox's kinds against the server's — a gap the sync contract must close

The design's outbox `kind` list: `safety_tick | task_done | reading | material | note | signature | time | close |
raise`, and §11 adds `claim`. The server's `ITEM_KINDS` (`apps/work/sync_models.py:38`): `safety_tick`,
`task_tick`, `reading`, `material`, `attachment`, `signature`, `close`, `photo`.

| Handset kind | Server kind | |
|---|---|---|
| `safety_tick` | `safety_tick` | exists |
| `task_done` | `task_tick` | exists — **a name mismatch to settle in the wire mapping** (`R117`), never by renaming either side |
| `reading` | `reading` | exists, **per order**; a ROUTE reading has no order and no sync route (§2.5, `07-endpoints.md` §2) |
| `material` | `material` | exists |
| `signature` | `signature` | exists |
| `close` | `close` | exists |
| (photo declaration) | `photo` | exists — the declaration rides with the data (`AD-23`) |
| `note` | — | **NEW** — and until it exists a note sent as an unknown kind is *stored as received and flagged, never dropped* (`RECEIPT_KINDS` carries `unrecognised`, TECHNICIAN SYNC DESIGN (2)) |
| `time` | — | **NEW** (per-person labour, T-38) |
| `raise` | — | **NEW** (field-raised order, T-42; `R24` — no number until it syncs) |
| `claim` | — | **NEW** (T-39) — and claiming is ONLINE (`AD-04`), so it may be a direct call rather than an outbox kind; the design's §11 writes it to the outbox. Not decided here |

### 2.7 · Who owns a row — the two ids, and why they are solved differently (`AD-24`, `R131`–`R133`)

A handset is shared by several technicians in turn, and **a sign-out deletes nothing** — the previous technician's
unsent work has to stay and send under their name. So every technician's rows coexist in one database at the same
time, and ownership cannot be inferred from who is signed in.

**Tenant — a separate database FILE, not a column.** One SQLite file per tenant, `field-<tenant>.sqlite`, chosen at
sign-in. A contractor working for two utilities gets two files and picks one. A column would put the burden on every
query: nineteen tables and roughly two hundred reads would each have to remember the filter, and the one that forgets
is a cross-tenant leak that no test is looking for. A separate file makes the wrong read impossible rather than
unlikely — the same reasoning the server uses when it turns on forced row-level security instead of trusting each
query. **Cost: zero columns.** It is both the cheaper and the safer option, which is rare enough to say out loud.

**Technician — a real column, `NOT NULL`, on ten tables.** This one cannot be a separate file: a per-technician file
would hide the previous technician's outbox until they signed back in, and the whole point is that it sends on the
next signal under their own name.

| Tables | How it is scoped |
|---|---|
| `work_order` · `wo_item` · `wo_reading` · `route` · `route_stop` · `route_read` · `outbox` · `photo` · `activity` · `crew_time` | `technician_id TEXT NOT NULL`. Ten tables. Fixes the day list: without it the next technician to sign in sees the previous one's jobs |
| `sync_state` | In the key, per technician per table. Without it one technician's pull advances the other's cursor and the other loses deltas with nothing raising |
| `search_index` | Carries it, and is built from scoped rows. A customer enters the index once per technician who has a job there — small duplication, and search stops finding the other person's customers |
| `premise` · `customer` · `asset` · `document` · `work_order_templates` | **Not scoped, on purpose.** Shared reference data, reachable only by join from a scoped row — so it cannot be read without passing through the filter. Scoping it would mean two rows for one building, and an address lives in exactly one place |
| `technician` · `settings` | Not scoped. One is the roster the filter resolves against; the other is the device |

**The column is the smaller half. One helper is the other.** Ten tables and one scoped-query helper is defensible.
Ten tables and two hundred queries each remembering the filter is not — it only has to be forgotten once, and the
screen renders perfectly with the wrong person's data in it. So every read of a scoped table goes through one
function that injects the filter (`field-app/src/db/scoped.ts`), and **a test walks the query layer and fails if any
statement touches a scoped table without it** (`tests/scoping.test.ts`). **That test is the deliverable, not the
columns.**

⚠ **`12-security.md` §3 quotes the design's Security page, which says *"Every table carries `tenant_id` and every
query names it"*. That sentence is SUPERSEDED by `AD-24`** (*"Supersedes a sentence of mine that said 'every local
table carries tenant_id'. No table in the inventory carried it — it was a claim, not a design"*). **This section is
the rule.**

### 2.8 · The two tables that matter — the design's DDL

```sql
-- Every act, exactly once. The idempotency key is minted AT CAPTURE,
-- on the handset, so a re-send can never double-apply.
CREATE TABLE outbox (
 id TEXT PRIMARY KEY,            -- uuid, minted at capture = the idempotency key
 technician_id TEXT NOT NULL,    -- WHOSE ROW IT IS. Every read filters on this
 work_order_id TEXT,
 kind TEXT NOT NULL,             -- safety_tick | task_done | reading | material |
                                 -- note | signature | time | close | raise
 payload TEXT NOT NULL,          -- JSON
 seq INTEGER NOT NULL,           -- capture order WITHIN the order
 captured_by TEXT NOT NULL,      -- WHO DID IT. Usually = technician_id; when it
                                 -- differs the server stores and FLAGS, never refuses
 captured_at TEXT NOT NULL,      -- ISO 8601, device clock
 lat REAL, lng REAL, accuracy_m REAL,
 state TEXT NOT NULL,            -- pending | sending | accepted | duplicate | refused
 attempts INTEGER NOT NULL DEFAULT 0,
 last_error TEXT,
 settled_at TEXT                 -- when the server answered; drives the purge
);
CREATE INDEX ix_outbox_send ON outbox (state, work_order_id, seq);
CREATE INDEX ix_outbox_purge ON outbox (state, settled_at);
-- Photos: the BYTES live on disk, the row lives here.
CREATE TABLE photo (
 id TEXT PRIMARY KEY,
 technician_id TEXT NOT NULL,    -- whose row it is; the scoping column
 outbox_id TEXT,                 -- the task, reading or remark it proves
 work_order_id TEXT,
 local_path TEXT NOT NULL,       -- file on disk, deleted once uploaded
 bytes INTEGER NOT NULL,
 width INTEGER, height INTEGER,
 captured_by TEXT NOT NULL,
 captured_at TEXT NOT NULL,
 lat REAL, lng REAL, accuracy_m REAL, -- burned into the watermark too
 state TEXT NOT NULL,            -- pending | uploading | uploaded | failed
 attempts INTEGER NOT NULL DEFAULT 0,
 remote_id TEXT,
 uploaded_at TEXT
);
CREATE INDEX ix_photo_send ON photo (state, captured_at);
```

**`photo.id` is the server's `work_photo_links.photo_id`** (a client uuid, unique per tenant) and the declaration
carries its `sha256` — the server refuses bytes whose hash does not match (`work.photo.hash_mismatch`, 409) and keeps
nothing, so the handset sends again.

**Why a photo on every reading does not fit.** A 151-meter route with photographs only where they are needed — 7
could-not-reads and 11 flagged — is 18 photos, about 5 MB. Fine. A 1,000-read route with a photograph on every
reading is 300 MB in one day, against a 500 MB target footprint and an 11 MB daily data budget. It is possible, and it
is a costed choice the utility makes per reading prompt — not a default anybody should drift into (`R97`). `R110`
moves the 151-meter figure: *"Three per task turns a 151-meter route's 18 photographs and 5 MB into nearer 50 and
15 MB — stated rather than left as the old figure."*

### 2.9 · Downloaded catalogue — read-only, shared by everyone on the handset

| Handset table | Holds | Rows | Server |
|---|---|---|---|
| `work_order_templates` | Every template published in the back office, so FF-62 can raise an order offline. Columns: `id`, `name`, `version`, `service`, `published`, `step_count`, `safety_count`, `reading_count`, `body` (JSON), `last_used_at`. Not scoped — it is the tenant's catalogue, identical for every technician on the device | ~24 | **`work_order_templates`** (`apps/metering/connections.py`: `template_no`, `name`, `service`, `version`, `active`, `type`, `skill`, `crew_size`) + **`work_order_template_versions`** (`version`, `published_at`) + the bodies in `wot_details`, `wot_safety`, `wot_tasks`, `wot_materials`, `wot_readings`, `wot_help`. **NEW: a catalogue read a technician may call** — `GET /work/templates` carries `WorkTemplateListRead`, which admits office roles and a Billing Clerk, not the field technician (`07-endpoints.md` §3). `R112`: the order *takes its own copy and stamps the version* — the server already does (`BR-WRK-008`, `work_orders.template_version`) |

---

## 3 · Search

Two kinds, and the difference is the thing to get right: **local search is instant and bounded; server search is
complete and needs a signal** (`R41`).

| Screen | Search and filter by | Scope | Index that makes it instant |
|---|---|---|---|
| FF-10 Today | Customer name · address · work-order number · status · service · priority · window | Local | `work_order(window_start, due_at, number)` + FTS5 |
| FF-11 Nearby | Radius (1 / 2 / 5 / 10 mi) · job type · priority · due date · unassigned only | Server | Server-side spatial query on the premise point — **NEW**, T-40 |
| FF-35 Completed | Date range · outcome · customer · work-order number · accepted or not | Local 14 days, then server | `work_order(status, closed_at)` |
| FF-41 Asset search | Serial · badge · device ID · address · account number | Local first, server on demand | `asset(serial)`, `asset(badge)`, `asset(device_id)` + FTS5 |
| FF-38 Scan | The scanned code, matched against serial then badge then device ID | Local | Same three indexes |
| FF-28 Documents | Title · kind · which job it belongs to | Local | `document(work_order_id)` |
| FF-47 Timesheet | Date range · job or admin · technician | Local | `crew_time(technician_id, started_at)` |
| FF-50 Sync | State (pending / failed) · kind · technician | Local | `ix_outbox_send` |

**One free-text box, one index.** A single FTS5 virtual table covers customer name, address, asset serial and badge.
One query serves Today, Assets and Scan. At 10,000 rows it answers in under a millisecond, so the field never lags
behind the typing — and the technician can scan instead of typing in the first place.

**The honest limit, shown on screen** (`R42`). Offline, FF-41 searches only what is on the handset and says so:
*"Only today's assets are here. A signal searches the whole utility."* A search that silently returns a subset is
worse than one that refuses — the technician concludes the meter does not exist.

**Note on FF-11's radius:** `R34` makes the radius a setting inside the app, **default 2 miles**. The server-side
query must be **paged, with no hard cap** (`NFR-3`, `NFR-5`; T-40).

---

## 4 · Sending a thousand readings

A meter-reading route is the hard case: **500 to 1,000 readings captured over a day with no signal, then sent at
once.**

| | Batches of 50, in capture order, resumable |
|---|---|
| **Capture** | Each reading is one outbox row with a key minted on the spot. 1,000 inserts inside one transaction take milliseconds on SQLite — capture is never the bottleneck |
| **Batch size** | **50 items per request.** Not 1,000 in one (a timeout loses everything and a web worker is given sixty seconds — `docker-entrypoint.sh`, `GUNICORN_TIMEOUT:-60`) and not 1,000 separate requests (a thousand round trips on a weak connection). 50 items is a few hundred kilobytes and finishes in a second or two on 3G (`R45`) |
| **Order** | Capture order is preserved within a work order, because a safety tick must land before the close it unlocks. Across orders the sequence does not matter, so batches can be grouped by order. (The server applies a batch in the order it arrived and **does not re-sort** — `sync.py`: *"a server that helpfully re-sorted the batch would silently repair a tampered client"*) |
| **In flight** | At most two batches at a time. More does not go faster on a cellular link and makes failures harder to reason about (`R50`) |
| **Per-item results** | The server answers accepted / duplicate / refused for each item, never a boolean for the batch. One bad row does not poison the other 49 — that is what the savepoint on the server is for |
| **Resume** | State lives per row. A batch that dies halfway leaves 23 accepted and 27 pending; the next attempt sends the 27. Nothing is re-sent that was accepted, and if it is, the key makes it a duplicate and nothing doubles |
| **Retry** | Exponential backoff with jitter: 2s, 4s, 8s, 30s, 2m, 10m. After 5 failures the row shows on FF-50 as needing attention, never silently dropped |
| **Refused** | A refusal is something the technician must see and redo. It surfaces on FF-50 with the server's reason, and the row stays until they act (`R48`) |

**Worked figure.** 1,000 readings = 20 batches of 50. At roughly 1.5 seconds a batch on a poor connection, that is
**about 30 seconds of data sync** — and the technician can keep working through it. Photos are a separate phase and
may take much longer.

**Against the server today:** `POST /work/mobile/jobs/{id}/sync` takes one ORDER's items, up to `MAX_ITEMS = 200`
(`sync.py:118`), so 50 fits. **A route read has no order, so 1,000 route readings have no sync route at all** — that
is the largest server gap this page opens (`07-endpoints.md` §2, T-30).

---

## 5 · Photos, asynchronously

| | |
|---|---|
| **Declare, then send** | The declaration rides with the data; the bytes follow separately. When a photograph is taken the handset sends its id, its sha256, what it proves and whether the template required it — in the same payload as the reading. The bytes go up on their own afterwards. This supersedes an earlier *"data first, photos after"* framing on this page. It is better, and it is what `work_photo_links` already does: because `required` is copied at declaration, *"required photographs still uploading"* is one query — so the office never sees a reading as complete when its evidence has not arrived (`AD-23`) |
| **Before queueing** | Compressed to a 1,600 px long edge, quality stepped down until the bytes fit (~300 KB). If even the smallest quality will not fit, it is queued anyway and the server checks — a technician learning at the end of the day that a photo was dropped is worse than a large upload. ⚠ **The ~300 KB target conflicts with `BR-WRK-047` (70–100 KB, PO-ruled) — §12** |
| **Watermark** | Burned in at capture — date, time, coordinates with accuracy, technician, work-order number. Burned in, not overlaid, so it survives export (`R94`) |
| **Upload** | One at a time, oldest first, resumable, with the same backoff as the data phase. One failure never blocks the next photo (`R53`) |
| **Network choice** | ⚠ **`R54` SUPERSEDED 2026-10-28 (PO, FB-015 option A).** Photos upload on mobile data AND wi-fi by default, data items first. FF-51's *Photos on wi-fi only* (OFF by default) makes them wait for wi-fi, and only then does FF-50 say *Photos wait for wi-fi.* *(Read until then: "Wi-fi only by default … unless the technician turns it on".)* |
| **Visible** | FF-50 shows photos on their own line — *"all work sent · 38 photos uploading"* reads as finished, not broken. The sync number counts items, not bytes, so one large photo cannot swamp it (`R33`, `R65`) |
| **Background** | Continues when the app is closed, within what each platform allows, and resumes on next launch |

**Worked figure.** 38 photos × ~300 KB ≈ **11 MB**. About a minute on depot wi-fi. On a weak cellular link it may run
for an hour — which is exactly why it is a second phase and why the day's work is already safely on the server before
it starts. (At the signed 100 KB ceiling the same 38 photos are ≈ 3.7 MB.)

---

## 6 · Refresh

Four triggers, and **never a full re-download** (`R56`).

| Trigger | When | What it pulls |
|---|---|---|
| Pull to refresh | The technician asks, on any list | Delta for that scope, immediately |
| App comes forward | Foreground, if the last pull was over 5 minutes ago | Delta, silently |
| Push-triggered | The server pushes a change — new job, cancelled job, schedule change, payment cleared | Just that record, not the whole day |
| Periodic | Every 15 minutes while on shift and connected | Delta |

**How a delta works, and the part everyone forgets.**

* **Cursor.** `sync_state` keeps a watermark per technician per table. The request says *"everything changed since
  X"* and the response carries a new X. A full re-download happens only on first sign-in and after a schema change.
* ⚠ **Tombstones** (`R57`). The delta must also carry what was removed. A job reassigned to someone else, an order
  cancelled, an asset off the route — without a tombstone it stays on the handset forever and the technician drives
  to a job that is not theirs. This is the single most common bug in offline sync and it is invisible in testing,
  because nothing ever looks wrong. **Server today:** `GET /work/mobile/changes` already emits `removed` for a job
  UNASSIGNED from this technician (`work_order_assignments.act = "unassign"`). **Not covered:** a cancelled order
  still assigned (it arrives as an `upsert` carrying its state — the handset must treat a cancelled state as a
  removal or the server must send one), an asset leaving a route, and any route data at all. T-31.
* **Conflict** (`R58`). The server wins on mirrored tables; the handset wins on captured ones. A dispatcher changing a
  window overwrites the local copy. A reading the technician took is never overwritten — it is in the outbox and the
  outbox only moves one way.
* **Ordering** (`R59`). A pull never runs while a push is mid-batch for the same order, so a stale mirror cannot
  overwrite a record the server has just accepted.

---

## 7 · What happens to the data after it syncs

The question that decides whether a handset still works in six months.

| Data | After a successful sync | Kept for |
|---|---|---|
| `outbox` accepted | Row kept so the technician can see what they sent, and so a duplicate reply has something to match | 7 days |
| `outbox` duplicate | Same | 7 days |
| `outbox` refused | Never purged. It stays until the technician acts on it | Until resolved |
| `outbox` pending | Never purged, at any age. **This is the hard rule** | Until sent |
| Photo file on disk | Deleted the moment the server confirms it. This is what keeps the handset usable | 0 — deleted |
| `photo` row | Kept with its `remote_id` so the gallery can still show it was taken | 7 days |
| Closed work orders | Kept so FF-35 Completed works offline | 14 days |
| Asset history | Kept while the asset is in scope; dropped when it leaves the route | While in scope |
| Documents | Kept while referenced by a job in scope, then evicted oldest-first above a cap | 200 MB cap |
| Another technician's unsent work | Untouched by a sign-out or a handover. It sends under their name whenever this handset next has a signal | Until sent |

**Three rules that are never bent** (`R60`, `R61`, `R63`):

1. Nothing with unsent work is ever deleted, whatever its age and whoever is signed in.
2. A photo file is deleted only after the server has confirmed receipt — never after merely sending it.
3. A purge runs on app start, not on a timer, so it can never run mid-upload.

**Target footprint: under 500 MB** (`R62`). Photos are the only thing that can break it, and they leave on upload.
Without rule 2, a technician shooting 38 photos a day fills a 64 GB handset in about four years — but a technician on a
photo-heavy route fills it in months.

⚠ **14 days of closed jobs is the design's number, not the utility's** — `12-security.md` §7 item 4 says it must be
reconciled with the utility's data policy before code.

---

## 8 · What it costs the technician's mobile allowance

| Direction | Typical day, 11 jobs | Read route, 1,000 readings |
|---|---|---|
| Down · first sync of the day | 2–4 MB of JSON | 6–10 MB |
| Down · documents | Up to 20 MB, but once — cached until they change | Same |
| Down · deltas through the day | Under 500 KB | Under 1 MB |
| Up · the outbox | ~400 KB | 1–2 MB |
| Up · photos | ~11 MB (38 × 300 KB) | Varies — often the largest number on the page |
| **Realistic day total** | **15–18 MB, or 4–6 MB with photos on wi-fi only** | **10–14 MB plus photos** |

**Three things that keep it small:** deltas, never full pulls — the day is downloaded once, then only what changed;
photos default to wi-fi — which is why the depot sync at 07:40 matters, and why FF-08 asks the technician to wait for
100%; documents are cached by content — a safety sheet downloads once and is reused across every job that cites it.

---

## 9 · What is a column, and what is a blob (`R116`, `R117`)

The server speaks JSON. The handset is relational. **The rule is one sentence, and the second half matters more than
the first: queried, sorted or filtered → a column. Only ever displayed → a blob.**

A work order arrives as a deep JSON document: the order, its template snapshot, its tasks with their photo
requirements, its safety rows, its readings, its help text. Normalising all of that into tables would be a week of
mapping code for no gain, because most of it is only ever rendered. So the order's own facts — number, window,
status, priority, premise, account, asset — become columns, because the day list sorts and filters on them. The
template snapshot stays as one JSON blob, read whole when the job opens. SQLite's JSON1 functions reach into it on the
rare occasion we need to.

| What arrives | Stored as | Why |
|---|---|---|
| Order number, window, status, priority | Columns | The day list sorts and filters on every one |
| Premise, account, asset ids | Columns | Joined on, and the stop groups by premise |
| The template snapshot | JSON blob | Deep, nested, read whole when the job opens, never queried across |
| Tasks, safety rows, readings | Columns | Each gets a row — they are ticked, counted and sent individually |
| Help text, SOP references | JSON blob | Displayed, never searched |
| Rule outcomes from validation | JSON blob | Rendered through named keys only — never iterated, which is a signed rule |
| Reading value, unit, status, position | Columns | The outbox batches, orders and resumes on them |
| Anything a future server adds | JSON blob | An unknown field is kept and sent back untouched rather than dropped |

**The half that actually bites: the mapping is explicit and versioned.** A web app renames a server field and ships
the fix the same hour. A handset cannot. A technician on a route has the old build until they reach wi-fi, and
perhaps until the app store approves the next one — days. So the wire shape and the local shape are two declared
things with a mapping between them, not one shape assumed to be both. **The payload carries a schema version; the
handset refuses a version it does not know and says so, instead of silently storing nulls.** An unknown field is
preserved, not dropped, so a newer server's data survives a round trip through an older handset. **Server today:**
no response carries a schema version — **NEW** (`07-endpoints.md` §0).

---

## 10 · Deleting after it is sent (`R118`)

§7 says how long things are kept. This is how they actually go — the order, the triggers and the three cases that
lose data if they are wrong.

| When | What happens, in this order |
|---|---|
| The server confirms a photo | 1. The file on disk is deleted. 2. The row is kept with its `remote_id`, so the gallery still shows it was taken. Never the other way round — a row without a file is a gap; a file without a row is just bytes |
| An item is accepted | State moves to accepted and `settled_at` is stamped. Nothing is deleted yet — the technician can still see what they sent |
| App start, 7 days later | Accepted and duplicate outbox rows are hard-deleted. On start, never on a timer, so a purge can never run mid-upload |
| App start, 14 days later | Closed and accepted work orders go, and their tasks, readings, materials and photo rows go with them — one cascade, one transaction |
| A route is turned in | Stops and reads stay 14 days so Completed works offline, then cascade together |
| A job leaves your day | The delta carries a removal; the mirror row is deleted on sight. Captured work against it is not — it still has to reach the server |
| Documents over the cap | Oldest-first eviction above 200 MB, skipping anything a job in scope still cites |
| Sign-out | Nothing is deleted. Not the session's work, not the other technician's (`R64`) |
| The office signs the device out | Mirror tables are dropped. The outbox and its photo files are not — they send on next contact, then go. A remote wipe that discards unsent work is a remote wipe that loses a day (`R115`) |

**Three rules with no exceptions:** (1) Nothing unsent is deleted. At any age, under any sign-in, including work that
is not yours. (2) A refused item is never purged by age — it waits for a person. (3) A delete is one transaction with
its cascade. A half-deleted job is worse than a stale one, because the screen renders and the data is wrong.

---

## 11 · Every screen, and the tables behind it

What each screen reads and writes. **This is the check that catches a screen needing a table nobody designed — and it
caught two, noted at the foot.** `R119`: no SQL in a screen; every query lives in `db/queries/`, one file per table,
which is what makes this map checkable rather than aspirational.

| Screen | Reads | Writes |
|---|---|---|
| FF-10 Today | `work_order` · `premise` · `customer` · `sync_state` | — |
| FF-11 Nearby | server only · `premise` for distance | — |
| FF-12 Claim | `work_order` | `outbox` (claim) |
| FF-15 Job | `work_order` · `wo_item` · `wo_reading` · `document` | `activity` |
| FF-16 Safety | `wo_item` (safety) | `outbox` · `activity` |
| FF-17 Tasks | `wo_item` (task) · `photo` | `outbox` · `photo` |
| FF-18 Add step | `wo_item` | `wo_item` · `outbox` |
| FF-20 Readings | `wo_reading` · `asset` · `photo` | `outbox` · `photo` |
| FF-25 Customer | `customer` · `premise` · server for money | — |
| FF-27 Disconnect · FF-61 Reconnect | server only · `work_order` | `outbox` (unverified stamp) |
| FF-29 Crew | `technician` · `crew_time` | `crew_time` · `outbox` |
| FF-33 Signature | `work_order` | `photo` · `outbox` |
| FF-34 Close | every `wo_*` | `outbox` · `activity` |
| FF-38 Scan | `asset` · `search_index` | — |
| FF-50 Sync | `outbox` · `photo` · `sync_state` | `outbox` · `photo` (state) |
| FF-56/57 Activate | — | `technician` · session · `settings` |
| FF-58 Hand back | `work_order` | `outbox` · `activity` |
| FF-60 Asset papers | `asset` | `document` (owner = asset) · `outbox` |
| FF-62 Pick a template | `work_order_templates` | — |
| RW-01/02/03 Routes | `route` · `route_stop` · `sync_state` | `sync_state` |
| RW-05 The walk | `route_stop` · `premise` · `route_read` | — |
| RW-06 The stop | `route_stop` · `asset` · `customer` | — |
| RW-09 Read entry | `route_read` · `asset` | `route_read` · `outbox` · `photo` |
| RW-17 Can't read | `settings` (the reason list) | `route_read` · `outbox` · `photo` |
| RW-20 Add a meter | `premise` | `asset` (pending) · `outbox` · `photo` |
| RW-22/23 Progress | `route_read` · `route_stop` | — derived, never a stored counter |
| RW-25/26/27 Turn in | `outbox` · `photo` · `route_read` | `outbox` · `sync_state` |

**The map caught two tables nobody had designed.**

* **Asset papers** — FF-60 attaches certificates, permits and typed values to a newly fitted meter, each with its
  source recorded. Nothing held it. It is now `document` with `owner_kind` + `owner_id` and a `source` column
  (camera / file / typed) — a table in the first draft, folded into `document` in the reduction pass because the
  shape was identical.
* **template** — FF-62 offers every published template the back office made, which means the catalogue has to be on
  the handset to raise an order offline. There was no table and no download for it. Columns: `id`, `name`, `version`,
  `service`, `published`, `step_count`, `safety_count`, `reading_count`, `body` (JSON), `last_used_at`. It joins the
  day's download, which is a change to §4's figures.

**Screens the map does not list, and what they need — ours, recorded so the next lane does not rediscover it:**
FF-19 Checklist (branching questions — no table, §2.1), FF-30 Notes (remarks — `activity` with `kind = remark`),
FF-31 Activity (`activity`), FF-46 Shifts / FF-45 Availability / FF-48 Admin / FF-47 Timesheet (`crew_time` and the
`technicians.status`; non-job time has no server home — `NEW`), FF-49 Van (stock on the van — reads `parts` stock by
van; **out of scope to reconcile**, Walkthrough §5), FF-42 Alerts / FF-43 Emergency (push payloads; no local table —
an acknowledgement is an online act).

---

## 12 · What the server already has, and what it needs

*"Checked against the code on 2026-10-21, not assumed. Most of the hard part is built, and two of its design notes are
better than what this page previously said."* Re-checked by this lane the same day against this branch.

**Already there**

* **`work_order_attachments`** — one file the phone sent. Its `idempotency_key` is minted on the handset and scoped to
  `(tenant, work_order, key)` rather than `(tenant, key)`, because two phones can independently mint the same short
  key. The model's own note gives the reason: nine photographs queued offline, the sync retried after a timeout, and
  without the key the supervisor sees every one twice.
* **`work_photo_links`** — the declaration: `photo_id`, the phone's `sha256`, `reading_id` or `task_id`, `required`,
  `taken_at`, `captured_by`, and `staged` for the landed bytes.
* **`TechnicianDevice`** (`technician_devices`) — tenant, technician, token, platform, label, active, registered and
  last-seen.
* **`work_order_templates`** — versioned, and an order takes its own copy.
* And **`taken_at` is not `created_at`, deliberately**: the shutter closed at 16:02 in a meter cupboard with no
  signal; the row reached the server at 17:40. A supervisor reviewing a disputed read is asking the first question.

**What is genuinely new — mostly columns, one table** (the design's list, each with its owning module added here)

| What | Shape | Why | Owner |
|---|---|---|---|
| `document` (`owner_kind`, `owner_id`, `source`) | Columns | FF-60's permits and certificates, each with its source recorded. `work_order_attachments` is close but has no source field and no asset link | work (documents) |
| Field capture on `meter_reads` | Columns | It has status, rule outcomes, route and read method — and no position, no accuracy, no device clock, no can't-read reason, no off-route flag | metering |
| Can't-read reasons | Catalogue | Eight seeded, tenant-extensible — the same pattern as `read_methods`, which is already eight and already extensible | metering (with `read_methods` in assets) |
| Photographs per task | Column | `required` is a boolean today; the template needs a minimum count | work |
| Freshness on a step | Column | So a step can declare it needs a figure no older than five minutes, and no code knows what a disconnect is | work |
| Reconnect fee | Seam method | The money seam answers *what is the balance*; it has to answer *is this fee paid* | payments (read seam) |
| The capture credential | Columns | `TechnicianDevice.token` exists. `AD-21`'s two-credential split needs one or two more, not a table | work + identity |
| Template catalogue read | Endpoint | The table exists; the handset has no way to download it, and FF-62 cannot raise an order offline without it | work |

**Found by this lane on 2026-10-21, in addition to the design's list:**

| Gap | Where the design names it | Owner |
|---|---|---|
| `assets.badge`, `assets.device_id` (or a ruling on which existing column is which) | `R43`, FF-38, FF-41 | assets |
| Premises-level access notes / hazard / gate code for read routes | RW-07 | metering |
| Task `added_in_field` + `reason`; material `reason` | `R7`, FF-18, FF-23 | work |
| Branching checklist questions | FF-19 | work |
| Remark rows with author and time | `R10`, FF-30 | work |
| Per-person labour and a separate travel clock | `R8`, `R9`, FF-29 | work |
| Employment (employee · contractor) on a technician | `R26` | work |
| A pending (unbilled-until-accepted) field-added meter | `R85`, RW-20 | assets |
| An idempotent sync route for ROUTE reads | §4, E2E-03 | metering |
| Outbox kinds `note`, `time`, `raise`, `claim` | §2.6 | work |
| A schema version on every payload | §9, `R117` | work |
| Per-table watermark; tombstones for cancelled orders and route changes | §6, `R57`, `R134` | work, metering |

**Photographs: binary, never base64** (`R124`)

| Decision | Reason |
|---|---|
| Binary bytes, multipart | Base64 is 33% larger — 11 MB of photographs becomes 14.6 MB |
| One photograph per request | You cannot resume a base64 blob inside a JSON body, and the photo phase is explicitly resumable |
| Never through JSON | The whole blob sits in memory as a string. On a mid-range Android that is a crash, not a slowdown |
| Hash declared first | The phone sends its sha256 with the declaration, so the server can refuse bytes that do not match what was promised |
| Files, not blobs, at rest | `staged` holds the landed bytes only until the background job files them. 137 MB a day of photographs living in PostgreSQL would be the wrong place |

**Synchronous or background — the split that matters** (`R125`, `R126`). Data items: **synchronously** — the
technician needs the per-item receipt in the response (accepted, duplicate, refused); the refused-item flow on RW-27
depends on knowing which. Photo bytes: **accepted synchronously, filed in the background** — bytes land in `staged`,
a job moves them into the attachment. And the subtlety that decides whether evidence survives: the handset deletes a
photo file only on confirmed receipt, **so the 200 must come from the bytes being durably stored, never from a job
being enqueued.** Return on enqueue, and a later job failure means we told a handset to delete evidence that never
landed. **Server today:** `photo_links.receive_bytes` writes `staged` and commits it BEFORE it enqueues the job and
answers — the bytes are in PostgreSQL when the 200 leaves, so `R125` holds as built.

### Volume, at the top of the ICP

| Measure | Normal day | Day with three read routes |
|---|---|---|
| Technicians in the field | ~12 of 20 staff | same |
| Items to send | 2,400 | 4,800 |
| Photographs | ~460 a day at 300 KB = **137 MB** | |
| Photograph storage | **~34 GB per utility per year** — the number that drives where they live | |
| The shape that matters | Everybody syncs at the depot between 16:00 and 17:00. The whole day arrives in one hour: **~96 batch requests and ~8 photograph uploads a minute.** Comfortable — but it is a peak, not an average | |

| Limit | Value |
|---|---|
| Items per batch | 50, about 1 MB |
| Photographs per request | One, 10 MB ceiling |
| In flight per device | 2 batches and 1 photograph |
| Per tenant | ~600 requests a minute — twelve technicians syncing at once, with headroom |

⚠ **THE PHOTOGRAPH FIGURES ABOVE ARE AT 300 KB; THE SIGNED RULE IS 100 KB.** `BR-WRK-047` (CONFIRMED, PO
2026-09-04/05 and 2026-10-04: *"you also need to compress images to 70 to 100 Kb before you upload"*; *"you cannot
reject the photo"*) — the server ACCEPTS any real image and shrinks anything over 100 KB before storing it. At the
signed ceiling the same ~460 photographs are **≈ 46 MB a day and ≈ 11 GB a year** per utility, and the design's
10 MB per-request ceiling is a transport limit, not a storage size. **Which figure governs the handset's compressor is
for the PO** (a ruling that collides with a signed rule — law 13's first case); until then the signed rule is the one
built to. Recorded for the coordinator to mint as an `OQ-FLD` question; not decided here.

### Tenant id: from the credential, never from the payload (`R127`)

On the server, every new table carries `tenant_id` under forced row-level security. On the handset the tenant IS the
database file — `field-<tenant>.sqlite`, §2.7 — so no local table carries the column and no local query can reach
across one. **Either way, the part that decides whether it is safe is the same: the tenant is resolved from the
capture credential, not read out of the request body.** A tenant id in a payload is an attack surface; a tenant-bound
credential means a handset physically cannot send to the wrong one. **Server today:** routes are path-tenanted
(`/api/{tenant}/…`, PO 2026-08-10) and the capture token is signed with its tenant (`mobile.issue_capture_token`,
field `"t"`); no field-app route reads a tenant from a body.
