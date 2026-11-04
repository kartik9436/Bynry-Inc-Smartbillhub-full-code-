/**
 * DEF-FLD-10624 — each cause of *Sync shows ONLINE and sends nothing*, alone
 * (decision log 2026-10-27, *"start A to F"*). The PO's whole case, end to
 * end through the app, is `def_fld_10624_sync_sends_nothing.test.tsx`.
 *
 *  A — a run's result and an item's saved failure read as one short reason;
 *  B — a send the server answered records the push time;
 *  C — a manual press clears this technician's backoff (and nobody else's,
 *      and never the server's own Retry-After wait);
 *  D — a job is due when its FIRST waiting item is, as `nextBatch` sends;
 *  F — a step, and the engine's whole run, end at their limit and let go.
 */
import * as outboxQ from '../../src/db/queries/outbox';
import * as syncStateQ from '../../src/db/queries/syncState';
import { deviceWide, scoped } from '../../src/db/scoped';
import { kindOf } from '../../src/device/network';
import { DELTA_TABLE } from '../../src/sync/delta';
import { SyncEngine, type SyncResult } from '../../src/sync/engine';
import { capture } from '../../src/sync/outbox';
import { applyBatchAnswer, applyBatchFailure } from '../../src/sync/receipts';
import { StepTimeLimitError, within } from '../../src/sync/runLimits';
import { reasonOfFailure, reasonOfLastError, reasonOfResult } from '../../src/sync/syncReason';
import { TransportError, type BatchAnswer, type WireItem } from '../../src/sync/transport';
import { FakeClock, idSource, MemoryFiles, openStore, steadyRandom } from '../db/support/fixtures';
import { FakeServer } from './support/fakeServer';

const MINUTE = 60_000;

function three(tech = 'dana') {
  const clock = new FakeClock();
  const db = openStore('north', undefined, clock);
  const ids = idSource(tech);
  const keys = [0, 1, 2].map(
    () => capture(db, { technicianId: tech, capturedBy: tech }, { kind: 'task_tick', workOrderId: 'wo-1', payload: {} }, { newId: ids, clock }).key,
  );
  return { clock, db, keys, s: scoped(db, tech) };
}

function backOff(db: ReturnType<typeof openStore>, key: string, until: string, error = 'Network request failed') {
  outboxQ.retryLater(deviceWide(db, 'receipt'), key, until, error, true);
}

describe('D — a job is due when its FIRST waiting item is', () => {
  test('a later item backing off does not hold the earlier ones', () => {
    const { clock, db, keys } = three();
    backOff(db, keys[2]!, new Date(clock.now().getTime() + 10 * MINUTE).toISOString());
    const send = deviceWide(db, 'send');
    const groups = outboxQ.dueGroups(send, clock.iso());
    expect(groups.map((g) => g.work_order_id)).toEqual(['wo-1']);
    // nextBatch then stops before the one backing off: capture order holds (R45).
    expect(outboxQ.nextBatch(send, groups[0]!, 50, clock.iso()).map((r) => r.id)).toEqual(keys.slice(0, 2));
  });

  test('the FIRST item backing off still holds the job (nothing overtakes it)', () => {
    const { clock, db, keys } = three();
    backOff(db, keys[0]!, new Date(clock.now().getTime() + 10 * MINUTE).toISOString());
    expect(outboxQ.dueGroups(deviceWide(db, 'send'), clock.iso())).toEqual([]);
  });
});

describe('C — a manual press clears the backoff', () => {
  test('mine only, and never the server’s own Retry-After wait', () => {
    const { clock, db, keys, s } = three('dana');
    const later = new Date(clock.now().getTime() + 10 * MINUTE).toISOString();
    const marco = capture(db, { technicianId: 'marco', capturedBy: 'marco' }, { kind: 'task_tick', workOrderId: 'wo-2', payload: {} }, { newId: idSource('m'), clock }).key;
    backOff(db, keys[0]!, later);
    backOff(db, keys[1]!, later, 'HTTP 502');
    outboxQ.retryLater(deviceWide(db, 'receipt'), keys[2]!, later, 'rate_limited', false);
    backOff(db, marco, later);
    expect(outboxQ.clearBackoffMine(s)).toBe(2);
    const next = (k: string) => deviceWide(db, 'receipt').get<{ n: string | null }>('SELECT next_attempt_at AS n FROM outbox WHERE id = :id', { id: k })?.n;
    expect(next(keys[0]!)).toBeNull();
    expect(next(keys[1]!)).toBeNull();
    expect(next(keys[2]!)).toBe(later);
    expect(next(marco)).toBe(later);
  });
});

