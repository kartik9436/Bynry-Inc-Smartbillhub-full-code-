/**
 * @jest-environment node
 *
 * T-10 — the outbox: capture is atomic and keyed at capture; sending is per
 * item, in order, bounded, backed off, and never drops or silently retries a
 * refusal.
 */
import { readFileSync } from 'fs';
import { join } from 'path';

import type { TenantDb } from '../../src/db/database';
import * as outboxQ from '../../src/db/queries/outbox';
import * as photoQ from '../../src/db/queries/photo';
import * as woItemQ from '../../src/db/queries/woItem';
import { deviceWide, scoped } from '../../src/db/scoped';
import { NEEDS_ATTENTION_AFTER } from '../../src/sync/backoff';
import { capture, JOB_SYNC_KINDS, resendRefused, sendPending, type CaptureInput } from '../../src/sync/outbox';
import { TransportError } from '../../src/sync/transport';
import { FakeClock, idSource, openStore, steadyRandom } from '../db/support/fixtures';
import { FakeServer } from './support/fakeServer';

const dana = { technicianId: 'dana', capturedBy: 'dana' };
const marco = { technicianId: 'marco', capturedBy: 'marco' };
const tokens = { tokenFor: (t: string) => `token-of-${t}` };

function setup() {
  const clock = new FakeClock();
  const db = openStore('north', undefined, clock);
  const deps = { newId: idSource('k'), clock };
  const server = new FakeServer();
  const opts = { clock, tokens, random: steadyRandom };
  return { clock, db, deps, server, opts };
}

function count(db: TenantDb, sql: string): number {
  return deviceWide(db, 'count').get<{ n: number }>(sql)?.n ?? 0;
}

describe('capture', () => {
  test("the server's item kinds and ours are the same list (apps/work/sync_models.py)", () => {
    const py = readFileSync(join(__dirname, '../../../06-backend/apps/work/sync_models.py'), 'utf8');
    const block = /ITEM_KINDS = \(([\s\S]*?)\n\)/.exec(py)?.[1] ?? '';
    const serverKinds = [...block.matchAll(/^\s*"(\w+)",/gm)].map((m) => m[1]);
    expect(serverKinds.length).toBeGreaterThan(0);
    expect([...JOB_SYNC_KINDS]).toEqual(serverKinds);
  });

  test('mints the key at capture and keeps capture order within the order', () => {
    const { db, deps } = setup();
    const a = capture(db, dana, { kind: 'safety_tick', workOrderId: 'wo-1', payload: { safety_id: 's1' } }, deps);
    const b = capture(db, dana, { kind: 'close', workOrderId: 'wo-1', payload: {} }, deps);
    const rows = outboxQ.listMine(scoped(db, 'dana'), { limit: 10 }).sort((x, y) => x.seq - y.seq);
    expect(rows.map((r) => [r.id, r.seq, r.state])).toEqual([
      [a.key, 1, 'pending'],
      [b.key, 2, 'pending'],
    ]);
  });

  test('a reading, its photo row and its declaration land in ONE transaction', () => {
    const { db, deps } = setup();
    const s = scoped(db, 'dana');
    woItemQ.upsert(s, { id: 't1', workOrderId: 'wo-1', kind: 'task', position: 1, label: 'Fit meter' }, '2026-10-21');
    const out = capture(
      db,
      dana,
      {
        kind: 'task_tick',
        workOrderId: 'wo-1',
        payload: { task_id: 't1' },
        photos: [{ localPath: '/p/1.jpg', sha256: 'a'.repeat(64), bytes: 300_000, target: { task_id: 't1' } }],
        apply: (sc) => woItemQ.setState(sc, 't1', 'done'),
      },
      deps,
    );
    expect(outboxQ.getMine(s, out.key)?.kind).toBe('task_tick');
    const decl = outboxQ.getMine(s, out.declarationKeys[0]!);
    expect(decl?.kind).toBe('photo');
    expect(JSON.parse(decl!.payload)).toEqual({ photo_id: out.photoIds[0], sha256: 'a'.repeat(64), task_id: 't1' });
    expect(photoQ.getMine(s, out.photoIds[0]!)).toMatchObject({ outbox_id: out.key, declare_id: decl!.id, local_path: '/p/1.jpg' });
    expect(woItemQ.listForOrder(s, 'wo-1')[0]?.state).toBe('done');
  });

  test('a failure mid-capture leaves NOTHING half-written', () => {
    const { db, deps } = setup();
    const s = scoped(db, 'dana');
    woItemQ.upsert(s, { id: 't1', workOrderId: 'wo-1', kind: 'task', position: 1, label: 'Fit meter' }, '2026-10-21');
    const input: CaptureInput = {
      kind: 'task_tick',
      workOrderId: 'wo-1',
      payload: { task_id: 't1' },
      photos: [{ localPath: '/p/1.jpg', sha256: 'a'.repeat(64), bytes: 1, target: { task_id: 't1' } }],
      apply: (sc) => {
        woItemQ.setState(sc, 't1', 'done');
        throw new Error('the device ran out of space');
      },
    };
    expect(() => capture(db, dana, input, deps)).toThrow('out of space');
    expect(count(db, 'SELECT COUNT(*) AS n FROM outbox')).toBe(0);
    expect(count(db, 'SELECT COUNT(*) AS n FROM photo')).toBe(0);
    expect(woItemQ.listForOrder(s, 'wo-1')[0]?.state).toBeNull();

    // and a constraint failure half way (a repeated key) rolls back the same way
    const sameId = () => 'k-same';
    expect(() =>
      capture(db, dana, { ...input, apply: undefined }, { ...deps, newId: sameId }),
    ).toThrow(/UNIQUE|PRIMARY/);
    expect(count(db, 'SELECT COUNT(*) AS n FROM outbox')).toBe(0);
    expect(count(db, 'SELECT COUNT(*) AS n FROM photo')).toBe(0);
  });

  test('refuses a job item with no job, and parks kinds with no server door', () => {
    const { db, deps } = setup();
    expect(() => capture(db, dana, { kind: 'reading', payload: {} }, deps)).toThrow(/job/);
    const r = capture(db, dana, { kind: 'remark', workOrderId: 'wo-1', payload: { text: 'dog' } }, deps);
    expect(outboxQ.getMine(scoped(db, 'dana'), r.key)?.channel).toBe('unrouted');
  });
});

