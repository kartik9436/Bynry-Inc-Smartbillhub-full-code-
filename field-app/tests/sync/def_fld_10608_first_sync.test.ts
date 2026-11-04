/**
 * @jest-environment node
 *
 * DEF-FLD-10608 (decision log 2026-10-26, FA-10 *"keep Open my day as a
 * button"*): FF-08 *Loading your day* read *Jobs and checklists — Did not
 * load*, with no reason, and *Open my day* never enabled, whenever ONE job's
 * details, the template catalogue or a hung call failed.
 *
 * Why no check saw it: every sync test used a fake server that either
 * succeeds or fails cleanly — never a call that hangs, never a single bad job
 * among good ones — and one variable (`pullError`) covered three steps.
 *
 * So this file drives the REAL `SyncEngine` and the REAL `engineFirstSync`
 * over a server where one job's bundle is a 500, the catalogue fails, or the
 * sign-in has expired; and the REAL `HttpTransport` over a fetch that never
 * answers.
 */
import { engineFirstSync, isComplete, percentOf, reasonFor, type FirstSyncProgress } from '../../src/screens/gettingIn/firstSync';
import * as workOrderQ from '../../src/db/queries/workOrder';
import { scoped } from '../../src/db/scoped';
import { SyncEngine } from '../../src/sync/engine';
import type { WirePage, WireTemplate } from '../../src/sync/fieldApi';
import { capture } from '../../src/sync/outbox';
import * as outboxQ from '../../src/db/queries/outbox';
import { CALL_TIME_LIMIT_MS, HttpTransport, TimeLimitError, TransportError } from '../../src/sync/transport';
import { FakeClock, idSource, MemoryFiles, openStore, steadyRandom } from '../db/support/fixtures';
import { FakeServer, serverBundle, serverCard } from './support/fakeServer';

const TECH = 'tech-dana';

/** The field doors the engine looks for, over the shared fake. */
class DayServer extends FakeServer {
  readonly bundleFails = new Map<string, TransportError>();
  templatesFail: TransportError | null = null;
  bundleCalls: string[] = [];
  async jobBundle(jobId: string) {
    this.bundleCalls.push(jobId);
    const fail = this.bundleFails.get(jobId);
    if (fail) throw fail;
    return super.jobBundle(jobId);
  }
  raiseOrder(): never {
    throw new Error('not asked');
  }
  async templates(_page: number): Promise<WirePage<WireTemplate>> {
    if (this.templatesFail) throw this.templatesFail;
    return { count: 0, next: null, results: [] };
  }
}

/** Eleven jobs on the feed, each with its bundle. */
function elevenJobs(server: DayServer): string[] {
  const ids = Array.from({ length: 11 }, (_, i) => `wo-${7001 + i}`);
  server.pages.push({
    changes: ids.map((id, i) => ({ change: 'upsert' as const, order_id: id, at: `t${i}`, job: serverCard({ id, order_no: id.toUpperCase() }) })),
    count: ids.length,
    next_cursor: 'c1',
    has_more: false,
  });
  for (const id of ids) server.bundles.set(id, serverBundle(serverCard({ id, order_no: id.toUpperCase() })));
  return ids;
}

function rig() {
  const clock = new FakeClock();
  const db = openStore('north', undefined, clock);
  const server = new DayServer();
  const engine = new SyncEngine({ db, transport: server, files: new MemoryFiles(), tokens: { tokenFor: () => 't' }, clock, random: steadyRandom });
  const calls: string[] = [];
  const port = engineFirstSync((what, opts) => {
    calls.push(what);
    return engine.sync({ technicianId: TECH, network: 'wifi', onlyDetails: what === 'details', withTemplates: opts?.templates });
  });
  return { db, server, engine, port, calls };
}

const jobsOf = (p: FirstSyncProgress) => p.parts.find((x) => x.id === 'jobs')!;

