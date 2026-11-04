/**
 * @jest-environment node
 *
 * DEF-MET-10609 (decision log 2026-10-26, PO *"yes do it"*): ONE can't-read
 * list for route AND job readings. A job's bundle now carries the utility's
 * switched-on reasons (`mobile.bundle` → `cant_read_reasons`), and the phone
 * keeps them where RW-17 already reads its list (`CANT_READ_KEY`), so a
 * technician with no route still picks a reason offline.
 *
 * Proved red (law 7): before the fix `applyBundle` ignored the key and (a)
 * read `null`.
 */
import * as settingsQ from '../../src/db/queries/settings';
import { applyChangesPage } from '../../src/sync/delta';
import { applyBundle } from '../../src/sync/extras';
import type { WireBundle } from '../../src/sync/fieldApi';
import { CANT_READ_KEY } from '../../src/sync/routes';
import type { JobCard } from '../../src/sync/transport';
import { cantReadReasons } from '../../src/screens/reads/CantReadReasonPicker';
import { FakeClock, openStore } from '../db/support/fixtures';

const card: JobCard = {
  id: 'wo-30',
  order_no: 'WO-0030',
  type: 'Meter exchange',
  premise: { id: 'p-30', premise_no: 'PR-30', address: '14 Elm St' },
  window_start: '2026-10-26T15:30:00Z',
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

function bundle(extra: Record<string, unknown>): WireBundle {
  return {
    order_id: 'wo-30',
    order_no: 'WO-0030',
    template_id: 'tpl-1',
    template_version: 1,
    safety: [],
    tasks: [],
    readings: [],
    materials: [],
    ...extra,
  } as unknown as WireBundle;
}

function store() {
  const clock = new FakeClock();
  const db = openStore('north', undefined, clock);
  applyChangesPage(db, 'dana', { changes: [{ change: 'upsert', order_id: 'wo-30', at: 't', job: card }], count: 1, next_cursor: 'c0', has_more: false }, clock.now());
  return { db, clock };
}

test('(a) the bundle list is kept where the RW-17 picker reads it, in its order', () => {
  const { db, clock } = store();
  applyBundle(db, 'dana', bundle({ cant_read_reasons: [{ code: 'dog', name: 'Dog' }, { code: 'flooded', name: 'Flooded pit' }] }), clock.now());
  expect(cantReadReasons(db)).toEqual([
    { code: 'dog', label: 'Dog' },
    { code: 'flooded', label: 'Flooded pit' },
  ]);
});

test('(b) a bundle with no list leaves the phone its own', () => {
  const { db, clock } = store();
  settingsQ.set(db, CANT_READ_KEY, [{ code: 'locked', label: 'Locked' }], clock.now().toISOString());
  applyBundle(db, 'dana', bundle({}), clock.now());
  expect(cantReadReasons(db)).toEqual([{ code: 'locked', label: 'Locked' }]);
});