describe('sending', () => {
  test('per-item receipts: accepted, duplicate, held for review, refused', async () => {
    const { db, deps, server, opts } = setup();
    server.holdKinds.add('material');
    const ok = capture(db, dana, { kind: 'safety_tick', workOrderId: 'wo-1', payload: {} }, deps);
    const bad = capture(db, dana, { kind: 'close', workOrderId: 'wo-1', payload: { refuse: true } }, deps);
    const held = capture(db, dana, { kind: 'material', workOrderId: 'wo-1', payload: {} }, deps);
    server.receipts.add(`job:wo-1|${ok.key}`); // already there from an earlier, lost answer
    const summary = await sendPending(db, server, opts);
    expect(summary).toMatchObject({ batches: 1, duplicate: 1, refused: 1, held_for_review: 1, accepted: 0 });
    const s = scoped(db, 'dana');
    expect(outboxQ.getMine(s, ok.key)?.state).toBe('duplicate');
    expect(outboxQ.getMine(s, held.key)?.state).toBe('held_for_review');
    const refused = outboxQ.getMine(s, bad.key)!;
    expect(refused.state).toBe('refused');
    expect(JSON.parse(refused.refusal!)).toMatchObject({ message_key: 'work.safety.locked' });
    expect(refused.settled_at).toBeNull();
  });

  test('a refusal is kept and shown, never retried silently; the technician sends it again', async () => {
    const { db, deps, server, opts, clock } = setup();
    const bad = capture(db, dana, { kind: 'close', workOrderId: 'wo-1', payload: { refuse: true } }, deps);
    await sendPending(db, server, opts);
    clock.advanceDays(30);
    await sendPending(db, server, opts);
    expect(server.requests).toHaveLength(1);
    expect(outboxQ.needsAttentionMine(scoped(db, 'dana'), NEEDS_ATTENTION_AFTER).map((r) => r.id)).toEqual([bad.key]);

    server.refuseWhen = () => false; // the technician ticked the safety row
    expect(resendRefused(db, 'dana', bad.key)).toBe(true);
    const again = await sendPending(db, server, opts);
    expect(again.accepted).toBe(1);
    expect(server.applied.map((a) => a.key)).toEqual([bad.key]); // same key, once
  });

  test('batches of 50, capture order kept, at most two in flight, never two of one order at once', async () => {
    const { db, deps, server, opts } = setup();
    const perOrder = 120;
    for (const order of ['wo-1', 'wo-2', 'wo-3', 'wo-4', 'wo-5']) {
      for (let i = 0; i < perOrder; i++) capture(db, dana, { kind: 'reading', workOrderId: order, payload: { i } }, deps);
    }
    const inFlightByGroup = new Map<string, number>();
    let overlapSameOrder = false;
    const realSend = server.sendJobBatch.bind(server);
    server.sendJobBatch = async (id, items) => {
      const n = (inFlightByGroup.get(id) ?? 0) + 1;
      if (n > 1) overlapSameOrder = true;
      inFlightByGroup.set(id, n);
      try {
        return await realSend(id, items);
      } finally {
        inFlightByGroup.set(id, (inFlightByGroup.get(id) ?? 1) - 1);
      }
    };
    const summary = await sendPending(db, server, opts);
    expect(summary.accepted).toBe(600);
    expect(server.requests).toHaveLength(15); // 5 orders × (50 + 50 + 20)
    expect(Math.max(...server.requests.map((r) => r.size))).toBe(50);
    expect(server.maxInFlight).toBe(2);
    expect(overlapSameOrder).toBe(false);
    for (const order of ['wo-1', 'wo-2', 'wo-3', 'wo-4', 'wo-5']) {
      const seqs = server.applied.filter((a) => a.group === `job:${order}`).map((a) => a.seq);
      expect(seqs).toEqual(Array.from({ length: perOrder }, (_, i) => i + 1));
    }
  });

  test('a dead connection backs off: pending again, attempts counted, nothing sent before the time', async () => {
    const { db, deps, server, opts, clock } = setup();
    const k = capture(db, dana, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, deps);
    server.killPlan.set(1, 0);
    await sendPending(db, server, opts);
    const row = outboxQ.getMine(scoped(db, 'dana'), k.key)!;
    expect(row).toMatchObject({ state: 'pending', attempts: 1 });
    expect(Date.parse(row.next_attempt_at!) - clock.now().getTime()).toBe(2_000);

    await sendPending(db, server, opts); // not yet due
    expect(server.requests).toHaveLength(1);
    clock.advance(2_000);
    await sendPending(db, server, opts);
    expect(outboxQ.getMine(scoped(db, 'dana'), k.key)?.state).toBe('accepted');
  });

  test('after five failures it needs attention — and is still there, still pending', async () => {
    const { db, deps, server, opts, clock } = setup();
    const k = capture(db, dana, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, deps);
    for (let i = 1; i <= 6; i++) {
      server.killPlan.set(i, 0);
      await sendPending(db, server, opts);
      clock.advance(10 * 60_000);
    }
    const row = outboxQ.getMine(scoped(db, 'dana'), k.key)!;
    expect(row.state).toBe('pending');
    expect(row.attempts).toBe(6);
    expect(outboxQ.needsAttentionMine(scoped(db, 'dana'), NEEDS_ATTENTION_AFTER).map((r) => r.id)).toEqual([k.key]);
  });

  test('an expired sign-in stops sending without counting an attempt (Security §1)', async () => {
    const { db, deps, server, opts } = setup();
    const k = capture(db, dana, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, deps);
    server.authFails = true;
    const summary = await sendPending(db, server, opts);
    expect(summary.stoppedForAuth).toBe(true);
    expect(outboxQ.getMine(scoped(db, 'dana'), k.key)).toMatchObject({ state: 'pending', attempts: 0 });
  });

  test('a job the server does not know (another tenant’s, J65 step 13) is refused and shown', async () => {
    const { db, deps, server, opts } = setup();
    const k = capture(db, dana, { kind: 'reading', workOrderId: 'wo-x', payload: {} }, deps);
    server.sendJobBatch = async () => {
      throw new TransportError('http', 'HTTP 404', 404);
    };
    await sendPending(db, server, opts);
    expect(outboxQ.getMine(scoped(db, 'dana'), k.key)?.state).toBe('refused');
  });

  test('DEF-SHL-10621: a 429 (too many syncs from this phone) is NOT a refusal — the batch waits and resends, nothing lost', async () => {
    const { clock, db, deps, server, opts } = setup();
    const k = capture(db, dana, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, deps);
    const realSend = server.sendJobBatch.bind(server);
    server.sendJobBatch = async () => {
      throw new TransportError('http', 'HTTP 429', 429, {
        code: null,
        message_key: 'api.error.rate_limited',
        params: { retry_after_seconds: 30 },
      });
    };
    const first = await sendPending(db, server, opts);
    expect(first.refused).toBe(0);
    const row = outboxQ.getMine(scoped(db, 'dana'), k.key)!;
    expect(row.state).toBe('pending');
    expect(row.attempts).toBe(0); // the item did nothing wrong
    expect(row.refusal ?? null).toBeNull();
    // It waits for the server's Retry-After, not the backoff curve…
    expect(Date.parse(row.next_attempt_at!) - clock.now().getTime()).toBe(30_000);
    // …and is sent, once, after it.
    server.sendJobBatch = realSend;
    clock.advance(31_000);
    const second = await sendPending(db, server, opts);
    expect(second.accepted + second.duplicate).toBe(1);
  });

  test("handover: Dana's work sends under Dana's token while Marco is signed in (E2E-21)", async () => {
    const { db, deps, server, opts } = setup();
    for (let i = 0; i < 62; i++) capture(db, dana, { kind: 'task_tick', workOrderId: 'wo-d', payload: {} }, deps);
    for (let i = 0; i < 31; i++) capture(db, marco, { kind: 'task_tick', workOrderId: 'wo-m', payload: {} }, deps);
    const summary = await sendPending(db, server, opts);
    expect(summary.accepted).toBe(93);
    expect(server.applied.filter((a) => a.captor === 'token-of-dana')).toHaveLength(62);
    expect(server.applied.filter((a) => a.captor === 'token-of-marco')).toHaveLength(31);
    expect(server.applied.every((a) => (a.group === 'job:wo-d') === (a.captor === 'token-of-dana'))).toBe(true);
  });

  test('without the captor’s own credential the work waits, rather than travel as someone else', async () => {
    const { db, deps, server, opts } = setup();
    capture(db, dana, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, deps);
    const summary = await sendPending(db, server, { ...opts, tokens: { tokenFor: () => null } });
    expect(summary.skippedNoToken).toBe(1);
    expect(server.requests).toHaveLength(0);
  });

  test('route readings wait, unsent and unharmed, while the server has no door for them', async () => {
    const { db, deps, server, opts } = setup();
    server.routeEndpointExists = false;
    const k = capture(db, dana, { kind: 'route_read', routeId: 'r-1', payload: {} }, deps);
    await sendPending(db, server, opts);
    expect(outboxQ.getMine(scoped(db, 'dana'), k.key)).toMatchObject({ state: 'pending', attempts: 0 });
    expect(outboxQ.getMine(scoped(db, 'dana'), k.key)?.last_error).toMatch(/endpoint_missing/);
  });

  test('a crash mid-send leaves rows "sending"; the next run sends them again and the key makes it safe', async () => {
    const { db, deps, server, opts } = setup();
    const k = capture(db, dana, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, deps);
    outboxQ.markSending(deviceWide(db, 'send'), [k.key]); // the app died here last time
    server.receipts.add(`job:wo-1|${k.key}`); // and the server had it
    const summary = await sendPending(db, server, opts);
    expect(summary.duplicate).toBe(1);
    expect(server.applied).toHaveLength(0);
  });
});
