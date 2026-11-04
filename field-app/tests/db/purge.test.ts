/**
 * @jest-environment node
 *
 * T-11 / T-49 — the retention purge.
 *
 * ⚠ THE GUARD (R60, requirement 48): nothing unsent is ever deleted — at any
 * age, under any sign-in, including another technician's work on a shared
 * handset. The first test below is that guard; it was proved RED by breaking
 * the purge before it was trusted green (see the lane report).
 */
import { readdirSync, readFileSync } from 'fs';
import { join } from 'path';

import type { TenantDb } from '../../src/db/database';
import * as activityQ from '../../src/db/queries/activity';
import * as documentQ from '../../src/db/queries/document';
import * as outboxQ from '../../src/db/queries/outbox';
import * as photoQ from '../../src/db/queries/photo';
import * as routeQ from '../../src/db/queries/route';
import * as routeReadQ from '../../src/db/queries/routeRead';
import * as workOrderQ from '../../src/db/queries/workOrder';
import * as woItemQ from '../../src/db/queries/woItem';
import { purgeOnAppStart, RETENTION } from '../../src/db/purge';
import { deviceWide, scoped } from '../../src/db/scoped';
import { capture } from '../../src/sync/outbox';
import { FakeClock, idSource, MemoryFiles, openStore } from './support/fixtures';

const dana = { technicianId: 'dana', capturedBy: 'dana' };
const marco = { technicianId: 'marco', capturedBy: 'marco' };

function setup() {
  const clock = new FakeClock(Date.parse('2026-07-01T08:00:00.000Z'));
  const db = openStore('north', undefined, clock);
  return { clock, db, deps: { newId: idSource('k'), clock }, files: new MemoryFiles() };
}

function settleAt(db: TenantDb, key: string, at: Date): void {
  outboxQ.settle(deviceWide(db, 'receipt'), key, 'accepted', at.toISOString(), null);
}

function rows(db: TenantDb, table: string): number {
  return deviceWide(db, 'count').get<{ n: number }>(`SELECT COUNT(*) AS n FROM ${table}`)?.n ?? 0;
}

const wo = (id: string): workOrderQ.WorkOrderFromServer => ({
  id, number: id, type: null, state: null, dispatchState: null, priorityCode: null, priorityRank: null, premiseId: null,
  windowStart: null, windowEnd: null, dueAt: null, estMinutes: null, accessNotes: null, hazards: null, gateCode: null,
  extra: null, serverUpdatedAt: null,
});

