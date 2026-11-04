/**
 * @jest-environment node
 *
 * DEF-FLD-10587 (beta MQ-030): a task's instruction, written in the work
 * template, reaches the handset with the job bundle and is KEPT — in the task
 * row's own `detail` (R130), with no schema change. A blank instruction stores
 * nothing, so the card cannot draw an empty line for it.
 *
 * Proved red (law 7): before the fix `applyBundle` copied title, flags, state
 * and minutes and dropped `instruction`, so test (a) read `undefined`.
 */
import * as woItemQ from '../../src/db/queries/woItem';
import { scoped } from '../../src/db/scoped';
import { applyChangesPage } from '../../src/sync/delta';
import { applyBundle } from '../../src/sync/extras';
import type { WireBundle } from '../../src/sync/fieldApi';
import type { JobCard } from '../../src/sync/transport';
import { FakeClock, openStore } from '../db/support/fixtures';

const LID = 'Compare the ID stamped on the lid with the work order. If it does not match, stop and call dispatch.';

const card: JobCard = {
  id: 'wo-29',
  order_no: 'WO-0029',
  type: 'Meter exchange',
  premise: { id: 'p-29', premise_no: 'PR-29', address: '12 Elm St' },
  window_start: '2026-10-24T15:30:00Z',
  window_end: null,
  due_at: null,
  est_minutes: 30,
  priority: { code: 'P2', rank: 2 },
  state: 'scheduled',
  dispatch_state: 'SCHEDULED',
  access_notes: '',
  hazards: '',
  gate_code: '',
};

const bundle: WireBundle = {
  order_id: 'wo-29',
  order_no: 'WO-0029',
  template_id: 'tpl-1',
  template_version: 2,
  safety: [],
  tasks: [
    { id: 't-1', seq: 1, title: 'Check the meter ID', instruction: LID, is_mandatory: true },
    { id: 't-2', seq: 2, title: 'Fit new meter', instruction: '   ' },
    { id: 't-3', seq: 3, title: 'Record opening read', instruction: null },
  ],
  readings: [],
  materials: [],
} as unknown as WireBundle;

function detailOf(db: ReturnType<typeof openStore>, id: string): Record<string, unknown> {
  const row = woItemQ.listForOrder(scoped(db, 'dana'), 'wo-29', 'task').find((t) => t.id === id);
  return JSON.parse(row?.detail ?? '{}');
}

test('(a) a bundle task with an instruction stores it verbatim; a blank or null one stores nothing', () => {
  const clock = new FakeClock();
  const db = openStore('north', undefined, clock);
  applyChangesPage(db, 'dana', { changes: [{ change: 'upsert', order_id: 'wo-29', at: 't', job: card }], count: 1, next_cursor: 'c0', has_more: false }, clock.now());
  applyBundle(db, 'dana', bundle, clock.now());

  expect(detailOf(db, 't-1').instruction).toBe(LID);
  expect(detailOf(db, 't-2')).not.toHaveProperty('instruction');
  expect(detailOf(db, 't-3')).not.toHaveProperty('instruction');
});
