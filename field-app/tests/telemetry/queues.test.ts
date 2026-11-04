/**
 * T-73 — the analytics queue, the crash file and the yield rule (R67).
 */
import {
  createAnalyticsQueue,
  createCrashCapture,
  createFakeCrashReporter,
  createMemoryStore,
  createScrubber,
  createTelemetry,
  createWorkGate,
  installGlobalCrashHandler,
  type AnalyticsTransport,
  type ScrubbedEvent,
  type TelemetryIdentity,
  type WorkGate,
} from '../../src/telemetry';

const ID: TelemetryIdentity = {
  tenant: 'carl-water',
  role: 'technician',
  deviceId: '3f2b8c1e-9a4d-4e7f-8b21-6c0d5e9a1f47',
};

function clearGate(): WorkGate {
  const g = createWorkGate();
  g.reportWork({ outbox: 0, photos: 0, syncing: false, online: true });
  return g;
}

function recorder() {
  const batches: (readonly ScrubbedEvent[])[] = [];
  let fail: Error | null = null;
  let hang = false;
  const transport: AnalyticsTransport = {
    send: (events) => {
      if (hang) return new Promise(() => {});
      if (fail) return Promise.reject(fail);
      batches.push(events);
      return Promise.resolve();
    },
  };
  return {
    transport,
    batches,
    failWith: (e: Error | null) => (fail = e),
    hang: (h: boolean) => (hang = h),
  };
}

describe('the work gate', () => {
  it('is closed until the sync engine reports (fail-closed)', () => {
    const g = createWorkGate();
    expect(g.canSend()).toBe(false);
    expect(g.reason()).toBe('unreported');
  });

  it.each([
    [{ outbox: 3, photos: 0, syncing: false, online: true }, 'outbox'],
    [{ outbox: 0, photos: 2, syncing: false, online: true }, 'photos'],
    [{ outbox: 0, photos: 0, syncing: true, online: true }, 'syncing'],
    [{ outbox: 0, photos: 0, syncing: false, online: false }, 'offline'],
  ] as const)('yields while %o', (state, reason) => {
    const g = createWorkGate();
    g.reportWork(state);
    expect(g.canSend()).toBe(false);
    expect(g.reason()).toBe(reason);
  });

  it('opens only when the outbox and the photo queue are both clear', () => {
    expect(clearGate().canSend()).toBe(true);
  });
});

describe('the analytics queue', () => {
  const build = (gate: WorkGate, r = recorder(), store = createMemoryStore(), maxEvents = 2000) =>
    createAnalyticsQueue({
      store,
      scrubber: createScrubber(() => 1000),
      gate,
      transport: r.transport,
      identity: () => ID,
      maxEvents,
      timeoutMs: 30,
    });

  it('holds events while the outbox has work, and sends once it is clear', async () => {
    const gate = createWorkGate();
    gate.reportWork({ outbox: 12, photos: 0, syncing: false, online: true });
    const r = recorder();
    const q = build(gate, r);
    q.track({ name: 'screen_view', fields: { screen: 'FF-10' } });
    expect(await q.flush()).toBe('yielded');
    expect(r.batches).toHaveLength(0);
    gate.reportWork({ outbox: 0, photos: 0, syncing: false, online: true });
    expect(await q.flush()).toBe('sent');
    expect(r.batches[0]!.map((e) => e.name)).toEqual(['screen_view']);
    expect(q.size()).toBe(0);
  });

  it('survives a restart: the queue is on the handset, not in memory', async () => {
    const store = createMemoryStore();
    const gate = createWorkGate();
    build(gate, recorder(), store).track({ name: 'app_start', fields: { duration_ms: 1800, cold: true } });
    const r = recorder();
    const after = build(clearGate(), r, store);
    expect(after.size()).toBe(1);
    await after.flush();
    expect(r.batches[0]![0]!.fields).toEqual({ duration_ms: 1800, cold: true });
  });

  it('drops the OLDEST past its bound, counts them, and reports the count once', async () => {
    const r = recorder();
    const q = build(createWorkGate(), r, createMemoryStore(), 3);
    for (let i = 0; i < 5; i++) q.track({ name: 'flow_abandoned', fields: { screen: 'FF-15', step: i } });
    expect(q.size()).toBe(3);
    expect(q.droppedCount()).toBe(2);

    const r2 = recorder();
    const q2 = createAnalyticsQueue({
      store: createMemoryStore(),
      scrubber: createScrubber(() => 1),
      gate: clearGate(),
      transport: r2.transport,
      identity: () => ID,
      maxEvents: 3,
    });
    for (let i = 0; i < 5; i++) q2.track({ name: 'flow_abandoned', fields: { screen: 'FF-15', step: i } });
    expect(await q2.flush()).toBe('sent');
    const sent = r2.batches[0]!;
    expect(sent.slice(0, 3).map((e) => e.fields.step)).toEqual([2, 3, 4]);
    expect(sent[3]).toMatchObject({ name: 'telemetry_dropped', fields: { events: 2, crashes: 0 } });
    expect(q2.droppedCount()).toBe(0);
  });

  it('is invisible when the endpoint is dead: no throw, events kept', async () => {
    const r = recorder();
    const q = build(clearGate(), r);
    q.track({ name: 'screen_view', fields: { screen: 'FF-10' } });
    r.failWith(new Error('ECONNREFUSED'));
    await expect(q.flush()).resolves.toBe('failed');
    expect(q.size()).toBe(1);
    r.failWith(null);
    r.hang(true);
    await expect(q.flush()).resolves.toBe('failed'); // timed out, not hung
    expect(q.size()).toBe(1);
  });

  it('never throws when the store itself fails', () => {
    const broken = { getString: () => { throw new Error('disk'); }, set: () => { throw new Error('disk'); }, delete: () => {} };
    const q = createAnalyticsQueue({
      store: broken,
      scrubber: createScrubber(),
      gate: clearGate(),
      transport: recorder().transport,
      identity: () => ID,
    });
    expect(() => q.track({ name: 'screen_view', fields: { screen: 'FF-10' } })).not.toThrow();
  });
});

