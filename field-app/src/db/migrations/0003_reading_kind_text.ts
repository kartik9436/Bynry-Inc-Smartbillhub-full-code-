/**
 * 0003 — a reading may be WORDS (DEF-FLD-10585, beta MQ-022).
 *
 * The server's template readings carry `kind` (`number` | `text`,
 * `apps/work/models.py`) and store a text reading in `value_text` — a serial,
 * a seal number — with no unit, no range, and never posted as a meter read
 * (`apps/work/evidence.py` `_set_text_reading`). 0001 had only the numeric
 * `value`, so the handset dropped `kind` and parsed every reading as a decimal.
 *
 * ⚠ **A TEXT READING NEVER GOES INTO `value`.** `value` stays a TEXT decimal
 * with its unit (hard rules 2, 3); words go into `value_text`. A text reading's
 * `unit` is the empty string the server sends — the column stays NOT NULL, and
 * `woReading.ts` still refuses an empty unit on a NUMBER reading.
 *
 * Forward only, appended after 0002 (`document_help`, DEF-FLD-10581) — shipped
 * migrations are never edited (Mobile data §9).
 */
import type { Migration } from './types';

export const m0003: Migration = {
  id: 3,
  name: 'reading_kind_text',
  statements: [
    `ALTER TABLE wo_reading ADD COLUMN kind TEXT NOT NULL DEFAULT 'number' CHECK (kind IN ('number','text'))`,
    `ALTER TABLE wo_reading ADD COLUMN value_text TEXT`,
  ],
};