describe('B — a send the server answered moves "Last reached the server"', () => {
  const answerAll = (rows: outboxQ.OutboxRow[]): BatchAnswer => ({
    accepted: rows.length,
    duplicate: 0,
    refused: 0,
    acknowledged: rows.map((r) => r.id),
    items: rows.map((r) => ({ key: r.id, kind: r.kind, seq: r.seq, result: 'accepted' as const, ack: true })),
  });

  test('an answer records the push time; a dropped connection does not', () => {
    const { clock, db, s } = three();
    const rows = outboxQ.listMine(s, { limit: 10 });
    applyBatchFailure(db, rows, new TransportError('network', 'dropped'), clock.now(), steadyRandom);
    expect(syncStateQ.get(s, DELTA_TABLE)?.last_push_at ?? null).toBeNull();
    clock.advance(MINUTE);
    applyBatchAnswer(db, rows, answerAll(rows), clock.now(), steadyRandom);
    expect(syncStateQ.get(s, DELTA_TABLE)).toMatchObject({ last_push_at: clock.iso(), pending_count: 0 });
  });
});

describe('F — every step has a time limit', () => {
  test('within: the work, or StepTimeLimitError at the limit', async () => {
    await expect(within(Promise.resolve(7), 50, 'x')).resolves.toBe(7);
    await expect(within(new Promise(() => undefined), 20, 'network check')).rejects.toBeInstanceOf(StepTimeLimitError);
  });

  test('the engine lets a hung run go: the caller is answered, busy is released, the next call starts afresh', async () => {
    const { clock, db } = three();
    const server = new FakeServer();
    const send = server.sendJobBatch.bind(server);
    let hang = true;
    server.sendJobBatch = (id: string, items: WireItem[]) => (hang ? new Promise<BatchAnswer>(() => undefined) : send(id, items));
    const engine = new SyncEngine({ db, transport: server, files: new MemoryFiles(), tokens: { tokenFor: () => 't' }, clock, runLimitMs: 50 });
    await expect(engine.sync({ technicianId: 'dana', network: 'wifi' })).rejects.toBeInstanceOf(StepTimeLimitError);
    expect(engine.running).toBe(false);
    hang = false;
    const r = await engine.sync({ technicianId: 'dana', network: 'wifi' });
    expect(r.data.accepted).toBe(3); // the rows the hung run left `sending` went again (R49)
  });

  test('after airplane mode off, NetInfo’s first answers read as connected, never "none"', () => {
    expect(kindOf({ type: 'wifi', isConnected: true, isInternetReachable: null })).toBe('wifi');
    expect(kindOf({ type: 'cellular', isConnected: true, isInternetReachable: true })).toBe('cellular');
    expect(kindOf({ type: 'none', isConnected: false, isInternetReachable: false })).toBe('none');
  });
});

describe('A — why nothing went, as one reason', () => {
  test('a step’s failure', () => {
    expect(reasonOfFailure({ kind: 'auth' })).toBe('signIn');
    expect(reasonOfFailure({ kind: 'network' })).toBe('noSignal');
    expect(reasonOfFailure({ kind: 'network', status: 503 })).toBe('server');
    expect(reasonOfFailure({ kind: 'http', status: 429 })).toBe('rateLimited');
    expect(reasonOfFailure({ kind: 'certificate' })).toBe('certificate');
    expect(reasonOfFailure({ kind: 'endpoint_missing' })).toBe('outdated');
    expect(reasonOfFailure({ kind: 'app_too_old' })).toBe('update');
  });

  test('an item’s saved failure, as receipts.ts writes it', () => {
    expect(reasonOfLastError(null)).toBeNull();
    expect(reasonOfLastError('waiting_for_sign_in')).toBe('signIn');
    expect(reasonOfLastError('waiting_for_captor_sign_in')).toBe('signIn');
    expect(reasonOfLastError('waiting_for_app_update')).toBe('update');
    expect(reasonOfLastError('rate_limited')).toBe('rateLimited');
    expect(reasonOfLastError('endpoint_missing: HTTP 404 not JSON')).toBe('outdated');
    expect(reasonOfLastError('HTTP 502')).toBe('server');
    expect(reasonOfLastError('no answer in 30000 ms')).toBe('noSignal');
    expect(reasonOfLastError('Network request failed')).toBe('noSignal');
  });

  test('a run’s result: a stop for sign-in wins; a clean run says nothing', () => {
    const data = { accepted: 0, duplicate: 0, held_for_review: 0, refused: 0, unanswered: 0, batches: 0, stoppedForAuth: false, stoppedForUpdate: false, skippedNoToken: 0, skippedNoTokenBy: {}, waitingForCaptor: 0 };
    const base: SyncResult = { data, photos: null, pull: null, pullError: null, failures: { pull: null, bundles: null, templates: null } };
    expect(reasonOfResult(base)).toBeNull();
    expect(reasonOfResult({ ...base, stoppedForAuth: true })).toBe('signIn');
    // DEF-FLD-10629 (G): MY work waiting for a capture credential — *Sign in again to send*;
    // another captor's is shown under their name, not as this run's reason.
    const skipped = { ...base, data: { ...data, skippedNoToken: 2, skippedNoTokenBy: { dana: 2 } } };
    expect(reasonOfResult(skipped, 'dana')).toBe('signInToSend');
    expect(reasonOfResult(skipped, 'marco')).toBeNull();
    expect(reasonOfResult({ ...base, failures: { pull: { kind: 'network', message: 'x' }, bundles: null, templates: null } })).toBe('noSignal');
  });
});
