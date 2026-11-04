/**
 * 0005 — the job's NUMBER on every outbox row, written at capture
 * (DEF-FLD-10623, PO retest item 7).
 *
 * FF-50 named a refused item's job by reading the job mirror
 * (`work_order.number`). When the office reassigns a job, the change feed
 * answers `removed` and the mirror is deleted (`sync/delta.ts`
 * `removeJobMirror`) — so the one row that most needs the number
 * (*"This job was reassigned."*) had none, and read *"4 items · This job was
 * reassigned."* with nothing to quote to the office.
 *
 *   outbox.work_order_number — the number the job carried when the act was
 *        captured (`sync/outbox.ts` `capture`). NULL for an act with no job,
 *        or a job the phone did not hold. Never rewritten afterwards: it is
 *        what the technician saw when they did the work.
 *
 * Rows captured before this build are filled from the mirror where the job is
 * still on the phone; a job already removed stays NULL (nothing to read it
 * from), and FF-50 then falls back to the mirror as before.
 *
 * Forward only, appended after 0004 — shipped migrations are never edited
 * (Mobile data §9).
 */
import type { Migration } from './types';

export const m0005: Migration = {
  id: 5,
  name: 'outbox_work_order_number',
  statements: [
    'ALTER TABLE outbox ADD COLUMN work_order_number TEXT',
    `UPDATE outbox
        SET work_order_number = (
          SELECT w.number FROM work_order w
           WHERE w.technician_id = outbox.technician_id AND w.id = outbox.work_order_id)
      WHERE work_order_id IS NOT NULL`,
  ],
};
