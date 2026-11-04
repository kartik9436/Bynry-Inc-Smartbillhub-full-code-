/**
 * @jest-environment node
 *
 * T-10 delta / T-47: a watermark per technician per table (R134), and
 * tombstones that REMOVE (R57) — the job taken away leaves the handset, the
 * work captured against it does not.
 */
import * as activityQ from '../../src/db/queries/activity';
import * as dayQ from '../../src/db/queries/day';
import * as outboxQ from '../../src/db/queries/outbox';
import * as photoQ from '../../src/db/queries/photo';
import * as premiseQ from '../../src/db/queries/premise';
import * as searchQ from '../../src/db/queries/searchIndex';
import * as syncStateQ from '../../src/db/queries/syncState';
import * as workOrderQ from '../../src/db/queries/workOrder';
import * as woItemQ from '../../src/db/queries/woItem';
import { scoped } from '../../src/db/scoped';
import { applyChangesPage, pullChanges, UnknownSchemaVersionError } from '../../src/sync/delta';
import { capture } from '../../src/sync/outbox';
import type { ChangesPage, JobCard } from '../../src/sync/transport';
import { FakeClock, idSource, openStore } from '../db/support/fixtures';
import { FakeServer } from './support/fakeServer';

const card = (id: string, over: Partial<JobCard> = {}): JobCard => ({
  id,
  order_no: `WO-${id}`,
  type: 'Meter exchange',
  premise: { id: `p-${id}`, premise_no: 'PR-1', address: '221 Oak Ave' },
  window_start: '2026-10-21T15:30:00Z',
  window_end: null,
  due_at: null,
  est_minutes: 45,
  priority: { code: 'P1', rank: 1 },
  state: 'scheduled',
  dispatch_state: 'SCHEDULED',
  access_notes: 'dog in rear yard',
  hazards: '',
  gate_code: '4417',
  ...over,
});

function setup() {
  const clock = new FakeClock();
  const db = openStore('north', undefined, clock);
  return { clock, db, server: new FakeServer(), deps: { newId: idSource('k'), clock } };
}

