/**
 * 0006 — every photograph names the READING it proves (DEF-FLD-10631, FB-003).
 *
 * RW-13 counted a reading's photos by joining `route_read.capture_key` to
 * `photo.outbox_id`. That join holds for a photo saved WITH the reading and
 * for nothing else:
 *   - a photo added on RW-13 AFTER saving is its own `photo` act (R123), so its
 *     `outbox_id` is that act's key — the reading said *"0 photos"*;
 *   - a reading changed and saved again gets a NEW capture key, so every photo
 *     it already had dropped out of the count.
 *
 *   photo.route_read_id — the reading the photograph is declared against,
 *        written at capture from the declaration's own target
 *        (`sync/outbox.ts` `capture`). NULL for a job's photograph.
 *
 * Older rows are filled two ways, in order: by the reading whose capture key
 * the photo was saved under, then by the `route_read_id` its declaration
 * (`declare_id`, kind `photo`) names. A declaration already purged after the
 * server answered leaves only the first way; a photo neither way names stays
 * NULL — nothing is guessed.
 *
 * Forward only, appended after 0005 — shipped migrations are never edited
 * (Mobile data §9).
 */
import type { Migration } from './types';

export const m0006: Migration = {
  id: 6,
  name: 'photo_route_read',
  statements: [
    'ALTER TABLE photo ADD COLUMN route_read_id TEXT',
    `UPDATE photo
        SET route_read_id = (
          SELECT rr.id FROM route_read rr
           WHERE rr.technician_id = photo.technician_id AND rr.capture_key = photo.outbox_id)
      WHERE route_read_id IS NULL`,
    `UPDATE photo
        SET route_read_id = (
          SELECT json_extract(o.payload, '$.route_read_id') FROM outbox o
           WHERE o.technician_id = photo.technician_id AND o.id = photo.declare_id)
      WHERE route_read_id IS NULL`,
    'CREATE INDEX ix_photo_route_read ON photo (technician_id, route_read_id)',
  ],
};