describe('the purge', () => {
  test('NEVER deletes unsent work — at ninety days, refused or pending, mine or another technician’s (R60)', async () => {
    const { clock, db, deps, files } = setup();
    // Dana's day, ninety days ago, never sent.
    files.add('/p/dana.jpg');
    const pending = capture(db, dana, {
      kind: 'reading', workOrderId: 'wo-d', payload: {},
      photos: [{ localPath: '/p/dana.jpg', sha256: 'a'.repeat(64), bytes: 1, target: { reading_id: 'r' } }],
    }, deps);
    const refused = capture(db, dana, { kind: 'close', workOrderId: 'wo-d', payload: {} }, deps);
    outboxQ.refuse(deviceWide(db, 'receipt'), refused.key, { message_key: 'work.safety.locked' });
    // Marco's, on the same handset, never sent, his photo failing.
    files.add('/p/marco.jpg');
    const his = capture(db, marco, {
      kind: 'task_tick', workOrderId: 'wo-m', payload: {},
      photos: [{ localPath: '/p/marco.jpg', sha256: 'c'.repeat(64), bytes: 1, target: { task_id: 't' } }],
    }, deps);
    photoQ.markFailed(deviceWide(db, 'receipt'), his.photoIds[0]!, null, 'dropped');
    // Their jobs closed long ago — still nothing may go.
    workOrderQ.upsertFromServer(scoped(db, 'dana'), wo('wo-d'), clock.iso());
    workOrderQ.markClosed(scoped(db, 'dana'), 'wo-d', clock.iso());
    workOrderQ.upsertFromServer(scoped(db, 'marco'), wo('wo-m'), clock.iso());
    workOrderQ.markClosed(scoped(db, 'marco'), 'wo-m', clock.iso());

    clock.advanceDays(90);
    const report = await purgeOnAppStart(db, { now: clock.now(), files });

    expect(outboxQ.getMine(scoped(db, 'dana'), pending.key)?.state).toBe('pending');
    expect(outboxQ.getMine(scoped(db, 'dana'), pending.declarationKeys[0]!)?.state).toBe('pending');
    expect(outboxQ.getMine(scoped(db, 'dana'), refused.key)?.state).toBe('refused');
    expect(outboxQ.getMine(scoped(db, 'marco'), his.key)?.state).toBe('pending');
    expect(photoQ.getMine(scoped(db, 'dana'), pending.photoIds[0]!)?.state).toBe('pending');
    expect(photoQ.getMine(scoped(db, 'marco'), his.photoIds[0]!)?.state).toBe('failed');
    expect([...files.paths].sort()).toEqual(['/p/dana.jpg', '/p/marco.jpg']);
    expect(files.deleted).toEqual([]);
    expect(workOrderQ.getMine(scoped(db, 'dana'), 'wo-d')).toBeDefined();
    expect(workOrderQ.getMine(scoped(db, 'marco'), 'wo-m')).toBeDefined();
    expect(report).toMatchObject({ outboxRows: 0, photoRows: 0, closedJobs: 0, closedJobsKeptForUnsentWork: 2 });
  });

  test('sent work goes after 7 days and not before', async () => {
    const { clock, db, deps, files } = setup();
    const old = capture(db, dana, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, deps);
    const recent = capture(db, dana, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, deps);
    settleAt(db, old.key, clock.now());
    clock.advanceDays(2);
    settleAt(db, recent.key, clock.now());
    clock.advanceDays(RETENTION.sentDays - 1); // old: 8 days; recent: 6 days
    clock.advance(1);
    const report = await purgeOnAppStart(db, { now: clock.now(), files });
    expect(report.outboxRows).toBe(1);
    expect(outboxQ.getMine(scoped(db, 'dana'), old.key)).toBeUndefined();
    expect(outboxQ.getMine(scoped(db, 'dana'), recent.key)?.state).toBe('accepted');
  });

  test("a declaration is kept while its photograph's bytes are still on the handset", async () => {
    const { clock, db, deps, files } = setup();
    files.add('/p/1.jpg');
    const out = capture(db, dana, {
      kind: 'reading', workOrderId: 'wo-1', payload: {},
      photos: [{ localPath: '/p/1.jpg', sha256: 'a'.repeat(64), bytes: 1, target: { reading_id: 'r' } }],
    }, deps);
    settleAt(db, out.key, clock.now());
    settleAt(db, out.declarationKeys[0]!, clock.now());
    clock.advanceDays(30); // on mobile data for a month, waiting for wi-fi
    await purgeOnAppStart(db, { now: clock.now(), files });
    expect(outboxQ.getMine(scoped(db, 'dana'), out.key)).toBeUndefined();
    expect(outboxQ.getMine(scoped(db, 'dana'), out.declarationKeys[0]!)?.state).toBe('accepted');
    expect(files.paths.has('/p/1.jpg')).toBe(true);
  });

  test('a photo whose job is not on the handset: its file and row go 7 days after confirmed upload (FB-030)', async () => {
    const { clock, db, deps, files } = setup();
    files.add('/p/1.jpg');
    const out = capture(db, dana, {
      kind: 'reading', workOrderId: 'wo-1', payload: {},
      photos: [{ localPath: '/p/1.jpg', sha256: 'a'.repeat(64), bytes: 1, target: { reading_id: 'r' } }],
    }, deps);
    photoQ.markUploaded(deviceWide(db, 'receipt'), out.photoIds[0]!, 'att-1', clock.iso());
    clock.advanceDays(6);
    await purgeOnAppStart(db, { now: clock.now(), files });
    expect(photoQ.getMine(scoped(db, 'dana'), out.photoIds[0]!)?.remote_id).toBe('att-1');
    expect(files.deleted).toEqual([]);
    clock.advanceDays(2);
    await purgeOnAppStart(db, { now: clock.now(), files });
    expect(files.deleted).toEqual(['/p/1.jpg']);
    // The file goes this start and the row with it: no record is left to show it.
    expect(photoQ.getMine(scoped(db, 'dana'), out.photoIds[0]!)).toBeUndefined();
  });

  test('a closed job 14 days on goes whole — items, activity, sent rows — in one cascade', async () => {
    const { clock, db, deps, files } = setup();
    const s = scoped(db, 'dana');
    workOrderQ.upsertFromServer(s, wo('wo-1'), clock.iso());
    woItemQ.upsert(s, { id: 'i1', workOrderId: 'wo-1', kind: 'task', position: 1, label: 'x' }, clock.iso());
    const out = capture(db, dana, {
      kind: 'close', workOrderId: 'wo-1', payload: {},
      apply: (sc, key) => activityQ.insert(sc, { id: 'a1', workOrderId: 'wo-1', kind: 'status', status: 'closed', at: clock.iso(), outboxId: key }),
    }, deps);
    settleAt(db, out.key, clock.now());
    // The close queued the job's accept ahead of it (DEF-FLD-10612); it is sent too.
    for (const r of s.all<{ id: string }>(`SELECT id FROM outbox WHERE technician_id = :technician_id AND kind = 'job_accept'`)) {
      settleAt(db, r.id, clock.now());
    }
    workOrderQ.markClosed(s, 'wo-1', clock.iso());
    clock.advanceDays(13);
    expect((await purgeOnAppStart(db, { now: clock.now(), files })).closedJobs).toBe(0);
    clock.advanceDays(2);
    expect((await purgeOnAppStart(db, { now: clock.now(), files })).closedJobs).toBe(1);
    expect(workOrderQ.getMine(s, 'wo-1')).toBeUndefined();
    expect(woItemQ.listForOrder(s, 'wo-1')).toEqual([]);
    expect(activityQ.listForOrder(s, 'wo-1')).toEqual([]);
    expect(rows(db, 'outbox')).toBe(0);
  });

  test('a turned-in route goes 14 days on — unless a reading on it is still unsent', async () => {
    const { clock, db, deps, files } = setup();
    const s = scoped(db, 'dana');
    for (const r of ['r-done', 'r-stuck']) {
      routeQ.upsert(s, { id: r }, clock.iso());
      routeReadQ.upsertFromServer(s, { id: `${r}-m1`, routeId: r, stopId: 's', assetId: 'a', unit: 'kWh' }, clock.iso());
      const out = capture(db, dana, {
        kind: 'route_read', routeId: r, payload: {},
        apply: (sc, key) => routeReadQ.recordCapture(sc, `${r}-m1`, { captureKey: key, value: '1.00', unit: 'kWh', readerStatus: 'read', capturedAt: clock.iso(), capturedBy: 'dana', identifiedBy: 'scan', readMethod: 'manual' }),
      }, deps);
      if (r === 'r-done') {
        settleAt(db, out.key, clock.now());
        routeReadQ.setStateByKey(deviceWide(db, 'receipt'), out.key, 'accepted');
      }
      routeQ.markTurnedIn(s, r, clock.iso());
    }
    clock.advanceDays(20);
    const report = await purgeOnAppStart(db, { now: clock.now(), files });
    expect(report).toMatchObject({ routes: 1, routesKeptForUnsentWork: 1 });
    expect(routeReadQ.getMine(s, 'r-done-m1')).toBeUndefined();
    expect(routeReadQ.getMine(s, 'r-stuck-m1')?.state).toBe('pending');
  });

  test('documents above the cap go oldest first, never one a job on the handset still cites', async () => {
    const { clock, db, files } = setup();
    const MB = 1024 * 1024;
    workOrderQ.upsertFromServer(scoped(db, 'dana'), wo('wo-live'), clock.iso());
    const doc = (id: string, ownerId: string, used: string) => {
      files.add(`/d/${id}`);
      documentQ.upsert(db, { id, ownerKind: 'work_order', ownerId, title: id, source: 'server', localPath: `/d/${id}`, bytes: 80 * MB, lastUsedAt: used }, clock.iso());
    };
    doc('cited-oldest', 'wo-live', '2026-01-01');
    doc('old', 'wo-gone', '2026-02-01');
    doc('newer', 'wo-gone', '2026-03-01');
    const report = await purgeOnAppStart(db, { now: clock.now(), files });
    expect(report.documentsEvicted).toBe(1); // 240 MB → 160 MB
    expect(files.deleted).toEqual(['/d/old']);
    expect(documentQ.get(db, 'old')?.local_path).toBeNull();
    expect(documentQ.get(db, 'cited-oldest')?.local_path).toBe('/d/cited-oldest');
  });

  test('runs on app start only: nothing schedules it, and the sync engine never calls it (R63)', () => {
    const purgeSrc = readFileSync(join(__dirname, '../../src/db/purge.ts'), 'utf8');
    expect(purgeSrc).not.toMatch(/setInterval|setTimeout|BackgroundFetch|TaskManager/);
    const syncDir = join(__dirname, '../../src/sync');
    for (const f of readdirSync(syncDir)) {
      expect(`${f}: ${/from '\.\.\/db\/purge'/.test(readFileSync(join(syncDir, f), 'utf8'))}`).toBe(`${f}: false`);
    }
  });
});
