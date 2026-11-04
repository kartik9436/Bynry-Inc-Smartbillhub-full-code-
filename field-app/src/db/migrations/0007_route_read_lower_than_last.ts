/**
 * 0007 — a reading refilled from the server says whether it was LOWER THAN
 * THE LAST (FB-030, PO 2026-10-31; the flag is FB-022's).
 *
 *   route_read.lower_than_last — 1 when the server posted this reading with
 *        FB-022's flag (`negative_usage`: below the meter's last reading, not
 *        billed until a clerk corrects it); 0 when it said not; NULL when the
 *        server never said (every reading this phone captured itself, whose
 *        flag RW-28 derives from its own previous value, `figures.verdict`).
 *
 * A reading a new phone, a reinstall or a remote sign-out refills from
 * `GET work/mobile/reads/history` has no previous value on the handset, so
 * the server's word is the only way RW-28's drill can say *Lower than last*.
 *
 * Forward only, appended after 0006 — shipped migrations are never edited
 * (Mobile data §9). No back-fill: NULL is exactly right for every existing row.
 */
import type { Migration } from './types';

export const m0007: Migration = {
  id: 7,
  name: 'route_read_lower_than_last',
  statements: ['ALTER TABLE route_read ADD COLUMN lower_than_last INTEGER'],
};