describe('the engine reports the feed, the bundles and the catalogue separately', () => {
  test('feed ok + one bundle 500: pullError is null; the bundle is counted, with its reason', async () => {
    const { server, engine } = rig();
    const ids = elevenJobs(server);
    server.bundleFails.set(ids[4]!, new TransportError('network', 'HTTP 500', 500));
    const r = await engine.sync({ technicianId: TECH, network: 'wifi' });
    expect(r.pullError).toBeNull();
    expect(r.pull?.upserts).toBe(11);
    expect(r.bundles).toMatchObject({ fetched: 10, failed: 1 });
    expect(r.bundles?.lastFailure).toMatchObject({ kind: 'network', status: 500 });
    expect(r.templatesError ?? null).toBeNull();
  });

  test('the catalogue failing is templatesError, never pullError', async () => {
    const { server, engine } = rig();
    elevenJobs(server);
    server.templatesFail = new TransportError('network', 'HTTP 503', 503);
    const r = await engine.sync({ technicianId: TECH, network: 'wifi' });
    expect(r.pullError).toBeNull();
    expect(r.templatesError).toBe('HTTP 503');
    expect(r.bundles).toMatchObject({ fetched: 11, failed: 0 });
  });

  test('a bundle with no answer at all (no signal, a time limit) stops the loop; the rest wait, counted', async () => {
    const { db, server, engine } = rig();
    const ids = elevenJobs(server);
    server.bundleFails.set(ids[0]!, new TimeLimitError(CALL_TIME_LIMIT_MS));
    const r = await engine.sync({ technicianId: TECH, network: 'wifi' });
    expect(server.bundleCalls).toHaveLength(1);
    expect(r.bundles).toMatchObject({ fetched: 0, failed: 11 });
    expect(workOrderQ.needingBundle(scoped(db, TECH), 100)).toHaveLength(11);
  });
});

describe('FF-08 over the real engine', () => {
  test('feed ok + one bundle 500 → Jobs DONE, 10 of 11, Server error, 100% and the day opens', async () => {
    const { server, port } = rig();
    const ids = elevenJobs(server);
    server.bundleFails.set(ids[4]!, new TransportError('network', 'HTTP 500', 500));
    const out = await port.run(() => undefined);
    expect(jobsOf(out)).toMatchObject({ state: 'done', done: 10, total: 11, reason: 'server' });
    expect(percentOf(out)).toBe(100);
    expect(isComplete(out)).toBe(true);
  });

  test('the catalogue failing leaves Jobs done, 11 of 11, no reason', async () => {
    const { server, port } = rig();
    elevenJobs(server);
    server.templatesFail = new TransportError('network', 'HTTP 503', 503);
    const out = await port.run(() => undefined);
    expect(jobsOf(out)).toMatchObject({ state: 'done', done: 11, total: 11, reason: null });
    expect(isComplete(out)).toBe(true);
  });

  test('Retry after one bundle failed fetches only the missing details and reaches 100% with 11 of 11', async () => {
    const { server, port, calls } = rig();
    const ids = elevenJobs(server);
    server.bundleFails.set(ids[4]!, new TransportError('network', 'HTTP 500', 500));
    await port.run(() => undefined);
    server.bundleFails.clear();
    server.bundleCalls = [];
    const seen: FirstSyncProgress[] = [];
    const out = await port.retry!((p) => seen.push(p));
    expect(calls).toEqual(['all', 'details']);
    expect(server.bundleCalls).toEqual([ids[4]]);
    expect(server.cursorsSeen).toHaveLength(1); // the feed was not asked again
    expect(jobsOf(out)).toMatchObject({ state: 'done', done: 11, total: 11, reason: null });
    expect(percentOf(out)).toBe(100);
  });

  test('Retry after the LIST failed runs the whole sync again', async () => {
    const { server, port, calls } = rig();
    elevenJobs(server);
    const changes = server.changes.bind(server);
    let down = true;
    server.changes = async (c, n) => {
      if (down) throw new TimeLimitError(CALL_TIME_LIMIT_MS);
      return changes(c, n);
    };
    const first = await port.run(() => undefined);
    expect(jobsOf(first)).toMatchObject({ state: 'failed', reason: 'noSignal' });
    expect(isComplete(first)).toBe(false);
    down = false;
    const out = await port.retry!(() => undefined);
    expect(calls).toEqual(['all', 'all']);
    expect(jobsOf(out)).toMatchObject({ state: 'done', done: 11, total: 11 });
    expect(percentOf(out)).toBe(100);
  });
});

