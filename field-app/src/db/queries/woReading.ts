/**
 * `wo_reading` — the readings a job asks for (R130's one exception to wo_item).
 * Figures are TEXT decimals and the unit is never absent (hard rules 2, 3). Scoped.
 *
 * A reading is a NUMBER (`value`, with its unit) or TEXT (`value_text`, a
 * serial or a seal number, with no unit and no range) — `kind`, from the
 * server's template (migration 0003, DEF-FLD-10585). Words never go into
 * `value`, and a number reading is still refused without its unit.
 */
import { optionalDecimal } from '../decimal';
import type { ScopedRunner } from '../scoped';

export interface WoReadingRow {
  technician_id: string;
  id: string;
  work_order_id: string;
  position: number;
  prompt: string;
  unit: string;
  min_value: string | null;
  max_value: string | null;
  previous_value: string | null;
  photo_required: number;
  kind: ReadingKind;
  value: string | null;
  value_text: string | null;
  flagged: number;
  unable_to_read: number;
  captured_at: string | null;
  updated_at: string;
}

export type ReadingKind = 'number' | 'text';

export interface WoReadingInput {
  id: string;
  workOrderId: string;
  position: number;
  prompt: string;
  unit: string;
  minValue?: string | null;
  maxValue?: string | null;
  previousValue?: string | null;
  photoRequired?: boolean;
  /** `number` unless the server says `text`. */
  kind?: ReadingKind;
}

function requireUnit(unit: string): string {
  if (!unit || !unit.trim()) throw new Error('a reading never exists without its unit (hard rule 3)');
  return unit;
}

export function upsert(s: ScopedRunner, r: WoReadingInput, now: string): void {
  const text = r.kind === 'text';
  s.run(
    `INSERT INTO wo_reading (technician_id, id, work_order_id, position, prompt, unit, min_value, max_value,
                             previous_value, photo_required, kind, updated_at)
     VALUES (:technician_id, :id, :work_order_id, :position, :prompt, :unit, :min_value, :max_value,
             :previous_value, :photo_required, :kind, :now)
     ON CONFLICT (technician_id, id) DO UPDATE SET
       position = excluded.position, prompt = excluded.prompt, unit = excluded.unit,
       min_value = excluded.min_value, max_value = excluded.max_value,
       previous_value = excluded.previous_value, photo_required = excluded.photo_required,
       kind = excluded.kind, updated_at = excluded.updated_at`,
    {
      id: r.id,
      work_order_id: r.workOrderId,
      position: r.position,
      prompt: r.prompt,
      // A text reading has no unit and no range; a number reading never lacks its unit.
      unit: text ? (r.unit ?? '').trim() : requireUnit(r.unit),
      min_value: text ? null : optionalDecimal(r.minValue, 'min_value'),
      max_value: text ? null : optionalDecimal(r.maxValue, 'max_value'),
      previous_value: text ? null : optionalDecimal(r.previousValue, 'previous_value'),
      photo_required: r.photoRequired ?? false,
      kind: text ? 'text' : 'number',
      now,
    },
  );
}

/**
 * The figure the technician typed, with its unit — refused without one. With
 * no figure (*Unable to read*, R13) there is no consumption to carry a unit, so
 * a TEXT reading, whose unit is empty, can be marked unable too; the row's unit
 * must still match what was sent.
 */
export function recordValue(
  s: ScopedRunner,
  id: string,
  v: { value: string | null; unit: string; flagged: boolean; unableToRead: boolean; capturedAt: string },
): number {
  return s.run(
    `UPDATE wo_reading SET value = :value, value_text = NULL, flagged = :flagged, unable_to_read = :unable, captured_at = :at
      WHERE technician_id = :technician_id AND id = :id AND unit = :unit`,
    {
      id,
      value: optionalDecimal(v.value, 'value'),
      unit: v.value === null && v.unableToRead ? v.unit : requireUnit(v.unit),
      flagged: v.flagged,
      unable: v.unableToRead,
      at: v.capturedAt,
    },
  ).changes;
}

/**
 * The words the technician typed on a TEXT reading, exactly as typed (trimmed
 * only) — never into `value`. Refused on a number reading (0 rows changed).
 */
export function recordText(s: ScopedRunner, id: string, v: { valueText: string; capturedAt: string }): number {
  const text = v.valueText.trim();
  if (!text) throw new Error('a text reading is saved with words in it');
  return s.run(
    `UPDATE wo_reading SET value_text = :text, value = NULL, flagged = 0, unable_to_read = 0, captured_at = :at
      WHERE technician_id = :technician_id AND id = :id AND kind = 'text'`,
    { id, text, at: v.capturedAt },
  ).changes;
}

/**
 * FB-030 — a CLOSED job refilled onto a new phone: the server's captured
 * value, written ONLY where the handset holds none (its own capture wins).
 * A number still never lands without the row's own unit (hard rule 3).
 */
export function fillValueIfEmpty(
  s: ScopedRunner,
  id: string,
  v: { value: string | null; valueText: string | null; unableToRead: boolean; capturedAt: string | null },
): number {
  return s.run(
    `UPDATE wo_reading SET value = :value, value_text = :text, unable_to_read = :unable, captured_at = :at
      WHERE technician_id = :technician_id AND id = :id
        AND value IS NULL AND value_text IS NULL AND unable_to_read = 0 AND captured_at IS NULL
        AND (:value IS NULL OR unit != '')`,
    {
      id,
      value: optionalDecimal(v.value, 'value'),
      text: v.valueText && v.valueText.trim() ? v.valueText.trim() : null,
      unable: v.unableToRead,
      at: v.capturedAt,
    },
  ).changes;
}

export function listForOrder(s: ScopedRunner, workOrderId: string): WoReadingRow[] {
  return s.all<WoReadingRow>(
    `SELECT * FROM wo_reading WHERE technician_id = :technician_id AND work_order_id = :work_order_id
      ORDER BY position`,
    { work_order_id: workOrderId },
  );
}

export function deleteForOrder(s: ScopedRunner, workOrderId: string): number {
  return s.run('DELETE FROM wo_reading WHERE technician_id = :technician_id AND work_order_id = :work_order_id', {
    work_order_id: workOrderId,
  }).changes;
}
