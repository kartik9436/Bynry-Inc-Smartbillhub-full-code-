/**
 * 0004 — a utility's own READ FORMATS on the handset (MQ-033, `CR-192-BRC10`
 * task 12; decision log 2026-10-24, the four rows headed *"MQ-033"*).
 *
 * The route download now names, per service the route reads, the format
 * version resolved route → cycle → service (`route.read_formats[]`), and the
 * route page carries each version with its questions
 * (`read_format_versions[]`, also `GET work/mobile/read-formats/versions/{id}`).
 * A reading's answers then travel inside its own item, stamped with the
 * version (`field_reads.sync_reads`).
 *
 *   read_format_version — one PUBLISHED version, kept by its id. A published
 *        version never changes on the server (BR-MET-1213), so a version the
 *        phone already holds is never fetched again, and the walk works with no
 *        signal. Shared by every reader on the handset, like the template
 *        catalogue: it holds the utility's questions, nobody's work.
 *   route.read_formats — the route's resolved version per service, as served
 *        (`[{service, source, version_id}]`, JSON). Empty or NULL is a route
 *        with no format, which reads exactly as before.
 *   route_read.read_format_version_id, route_read.answers — the version a
 *        reading was TAKEN under and the answers given, written in the same
 *        transaction as the figure (`acts.saveReading`). A reading already
 *        taken keeps its version when tomorrow's download names a newer one
 *        (BR-WRK-008's reason: a re-worded form never re-words an answer).
 *
 * Forward only, appended after 0003 — shipped migrations are never edited
 * (Mobile data §9).
 */
import type { Migration } from './types';

export const m0004: Migration = {
  id: 4,
  name: 'read_formats',
  statements: [
    `CREATE TABLE read_format_version (
       id             TEXT PRIMARY KEY,
       read_format_id TEXT NOT NULL,
       name           TEXT,
       service        TEXT,
       version_no     INTEGER,
       questions      TEXT NOT NULL,          -- JSON: the server's questions, in order
       updated_at     TEXT NOT NULL
     )`,
    'ALTER TABLE route ADD COLUMN read_formats TEXT',
    'ALTER TABLE route_read ADD COLUMN read_format_version_id TEXT',
    'ALTER TABLE route_read ADD COLUMN answers TEXT',
  ],
};