describe('signed out', () => {
  test('the sign-in expired at the push → Jobs failed with signedOut, never a bare failure', async () => {
    const clock = new FakeClock();
    const db = openStore('north', undefined, clock);
    const server = new DayServer();
    elevenJobs(server);
    server.authFails = true;
    capture(db, { technicianId: TECH, capturedBy: TECH }, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, { newId: idSource(), clock });
    const engine = new SyncEngine({ db, transport: server, files: new MemoryFiles(), tokens: { tokenFor: () => 't' }, clock });
    const port = engineFirstSync(() => engine.sync({ technicianId: TECH, network: 'wifi' }));
    const out = await port.run(() => undefined);
    expect(jobsOf(out)).toMatchObject({ state: 'failed', reason: 'signedOut' });
  });
});

describe('every call has a time limit', () => {
  const hung = () => {
    const signals: AbortSignal[] = [];
    const fetchImpl = ((_url: string, init?: RequestInit) => {
      if (init?.signal) signals.push(init.signal);
      return new Promise<Response>(() => undefined); // never answers
    }) as unknown as typeof fetch;
    return { signals, fetchImpl };
  };

  test('a hung call stops at the limit as a NETWORK error with no status — read as No signal', async () => {
    const { signals, fetchImpl } = hung();
    const t = new HttpTransport({ origin: 'https://north.example.test', tenant: 'north', accessToken: () => 'tok', fetchImpl, appHeaders: () => ({}), timeoutMs: 40 });
    const started = Date.now();
    const err = await t.changes(null, 50).then(
      () => null,
      (e: unknown) => e,
    );
    expect(Date.now() - started).toBeLessThan(5_000);
    expect(err).toBeInstanceOf(TransportError);
    expect(err).toMatchObject({ kind: 'network', status: undefined });
    expect(signals[0]?.aborted).toBe(true);
    expect(reasonFor(err as TransportError)).toBe('noSignal');
  });

  test('the default limit is 30 s; a photograph gets the longer transfer limit', async () => {
    expect(CALL_TIME_LIMIT_MS).toBe(30_000);
    const { fetchImpl } = hung();
    const t = new HttpTransport({ origin: 'https://north.example.test', tenant: 'north', accessToken: () => 'tok', fetchImpl, appHeaders: () => ({}), timeoutMs: 10, transferTimeoutMs: 120 });
    const started = Date.now();
    await expect(t.putPhoto({ photoId: 'p1', uploadUrl: null, localPath: 'file:///p1.jpg', sha256: 'x', contentType: 'image/jpeg' })).rejects.toBeInstanceOf(TimeLimitError);
    expect(Date.now() - started).toBeGreaterThanOrEqual(100);
  });

  test('the outbox treats a time-limited send as a dropped connection: kept pending, retried with backoff', async () => {
    const clock = new FakeClock();
    const db = openStore('north', undefined, clock);
    const { fetchImpl } = hung();
    const t = new HttpTransport({ origin: 'https://north.example.test', tenant: 'north', accessToken: () => 'tok', fetchImpl, appHeaders: () => ({}), timeoutMs: 20 });
    capture(db, { technicianId: TECH, capturedBy: TECH }, { kind: 'reading', workOrderId: 'wo-1', payload: {} }, { newId: idSource(), clock });
    const engine = new SyncEngine({ db, transport: t, files: new MemoryFiles(), tokens: { tokenFor: () => 'tok' }, clock, random: steadyRandom });
    const r = await engine.sync({ technicianId: null, network: 'wifi' });
    expect(r.data.unanswered).toBe(1);
    const [row] = outboxQ.listMine(scoped(db, TECH), { limit: 10 });
    expect(row).toMatchObject({ state: 'pending', attempts: 1, last_error: `no answer in 20 ms` });
    expect(row!.next_attempt_at).not.toBeNull();
  });
});