describe('the delta', () => {
  test('pages until done, storing the cards, the premise and the search entry', async () => {
    const { db, server, clock } = setup();
    server.pages = [
      { changes: [{ change: 'upsert', order_id: '1', at: 't1', job: card('1') }], count: 1, next_cursor: 'c1', has_more: true },
      { changes: [{ change: 'upsert', order_id: '2', at: 't2', job: card('2', { surprise: 'kept' }) }], count: 1, next_cursor: 'c2', has_more: false },
    ];
    const r = await pullChanges(db, server, 'dana', { clock });
    expect(r).toEqual({ pages: 2, upserts: 2, removals: 0 });
    expect(server.cursorsSeen).toEqual([null, 'c1']);
    const s = scoped(db, 'dana');
    expect(workOrderQ.getMine(s, '1')).toMatchObject({ number: 'WO-1', gate_code: '4417', priority_code: 'P1', premise_id: 'p-1', needs_bundle: 1 });
    expect(JSON.parse(workOrderQ.getMine(s, '2')!.extra!)).toEqual({ surprise: 'kept' }); // unknown field kept
    expect(premiseQ.get(db, 'p-1')?.address_line).toBe('221 Oak Ave');
    expect(searchQ.search(s, 'oak', { limit: 10 }).map((h) => h.entity_id).sort()).toEqual(['1', '2']);
    expect(syncStateQ.get(s, 'work_order')?.cursor).toBe('c2');
  });

  test('a tombstone removes the job from the handset — and leaves the work captured on it', async () => {
    const { db, server, clock, deps } = setup();
    const s = scoped(db, 'dana');
    applyChangesPage(db, 'dana', { changes: [{ change: 'upsert', order_id: '7', at: 't', job: card('7') }], count: 1, next_cursor: 'c0', has_more: false }, clock.now());
    woItemQ.upsert(s, { id: 'i1', workOrderId: '7', kind: 'task', position: 1, label: 'x' }, clock.iso());
    const captured = capture(
      db,
      { technicianId: 'dana', capturedBy: 'dana' },
      {
        kind: 'task_tick',
        workOrderId: '7',
        payload: {},
        photos: [{ localPath: '/p.jpg', sha256: 'b'.repeat(64), bytes: 1, target: { task_id: 'i1' } }],
        apply: (sc, key) => activityQ.insert(sc, { id: 'act-1', workOrderId: '7', kind: 'status', status: 'started', at: clock.iso(), outboxId: key }),
      },
      deps,
    );

    // the stored cursor is c0, so the fake serves its page 0 next
    server.pages = [{ changes: [{ change: 'removed', order_id: '7', at: 't9' }], count: 1, next_cursor: 'c1', has_more: false }];
    await pullChanges(db, server, 'dana', { clock });

    expect(workOrderQ.getMine(s, '7')).toBeUndefined();
    expect(woItemQ.listForOrder(s, '7')).toEqual([]);
    expect(searchQ.search(s, 'oak', { limit: 10 })).toEqual([]);
    expect(workOrderQ.listDay(s, { before: '2099-01-01', limit: 10 })).toEqual([]); // what the screen then shows
    // captured work still has to reach the server
    expect(outboxQ.getMine(s, captured.key)?.state).toBe('pending');
    expect(photoQ.getMine(s, captured.photoIds[0]!)?.state).toBe('pending');
    expect(activityQ.listForOrder(s, '7')).toHaveLength(1);
  });

  test('FB-029: a job assigned 10 days out lands in Later and All, and leaves both when reassigned away (DEF-FLD-10804)', async () => {
    const { db, server, clock } = setup();
    const s = scoped(db, 'dana');
    const now = clock.now();
    const tenDays = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 10, 9, 0).toISOString();
    server.pages = [
      { changes: [{ change: 'upsert', order_id: '10', at: 't1', job: card('10', { window_start: tenDays }) }], count: 1, next_cursor: 'c1', has_more: false },
    ];
    await pullChanges(db, server, 'dana', { clock });
    const later = () => dayQ.listLater(s, { from: dayQ.dayBounds(now, 3).from }).map((j) => j.id);
    const all = () => dayQ.listAll(s, {}).map((j) => j.id);
    expect(later()).toEqual(['10']);
    expect(all()).toEqual(['10']);
    // Not on any of the three day tabs — that was the defect.
    for (const offset of [0, 1, 2]) {
      expect(dayQ.listDay(s, { ...dayQ.dayBounds(now, offset), today: offset === 0 })).toEqual([]);
    }

    // The dispatcher gives it to Marco: the feed sends a removal.
    server.pages = [
      { changes: [{ change: 'upsert', order_id: '10', at: 't1', job: card('10', { window_start: tenDays }) }], count: 1, next_cursor: 'c1', has_more: false },
      { changes: [{ change: 'removed', order_id: '10', at: 't2' }], count: 1, next_cursor: 'c2', has_more: false },
    ];
    await pullChanges(db, server, 'dana', { clock });
    expect(later()).toEqual([]);
    expect(all()).toEqual([]);
    expect(dayQ.allCounts(s).left).toBe(0);
  });

  test("the cursor is per technician: Marco's pull never advances Dana's (R134)", async () => {
    const { db, server, clock } = setup();
    server.pages = [{ changes: [], count: 0, next_cursor: 'c5', has_more: false }];
    await pullChanges(db, server, 'marco', { clock });
    expect(syncStateQ.get(scoped(db, 'marco'), 'work_order')?.cursor).toBe('c5');
    expect(syncStateQ.get(scoped(db, 'dana'), 'work_order')).toBeUndefined();
  });

  test('the server wins on what it sends; a job reassigned to Marco is his row, not a steal of Dana’s', () => {
    const { db, clock } = setup();
    const page = (job: JobCard): ChangesPage => ({ changes: [{ change: 'upsert', order_id: job.id, at: 't', job }], count: 1, next_cursor: 'c', has_more: false });
    applyChangesPage(db, 'dana', page(card('8')), clock.now());
    applyChangesPage(db, 'dana', page(card('8', { gate_code: '9999' })), clock.now());
    applyChangesPage(db, 'marco', page(card('8')), clock.now());
    expect(workOrderQ.getMine(scoped(db, 'dana'), '8')?.gate_code).toBe('9999');
    expect(workOrderQ.getMine(scoped(db, 'marco'), '8')?.gate_code).toBe('4417');
  });

  test('a page in a wire version this build does not know is refused, and nothing is stored', () => {
    const { db, clock } = setup();
    expect(() =>
      applyChangesPage(db, 'dana', { schema_version: 2, changes: [{ change: 'upsert', order_id: '1', at: 't', job: card('1') }], count: 1, next_cursor: 'c1', has_more: false }, clock.now()),
    ).toThrow(UnknownSchemaVersionError);
    expect(workOrderQ.getMine(scoped(db, 'dana'), '1')).toBeUndefined();
    expect(syncStateQ.get(scoped(db, 'dana'), 'work_order')).toBeUndefined();
  });

  test('a feed that says "more" without moving its cursor is stopped, not looped on', async () => {
    const { db, server, clock } = setup();
    server.pages = [{ changes: [], count: 0, next_cursor: null, has_more: true }];
    await expect(pullChanges(db, server, 'dana', { clock })).rejects.toThrow(/without advancing/);
  });
});