describe('the crash file', () => {
  it('is written synchronously at crash time and sent on the next start', async () => {
    const store = createMemoryStore();
    const first = createCrashCapture({ store, scrubber: createScrubber(() => 5), identity: () => ID });
    first.record({ error: new TypeError('x'), fatal: true, screen: 'FF-15' });
    // On disk the moment record() returned — no await happened.
    expect(store.dump()['telemetry.crashes.v1']).toContain('TypeError');

    // "Next start": a fresh capture over the same store.
    const next = createCrashCapture({ store, scrubber: createScrubber(), identity: () => ID });
    const reporter = createFakeCrashReporter();
    expect(await next.sendPending(reporter, createWorkGate())).toBe('yielded'); // gate unreported
    expect(await next.sendPending(reporter, clearGate())).toBe('sent');
    expect(reporter.sent).toHaveLength(1);
    expect(reporter.sent[0]).toMatchObject({ errorType: 'TypeError', fatal: true, screen: 'FF-15' });
    expect(next.pending()).toHaveLength(0);
  });

  it('keeps reports when the provider is unreachable', async () => {
    const store = createMemoryStore();
    const c = createCrashCapture({ store, scrubber: createScrubber(), identity: () => ID, timeoutMs: 30 });
    c.record({ error: new Error('x'), fatal: false });
    const reporter = createFakeCrashReporter();
    reporter.failWith(new Error('offline'));
    await expect(c.sendPending(reporter, clearGate())).resolves.toBe('failed');
    expect(c.pending()).toHaveLength(1);
  });

  it('is bounded, oldest dropped, and the drop is counted into telemetry_dropped', async () => {
    const r = recorder();
    const t = createTelemetry({ store: createMemoryStore(), analytics: r.transport, identity: () => ID });
    for (let i = 0; i < 12; i++) t.crashes.record({ error: new Error(String(i)), fatal: false });
    expect(t.crashes.pending()).toHaveLength(10);
    expect(t.crashes.droppedCount()).toBe(2);
    t.gate.reportWork({ outbox: 0, photos: 0, syncing: false, online: true });
    await t.flush(createFakeCrashReporter());
    expect(r.batches[0]!.at(-1)).toMatchObject({ name: 'telemetry_dropped', fields: { crashes: 2 } });
    expect(t.crashes.droppedCount()).toBe(0);
  });

  it('the global handler records, then still calls the handler that was there', () => {
    const store = createMemoryStore();
    const c = createCrashCapture({ store, scrubber: createScrubber(), identity: () => ID });
    const previous = jest.fn();
    let installed: (e: unknown, f?: boolean) => void = () => {};
    const uninstall = installGlobalCrashHandler(c, {
      getGlobalHandler: () => previous,
      setGlobalHandler: (h) => (installed = h),
    });
    const err = new RangeError('boom');
    installed(err, true);
    expect(previous).toHaveBeenCalledWith(err, true);
    expect(c.pending()[0]).toMatchObject({ errorType: 'RangeError', fatal: true });
    uninstall();
    expect(installed).toBe(previous);
  });

  it('a report written by an older build is re-judged before it leaves', async () => {
    const store = createMemoryStore({
      'telemetry.crashes.v1': JSON.stringify([
        {
          kind: 'crash',
          errorType: 'Error',
          message: 'Sarah Miller owes $241.38',
          fatal: false,
          screen: 'Sarah Miller',
          frames: [{ fn: 'Sarah Miller', file: '/Users/x/A-10432.ts', line: 1, col: 2 }],
          components: ['Customer', 'sarah miller'],
          breadcrumbs: [{ name: 'customer_opened', fields: { name: 'Sarah Miller' }, at: 1 }],
          identity: { ...ID, name: 'Sarah Miller' },
          at: 1,
        },
      ]),
    });
    const c = createCrashCapture({ store, scrubber: createScrubber(), identity: () => ID });
    const reporter = createFakeCrashReporter();
    await c.sendPending(reporter, clearGate());
    const sent = JSON.stringify(reporter.sent);
    expect(sent).not.toContain('Sarah');
    expect(sent).not.toContain('241.38');
    expect(sent).not.toContain('A-10432');
    expect(reporter.sent[0]).toMatchObject({ screen: null, components: ['Customer'], breadcrumbs: [] });
  });
});
