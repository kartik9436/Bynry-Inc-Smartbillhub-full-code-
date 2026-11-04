/**
 * 0001 — the handset store, from zero. The design's nineteen tables
 * (Mobile data §2) plus the store's two housekeeping tables.
 *
 * Forward only: there is no `down`. A handset on a route cannot be rolled back
 * by a deploy, so a mistake here is corrected by 0002, never by editing this.
 * (`migrations.test.ts` holds this file's text to a recorded hash.)
 */
import type { Migration } from './types';

const SEND_STATE = `CHECK (state IN ('pending','sending','accepted','duplicate','refused','held_for_review'))`;

export const m0001: Migration = {
  id: 1,
  name: 'initial',
  statements: [
    // ── The store's own housekeeping ───────────────────────────────────────
    `CREATE TABLE db_meta (
       key   TEXT PRIMARY KEY,
       value TEXT NOT NULL
     )`,

    // ── Mirror: a slice of the server ──────────────────────────────────────
    // Not scoped: the roster the scope resolves against (Mobile data §2).
    `CREATE TABLE technician (
       id                TEXT PRIMARY KEY,
       name              TEXT NOT NULL,
       role              TEXT,
       employment        TEXT,
       photo_path        TEXT,              -- a file on disk, never bytes
       last_signed_in_at TEXT,
       updated_at        TEXT NOT NULL
     )`,

    // An address lives here and nowhere else (CLAUDE.md hard rule 8).
    `CREATE TABLE premise (
       id           TEXT PRIMARY KEY,
       premise_no   TEXT,
       address_line TEXT,
       locality     TEXT,
       region       TEXT,
       postal_code  TEXT,
       lat          REAL,
       lng          REAL,
       extra        TEXT,                   -- unknown server fields, kept and sent back untouched
       updated_at   TEXT NOT NULL
     )`,

    // No balance, no tariff — those are online-only (Mobile data §2).
    `CREATE TABLE customer (
       id             TEXT PRIMARY KEY,
       name           TEXT,
       account_number TEXT,
       phone          TEXT,
       email          TEXT,
       extra          TEXT,
       updated_at     TEXT NOT NULL
     )`,

    // A field-added meter is `pending` until the office accepts it (R85); it is
    // captured work then, tied to its outbox row, and the purge leaves it alone.
    `CREATE TABLE asset (
       id              TEXT PRIMARY KEY,
       serial          TEXT,
       badge           TEXT,
       device_id       TEXT,
       model           TEXT,
       size            TEXT,
       service         TEXT,
       parent_asset_id TEXT,
       premise_id      TEXT,
       status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','pending')),
       outbox_id       TEXT,                 -- set on a field-added meter
       history         TEXT,                 -- JSON, rendered whole, never queried across
       extra           TEXT,
       updated_at      TEXT NOT NULL
     )`,
    `CREATE INDEX ix_asset_serial ON asset (serial)`,
    `CREATE INDEX ix_asset_badge ON asset (badge)`,
    `CREATE INDEX ix_asset_device ON asset (device_id)`,
    `CREATE INDEX ix_asset_premise ON asset (premise_id)`,

    // SOPs, safety sheets and asset papers. `source` records where each came
    // from (R108); a captured one carries its outbox row and is never evicted
    // while that row is unsent.
    `CREATE TABLE document (
       id           TEXT PRIMARY KEY,
       owner_kind   TEXT NOT NULL CHECK (owner_kind IN ('work_order','asset','template','tenant')),
       owner_id     TEXT,
       title        TEXT NOT NULL,
       kind         TEXT,
       source       TEXT NOT NULL CHECK (source IN ('server','camera','file','typed')),
       local_path   TEXT,                   -- a file on disk, never bytes
       bytes        INTEGER NOT NULL DEFAULT 0,
       content_hash TEXT,                   -- cached by content (Mobile data §8)
       outbox_id    TEXT,
       last_used_at TEXT,
       updated_at   TEXT NOT NULL
     )`,
    `CREATE INDEX ix_document_owner ON document (owner_kind, owner_id)`,
    `CREATE INDEX ix_document_evict ON document (last_used_at)`,

    // The day and the next three. Composite key: if a job moves from Dana to
    // Marco on one shared handset, each has their own row until the tombstone
    // reaches Dana's — one key would let Marco's pull overwrite hers.
    `CREATE TABLE work_order (
       technician_id    TEXT NOT NULL,
       id               TEXT NOT NULL,
       number           TEXT,
       type             TEXT,
       state            TEXT,
       dispatch_state   TEXT,
       outcome          TEXT,
       priority_code    TEXT,               -- a badge, never a sort key (BR-WRK-035)
       priority_rank    INTEGER,
       template_id      TEXT,
       template_version TEXT,
       premise_id       TEXT,
       customer_id      TEXT,
       account_id       TEXT,
       asset_id         TEXT,
       window_start     TEXT,
       window_end       TEXT,
       due_at           TEXT,
       est_minutes      INTEGER,
       access_notes     TEXT,
       hazards          TEXT,
       gate_code        TEXT,
       closed_at        TEXT,               -- set on the handset when the close is captured
       needs_bundle     INTEGER NOT NULL DEFAULT 1,
       body             TEXT,               -- the template snapshot, JSON, read whole
       extra            TEXT,
       server_updated_at TEXT,
       updated_at       TEXT NOT NULL,
       PRIMARY KEY (technician_id, id)
     )`,
    `CREATE INDEX ix_wo_day ON work_order (technician_id, window_start, due_at, number)`,
    `CREATE INDEX ix_wo_closed ON work_order (technician_id, state, closed_at)`,

    // One row per thing to do, whatever its kind (R130).
    `CREATE TABLE wo_item (
       technician_id    TEXT NOT NULL,
       id               TEXT NOT NULL,
       work_order_id    TEXT NOT NULL,
       kind             TEXT NOT NULL CHECK (kind IN ('task','material','safety','checklist')),
       position         INTEGER NOT NULL,
       label            TEXT NOT NULL,
       must_do          INTEGER NOT NULL DEFAULT 0,
       photo_required   INTEGER NOT NULL DEFAULT 0,
       photo_min_count  INTEGER NOT NULL DEFAULT 0,  -- R110: how many, not just whether
       added_in_field   INTEGER NOT NULL DEFAULT 0,
       reason           TEXT,
       state            TEXT,
       detail           TEXT,                       -- JSON: what only this kind carries
       updated_at       TEXT NOT NULL,
       PRIMARY KEY (technician_id, id)
     )`,
    `CREATE INDEX ix_wo_item_order ON wo_item (technician_id, work_order_id, kind, position)`,

    // Deliberately not folded into wo_item (R130): tolerance compares min and
    // max as columns. Figures are TEXT decimals; the unit is never absent.
    `CREATE TABLE wo_reading (
       technician_id  TEXT NOT NULL,
       id             TEXT NOT NULL,
       work_order_id  TEXT NOT NULL,
       position       INTEGER NOT NULL,
       prompt         TEXT NOT NULL,
       unit           TEXT NOT NULL,
       min_value      TEXT,
       max_value      TEXT,
       previous_value TEXT,
       photo_required INTEGER NOT NULL DEFAULT 0,
       value          TEXT,
       flagged        INTEGER NOT NULL DEFAULT 0,
       unable_to_read INTEGER NOT NULL DEFAULT 0,
       captured_at    TEXT,
       updated_at     TEXT NOT NULL,
       PRIMARY KEY (technician_id, id)
     )`,
    `CREATE INDEX ix_wo_reading_order ON wo_reading (technician_id, work_order_id, position)`,

    // ── Capture: local-only ─────────────────────────────────────────────────
    // Every act, exactly once. `id` IS the idempotency key, minted AT CAPTURE.
    `CREATE TABLE outbox (
       id            TEXT PRIMARY KEY,
       technician_id TEXT NOT NULL,         -- whose row it is
       work_order_id TEXT,
       route_id      TEXT,
       kind          TEXT NOT NULL,
       channel       TEXT NOT NULL CHECK (channel IN ('job','route','unrouted')),  -- which server door it goes through
       payload       TEXT NOT NULL,         -- JSON
       seq           INTEGER NOT NULL,      -- capture order within the order / route
       captured_by   TEXT NOT NULL,         -- who did it, from the capture credential
       captured_at   TEXT NOT NULL,         -- device clock (R92)
       lat REAL, lng REAL, accuracy_m REAL,
       fix_at        TEXT,
       state         TEXT NOT NULL DEFAULT 'pending' ${SEND_STATE},
       attempts      INTEGER NOT NULL DEFAULT 0,
       next_attempt_at TEXT,
       last_error    TEXT,
       refusal       TEXT,                  -- the server's reason, JSON, shown on FF-50
       answer        TEXT,                  -- the server's per-item detail, JSON
       settled_at    TEXT                   -- when the server answered; drives the purge
     )`,
    `CREATE INDEX ix_outbox_send ON outbox (state, work_order_id, seq)`,
    `CREATE INDEX ix_outbox_purge ON outbox (state, settled_at)`,
    `CREATE INDEX ix_outbox_tech ON outbox (technician_id, state)`,
    `CREATE INDEX ix_outbox_group ON outbox (state, technician_id, channel, work_order_id, route_id, seq)`,

    // The BYTES live on disk; the row lives here (R52).
    `CREATE TABLE photo (
       id            TEXT PRIMARY KEY,      -- the photo_id the server's link is keyed on
       technician_id TEXT NOT NULL,
       outbox_id     TEXT,                  -- the task, reading or remark it proves
       declare_id    TEXT,                  -- the outbox row that declares it (kind 'photo')
       work_order_id TEXT,
       route_id      TEXT,
       local_path    TEXT NOT NULL,
       sha256        TEXT NOT NULL,
       bytes         INTEGER NOT NULL,
       width INTEGER, height INTEGER,
       captured_by   TEXT NOT NULL,
       captured_at   TEXT NOT NULL,
       lat REAL, lng REAL, accuracy_m REAL,
       state         TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','uploading','uploaded','failed')),
       attempts      INTEGER NOT NULL DEFAULT 0,
       next_attempt_at TEXT,
       last_error    TEXT,
       upload_url    TEXT,
       file_deleted  INTEGER NOT NULL DEFAULT 0,
       remote_id     TEXT,
       uploaded_at   TEXT
     )`,
    `CREATE INDEX ix_photo_send ON photo (state, captured_at)`,
    `CREATE INDEX ix_photo_tech ON photo (technician_id, state)`,

    `CREATE TABLE activity (
       technician_id TEXT NOT NULL,
       id            TEXT PRIMARY KEY,
       work_order_id TEXT NOT NULL,
       kind          TEXT NOT NULL CHECK (kind IN ('status','remark')),
       status        TEXT,
       text          TEXT,
       author        TEXT,
       at            TEXT NOT NULL,
       outbox_id     TEXT
     )`,
    `CREATE INDEX ix_activity_order ON activity (technician_id, work_order_id, at)`,

    // Labour is per person, not per job (R8).
    `CREATE TABLE crew_time (
       technician_id TEXT NOT NULL,
       id            TEXT PRIMARY KEY,
       work_order_id TEXT,
       person_id     TEXT NOT NULL,
       kind          TEXT NOT NULL CHECK (kind IN ('travel','labour','admin')),
       started_at    TEXT NOT NULL,
       ended_at      TEXT,
       outbox_id     TEXT
     )`,
    `CREATE INDEX ix_crew_time_tech ON crew_time (technician_id, started_at)`,

    // ── Bookkeeping ─────────────────────────────────────────────────────────
    // The pair is the key (R134).
    `CREATE TABLE sync_state (
       technician_id  TEXT NOT NULL,
       table_name     TEXT NOT NULL,
       cursor         TEXT,
       last_pull_at   TEXT,
       last_push_at   TEXT,
       pending_count  INTEGER NOT NULL DEFAULT 0,
       PRIMARY KEY (technician_id, table_name)
     )`,

    // One free-text box, one index (Mobile data §3). Carries technician_id and
    // is built from scoped rows, so a search cannot surface another
    // technician's customers.
    `CREATE VIRTUAL TABLE search_index USING fts5(
       technician_id UNINDEXED,
       entity_kind   UNINDEXED,
       entity_id     UNINDEXED,
       number,
       customer_name,
       address,
       serial,
       badge,
       tokenize = 'unicode61',
       prefix = '2 3'
     )`,

    // Device-level; survives a reinstall; not a preference.
    `CREATE TABLE settings (
       key        TEXT PRIMARY KEY,
       value      TEXT NOT NULL,
       updated_at TEXT NOT NULL
     )`,

    // ── Route reading ───────────────────────────────────────────────────────
    // The assignment stays a row that could become many (R87): no uniqueness
    // on (route) alone, the technician is part of the key.
    `CREATE TABLE route (
       technician_id TEXT NOT NULL,
       id            TEXT NOT NULL,
       code          TEXT,
       service       TEXT,
       area          TEXT,
       read_type     TEXT,
       cycle         TEXT,
       window_start  TEXT,
       window_end    TEXT,
       notes         TEXT,
       assigned_to   TEXT,
       status        TEXT NOT NULL DEFAULT 'assigned' CHECK (status IN ('assigned','in_progress','turned_in')),
       turned_in_at  TEXT,
       extra         TEXT,
       updated_at    TEXT NOT NULL,
       PRIMARY KEY (technician_id, id)
     )`,

    // The stop is the address (R74).
    `CREATE TABLE route_stop (
       technician_id TEXT NOT NULL,
       id            TEXT NOT NULL,
       route_id      TEXT NOT NULL,
       premise_id    TEXT NOT NULL,
       walk_position INTEGER NOT NULL,
       lat REAL, lng REAL,                 -- downloaded with the route: nearest-first needs no signal (R76)
       access_notes  TEXT,
       hazard        TEXT,
       updated_at    TEXT NOT NULL,
       PRIMARY KEY (technician_id, id)
     )`,
    `CREATE INDEX ix_stop_route ON route_stop (technician_id, route_id, walk_position)`,

    // A reading is a RECORD (R88). One row per meter on the route, downloaded
    // as 'unread' with what the screen shows (previous, expected range), then
    // filled at capture; `capture_key` is the idempotency key minted then and
    // is the outbox row's id.
    `CREATE TABLE route_read (
       technician_id      TEXT NOT NULL,
       id                 TEXT NOT NULL,
       route_id           TEXT NOT NULL,
       stop_id            TEXT NOT NULL,
       asset_id           TEXT NOT NULL,
       parent_asset_id    TEXT,
       account_id         TEXT,              -- stamped at collection
       previous_value     TEXT,
       expected_min       TEXT,
       expected_max       TEXT,
       photo_required     INTEGER NOT NULL DEFAULT 0,
       value              TEXT,              -- TEXT decimal; null when it could not be read
       unit               TEXT NOT NULL,     -- always explicit, never assumed
       register           TEXT,
       reader_status      TEXT CHECK (reader_status IS NULL OR reader_status IN ('read','could_not_read','read_with_problem')),
       no_read_reason     TEXT,
       warned_accepted    INTEGER NOT NULL DEFAULT 0,
       lat REAL, lng REAL, accuracy_m REAL,
       fix_quality        TEXT CHECK (fix_quality IS NULL OR fix_quality IN ('good','poor','none')),
       metres_from_record REAL,
       captured_at        TEXT,
       captured_by        TEXT,
       identified_by      TEXT CHECK (identified_by IS NULL OR identified_by IN ('scan','listed','typed')),
       off_route          INTEGER NOT NULL DEFAULT 0,
       read_method        TEXT,
       remark             TEXT,
       remark_source      TEXT CHECK (remark_source IS NULL OR remark_source IN ('voice','typed')),
       capture_key        TEXT UNIQUE,
       state              TEXT NOT NULL DEFAULT 'unread'
                          CHECK (state IN ('unread','pending','sending','accepted','duplicate','refused','held_for_review')),
       updated_at         TEXT NOT NULL,
       PRIMARY KEY (technician_id, id)
     )`,
    `CREATE INDEX ix_read_send ON route_read (state, route_id, captured_at)`,
    `CREATE INDEX ix_read_stop ON route_read (technician_id, stop_id)`,

    // ── Downloaded catalogue ───────────────────────────────────────────────
    `CREATE TABLE work_order_templates (
       id            TEXT PRIMARY KEY,
       name          TEXT NOT NULL,
       version       TEXT NOT NULL,
       service       TEXT,
       published     INTEGER NOT NULL DEFAULT 1,
       step_count    INTEGER NOT NULL DEFAULT 0,
       safety_count  INTEGER NOT NULL DEFAULT 0,
       reading_count INTEGER NOT NULL DEFAULT 0,
       body          TEXT,                  -- JSON
       last_used_at  TEXT,
       updated_at    TEXT NOT NULL
     )`,
  ],
};
